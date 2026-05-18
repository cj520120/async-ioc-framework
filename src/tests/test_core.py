from typing import Annotated

import pytest

from ioc import ApplicationContext, Component, MissingDependencyError, Qualifier, Value


# ========== 组件定义（模块级别） ==========
@Component  # 添加此装饰器
class Repo:
    pass


@Component
class Service:
    def __init__(self, repo: Repo):
        self.repo = repo


@Component(name="implA")
class InterfaceA:
    def who(self):
        return "A"


@Component(name="implB")
class InterfaceB:
    def who(self):
        return "B"


@Component
class QualifierClient:
    def __init__(self, svc: Annotated[InterfaceB, Qualifier("implB")]):
        self.svc = svc


class BaseService:
    pass


@Component(primary=True)
class MainService(BaseService):
    def name(self):
        return "main"


@Component
class OtherService(BaseService):
    def name(self):
        return "other"


@Component
class PrimaryClient:
    def __init__(self, svc: BaseService):
        self.svc = svc


@Component(profile="dev")
class DevOnly:
    pass


@Component(profile="prod")
class ProdOnly:
    pass


@Component
class Always:
    pass


@Component
class ConfigClient:
    def __init__(
        self,
        name: Annotated[str, Value("${app_name}")],
        debug: Annotated[bool, Value("${debug}")],
        missing: Annotated[str, Value("${unknown_key:default}")],
    ):
        self.name = name
        self.debug = debug
        self.missing = missing


init_flag = False


@Component(lazy=True)
class LazyService:
    def __init__(self):
        global init_flag
        init_flag = True


# ========== 测试函数 ==========
@pytest.mark.asyncio
async def test_basic_di(container):
    service = ApplicationContext.get_bean(Service)
    assert isinstance(service.repo, Repo)


@pytest.mark.asyncio
async def test_qualifier(container):
    client = ApplicationContext.get_bean(QualifierClient)
    assert client.svc.who() == "B"


@pytest.mark.asyncio
async def test_primary(container):
    client = ApplicationContext.get_bean(PrimaryClient)
    assert client.svc.name() == "main"


@pytest.mark.asyncio
async def test_profile(container):
    assert ApplicationContext.get_bean(DevOnly) is not None
    assert ApplicationContext.get_bean(Always) is not None
    with pytest.raises(MissingDependencyError):
        ApplicationContext.get_bean(ProdOnly)


@pytest.mark.asyncio
async def test_value_injection(container):
    client = ApplicationContext.get_bean(ConfigClient)
    assert client.name == "TestApp"
    assert client.debug is True
    assert client.missing == "default"


@pytest.mark.asyncio
async def test_lazy_bean(container):
    global init_flag
    init_flag = False
    service = await ApplicationContext.get_bean_async(LazyService)
    assert init_flag is True
    assert ApplicationContext.get_bean(LazyService) is service
