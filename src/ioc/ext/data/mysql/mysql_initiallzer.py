from urllib.parse import quote_plus

from ....component import Component
from ..database import DatabaseInitializer


@Component
class MySqlInitiallzer(DatabaseInitializer):

    def parse(self, db: dict):
        host = db.get("host", "localhost")
        port = int(db.get("port", 3306))
        username = db.get("username", "root")
        password = quote_plus(db.get("password", ""))
        database = db.get("database", "test")
        charset = db.get("charset", "utf8mb4")
        self.async_url = f"mysql+asyncmy://{username}:{password}@{host}:{port}/{database}?charset={charset}"
        self.connect_args = {}
        pool_config = db.get("pool", {})
        self.engine_kwargs = {
            "pool_recycle": pool_config.get("recycle", 3600),
            "pool_size": pool_config.get("size", 10),
            "max_overflow": pool_config.get("max_overflow", 20),
            "pool_pre_ping": pool_config.get("pre_ping", True),
            **db.get("engine_kwargs", {}),
        }

    def get_type(self) -> str:
        return "mysql"
