"""Base class for all report-generation agents."""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """All report agents inherit from this."""

    @abstractmethod
    async def ask_questions(self, tb_data: list[dict]) -> list[dict]:
        """Return a list of CA-style clarification questions based on TB data.
        Each dict: {"id": str, "question": str, "account": str, "risk": str}
        """

    @abstractmethod
    async def generate(self, tb_data: list[dict], answers: dict[str, str], **kwargs) -> str:
        """Generate the report text."""
