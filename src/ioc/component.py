import inspect
import logging
from typing import List, Optional, Union, get_args, get_origin, get_type_hints

from .annotations import Condition
from .context import ApplicationContext
from .exceptions import BeanCreationError

logger = logging.getLogger(__name__)


def Component(name: str = None, priority: int = 10000000, primary: bool = False, profile: Union[str, List[str]] = None, lazy: bool = False, condition: Optional[Condition] = None):

    def decorator(cls):
        init_method = getattr(cls, "__init__", None)
        if init_method is object.__init__:
            bean_name = name or cls.__name__.lower()
            cls._component_priority = priority
            cls._component_primary = primary
            cls._component_lazy = lazy
            cls._component_condition = condition
            if profile is None:
                cls._component_profile = []
            elif isinstance(profile, str):
                cls._component_profile = [profile]
            else:
                cls._component_profile = list(profile)
            ApplicationContext.register_component_class(bean_name, cls)
            logger.debug(f"Registered component {cls.__name__} as '{bean_name}'")
            return cls
        sig = inspect.signature(cls.__init__)
        type_hints = get_type_hints(cls.__init__)
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                raise BeanCreationError(f"类 {cls.__name__} 的构造函数含有 *args 或 **kwargs")
            dep_type = type_hints.get(param_name)
            if dep_type is None:
                raise BeanCreationError(f"类 {cls.__name__} 的构造参数 {param_name} 没有类型注解")
            origin = get_origin(dep_type)
            if origin is Union:
                union_args = get_args(dep_type)
                non_none = [t for t in union_args if t is not type(None)]
                if len(non_none) != 1:
                    raise BeanCreationError(f"类 {cls.__name__} 参数 {param_name} 的 Union 仅支持 Optional[X]")
                dep_type = non_none[0]
                origin = get_origin(dep_type)
            if origin in (list, set):
                args_list = get_args(dep_type)
                if not args_list:
                    raise BeanCreationError(f"类 {cls.__name__} 参数 {param_name} 容器类型缺少元素类型")
                item_type = args_list[0]
                if not isinstance(item_type, type):
                    raise BeanCreationError(f"类 {cls.__name__} 参数 {param_name} 容器元素类型 {item_type} 不是类")

            elif not isinstance(dep_type, type):
                raise BeanCreationError(f"类 {cls.__name__} 参数 {param_name} 的类型 {dep_type} 不是类")
        bean_name = name or cls.__name__.lower()
        cls._component_priority = priority
        cls._component_primary = primary
        cls._component_lazy = lazy
        cls._component_condition = condition
        if profile is None:
            cls._component_profile = []
        elif isinstance(profile, str):
            cls._component_profile = [profile]
        else:
            cls._component_profile = list(profile)
        ApplicationContext.register_component_class(bean_name, cls)
        logger.debug(f"Registered component {cls.__name__} as '{bean_name}'")
        return cls

    if inspect.isclass(name):
        cls = name
        name = None
        priority = 10000000
        primary = False
        profile = None
        lazy = False
        condition = None
        return decorator(cls)
    return decorator
