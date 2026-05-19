from ....component import Component
from ..database import DatabaseInitializer


@Component
class SqliteInitiallzer(DatabaseInitializer):

    def parse(self, db: dict):
        database_file = db.get("file", "db.sqlite3")
        self.async_url = f"sqlite+aiosqlite:///{database_file}"
        self.sync_url = f"sqlite:///{database_file}"
        self.connect_args = db.get("connect_args", {"check_same_thread": False})
        if "isolation_level" not in self.connect_args:
            self.connect_args["isolation_level"] = "DEFERRED"
        self.engine_kwargs = db.get("engine_kwargs", {})
    def get_type(self)->str:
        return "sqlite"