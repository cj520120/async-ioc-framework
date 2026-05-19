import logging
from abc import ABC, abstractmethod
from typing import AsyncContextManager, List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ...component import Component
from ...config import AppConfig
from ...decorators import PostConstruct, PreDestroy

logger = logging.getLogger(__name__)


class DatabaseInitializer(ABC):

    engine: Optional[AsyncEngine] = None
    session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    async_url: Optional[str] = None

    @abstractmethod
    def parse(self, config: dict):
        pass

    @abstractmethod
    def get_type(self) -> str:
        pass


@Component(priority=1)
class DatabaseFactory:
    def __init__(self, app_config: AppConfig, initalizers: List[DatabaseInitializer]):
        self.config = app_config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self.initalizers = initalizers
        # self._parse_config()

    def get_engine(self) -> AsyncEngine:
        if self.engine is None:
            raise RuntimeError("DatabaseFactory not initialized")
        return self.engine

    @PostConstruct
    async def init_db(self):
        try:
            db_type = self.config.get("database", {}).get("type", "sqlite")
            for initializer in self.initalizers:
                if initializer.get_type() == db_type:
                    initializer.parse(self.config.get("database", {}))
                    logger.info(f"Connecting to database: {initializer.async_url}")
                    self.engine = create_async_engine(initializer.async_url, connect_args=initializer.connect_args, **initializer.engine_kwargs)
                    self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False)
                    logger.info("Database connection pool created successfully")
                    return
            raise RuntimeError(f"No initializer found for database type: {db_type}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise

    def get_session(self) -> AsyncContextManager[AsyncSession]:
        if self.session_factory is None:
            raise RuntimeError("DatabaseFactory not initialized")
        return self.session_factory()

    @PreDestroy
    async def close(self):
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection pool closed")
