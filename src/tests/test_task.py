import pytest
import asyncio
from ioc import ApplicationContext, Component, Task, MissingDependencyError


@pytest.mark.asyncio
async def test_interval_task(config_file):
    counter = 0

    @Component
    class Tasker:
        @Task(interval=0.1)
        async def inc(self):
            nonlocal counter
            counter += 1

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()
    await asyncio.sleep(0.35)
    await ApplicationContext.close()
    assert counter >= 3


@pytest.mark.asyncio
async def test_cron_task(config_file):
    registered = False

    @Component
    class CronTask:
        @Task(cron="*/1 * * * *")
        async def every_minute(self):
            nonlocal registered
            registered = True

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()
    await asyncio.sleep(65)
    await ApplicationContext.close()
    assert registered
