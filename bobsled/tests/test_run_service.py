import os
import time
from unittest.mock import Mock
import pytest
from ..base import Task, Status
from ..runners import LocalRunService, ECSRunService, MemoryRunPersister
from ..exceptions import AlreadyRunning


def local_run_service():
    return LocalRunService(MemoryRunPersister())


def ecs_run_service():
    cluster_name = os.environ.get("TEST_CLUSTER")
    subnet_id = os.environ.get("TEST_SUBNET")
    security_group_id = os.environ.get("TEST_SECURITY_GROUP")
    if cluster_name and subnet_id and security_group_id:
        return ECSRunService(
            MemoryRunPersister(),
            cluster_name=cluster_name,
            subnet_id=subnet_id,
            security_group_id=security_group_id,
            log_group="bobsled",
        )

# workaround until pytest.skip works w/ async (coming in 0.11)
if os.environ.get("TEST_CLUSTER"):
    runners = [local_run_service, ecs_run_service]
else:
    runners = [local_run_service]


async def _wait_to_finish(rs, run, seconds):
    ticks = 0
    while ticks < seconds * 10:
        await rs.update_status(run.uuid)
        n_running = len(await rs.get_runs(status=[Status.Running, Status.Pending]))
        if n_running == 0:
            break
        time.sleep(0.1)
        ticks += 1
    return n_running


@pytest.mark.parametrize("Cls", runners)
@pytest.mark.asyncio
async def test_simple_run(Cls):
    rs = Cls()
    if not rs:
        pytest.skip("ECS not configured")
    task = Task("hello-world", image="hello-world")
    run = await rs.run_task(task)

    assert run.status == Status.Running

    n_running = await _wait_to_finish(rs, run, 60)

    assert n_running == 0
    runs = await rs.get_runs(status=Status.Success)
    assert len(runs) == 1
    assert "Hello from Docker" in runs[0].logs
    assert await rs.cleanup() == 0


@pytest.mark.parametrize("Cls", runners)
@pytest.mark.asyncio
async def test_stop_run(Cls):
    rs = Cls()
    if not rs:
        pytest.skip("ECS not configured")
    # run forever task, then kill it
    task = Task("forever", image="forever")
    run = await rs.run_task(task)
    run = await rs.update_status(run.uuid, update_logs=True)
    await rs.stop_run(run.uuid)

    run = await rs.update_status(run.uuid, update_logs=True)
    assert run.status == Status.UserKilled
    assert await rs.cleanup() == 0


@pytest.mark.parametrize("Cls", runners)
@pytest.mark.asyncio
async def test_cleanup(Cls):
    rs = Cls()
    if not rs:
        pytest.skip("ECS not configured")
    # run forever task
    task = Task("forever", image="forever")
    await rs.run_task(task)

    assert await rs.cleanup() == 1


# doesn't need to be tested on multiple services since logic is in base class
@pytest.mark.asyncio
async def test_already_running():
    rs = local_run_service()
    task = Task("forever", image="forever")
    await rs.run_task(task)
    with pytest.raises(AlreadyRunning):
        await rs.run_task(task)

    assert await rs.cleanup() == 1


@pytest.mark.parametrize("Cls", runners)
@pytest.mark.asyncio
async def test_timeout(Cls):
    rs = Cls()
    if not rs:
        pytest.skip("ECS not configured")
    task = Task("timeout", image="forever", timeout_minutes=(1 / 60.0))
    run = await rs.run_task(task)

    assert run.status == Status.Running

    n_running = await _wait_to_finish(rs, run, 2)

    assert n_running == 0
    assert len(await rs.get_runs(status=Status.TimedOut)) == 1
    assert await rs.cleanup() == 0


@pytest.mark.asyncio
async def test_callback_on_success():
    callback = Mock()
    rs = LocalRunService(MemoryRunPersister(), [callback])
    task = Task("hello-world", image="hello-world")
    run = await rs.run_task(task)

    n_running = await _wait_to_finish(rs, run, 10)

    assert n_running == 0
    callback.on_success.assert_called_once_with(run, rs.persister)


@pytest.mark.asyncio
async def test_callback_on_error():
    callback = Mock()
    rs = LocalRunService(MemoryRunPersister(), [callback])
    task = Task("failure", image="alpine", entrypoint="sh -c 'exit 1'")
    run = await rs.run_task(task)

    n_running = await _wait_to_finish(rs, run, 10)

    assert n_running == 0
    callback.on_error.assert_called_once_with(run, rs.persister)
