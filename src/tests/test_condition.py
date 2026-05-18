import pytest

from ioc import AllConditions, ApplicationContext, Component, MissingDependencyError, OnClassExists, OnPropertyCondition


@pytest.mark.asyncio
async def test_on_property_condition(config_file):
    @Component(condition=OnPropertyCondition("feature.new.enabled", having_value=True))
    class FeatureEnabled:
        pass

    @Component(condition=OnPropertyCondition("feature.another.enabled", having_value=True))
    class FeatureDisabled:
        pass

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()

    assert ApplicationContext.get_bean(FeatureEnabled) is not None
    with pytest.raises(MissingDependencyError):
        ApplicationContext.get_bean(FeatureDisabled)
    await ApplicationContext.close()


@pytest.mark.asyncio
async def test_on_class_exists_condition(config_file):
    @Component(condition=OnClassExists("sqlalchemy.ext.asyncio.AsyncSession"))
    class ExistsClass:
        pass

    @Component(condition=OnClassExists("nonexistent.module.Nothing"))
    class NotExists:
        pass

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()

    try:
        pass
    except ImportError:
        pytest.skip("sqlalchemy not installed")
    else:
        assert ApplicationContext.get_bean(ExistsClass) is not None

    with pytest.raises(MissingDependencyError):
        ApplicationContext.get_bean(NotExists)
    await ApplicationContext.close()


@pytest.mark.asyncio
async def test_all_conditions(config_file):
    @Component(condition=AllConditions(OnPropertyCondition("feature.new.enabled", having_value=True), OnClassExists("sqlalchemy.ext.asyncio.AsyncSession")))
    class BothTrue:
        pass

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()

    try:
        pass
    except ImportError:
        # 条件不满足（类不存在）-> 组件不应创建
        with pytest.raises(MissingDependencyError):
            ApplicationContext.get_bean(BothTrue)
    else:
        # 两个条件都满足 -> 组件存在
        assert ApplicationContext.get_bean(BothTrue) is not None
    await ApplicationContext.close()
