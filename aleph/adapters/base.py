from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgentAdapter(ABC):
    kind = "base"

    @abstractmethod
    def invoke(self, context) -> dict:
        raise NotImplementedError

