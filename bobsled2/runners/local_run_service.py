import datetime
import docker
from ..base import RunService, Run, Status
from ..exceptions import AlreadyRunning


class LocalRunService(RunService):
    def __init__(self, persister):
        self.client = docker.from_env()
        self.persister = persister

    def _get_container(self, run):
        if run.status == Status.Running:
            try:
                return self.client.containers.get(run.run_info["container_id"])
            except docker.errors.NotFound:
                return None

    async def cleanup(self):
        n = 0
        for r in await self.persister.get_runs():
            c = self._get_container(r)
            if c:
                c.remove(force=True)
                n += 1
        return n

    async def run_task(self, task):
        # TODO handle waiting
        running = await self.get_runs(status=Status.Running, task_name=task.name)
        if running:
            raise AlreadyRunning()
        container = self.client.containers.run(
            task.image,
            task.entrypoint if task.entrypoint else None,
            detach=True
        )
        now = datetime.datetime.utcnow()
        timeout_at = ""
        if task.timeout_minutes:
            timeout_at = (now + datetime.timedelta(minutes=task.timeout_minutes)).isoformat()
        run = Run(
            task.name,
            Status.Running,
            start=now.isoformat(),
            run_info={
                "container_id": container.id,
                "timeout_at": timeout_at,
            }
        )
        await self.persister.add_run(run)
        return run

    async def update_status(self, run_id, update_logs=False):
        run = await self.persister.get_run(run_id)

        if run.status in (Status.Success, Status.Error, Status.TimedOut, Status.UserKilled):
            return run

        container = self._get_container(run)
        if not container:
            # TODO: handle this
            print("missing container for", run)
            return run

        if container.status == "exited":
            resp = container.wait()
            if resp["Error"] or resp["StatusCode"]:
                run.status = Status.Error
            else:
                run.status = Status.Success
            run.exit_code = resp["StatusCode"]
            run.logs = container.logs().decode()
            run.end = datetime.datetime.utcnow().isoformat()
            await self.persister.save_run(run)
            container.remove()

        elif run.status == Status.Running:
            # handle timeouts and update_logs params together
            if run.run_info["timeout_at"] and datetime.datetime.utcnow().isoformat() > run.run_info["timeout_at"]:
                container.remove(force=True)
                run.status = Status.TimedOut
                update_logs = True

            # will be set if we timed out
            if update_logs:
                run.logs = self.get_logs(run)
                await self.persister.save_run(run)
        return run

    def get_logs(self, run):
        container = self._get_container(run)
        if container:
            return container.logs().decode()
        else:
            return ""

    async def get_run(self, run_id):
        return await self.update_status(run_id, update_logs=True)

    async def get_runs(self, *, status=None, task_name=None, update_status=False):
        runs = await self.persister.get_runs(status=status, task_name=task_name)
        if update_status:
            for run in runs:
                await self.update_status(run.uuid)
        # todo:? refresh runs dict?
        return runs

    async def stop_run(self, run_id):
        run = await self.persister.get_run(run_id)
        if run.status == Status.Running:
            container = self._get_container(run)
            if not container:
                print("MISSING CONTAINER")
                return
            container.remove(force=True)
            run.status = Status.UserKilled
            run.end = datetime.datetime.utcnow().isoformat()
            await self.persister.save_run(run)

    def register_crons(self, tasks):
        # TODO
        pass
