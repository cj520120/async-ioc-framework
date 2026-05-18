import inspect
from functools import wraps
from typing import Any, Callable, Optional


def Task(interval: Optional[float] = None, cron: Optional[str] = None, func: Optional[Callable[[Any], float]] = None):
    """
    定时任务装饰器，用法：
        @Task(5)                # 每5秒执行一次（异步）
        @Task(interval=2.5)     # 每2.5秒
        @Task(cron="*/1 * * * *")  # 每分钟（需要 croniter）
        @Task(func=lambda self: self.any_method_returning_float()   # 根据返回值决定间隔
    注意：只能装饰 async def 方法。
    """

    config_interval = [interval, cron, func]
    if sum([i is not None for i in config_interval]) > 1:
        raise ValueError("只能指定 interval 、cron 或 func 之一")

    if all([i is None for i in config_interval]):
        raise ValueError("必须指定 interval 、cron 或 func 之一")

    def decorator(callable):
        if not inspect.iscoroutinefunction(callable):
            raise TypeError("@Task 只能装饰异步函数（async def）")

        @wraps(callable)
        def wrapper(*args, **kwargs):
            return callable(*args, **kwargs)

        if cron:
            wrapper._task_config = {"cron": cron, "registered": False}
        elif func:
            wrapper._task_config = {"func": func, "registered": False}
        else:
            wrapper._task_config = {"interval": float(interval), "registered": False}
        return wrapper

    return decorator


def PostConstruct(func: Callable) -> Callable:
    func._post_construct = {"invoked": False}
    return func


def PreDestroy(func: Callable) -> Callable:
    func._pre_destroy = {"invoked": False}
    return func
