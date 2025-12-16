"""Abstract interface for LLM clients."""

from abc import ABC, abstractmethod
from typing import List, Optional


class LLMInterface(ABC):
    """Abstract interface for LLM clients to enable different backends."""

    @abstractmethod
    async def generate_questions(
        self, content: str, temperature: float = 0.7, max_tokens: int = 500, pbar=None
    ) -> Optional[List[str]]:
        """Generate questions from content."""
        pass

    @abstractmethod
    async def get_answer_single(
        self,
        question: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        pbar=None,
    ) -> Optional[str]:
        """Generate an answer to a question based on context."""
        pass

    @abstractmethod
    def clear_context(self):
        """Clear any cached context or state."""
        pass
