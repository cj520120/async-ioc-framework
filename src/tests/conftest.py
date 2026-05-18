import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from ioc import ApplicationContext


@pytest.fixture(scope="session")
def config_yaml():
    return """
app_name: TestApp
database:
  type: sqlite
  url: "sqlite+aiosqlite:///:memory:"
timeout: 30
debug: true
active_profiles: ["dev"]
feature:
  new:
    enabled: true
  another:
    enabled: false
"""


@pytest.fixture(scope="session")
def config_file(config_yaml):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        path = f.name
    yield path
    Path(path).unlink()


@pytest_asyncio.fixture(scope="function")
async def container(config_file):
    """每个测试独立容器，重置实例状态但保留类定义"""
    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()
    yield
    await ApplicationContext.close()
