import contextvars
import inspect
import logging
from contextlib import asynccontextmanager
from functools import wraps
from typing import AsyncGenerator, Callable, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...component import Component
from ...context import ApplicationContext
from .database import DatabaseFactory

logger = logging.getLogger(__name__)

_current_session: contextvars.ContextVar[Optional[AsyncSession]] = contextvars.ContextVar("_current_session", default=None)

_after_commit_callbacks: contextvars.ContextVar[Optional[List[Callable]]] = contextvars.ContextVar("_after_commit_callbacks", default=None)


@Component
class SessionManager:
    """会话管理器，负责会话的获取与生命周期绑定"""

    def __init__(self, db_factory: DatabaseFactory):
        self.db_factory = db_factory

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取当前事务的会话（自动复用或创建新会话）"""
        current = _current_session.get()
        if current is not None:
            yield current
        else:
            async with self.db_factory.get_session() as session:
                tx = await session.begin()
                token = _current_session.set(session)
                try:
                    yield session
                    await tx.commit()
                except:
                    logger.error("Transaction rolling back due to exception", exc_info=True)
                    await tx.rollback()
                    raise
                finally:
                    _current_session.reset(token)
                    session = None


def register_after_commit(callback: Callable) -> None:
    """
    注册一个事务提交后执行的回调函数。
    回调可以是同步函数或异步函数（async def）。
    只能在 @transactional 装饰的方法内调用。
    """
    callbacks = _after_commit_callbacks.get()
    if callbacks is None:
        raise RuntimeError("No active transaction, cannot register after_commit callback")
    callbacks.append(callback)


def transactional(func: Callable) -> Callable:
    if not inspect.iscoroutinefunction(func):
        raise TypeError("@transactional can only be applied to async functions")

    @wraps(func)
    async def wrapper(*args, **kwargs):
        session_mgr = ApplicationContext.get_bean(SessionManager)
        current_session = _current_session.get()
        if current_session is not None:
            return await func(*args, **kwargs)
        else:
            callbacks: List[Callable] = []
            token_callbacks = _after_commit_callbacks.set(callbacks)
            try:
                async with session_mgr.get_session():
                    result = await func(*args, **kwargs)
                for cb in callbacks:
                    try:
                        if inspect.iscoroutinefunction(cb):
                            await cb()
                        else:
                            cb()
                    except Exception as e:
                        logger.error(f"Error executing after_commit callback: {e}", exc_info=True)
                return result
            finally:
                _after_commit_callbacks.reset(token_callbacks)

    return wrapper


def get_current_session() -> AsyncSession:
    """
    获取当前活动事务中的数据库会话。
    只能在 @transactional 装饰的方法内调用。
    """
    sess = _current_session.get()
    if sess is None:
        raise RuntimeError("No active database session. Did you forget @transactional?")
    return sess
