import logging
from typing import AsyncContextManager, Optional
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ...component import Component
from ...config import AppConfig
from ...decorators import PostConstruct, PreDestroy

logger = logging.getLogger(__name__)


@Component(priority=1)
class DatabaseFactory:
    def __init__(self, app_config: AppConfig):
        self.config = app_config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._parse_config()

    def get_engine(self) -> AsyncEngine:
        if self.engine is None:
            raise RuntimeError("DatabaseFactory not initialized")
        return self.engine

    def _parse_config(self):
        db = self.config.get("database", {})
        self.db_type = db.get("type", "mysql")
        if self.db_type not in ("mysql", "sqlite"):
            raise ValueError(f"Unsupported database type: {self.db_type}")

        if self.db_type == "sqlite":
            database_file = db.get("file", "db.sqlite3")
            self.async_url = f"sqlite+aiosqlite:///{database_file}"
            self.sync_url = f"sqlite:///{database_file}"
            self.connect_args = db.get("connect_args", {"check_same_thread": False})
            if "isolation_level" not in self.connect_args:
                self.connect_args["isolation_level"] = "DEFERRED"
            self.engine_kwargs = db.get("engine_kwargs", {})
        else:  # mysql
            host = db.get("host", "localhost")
            port = int(db.get("port", 3306))
            username = db.get("username", "root")
            password = quote_plus(db.get("password", ""))
            database = db.get("database", "test")
            charset = db.get("charset", "utf8mb4")
            self.async_url = f"mysql+asyncmy://{username}:{password}@{host}:{port}/{database}?charset={charset}"
            self.connect_args = {}
            # 连接池配置可外部化
            pool_config = db.get("pool", {})
            self.engine_kwargs = {
                "pool_recycle": pool_config.get("recycle", 3600),
                "pool_size": pool_config.get("size", 10),
                "max_overflow": pool_config.get("max_overflow", 20),
                "pool_pre_ping": pool_config.get("pre_ping", True),
                **db.get("engine_kwargs", {}),
            }

    @PostConstruct
    async def init_db(self):
        try:
            logger.info(f"Connecting to database: {self.async_url}")
            self.engine = create_async_engine(self.async_url, connect_args=self.connect_args, **self.engine_kwargs)
            self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False)
            logger.info("Database connection pool created successfully")
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
