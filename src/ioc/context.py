import asyncio
import importlib
import inspect
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union, get_args, get_origin, get_type_hints

from croniter import croniter

from .annotations import *
from .config import AppConfig
from .exceptions import *

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ApplicationContext:
    """
    静态 IoC 容器，支持依赖注入、生命周期管理和定时任务。  
    注：容器在 refresh() 时创建所有单例 Bean。get_bean() 仅用于获取已创建实例，不会触发新创建。
    """

    _beans: Dict[str, Any] = {}
    _bean_classes: Dict[str, Type] = {}
    _type_to_name: Dict[Type, str] = {}
    _creating: Set[str] = set()
    _app_config: Optional[AppConfig] = None
    _scheduler_tasks: Set[asyncio.Task] = set()
    _active_profiles: Set[str] = set()
    _scheduler_running = False
    _initialized = False

    @classmethod
    def scan_directory(cls, base_path: Union[Path, str], base_package: str = "", raise_on_error: bool = False) -> None:
        """
        递归扫描目录下的所有 .py 文件，动态导入并触发 @Component 注册。
        :param base_path: 项目绝对路径
        :param base_package: 指定基础包名（用于构造模块名）
        :param raise_on_error: 是否在导入失败时抛出异常
        """
        if not isinstance(base_path, Path):
            base_path = Path(base_path)
        scan_path = base_path / base_package
        logger.info(f"开始扫描目录: {base_path} base package: {base_package}")
        for py_file in scan_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            rel_path = py_file.relative_to(base_path)
            module_name = str(rel_path.with_suffix('')).replace('/', '.').replace('\\', '.')
            try:
                if module_name not in sys.modules:
                    importlib.import_module(module_name)
                    logger.info(f"已导入模块: {module_name}")
            except Exception as e:
                logger.error(f"导入模块 {module_name} 失败: {e}")
                if raise_on_error:
                    raise

    @classmethod
    def get_app_config(cls) -> AppConfig:
        return cls._app_config

    @classmethod
    def set_active_profiles(cls, *profiles: str):
        cls._active_profiles = set(profiles)

    @classmethod
    def add_active_profile(cls, profile: str) -> None:
        cls._active_profiles.add(profile)

    @classmethod
    def initialize_from_body(cls, body: bytes):
        _app_config = AppConfig()
        _app_config.load_from_body(body)
        cls._initialize(_app_config)

    @classmethod
    def initialize(cls, config_file: str = "config.yaml"):
        _app_config = AppConfig()
        _app_config.load_from_file(config_file)
        cls._initialize(_app_config)

    @classmethod
    def _initialize(cls, app_config: AppConfig):
        if cls._initialized:
            raise RuntimeError("容器已初始化")
        cls._app_config = app_config
        cls.register_bean(cls._app_config)
        profiles = cls._app_config.get("active_profiles", [])
        if isinstance(profiles, str):
            profiles = [profiles]
        if profiles:
            cls.set_active_profiles(*profiles)
        # 环境变量覆盖
        env_profiles = os.environ.get("ACTIVE_PROFILES", "")
        if env_profiles:
            cls.set_active_profiles(*env_profiles.split(","))

    @classmethod
    def register_bean(cls, instance: Any, name: str = None) -> None:
        if type(instance) in cls._type_to_name:
            raise ValueError(f"类型 {type(instance)} 已被注册")
        name = name or instance.__class__.__name__.lower()
        if name in cls._beans:
            logger.warning(f"Bean 名称 '{name}' 已存在，将被覆盖")
        cls._beans[name] = instance
        cls._type_to_name[type(instance)] = name

    @classmethod
    def get_bean(cls, name_or_type: Union[str, Type[T]]) -> T:
        if not cls._initialized:
            raise RuntimeError("容器尚未初始化，请先调用 await ApplicationContext.refresh()")
        return cls._resolve_dependency(name_or_type, auto_create=False)

    @classmethod
    def get_all_beans(cls) -> List[Any]:
        """返回所有已注册的 Bean 实例列表"""
        return list(cls._beans.values())

    @classmethod
    async def get_bean_async(cls, name_or_type: Union[str, Type[T]]) -> T:
        """异步版本，支持懒加载 Bean 的异步 @PostConstruct"""
        bean = cls._resolve_dependency(name_or_type, auto_create=True)
        await cls._invoke_post_construct(bean)
        cls._register_tasks_for_instance(bean)
        return bean

    @classmethod
    def _check_match_profiles(cls, clazz: Optional[Type]) -> bool:
        if clazz is None:
            raise ValueError("类型不能为 None")
        component_profile = getattr(clazz, '_component_profile', [])
        if component_profile and not any(p in cls._active_profiles for p in component_profile):
            return False
        return True

    @classmethod
    def _check_match_condition(cls, clazz: Type) -> bool:
        condition = getattr(clazz, '_component_condition', None)
        if condition is None:
            return True
        else:
            context = {
                "config": cls._app_config,
                "bean_classes": cls._bean_classes,
                "beans": cls._beans,
                "active_profiles": cls._active_profiles,
            }
            match = condition.matches(context)
            if not match:
                logger.debug(f"Skipping component {clazz.__name__} due to condition {condition}")
            return match

    @classmethod
    def _get_dependency_class_from_name(cls, name: str) -> tuple[str, Type]:
        if name in cls._bean_classes:
            return name, cls._bean_classes[name]
        else:
            raise MissingDependencyError(f"未找到名为 '{name}' 的 Bean 定义")

    @classmethod
    def _get_dependency_class_from_type(cls, class_type: Type) -> tuple[str, Type]:
        matched = []
        for clstype, name in cls._type_to_name.items():
            if issubclass(clstype, class_type):
                if not cls._check_match_profiles(clstype):
                    continue
                if not cls._check_match_condition(clstype):
                    continue
                primary = getattr(clstype, '_component_primary', False)
                matched.append((name, primary))
        if not matched:
            for name, clstype in cls._bean_classes.items():
                if issubclass(clstype, class_type) and cls._check_match_profiles(clstype) and cls._check_match_condition(clstype):
                    primary = getattr(clstype, '_component_primary', False)
                    matched.append((name, primary))
        if not matched:
            raise MissingDependencyError(f"未找到类型 '{class_type.__name__}' 的 Bean")
        primary_names = [name for name, primary in matched if primary]
        non_primary_names = [name for name, primary in matched if not primary]
        if len(primary_names) == 1:
            bean_name = primary_names[0]
            logger.debug(f"类型 '{class_type.__name__}' 匹配到多个 Bean，自动选择 @Primary: {bean_name}")
        elif len(primary_names) > 1:
            raise AmbiguousDependencyError(f"类型 '{class_type.__name__}' 匹配到多个 @Primary Bean: {primary_names}。" f"请确保只有一个 @Primary 或使用 @Qualifier 指定。")
        elif len(matched) > 1:
            all_names = [nm for nm, _ in matched]
            raise AmbiguousDependencyError(f"类型 '{class_type.__name__}' 匹配到多个 Bean: {all_names}。" f"请使用 @Qualifier 指定具体的 Bean 名称，或标记一个 @Primary。")
        else:
            assert len(non_primary_names) > 0
            bean_name = non_primary_names[0]
        if bean_name in cls._beans:
            bean_class = type(cls._beans[bean_name])
        else:
            bean_class = cls._bean_classes.get(bean_name)
            if bean_class is None:
                raise MissingDependencyError(f"未找到名为 '{bean_name}' 的 Bean 定义")
        return bean_name, bean_class

    @classmethod
    def _get_dependency_class(cls, name_or_type: Union[str, Type[T]]) -> tuple[str, Type[T]]:
        if isinstance(name_or_type, Qualifier):
            return cls._get_dependency_class_from_name(name_or_type.name)
        elif isinstance(name_or_type, str):
            return cls._get_dependency_class_from_name(name_or_type)
        elif isinstance(name_or_type, type):
            return cls._get_dependency_class_from_type(name_or_type)
        else:
            raise BeanCreationError(f"参数必须是字符串或类型，实际为 {type(name_or_type)}")

    @classmethod
    def _resolve_dependency(cls, name_or_type: Union[str, Type[T]], auto_create=True) -> T:
        bean_name, bean_class = cls._get_dependency_class(name_or_type)
        if bean_name in cls._beans:
            return cls._beans[bean_name]
        if bean_name in cls._creating:
            raise CircularDependencyError(f"循环依赖检测到: {bean_name} 正在创建中")
        if not auto_create:
            raise MissingDependencyError(f"未找到名为 '{bean_name}' 的 Bean 定义")
        cls._creating.add(bean_name)
        try:
            instance = cls._create_bean(bean_class)
            cls.register_bean(instance, bean_name)
            return instance
        finally:
            cls._creating.remove(bean_name)

    @classmethod
    def get_beans_of_type(cls, target_type: Type[T]) -> List[T]:
        matching_names = []
        for name, clstype in cls._bean_classes.items():
            if issubclass(clstype, target_type) and cls._check_match_profiles(clstype) and cls._check_match_condition(clstype):
                matching_names.append(name)
        instances = []
        for name in matching_names:
            instance = cls._resolve_dependency(name)
            instances.append(instance)
        return instances

    @classmethod
    def _create_bean(cls, bean_class: Type) -> Any:
        if bean_class.__init__ is object.__init__:
            instance = bean_class()
            return instance
        logger.debug(f"Creating bean for {bean_class.__name__}")
        sig = inspect.signature(bean_class.__init__)
        type_hints = get_type_hints(bean_class.__init__, include_extras=True)
        params = sig.parameters
        injected_args = {}
        for param_name, param in params.items():
            if param_name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                raise BeanCreationError(f"{bean_class.__name__} 不允许 *args/**kwargs")

            dep_type = type_hints.get(param_name)
            if dep_type is None:
                raise BeanCreationError(f"{bean_class.__name__}.__init__ 参数 '{param_name}' 缺少类型注解")
            origin = get_origin(dep_type)
            if origin is Annotated:
                args_list = get_args(dep_type)
                base_type = args_list[0]
                qualifier = None
                value = None
                for extra in args_list[1:]:
                    if isinstance(extra, Qualifier):
                        qualifier = extra
                        break
                    if isinstance(extra, Value):
                        value = extra
                        break
                if qualifier and value:
                    raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' 不能同时包含 @Qualifier 和 @Value")
                if qualifier:
                    bean = cls._resolve_dependency(qualifier.name, auto_create=True)
                    if not isinstance(bean, base_type):
                        raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' 期望类型 {base_type.__name__}，" f"但名为 '{qualifier.name}' 的 Bean 类型为 {type(bean).__name__}")
                    injected_args[param_name] = bean
                    continue
                elif value:
                    config = cls.get_app_config()
                    val = config.get(value.key, value.default)
                    if val is None:
                        raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' 配置键 '{value.key}' 不存在且未提供默认值")
                    if base_type is not type(None) and base_type != str:
                        try:
                            if base_type is bool:
                                val = str(val).lower() in ("true", "1", "yes")
                            else:
                                val = base_type(val)
                        except Exception as e:
                            raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' 配置值 '{val}' 无法转换为 {base_type.__name__}")
                    injected_args[param_name] = val
                    continue
                else:
                    dep_type = base_type
                    origin = get_origin(dep_type)

            if origin is list or origin is set:
                args_list = get_args(dep_type)
                if not args_list:
                    raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' 容器未指定元素类型")
                item_type = args_list[0]
                instances = cls.get_beans_of_type(item_type)
                if origin is list:
                    injected_args[param_name] = instances
                else:
                    injected_args[param_name] = set(instances)
                continue

            if origin is Union:
                union_args = dep_type.__args__
                non_none = [t for t in union_args if t is not type(None)]
                if len(non_none) == 1:
                    dep_type = non_none[0]
                    origin2 = get_origin(dep_type)
                    if origin2 is list or origin2 is set:
                        args_list = get_args(dep_type)
                        if args_list:
                            item_type = args_list[0]
                            instances = cls.get_beans_of_type(item_type)
                            if origin2 in (list, List):
                                injected_args[param_name] = instances
                            else:
                                injected_args[param_name] = set(instances)
                            continue
                else:
                    raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' Union 仅支持 Optional")

            if not isinstance(dep_type, type):
                raise BeanCreationError(f"{bean_class.__name__} 参数 '{param_name}' 类型 {dep_type} 不是类")
            injected_args[param_name] = cls._resolve_dependency(dep_type)

        instance = bean_class(**injected_args)
        return instance

    @classmethod
    async def _invoke_post_construct(cls, instance: Any) -> None:
        for method_name in dir(instance):
            if method_name.startswith("_"):
                continue
            method = getattr(instance, method_name)
            if callable(method) and hasattr(method, "_post_construct"):
                post_construct = getattr(method, "_post_construct")
                if post_construct.get("invoked"):
                    continue
                post_construct["invoked"] = True
                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()

    @classmethod
    async def _invoke_pre_destroy(cls, instance: Any) -> None:
        for method_name in dir(instance):
            if method_name.startswith("_"):
                continue
            method = getattr(instance, method_name)
            if callable(method) and hasattr(method, "_pre_destroy"):
                if method._pre_destroy.get("invoked"):
                    continue
                method._pre_destroy["invoked"] = True
                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()

    @classmethod
    def register_component_class(cls, name: str, clstype: Type) -> None:
        if name in cls._bean_classes:
            if cls._bean_classes[name] != clstype:
                logger.error(f"Bean 名称冲突: {name} 已被 {cls._bean_classes[name].__class__.__name__} 注册")
                raise ValueError(f"Bean 名称冲突: {name} 已被 {cls._bean_classes[name].__class__.__name__} 注册")
            else:
                return
        cls._bean_classes[name] = clstype

    @classmethod
    async def refresh(cls) -> None:
        """异步刷新容器：实例化所有单例 Bean，并自动启动调度器。"""
        if cls._initialized:
            return

        items = list(cls._bean_classes.items())
        filtered_items = []
        for bean_name, clstype in items:
            if cls._check_match_profiles(clstype) and cls._check_match_condition(clstype):
                filtered_items.append((bean_name, clstype))
            else:
                component_profile = getattr(clstype, '_component_profile', [])
                logger.debug(f"Skipping component {bean_name} due to profile mismatch (needs {component_profile}, active: {cls._active_profiles})")

        filtered_items.sort(key=lambda x: getattr(x[1], '_component_priority', 10000000))
        for bean_name, clstype in filtered_items:

            if bean_name not in cls._beans:
                lazy = getattr(clstype, '_component_lazy', False)
                if lazy:
                    logger.debug(f"Skipping lazy bean {bean_name}, it's marked as lazy")
                    continue
                cls._resolve_dependency(bean_name)
        for instance in cls._beans.values():
            await cls._invoke_post_construct(instance)
        await cls._start_scheduler()
        cls._initialized = True

    @classmethod
    async def close(cls) -> None:
        """关闭容器：停止调度器并销毁所有单例。"""
        await cls._stop_scheduler()
        for instance in list(cls._beans.values()):
            await cls._invoke_pre_destroy(instance)
        # cls._bean_classes.clear()
        cls._type_to_name.clear()
        cls._creating.clear()
        cls._scheduler_tasks.clear()
        cls._active_profiles.clear()
        cls._scheduler_running = False
        cls._app_config = None
        cls._initialized = False
        for clstype in cls._bean_classes.values():
            for method_name in dir(clstype):
                method = getattr(clstype, method_name)
                if callable(method) and hasattr(method, '_post_construct'):
                    method._post_construct['invoked'] = False

                if hasattr(method, '_pre_destroy'):
                    method._pre_destroy['invoked'] = False

                if hasattr(method, '_task_config'):
                    method._task_config['registered'] = False

    @classmethod
    async def _run_interval_task(cls, coro, interval_seconds: float):
        while cls._scheduler_running:
            try:
                await coro()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"异步任务执行失败: {e}", exc_info=True)
            interval_seconds = max(0.1, interval_seconds)
            await asyncio.sleep(interval_seconds)

    @classmethod
    async def _run_func_task(cls, coro, instance: Any, func: Callable):
        while cls._scheduler_running:
            try:
                await coro()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"异步任务执行失败: {e}", exc_info=True)
            sleep_seconds = await func(instance) if inspect.iscoroutinefunction(func) else func(instance)
            sleep_seconds = max(0.1, sleep_seconds)
            await asyncio.sleep(sleep_seconds)

    @classmethod
    async def _run_cron_task(cls, coro, cron_expr: str):
        base = datetime.now()
        cron = croniter(cron_expr, base)
        while cls._scheduler_running:
            next_time = cron.get_next(datetime)
            sleep_seconds = (next_time - datetime.now()).total_seconds()
            sleep_seconds = max(0.1, sleep_seconds)
            await asyncio.sleep(sleep_seconds)
            try:
                await coro()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"异步 cron 任务执行失败: {e}", exc_info=True)

    @classmethod
    async def _start_scheduler(cls) -> None:
        """内部方法：启动调度器（由 refresh 自动调用）"""
        cls._scheduler_running = True
        for instance in cls._beans.values():
            cls._register_tasks_for_instance(instance)

    @classmethod
    def _register_tasks_for_instance(cls, instance: Any) -> None:
        """为单个实例注册 @Task 任务（如果调度器已运行且任务未注册）"""
        if not cls._scheduler_running:
            return
        for method_name in dir(instance):
            method = getattr(instance, method_name)
            if callable(method) and hasattr(method, "_task_config"):
                config = method._task_config
                if config.get("registered"):
                    logger.warning(f"{instance.__class__.__name__}.{method_name} 任务已经注册过")
                    continue
                if config.get("cron"):
                    task = asyncio.create_task(cls._run_cron_task(method, config["cron"]))
                elif config.get("interval") is not None:
                    task = asyncio.create_task(cls._run_interval_task(method, config["interval"]))
                elif config.get("func") is not None:
                    task = asyncio.create_task(cls._run_func_task(method, instance, config["func"]))
                else:
                    logger.warning(f"{instance.__class__.__name__}.{method_name} 任务配置无效")
                    continue
                cls._scheduler_tasks.add(task)
                task.add_done_callback(cls._scheduler_tasks.discard)
                config["registered"] = True
                logger.info(f"已注册定时任务: {instance.__class__.__name__}.{method_name}")

    @classmethod
    async def _stop_scheduler(cls) -> None:
        """内部方法：停止调度器（由 close 自动调用）"""
        if not cls._scheduler_running:
            return
        cls._scheduler_running = False
        if cls._scheduler_tasks:
            for task in cls._scheduler_tasks:
                task.cancel()
            await asyncio.gather(*cls._scheduler_tasks, return_exceptions=True)

        cls._scheduler_tasks.clear()
        logger.info("调度器已停止")
