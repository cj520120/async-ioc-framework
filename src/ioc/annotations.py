from abc import ABC, abstractmethod
from typing import Any, Dict


class Qualifier:
    def __init__(self, name: str):
        self.name = name


class Value:
    """用于从配置文件中注入值，支持默认值语法：${key:default}"""

    def __init__(self, expression: str):
        self.expression = expression
        self.key, self.default = self._parse(expression)

    def _parse(self, expr: str):
        if not expr.startswith("${") or not expr.endswith("}"):
            raise ValueError(f"Value expression must be like ${'{key}'} or ${'{key:default}'}, got {expr}")
        inner = expr[2:-1]
        if ":" in inner:
            key, default = inner.split(":", 1)
            return key.strip(), default
        else:
            return inner.strip(), None


class Condition(ABC):
    @abstractmethod
    def matches(self, context: Dict[str, Any]) -> bool:
        pass


class OnPropertyCondition(Condition):
    def __init__(self, key: str, having_value=None, match_if_missing=False):
        self.key = key
        self.having_value = having_value
        self.match_if_missing = match_if_missing

    def matches(self, context):
        value = context["config"].get(self.key)
        if value is None:
            return self.match_if_missing
        return value == self.having_value

    def __repr__(self):
        return f"OnPropertyCondition({self.key}:{self.having_value})"


class OnClassExists(Condition):
    def __init__(self, class_path: str):
        self.class_path = class_path

    def matches(self, context):
        import importlib

        module_path, _, class_name = self.class_path.rpartition('.')
        try:
            module = importlib.import_module(module_path)
            return hasattr(module, class_name)
        except ImportError:
            return False

    def __repr__(self):
        return f"OnClassExists({self.class_path})"


class OnMissingClass(Condition):
    def __init__(self, class_path: str):
        self.class_path = class_path

    def matches(self, context):
        import importlib

        module_path, _, class_name = self.class_path.rpartition('.')
        try:
            module = importlib.import_module(module_path)
            return not hasattr(module, class_name)
        except ImportError:
            return True

    def __repr__(self):
        return f"OnMissingClass({self.class_path})"


class AllConditions(Condition):
    def __init__(self, *conditions):
        self.conditions = conditions

    def matches(self, context):
        return all(c.matches(context) for c in self.conditions)

    def __repr__(self):
        return f"AllConditions({', '.join(map(repr, self.conditions))})"


class AnyCondition(Condition):
    def __init__(self, *conditions):
        self.conditions = conditions

    def matches(self, context):
        return any(c.matches(context) for c in self.conditions)

    def __repr__(self):
        return f"AnyCondition({', '.join(map(repr, self.conditions))})"


class NotCondition(Condition):
    def __init__(self, condition):
        self.condition = condition

    def matches(self, context):
        return not self.condition.matches(context)

    def __repr__(self):
        return f"NotCondition({self.condition})"
