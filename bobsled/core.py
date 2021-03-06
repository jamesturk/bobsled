import os
import asyncio
from bobsled import storages, runners, callbacks
from bobsled.environment import EnvironmentProvider
from bobsled.tasks import TaskProvider
from bobsled.utils import get_env_config, load_args


class Bobsled:
    def __init__(self):
        self.settings = {"secret_key": os.environ.get("BOBSLED_SECRET_KEY", None)}
        if self.settings["secret_key"] is None:
            raise ValueError("must set 'secret_key' setting")

        # env and task providers can't currently be overriden
        env_args = load_args(EnvironmentProvider)
        task_args = load_args(TaskProvider)
        # storage and run are overridable
        StorageCls, storage_args = get_env_config(
            "BOBSLED_STORAGE", "InMemoryStorage", storages
        )
        RunCls, run_args = get_env_config("BOBSLED_RUNNER", "LocalRunService", runners)

        callback_classes = []
        if os.environ.get("BOBSLED_ENABLE_GITHUB_ISSUE_CALLBACK"):
            CallbackCls = callbacks.GithubIssueCallback
            callback_classes.append(CallbackCls(**load_args(CallbackCls)))

        self.storage = StorageCls(**storage_args)
        self.env = EnvironmentProvider(**env_args)
        self.tasks = TaskProvider(storage=self.storage, **task_args)
        self.run = RunCls(
            storage=self.storage,
            environment=self.env,
            callbacks=callback_classes,
            **run_args,
        )

    async def initialize(self):
        await self.storage.connect()
        tasks = await self.storage.get_tasks()
        await self.env.update_environments()
        if not tasks:
            await self.refresh_config()
        else:
            self.run.initialize(tasks)

    async def refresh_config(self):
        await asyncio.gather(self.tasks.update_tasks(), self.env.update_environments())
        tasks = await self.storage.get_tasks()
        self.run.initialize(tasks)
        return tasks


bobsled = Bobsled()
