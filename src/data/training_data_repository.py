"""Repository for managing training data samples and file hashes with thread-safe connections."""

import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class TrainingDataRepository:
    """Manages training samples, Q&A pairs, and file hash tracking using thread-local connections."""

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize training data repository.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._local = threading.local()
        self._create_tables()

    @contextmanager
    def get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(str(self.db_path), timeout=30.0)
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")

        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise
        else:
            self._local.connection.commit()

    def _create_tables(self) -> None:
        """Create training data tables if they don't exist."""
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS TrainingSamples (
                    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_source VARCHAR(255),
                    creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model_type_intended VARCHAR(50),
                    sample_quality_score REAL,
                    is_multiturn BOOLEAN
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ConversationTurns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id INTEGER,
                    turn_index INTEGER,
                    role VARCHAR(50),
                    content TEXT,
                    is_label BOOLEAN,
                    metadata_json TEXT,
                    FOREIGN KEY (sample_id) REFERENCES TrainingSamples(sample_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS FileHashes (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    last_processed DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sample_id INTEGER,
                    FOREIGN KEY (sample_id) REFERENCES TrainingSamples(sample_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS FailedFiles (
                    failed_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    reason TEXT,
                    failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Create indexes for performance optimization
            # These use IF NOT EXISTS so they're safe to run on every connection
            conn.execute("CREATE INDEX IF NOT EXISTS idx_training_samples_dataset_source ON TrainingSamples(dataset_source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_turns_sample_id ON ConversationTurns(sample_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_turns_role ON ConversationTurns(role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hashes_file_path ON FileHashes(file_path)")
        logger.debug("Ensured TrainingDataRepository tables and indexes exist")

    def add_failed_file(self, file_path: str, reason: str) -> None:
        """Add a failed file to the database."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO FailedFiles (file_path, reason)
                VALUES (?, ?)
                """,
                (file_path, reason),
            )
        logger.warning("Added failed file", file_path=file_path, reason=reason)

    def get_failed_files(self) -> list[tuple[str, str]]:
        """Get all failed files from the database."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT file_path, reason FROM FailedFiles")
            return cursor.fetchall()

    def remove_failed_file(self, file_path: str) -> None:
        """Remove a failed file from the database."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM FailedFiles WHERE file_path = ?", (file_path,))
        logger.debug("Removed failed file", file_path=file_path)

    def add_qa_sample(self, file_path: str, question_text: str, answer_text: str) -> int:
        """Add a Q&A sample to the database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO TrainingSamples (dataset_source, model_type_intended, is_multiturn)
                VALUES (?, ?, ?)
                """,
                (f"repo_file:{file_path}", "Instruct", False),
            )
            sample_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO ConversationTurns (sample_id, turn_index, role, content, is_label)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sample_id, 0, "user", question_text, False),
            )

            conn.execute(
                """
                INSERT INTO ConversationTurns (sample_id, turn_index, role, content, is_label)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sample_id, 1, "assistant", answer_text, True),
            )
            return sample_id

    def add_qa_samples_batch(self, file_path: str, qa_pairs: list[tuple[str, str]]) -> list[int]:
        """Add multiple Q&A samples to the database in a single transaction."""
        if not qa_pairs:
            return []

        sample_ids = []
        with self.get_connection() as conn:
            for _ in qa_pairs:
                cursor = conn.execute(
                    """
                    INSERT INTO TrainingSamples (dataset_source, model_type_intended, is_multiturn)
                    VALUES (?, ?, ?)
                    """,
                    (f"repo_file:{file_path}", "Instruct", False),
                )
                sample_ids.append(cursor.lastrowid)

            conversation_turns_data = []
            for i, (question_text, answer_text) in enumerate(qa_pairs):
                sample_id = sample_ids[i]
                conversation_turns_data.append((sample_id, 0, "user", question_text, False))
                conversation_turns_data.append((sample_id, 1, "assistant", answer_text, True))

            conn.executemany(
                """
                INSERT INTO ConversationTurns (sample_id, turn_index, role, content, is_label)
                VALUES (?, ?, ?, ?, ?)
                """,
                conversation_turns_data,
            )
        logger.debug("Added Q&A samples in batch", file_path=file_path, count=len(qa_pairs))
        return sample_ids

    def get_processed_question_hashes(self, file_path: str) -> set[str]:
        """Get SHA256 hashes of all processed questions for a file."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT CT1.content
                FROM ConversationTurns CT1
                JOIN TrainingSamples TS ON CT1.sample_id = TS.sample_id
                JOIN ConversationTurns CT2 ON TS.sample_id = CT2.sample_id
                WHERE TS.dataset_source LIKE ?
                  AND CT1.role = 'user'
                  AND CT2.role = 'assistant'
                """,
                (f"repo_file:{file_path}%",),
            )

            return {hashlib.sha256(row[0].encode("utf-8")).hexdigest() for row in cursor.fetchall()}

    def get_file_hash(self, file_path: str) -> str | None:
        """Get stored hash for a file."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT content_hash FROM FileHashes WHERE file_path = ?", (file_path,))
            result = cursor.fetchone()
            return result[0] if result else None

    def save_file_hash(self, file_path: str, content_hash: str, sample_id: int | None = None) -> None:
        """Save file hash to database."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO FileHashes (file_path, content_hash, last_processed, sample_id)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (file_path, content_hash, sample_id),
            )
        logger.debug("Saved file hash", file_path=file_path)

    def delete_file_hash(self, file_path: str) -> None:
        """Delete file hash from database."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM FileHashes WHERE file_path = ?", (file_path,))
        logger.debug("Deleted file hash", file_path=file_path)

    def get_all_tracked_files(self) -> list[str]:
        """Get all tracked file paths."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT file_path FROM FileHashes")
            return [row[0] for row in cursor.fetchall()]

    def delete_samples_for_file(self, file_path: str) -> None:
        """Delete all samples and conversation turns for a removed file."""
        source_pattern = f"repo_file:{file_path}%"
        with self.get_connection() as conn:
            # Delete conversation turns first due to foreign key (if enabled)
            conn.execute(
                """
                DELETE FROM ConversationTurns
                WHERE sample_id IN (
                    SELECT sample_id FROM TrainingSamples
                    WHERE dataset_source LIKE ?
                )
                """,
                (source_pattern,),
            )

            # Then delete training samples
            cursor = conn.execute(
                "DELETE FROM TrainingSamples WHERE dataset_source LIKE ?",
                (source_pattern,),
            )
            deleted_count = cursor.rowcount

        logger.info("Deleted samples for removed file", file_path=file_path, count=deleted_count)

    def get_all_training_samples(self) -> list[dict[str, any]]:
        """Retrieve all training samples and their conversation turns."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    TS.sample_id, TS.dataset_source, TS.creation_date, TS.model_type_intended,
                    TS.sample_quality_score, TS.is_multiturn, CT.turn_index, CT.role,
                    CT.content, CT.is_label, CT.metadata_json
                FROM TrainingSamples AS TS
                JOIN ConversationTurns AS CT ON TS.sample_id = CT.sample_id
                ORDER BY TS.sample_id, CT.turn_index
                """
            )
            rows = cursor.fetchall()

        conversations = {}
        for row in rows:
            sample_id = row[0]
            if sample_id not in conversations:
                conversations[sample_id] = {
                    "sample_id": sample_id,
                    "dataset_source": row[1],
                    "creation_date": row[2],
                    "model_type_intended": row[3],
                    "sample_quality_score": row[4],
                    "is_multiturn": bool(row[5]),
                    "turns": [],
                }
            conversations[sample_id]["turns"].append(
                {
                    "turn_index": row[6],
                    "role": row[7],
                    "content": row[8],
                    "is_label": bool(row[9]),
                    "metadata_json": row[10],
                }
            )
        return list(conversations.values())

    def close(self) -> None:
        """Close thread-local database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            try:
                self._local.connection.close()
                logger.debug("TrainingDataRepository database connection closed")
            except Exception:
                pass
            finally:
                self._local.connection = None
