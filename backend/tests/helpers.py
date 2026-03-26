from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeExecuteResult:
    all_value: list[Any] | None = None
    scalar_value: Any = None

    def all(self):
        return self.all_value or []

    def scalar_one_or_none(self):
        return self.scalar_value
