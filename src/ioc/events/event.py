import inspect
import logging
from typing import Any, Awaitable, Callable, Dict, List, Type, Union

from ..component import Component
from ..context import ApplicationContext
from ..decorators import PostConstruct

logger = logging.getLogger(__name__)


class Event:
    """事件基类"""


@Component
class EventPublisher:
    def __init__(self):
        self._listeners: Dict[Type, List[Callable]] = {}

    @PostConstruct
    async def init(self):
        """扫描所有 Bean，注册带有 @EventListener 的方法"""
        for bean in ApplicationContext.get_all_beans():
            for method_name in dir(bean):
                if method_name.startswith('_'):
                    continue
                method = getattr(bean, method_name)
                if callable(method) and hasattr(method, '_event_listener'):
                    event_type = getattr(method, '_event_type')
                    self.register(event_type, method)
                    logger.debug(f"Registered event listener {bean.__class__.__name__}.{method_name} for {event_type.__name__}")
        logger.info("EventPublisher initialized")

    def register(self, event_type: Type, listener: Callable[[Any], Union[None, Awaitable[None]]]) -> None:
        self._listeners.setdefault(event_type, []).append(listener)

    async def publish(self, event: Event) -> None:
        event_type = type(event)
        for listener in self._listeners.get(event_type, []):
            if inspect.iscoroutinefunction(listener):
                await listener(event)
            else:
                listener(event)


def EventListener(event_type: Type):
    def decorator(func: Callable) -> Callable:
        setattr(func, '_event_listener', True)
        setattr(func, '_event_type', event_type)
        return func

    return decorator
