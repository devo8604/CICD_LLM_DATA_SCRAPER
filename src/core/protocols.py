"""Abstract interface for LLM clients."""

from abc import ABC, abstractmethod


class LLMInterface(ABC):
    """Abstract interface for LLM clients to enable different backends."""

    @property
    @abstractmethod
    def context_window(self) -> int:
        """The context window size (max tokens) of the model."""
        pass

    @abstractmethod
    async def generate_questions(
        self, content: str, temperature: float = 0.7, max_tokens: int = 500, pbar=None
    ) -> list[str] | None:
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
    ) -> str | None:
        """Generate an answer to a question based on context."""
        pass

    @abstractmethod
    def clear_context(self):
        """Clear any cached context or state."""
        pass
