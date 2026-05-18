# Async IoC Framework

一个轻量级、高性能的异步 IoC 容器，专为现代 Python 异步应用设计。提供依赖注入、配置管理、生命周期回调、定时任务、事务管理、事件驱动、条件注册等特性，语法与 Spring 框架高度相似，Java 开发者可以无缝迁移。

# 特性

- **依赖注入** – 基于类型注解的自动注入，支持构造函数、List[T]、Set[T]、Optional[T]

- **配置管理** – @Value 注解注入配置值，支持嵌套键与默认值

- **组件生命周期** – @PostConstruct / @PreDestroy，支持同步/异步方法

- **环境隔离** – @Profile + active_profiles，按环境启用/禁用组件

- **优先级与消歧义** – @Primary 指定主 Bean，@Qualifier 按名称注入

- **懒加载** – @Component(lazy=True)，按需创建实例

- **定时任务** – @Task 支持固定间隔、Cron 表达式、动态间隔函数

- **声明式事务** – @transactional 自动管理数据库会话与事务，支持传播（复用上层事务）

- **事件驱动** – @EventListener + EventPublisher，松散耦合的同步/异步事件处理

- **条件注册** – @Component(condition=...) 根据配置、类存在性等条件动态注册 Bean

- **模块扫描** – scan_directory 自动导入组件，无需手动注册

- **异步安全** – 基于 contextvars 的会话传递，同一调用链共享同一会话/事务

- **优雅关闭** – 支持信号处理（SIGINT/SIGTERM），自动清理资源

# 安装

## 使用 pip安装

```bash
pip install async-ioc-framework
```

## 从源码安装

```bash
git clone https://github.com/yourname/async-ioc-framework.git
cd async-ioc-framework
pip install -e .
```

## 可选依赖

数据库支持：pip install 'async-ioc-framework[mysql,sqlite]'（自动包含 SQLAlchemy 和对应驱动）

## 完整安装

```bash
pip install 'async-ioc-framework[all]'
```

# 快速开始

1. 定义组件

```python
from ioc import Component, PostConstruct

@Component
class Repository:
    @PostConstruct
    async def init(self):
        print("Repository ready")
```

2. 依赖注入

```python
@Component
class UserService:
    def __init__(self, repo: Repository):   # 构造函数自动注入
        self.repo = repo
```

3. 配置注入（config.yaml）

```yaml
app_name: MyApp
database:
  type: mysql
  url: mysql://localhost/test
  username: root
  password: pass123
timeout: 30
```

```python
from ioc import Component, Value, Annotated

@Component
class ConfigConsumer:
    def __init__(
        self,
        name: Annotated[str, Value("${app_name}")],
        db_url: Annotated[str, Value("${database.url:default.db}")],
        timeout: Annotated[int, Value("${timeout:10}")],
    ):
        self.name = name
        self.db_url = db_url
        self.timeout = timeout
```

4. 启动容器

```python
import asyncio
from ioc import ApplicationContext

async def main():
    ApplicationContext.initialize("config.yaml")
    await ApplicationContext.refresh()
    service = ApplicationContext.get_bean(UserService)
    # 运行你的业务...
    await ApplicationContext.close()

asyncio.run(main())
```

5. 使用启动辅助函数（推荐）

```python
from ioc import run_async

if __name__ == "__main__":
    asyncio.run(run_async("config.yaml", "/path/to/project", modules=["my_service"]))
```

# 核心概念详解

## 组件注册

@Component 支持以下参数：

| 参数      | 类型      | 说明                         |
| --------- | --------- | ---------------------------- |
| name      | str       | Bean 名称（默认类名小写）    |
| priority  | int       | 创建顺序（数字越小越先）     |
| primary   | bool      | 类型匹配时的首选 Bean        |
| profile   | str       | List[str] 需要激活的 profile |
| lazy      | bool      | 延迟到第一次使用时创建       |
| condition | Condition | 条件注册，满足条件才创建     |

```python
@Component(name="userRepo", priority=10, primary=True, profile="dev", lazy=False)
class UserRepository:
    pass
```

## 依赖注入

容器根据构造函数参数类型自动注入：

```python
@Component
class OrderService:
    def __init__(self, user_repo: UserRepository, logger: Logger):
        self.user_repo = user_repo
        self.logger = logger
```

- **集合注入：** List[Service] 或 Set[Service] 会注入所有匹配类型的 Bean。

- **可选依赖：** Optional[Service] 允许依赖不存在时注入 None。

- **按名称注入：** Annotated[Service, Qualifier("beanName")]。

