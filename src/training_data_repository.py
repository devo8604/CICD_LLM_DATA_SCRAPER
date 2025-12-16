"""Repository for managing training data samples and file hashes."""

import sqlite3
import hashlib
import logging
from pathlib import Path


class TrainingDataRepository:
    """Manages training samples, Q&A pairs, and file hash tracking."""

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize training data repository.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None
        self._connect_db()
        self._create_tables()

    def _connect_db(self) -> None:
        """Establish database connection."""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.cursor = self.conn.cursor()
            logging.debug(f"TrainingDataRepository connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logging.critical(f"Error connecting to database {self.db_path}: {e}")
            raise

    def _create_tables(self) -> None:
        """Create training data tables if they don't exist."""
        self.cursor.execute(
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
        self.cursor.execute(
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
        self.cursor.execute(
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
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS FailedFiles (
                failed_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                reason TEXT,
                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()
        logging.debug(
            "Ensured TrainingSamples, ConversationTurns, and FileHashes tables exist."
        )

    def add_failed_file(self, file_path: str, reason: str) -> None:
        """
        Add a failed file to the database.
        Args:
            file_path: Path to the failed file
            reason: Reason for failure
        """
        self.cursor.execute(
            """
            INSERT INTO FailedFiles (file_path, reason)
            VALUES (?, ?)
            """,
            (file_path, reason),
        )
        self.conn.commit()
        logging.warning(f"Added failed file {file_path} to database. Reason: {reason}")

    def get_failed_files(self) -> list[tuple[str, str]]:
        """
        Get all failed files from the database.
        Returns:
            List of tuples containing file_path and reason
        """
        self.cursor.execute("SELECT file_path, reason FROM FailedFiles")
        return self.cursor.fetchall()

    def remove_failed_file(self, file_path: str) -> None:
        """
        Remove a failed file from the database.
        Args:
            file_path: Path to the file to remove
        """
        self.cursor.execute("DELETE FROM FailedFiles WHERE file_path = ?", (file_path,))
        self.conn.commit()
        logging.info(f"Removed failed file {file_path} from database.")

    def add_qa_sample(
        self, file_path: str, question_text: str, answer_text: str
    ) -> int:
        """
        Add a Q&A sample to the database.

        Args:
            file_path: Source file path for the Q&A
            question_text: Question text
            answer_text: Answer text

        Returns:
            The sample_id of the created sample
        """
        # Insert into TrainingSamples
        self.cursor.execute(
            """
            INSERT INTO TrainingSamples (dataset_source, model_type_intended, is_multiturn)
            VALUES (?, ?, ?)
            """,
            (f"repo_file:{file_path}", "Instruct", False),
        )
        sample_id = self.cursor.lastrowid

        # Insert question as a ConversationTurn (role='user', is_label=FALSE)
        self.cursor.execute(
            """
            INSERT INTO ConversationTurns (sample_id, turn_index, role, content, is_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sample_id, 0, "user", question_text, False),
        )

        # Insert answer as a ConversationTurn (role='assistant', is_label=TRUE)
        self.cursor.execute(
            """
            INSERT INTO ConversationTurns (sample_id, turn_index, role, content, is_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sample_id, 1, "assistant", answer_text, True),
        )
        self.conn.commit()
        logging.debug(f"Added Q&A sample (ID: {sample_id}) for {file_path}.")
        return sample_id

    def get_processed_question_hashes(self, file_path: str) -> set[str]:
        """
        Get SHA256 hashes of all processed questions for a file.

        Args:
            file_path: Path to the file

        Returns:
            Set of question hashes
        """
        # Find sample_ids that originate from the given file_path
        self.cursor.execute(
            "SELECT sample_id FROM TrainingSamples WHERE dataset_source LIKE ?",
            (f"repo_file:{file_path}%",),
        )
        sample_ids_for_file = {row[0] for row in self.cursor.fetchall()}

        if not sample_ids_for_file:
            return set()

        # Find questions within these sample_ids that also have an assistant's answer
        placeholders = ",".join("?" * len(sample_ids_for_file))
        self.cursor.execute(
            f"""
            SELECT T1.content FROM ConversationTurns T1
            INNER JOIN ConversationTurns T2
            ON T1.sample_id = T2.sample_id
            WHERE T1.sample_id IN ({placeholders})
            AND T1.role = 'user'
            AND T2.role = 'assistant'
            """,
            tuple(sample_ids_for_file),
        )
        return {
            hashlib.sha256(row[0].encode("utf-8")).hexdigest()
            for row in self.cursor.fetchall()
        }

    def get_file_hash(self, file_path: str) -> str | None:
        """
        Get stored hash for a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA256 hash of file contents, or None if not found
        """
        self.cursor.execute(
            "SELECT content_hash FROM FileHashes WHERE file_path = ?", (file_path,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def save_file_hash(
        self, file_path: str, content_hash: str, sample_id: int | None = None
    ) -> None:
        """
        Save file hash to database.

        Args:
            file_path: Path to the file
            content_hash: SHA256 hash of file contents
            sample_id: Optional sample_id to associate with this file
        """
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO FileHashes (file_path, content_hash, last_processed, sample_id)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            """,
            (file_path, content_hash, sample_id),
        )
        self.conn.commit()
        logging.debug(f"Saved file hash for {file_path}.")

    def delete_file_hash(self, file_path: str) -> None:
        """
        Delete file hash from database.

        Args:
            file_path: Path to the file
        """
        self.cursor.execute("DELETE FROM FileHashes WHERE file_path = ?", (file_path,))
        self.conn.commit()
        logging.debug(f"Deleted file hash for {file_path}.")

    def get_all_tracked_files(self) -> list[str]:
        """
        Get all tracked file paths.

        Returns:
            List of file paths
        """
        self.cursor.execute("SELECT file_path FROM FileHashes")
        return [row[0] for row in self.cursor.fetchall()]

    def delete_samples_for_file(self, file_path: str) -> None:
        """
        Delete all samples and conversation turns for a removed file.

        Args:
            file_path: Path to the removed file
        """
        # Get sample_ids associated with this file_path
        self.cursor.execute(
            "SELECT sample_id FROM TrainingSamples WHERE dataset_source LIKE ?",
            (f"repo_file:{file_path}%",),
        )
        sample_ids = [row[0] for row in self.cursor.fetchall()]

        if sample_ids:
            # Delete ConversationTurns linked to these sample_ids
            placeholders = ",".join("?" * len(sample_ids))
            self.cursor.execute(
                f"DELETE FROM ConversationTurns WHERE sample_id IN ({placeholders})",
                tuple(sample_ids),
            )
            # Delete TrainingSamples
            self.cursor.execute(
                f"DELETE FROM TrainingSamples WHERE sample_id IN ({placeholders})",
                tuple(sample_ids),
            )
            self.conn.commit()
            logging.info(
                f"Deleted {len(sample_ids)} samples and their turns for removed file: {file_path}"
            )

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                logging.debug("TrainingDataRepository database connection closed.")
            except Exception:
                # Suppress errors during close (already closed or other issue)
                pass
            finally:
                self.conn = None
