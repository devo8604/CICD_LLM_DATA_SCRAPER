"""Protocol definitions for dependency injection and testing."""

from typing import Protocol, runtime_checkable
from pathlib import Path


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM client interactions."""

    async def generate_questions(
        self,
        text: str,
        temperature: float,
        max_tokens: int
    ) -> list[str] | None:
        """Generate questions from text."""
        ...

    async def get_answer_single(
        self,
        question: str,
        context: str,
        temperature: float,
        max_tokens: int
    ) -> str | None:
        """Generate answer for a single question."""
        ...

    async def get_answers_batch(
        self,
        batch_of_question_context_tuples: list[tuple[str, str]],
        temperature: float,
        max_tokens: int
    ) -> list[str | None]:
        """Generate answers for multiple questions in parallel."""
        ...

    def clear_context(self) -> None:
        """Clear context."""
        ...


@runtime_checkable
class DBManagerProtocol(Protocol):
    """Protocol for database operations."""

    def get_state(self) -> dict[str, any]:
        """Retrieve pipeline state."""
        ...

    def save_state(self, state_dict: dict[str, any]) -> None:
        """Save pipeline state."""
        ...

    def add_qa_sample(
        self,
        file_path: str,
        question_text: str,
        answer_text: str
    ) -> int:
        """Add Q&A sample to database."""
        ...

    def get_processed_question_hashes(self, file_path: str) -> set[str]:
        """Get hashes of processed questions for a file."""
        ...

    def get_file_hash(self, file_path: str) -> str | None:
        """Get stored hash for a file."""
        ...

    def save_file_hash(
        self,
        file_path: str,
        content_hash: str,
        sample_id: int | None = None
    ) -> None:
        """Save file hash to database."""
        ...

    def delete_file_hash(self, file_path: str) -> None:
        """Delete file hash from database."""
        ...

    def get_all_tracked_files(self) -> list[str]:
        """Get all tracked file paths."""
        ...

    def delete_samples_for_file(self, file_path: str) -> None:
        """Delete all samples for a file."""
        ...

    def close_db(self) -> None:
        """Close database connection."""
        ...


@runtime_checkable
class FileManagerProtocol(Protocol):
    """Protocol for file management operations."""

    def get_all_files_in_repo(self, current_repo_path: str) -> list[str]:
        """Get all processable files in a repository."""
        ...


@runtime_checkable
class DataPipelineProtocol(Protocol):
    """Protocol for data pipeline operations."""

    async def scrape(self) -> None:
        """Clone or update repositories."""
        ...

    async def prepare(self) -> None:
        """Process files and generate Q&A."""
        ...

    def close(self) -> None:
        """Cleanup resources."""
        ...


@runtime_checkable
class StateManagerProtocol(Protocol):
    """Protocol for pipeline state management."""

    def get_state(self) -> dict[str, any]:
        """Retrieve pipeline state."""
        ...

    def save_state(self, state_dict: dict[str, any]) -> None:
        """Save pipeline state."""
        ...

    def close(self) -> None:
        """Close state manager."""
        ...


@runtime_checkable
class TrainingDataRepositoryProtocol(Protocol):
    """Protocol for training data operations."""

    def add_qa_sample(
        self, file_path: str, question_text: str, answer_text: str
    ) -> int:
        """Add Q&A sample to database."""
        ...

    def get_processed_question_hashes(self, file_path: str) -> set[str]:
        """Get hashes of processed questions for a file."""
        ...

    def get_file_hash(self, file_path: str) -> str | None:
        """Get stored hash for a file."""
        ...

    def save_file_hash(
        self, file_path: str, content_hash: str, sample_id: int | None = None
    ) -> None:
        """Save file hash to database."""
        ...

    def delete_file_hash(self, file_path: str) -> None:
        """Delete file hash from database."""
        ...

    def get_all_tracked_files(self) -> list[str]:
        """Get all tracked file paths."""
        ...

    def delete_samples_for_file(self, file_path: str) -> None:
        """Delete all samples for a file."""
        ...

    def close(self) -> None:
        """Close training data repository."""
        ...