- **配置值注入：** Annotated[str, Value("${key:default}")]。

## 生命周期回调

- **@PostConstruct：** 实例化且依赖注入完成后执行（同步/异步均可）。

- **@PreDestroy：** 容器关闭前执行，用于资源释放（同步/异步均可）。

```python
@Component
class ConnectionPool:
    @PostConstruct
    async def init(self):
        await self.connect()

    @PreDestroy
    async def close(self):
        await self.disconnect()
```

## 环境隔离（Profile）

配置文件指定激活的 profiles：

```yaml
active_profiles: ["dev", "local"]
```

组件按条件注册：

```python
@Component(profile="dev")
class DevDataSource: ...

@Component(profile="prod")
class ProdDataSource: ...
```

## 定时任务

使用 @Task 装饰方法（必须是 async def）：

```python
@Component
class Scheduler:
    @Task(interval=5)
    async def run_every_5s(self):
        print("每5秒执行")

    @Task(cron="0 * * * *")
    async def run_hourly(self):
        print("每小时执行")

    @Task(func=lambda self: self.get_dynamic_interval())
    async def dynamic_task(self):
        print("动态间隔")
```

## 声明式事务（需 SQLAlchemy）

```python
from ioc.ext.data import transactional, get_current_session

@Component
class UserDao:
    @transactional
    async def create_user(self, name: str):
        session = get_current_session()
        user = User(name=name)
        session.add(user)
        # 无异常自动提交，异常自动回滚
```

事务传播：内层 @transactional 会自动复用外层事务。

## 事件驱动

```python
from ioc.events import Event, EventListener, EventPublisher

class UserCreated(Event):
    def __init__(self, user_id):
        self.user_id = user_id

@Component
class UserService:
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher

    async def create_user(self):
        await self.publisher.publish(UserCreated(123))

@Component
class Notifier:
    @EventListener(UserCreated)
    async def send_email(self, event: UserCreated):
        print(f"Send email to user {event.user_id}")
```

## 条件注册

内置条件类：

- OnPropertyCondition(key, having_value=None, match_if_missing=False) – 根据配置属性

- OnClassExists(class_path) / OnMissingClass(class_path) – 根据类是否存在

- AllConditions(\*conditions) – 所有条件满足

- AnyCondition(\*conditions) – 任一条件满足

- NotCondition(condition) – 取反

```python
@Component(condition=OnPropertyCondition("cache.enabled", having_value=True))
class CacheService: ...

@Component(condition=AllConditions(
    OnPropertyCondition("feature.new.enabled", having_value=True),
    OnClassExists("redis.asyncio.Redis")
))
class RedisCache: ...
```

# 配置参考

创建 config.yaml：

```yaml
active_profiles: ["dev"] # 激活的环境
app_name: MyApp
database:
  url: sqlite+aiosqlite:///test.db
timeout: 30
debug: true
feature:
  new:
    enabled: true
modules: # 可选：需要扫描的模块
  - services
  - dao
```

# 在 FastAPI 中集成

```python

from fastapi import FastAPI
from ioc import ApplicationContext
from ioc.ext.data import transactional, get_current_session

app = FastAPI()

@app.on_event("startup")
async def startup():
    ApplicationContext.initialize("config.yaml")
    await ApplicationContext.refresh()

@app.on_event("shutdown")
async def shutdown():
    await ApplicationContext.close()

@app.get("/users/{id}")
async def get_user(id: int):
    service = ApplicationContext.get_bean(UserService)
    return await service.get_user(id)
```

# API 参考

## 核心模块 (ioc)

- ApplicationContext – 静态容器，提供 initialize, refresh, get_bean, close 等方法

- Component – 组件装饰器

- Qualifier, Value – 注解类

- Task, PostConstruct, PreDestroy – 方法装饰器

- AppConfig – 配置类

- run – 启动辅助函数

- 条件类 – Condition, OnPropertyCondition, OnClassExists, OnMissingClass, AllConditions, AnyCondition, NotCondition

## 数据库扩展 (ioc.db)

- DatabaseFactory – 异步数据库连接池工厂

- SessionManager – 会话管理器

- transactional – 事务装饰器

- get_current_session – 获取当前会话

## 事件扩展 (ioc.events)

- Event – 事件基类

- EventListener – 事件监听器装饰器

- EventPublisher – 事件发布器

 
# 使用 pytest（需安装 pytest-asyncio）

pytest

# 贡献

欢迎提交 Issue 和 Pull Request。

# 仓库地址

https://gitcode.com/cj520120/async-ioc-framework.git
