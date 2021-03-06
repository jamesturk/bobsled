import os
import pytest
from ..storages import InMemoryStorage, DatabaseStorage
from ..base import Run, Status, Task, Trigger
from ..storages.database import Tasks, Runs, Users


async def mem_storage():
    return InMemoryStorage()


async def db_storage():
    db = DatabaseStorage(
        os.environ.get(
            "BOBSLED_TEST_DATABASE",
            "postgresql://bobsled:bobsled@localhost:5435/bobsled_test",
        )
    )
    await db.connect()
    await db.database.execute(Runs.delete())
    await db.database.execute(Tasks.delete())
    await db.database.execute(Users.delete())
    names = ["test-task", "stopped", "running", "running too", "one", "two", "three"]
    await db.set_tasks([Task(name, "image") for name in names])
    return db


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_simple_add_then_get(storage):
    p = await storage()
    r = Run("test-task", Status.Running)
    await p.add_run(r)
    r2 = await p.get_run(r.uuid)
    assert r.task == r2.task
    assert r.uuid == r2.uuid
    assert r.status == r2.status


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_update(storage):
    p = await storage()
    r = Run("test-task", Status.Running)
    await p.add_run(r)
    r.status = Status.Success
    r.exit_code = 0
    await p.save_run(r)
    r2 = await p.get_run(r.uuid)
    assert r2.status == Status.Success
    assert r2.exit_code == 0


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_bad_get(storage):
    p = await storage()
    r = await p.get_run("nonsense")
    assert r is None


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_get_runs(storage):
    p = await storage()
    await p.add_run(Run("stopped", Status.Success, start="2010-01-01"))
    await p.add_run(Run("running too", Status.Running, start="2015-01-01"))
    await p.add_run(Run("running", Status.Running, start="2019-01-01"))
    assert len(await p.get_runs()) == 3
    # status param
    assert len(await p.get_runs(status=Status.Running)) == 2
    assert len(await p.get_runs(status=[Status.Running, Status.Success])) == 3
    # task_name param
    assert len(await p.get_runs(task_name="stopped")) == 1
    assert len(await p.get_runs(task_name="empty")) == 0
    # check ordering
    assert [r.task for r in await p.get_runs()] == ["stopped", "running too", "running"]


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_get_runs_latest_n(storage):
    p = await storage()
    await p.add_run(Run("one", Status.Success, start="2010-01-01"))
    await p.add_run(Run("two", Status.Running, start="2015-01-01"))
    await p.add_run(Run("three", Status.Running, start="2019-01-01"))

    # latest param
    latest_one = await p.get_runs(latest=1)
    assert len(latest_one) == 1
    assert latest_one[0].task == "three"


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_task_storage(storage):
    s = await storage()
    tasks = [
        Task(
            name="one",
            image="img1",
            tags=["yellow", "green"],
            entrypoint="entrypoint",
            environment="envname",
            memory=1024,
            cpu=512,
            enabled=False,
            timeout_minutes=60,
            triggers=[Trigger(cron="@daily")],
            next_tasks=["two"],
        ),
        Task(name="two", image="img2"),
    ]
    await s.set_tasks(tasks)

    retr_tasks = await s.get_tasks()
    # order-indepdendent comparison
    assert [t.name for t in retr_tasks] == ["one", "two"]
    task = await s.get_task("one")
    assert task == tasks[0]


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_task_storage_updates(storage):
    s = await storage()
    tasks = [Task(name="one", image="img1"), Task(name="two", image="img2")]
    await s.set_tasks(tasks)

    tasks = [Task(name="one", image="newimg"), Task(name="three", image="img3")]
    await s.set_tasks(tasks)
    retr_tasks = await s.get_tasks()
    # order-indepdendent comparison
    assert len(retr_tasks) == 2
    assert {t.name for t in retr_tasks} == {"one", "three"}
    task = await s.get_task("one")
    assert task == tasks[0]


@pytest.mark.parametrize("storage", [mem_storage, db_storage])
@pytest.mark.asyncio
async def test_user_storage(storage):
    s = await storage()
    # non-existent user
    check = await s.check_password("someone", "abc")
    assert not check
    # wrong password
    await s.set_user("someone", "xyz", ["admin"])
    check = await s.check_password("someone", "abc")
    assert not check
    # right password
    check = await s.check_password("someone", "xyz")
    assert check
    # check users
    users = await s.get_users()
    assert len(users) == 1
    assert users[0].username == "someone"
    assert "argon2" in users[0].password_hash
    assert users[0].permissions == ["admin"]
    # check get_user
    user = await s.get_user("someone")
    assert user.username == "someone"
    assert "argon2" in user.password_hash
    assert user.permissions == ["admin"]
