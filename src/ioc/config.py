from typing import Any, Dict

import yaml


class AppConfig:
    def __init__(self):
        self._config = {}

    def load_from_file(self, path: str = "config.yaml"):
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

    def load_from_dict(self, config: Dict[Any, Any]):
        self._config = config

    def load_from_body(self, body: bytes):
        data = yaml.safe_load(body)
        self._config = data if isinstance(data, dict) else {}

    def __getitem__(self, key):
        return self._config[key]

    def get(self, key: str, default: Any = None):
        parts = key.split(".")
        cur = self._config
        for part in parts:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur

    def __setitem__(self, key, value):
        self._config[key] = value

    def merge_dict(self, config: Dict[Any, Any]):
        for key, value in config.items():
            if value:
                self._config[key] = value

    def __contains__(self, key):
        return key in self._config
