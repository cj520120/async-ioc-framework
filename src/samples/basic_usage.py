"""
async-ioc-framework 快速入门示例

本示例演示：
1. 定义组件（@Component）
2. 依赖注入（构造函数自动注入）
3. 配置注入（@Value）
4. 生命周期回调（@PostConstruct, @PreDestroy）
5. 定时任务（@Task）
6. 声明式事务（@transactional）
7. 事件驱动（@EventListener）

运行前请先安装框架：
    pip install async-ioc-framework

如果需要数据库支持，请额外安装：
    pip install 'async-ioc-framework[sqlite]'   # SQLite
    pip install 'async-ioc-framework[mysql]'    # MySQL
"""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import declarative_base

from ioc import Component, Event, EventListener, EventPublisher, PostConstruct, PreDestroy, Task, Value
from ioc.ext.data import DatabaseFactory, get_current_session, transactional
from ioc.runner import run_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()


# ========== 数据库模型 ==========
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)


# ========== 1. 基础业务组件 ==========
@Component
class GreetingService:
    def say_hello(self, name: str) -> str:
        return f"Hello, {name}!"


@Component
class UserService:
    def __init__(self, greeting: GreetingService):
        self.greeting = greeting

    def greet_user(self, name: str) -> str:
        return self.greeting.say_hello(name)


# ========== 2. 配置注入 ==========
@Component
class AppInfo:
    def __init__(
        self,
        name: Annotated[str, Value("${app.name}")],
        version: Annotated[str, Value("${app.version:1.0.0}")],
    ):
        self.name = name
        self.version = version

    @PostConstruct
    def init(self):
        logger.info(f"AppInfo loaded: {self.name} v{self.version}")


# ========== 3. 定时任务 ==========
@Component
class ScheduledTasks:
    @Task(interval=5)
    async def run_every_5_seconds(self):
        logger.info("Periodic task executed (every 5s)")

    @Task(cron="0 * * * *")  # 每小时整点执行
    async def run_hourly(self):
        logger.info("Hourly cron task executed")

    @Task(func=lambda self: self.get_dynamic_interval())
    async def dynamic_task(self):
        logger.info("Dynamic interval task executed")

    def get_dynamic_interval(self) -> float:
        return 10.0


# ========== 4. 数据库事务 ==========
@Component
class UserDao:
    def __init__(self, factory: DatabaseFactory):
        self.factory = factory  # 注意：属性名应与 __init__ 参数一致

    @PostConstruct
    async def init(self):
        async with self.factory.get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @transactional
    async def create_user(self, name: str) -> int:
        session = get_current_session()
        user = User(name=name)
        session.add(user)
        await session.flush()
        logger.info(f"User {name} created with id {user.id}")
        return user.id

    @transactional
    async def get_user(self, user_id: int):
        session = get_current_session()
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        logger.info(f"Fetched user: {user.name if user else None}")
        return user

    @PreDestroy
    @transactional
    async def cleanup(self):
        # 清理测试数据（可选）
        session = get_current_session()
        await session.execute(User.__table__.delete())
        logger.info("Cleaned up user table")


# ========== 5. 事件驱动 ==========
class UserRegisteredEvent(Event):
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username


@Component
class UserRegistrar:
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher

    async def register(self, username: str) -> int:
        # 模拟注册，实际应调用 UserDao 等
        user_id = 456
        await self.publisher.publish(UserRegisteredEvent(user_id, username))
        return user_id


@Component
class WelcomeEmailSender:
    @EventListener(UserRegisteredEvent)
    async def send_welcome(self, event: UserRegisteredEvent):
        logger.info(f"Sending welcome email to {event.username} (ID: {event.user_id})")


@Component
class AuditLogger:
    @EventListener(UserRegisteredEvent)
    def log_registration(self, event: UserRegisteredEvent):
        logger.info(f"Audit: user {event.username} registered with ID {event.user_id}")


# ========== 6. 启动应用 ==========
async def main():
    # 方式一：手动控制容器生命周期
    # ApplicationContext.initialize("config.yaml")
    # await ApplicationContext.refresh()
    # ... 使用组件 ...
    # await ApplicationContext.close()

    # 方式二：使用内置 runner（推荐）
    base_path = Path(__file__).resolve().parent
    await run_async("config.yaml", base_path, modules=[])


if __name__ == "__main__":
    asyncio.run(main())
