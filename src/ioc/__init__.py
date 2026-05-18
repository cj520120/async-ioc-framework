"""
IoC 容器模块，提供依赖注入、配置管理、定时任务等功能。
"""

# 异常类
from .exceptions import (
    CircularDependencyError,
    MissingDependencyError,
    BeanCreationError,
    SchedulerError,
    AmbiguousDependencyError,
)

# 注解类
from .annotations import Qualifier, Value, Condition, OnPropertyCondition, OnClassExists, OnMissingClass, AllConditions, AnyCondition, NotCondition

# 装饰器
from .decorators import Task, PostConstruct, PreDestroy

# 配置类
from .config import AppConfig

# 核心容器
from .context import ApplicationContext

# 组件装饰器
from .component import Component
from .event import Event, EventListener, EventPublisher

# 定义公开接口
__all__ = [
    # 异常
    "CircularDependencyError",
    "MissingDependencyError",
    "BeanCreationError",
    "SchedulerError",
    "AmbiguousDependencyError",
    # 注解
    "Qualifier",
    "Value",
    "Condition",
    "OnPropertyCondition",
    "OnClassExists",
    "OnMissingClass",
    "AllConditions",
    "AnyCondition",
    "NotCondition",
    # 装饰器
    "Task",
    "PostConstruct",
    "PreDestroy",
    # 配置
    "AppConfig",
    # 核心
    "ApplicationContext",
    # 组件注册
    "Component",
    "EventListener",
    "Event",
    "EventPublisher",
]
