"""Optimized database manager with batching and indexing improvements."""

import hashlib
import logging
import sqlite3
import threading
from contextlib import contextmanager

from src.core.error_handling import DatabaseError, retry

# Get logger for this module
logger = logging.getLogger(__name__)


class OptimizedDBManager:
    """Optimized database manager with batching and indexing improvements."""

    CREATE_TABLES_SQL = [
        """CREATE TABLE IF NOT EXISTS qa_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS file_hashes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS failed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            reason TEXT,
            failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS processing_state (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS processed_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            question_hash TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    # Create indexes for better performance
    CREATE_INDEXES_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_file_path ON qa_samples(file_path)",
        "CREATE INDEX IF NOT EXISTS idx_file_hashes_path ON file_hashes(file_path)",
        "CREATE INDEX IF NOT EXISTS idx_failed_files_path ON failed_files(file_path)",
        "CREATE INDEX IF NOT EXISTS idx_processed_questions_path ON processed_questions(file_path)",
        "CREATE INDEX IF NOT EXISTS idx_processed_questions_hash ON processed_questions(question_hash)",
        "CREATE INDEX IF NOT EXISTS idx_qa_samples_created_at ON qa_samples(created_at)",
    ]

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._connection_pool = {}
        self._lock = threading.Lock()
        self._batch_size = 100  # Default batch size
        self._batch_queue: list[tuple[str, tuple]] = []
        self._batch_buffer = []

        # Initialize database
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database tables and indexes."""
        try:
            # Create tables
            with self.get_connection() as conn:
                for sql in self.CREATE_TABLES_SQL:
                    conn.execute(sql)

                # Create indexes
                for sql in self.CREATE_INDEXES_SQL:
                    conn.execute(sql)

                conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}") from e

    @contextmanager
    def get_connection(self):
        """Get a database connection using connection pooling."""
        # Each thread gets its own connection

        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,  # 30 second timeout
            )
            # Set connection options for better performance
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA cache_size=10000")
            self._local.connection.execute("PRAGMA temp_store=memory")
            self._local.connection.row_factory = sqlite3.Row  # Enable dict-like access

        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise
        else:
            self._local.connection.commit()

    def _execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query safely with error handling."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                return cursor
            except sqlite3.Error as e:
                logger.error(f"Database error executing query: {query[:50]}... Error: {e}")
                raise DatabaseError(f"Query execution failed: {e}") from e

    def _execute_many(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute many queries in batch for better performance."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(query, params_list)
                return cursor
            except sqlite3.Error as e:
                logger.error(f"Database error executing batch query: {query[:50]}... Error: {e}")
                raise DatabaseError(f"Batch query execution failed: {e}") from e

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def add_qa_sample(self, file_path: str, question: str, answer: str) -> bool:
        """Add a Q&A sample to the database with retry logic."""
        try:
            query = "INSERT INTO qa_samples (file_path, question, answer) VALUES (?, ?, ?)"
            self._execute_query(query, (file_path, question, answer))
            return True
        except Exception as e:
            logger.error(f"Error adding Q&A sample for {file_path}: {e}")
            return False

    def add_qa_samples_batch(self, samples: list[tuple[str, str, str]]) -> bool:
        """Add multiple Q&A samples in a batch for better performance."""
        if not samples:
            return True

        try:
            query = "INSERT INTO qa_samples (file_path, question, answer) VALUES (?, ?, ?)"
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, samples)
                conn.commit()
            logger.info(f"Added {len(samples)} Q&A samples in batch")
            return True
        except Exception as e:
            logger.error(f"Error adding Q&A samples batch: {e}")
            return False

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def get_all_tracked_files(self) -> list[str]:
        """Get all tracked file paths with retry logic."""
        try:
            query = "SELECT DISTINCT file_path FROM qa_samples"
            cursor = self._execute_query(query)
            return [row["file_path"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting tracked files: {e}")
            return []

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def save_file_hash(self, file_path: str, file_hash: str) -> bool:
        """Save file hash to database with retry logic."""
        try:
            query = """
                INSERT OR REPLACE INTO file_hashes (file_path, file_hash, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """
            self._execute_query(query, (file_path, file_hash))
            return True
        except Exception as e:
            logger.error(f"Error saving file hash for {file_path}: {e}")
            return False

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def get_file_hash(self, file_path: str) -> str | None:
        """Get file hash from database with retry logic."""
        try:
            query = "SELECT file_hash FROM file_hashes WHERE file_path = ?"
            cursor = self._execute_query(query, (file_path,))
            row = cursor.fetchone()
            return row["file_hash"] if row else None
        except Exception as e:
            logger.error(f"Error getting file hash for {file_path}: {e}")
            return None

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def delete_file_hash(self, file_path: str) -> bool:
        """Delete file hash from database with retry logic."""
        try:
            query = "DELETE FROM file_hashes WHERE file_path = ?"
            self._execute_query(query, (file_path,))
            return True
        except Exception as e:
            logger.error(f"Error deleting file hash for {file_path}: {e}")
            return False

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def delete_samples_for_file(self, file_path: str) -> bool:
        """Delete all samples for a specific file with retry logic."""
        try:
            query = "DELETE FROM qa_samples WHERE file_path = ?"
            self._execute_query(query, (file_path,))
            return True
        except Exception as e:
            logger.error(f"Error deleting samples for {file_path}: {e}")
            return False

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def get_failed_files(self) -> list[tuple[str, str]]:
        """Get list of failed files with retry logic."""
        try:
            query = "SELECT file_path, reason FROM failed_files"
            cursor = self._execute_query(query)
            return [(row["file_path"], row["reason"]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting failed files: {e}")
            return []

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def add_failed_file(self, file_path: str, reason: str) -> bool:
        """Add a failed file to the database with retry logic."""
        try:
            query = """
                INSERT OR REPLACE INTO failed_files (file_path, reason, failed_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """
            self._execute_query(query, (file_path, reason))
            return True
        except Exception as e:
            logger.error(f"Error adding failed file {file_path}: {e}")
            return False

    @retry(max_attempts=3, exceptions=(sqlite3.Error, DatabaseError))
    def remove_failed_file(self, file_path: str) -> bool:
        """Remove a failed file from the database with retry logic."""
        try:
            query = "DELETE FROM failed_files WHERE file_path = ?"
            self._execute_query(query, (file_path,))
            return True
        except Exception as e:
            logger.error(f"Error removing failed file {file_path}: {e}")
            return False

    def get_processed_question_hashes(self, file_path: str) -> list[str]:
        """Get hashes of questions already processed for this file."""
        try:
            query = "SELECT question_hash FROM processed_questions WHERE file_path = ?"
            cursor = self._execute_query(query, (file_path,))
            return [row["question_hash"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting processed question hashes for {file_path}: {e}")
            return []

    def mark_question_processed(self, file_path: str, question: str) -> bool:
        """Mark a question as processed for the file."""
        try:
            import hashlib

            question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
            query = """
                INSERT OR IGNORE INTO processed_questions (file_path, question_hash)
                VALUES (?, ?)
            """
            self._execute_query(query, (file_path, question_hash))
            return True
        except Exception as e:
            logger.error(f"Error marking question processed for {file_path}: {e}")
            return False

    def mark_questions_processed_batch(self, file_path: str, questions: list[str]) -> bool:
        """Mark multiple questions as processed in a batch."""
        if not questions:
            return True

        try:
            question_hashes = [(file_path, hashlib.sha256(q.encode("utf-8")).hexdigest()) for q in questions]
            query = """
                INSERT OR IGNORE INTO processed_questions (file_path, question_hash)
                VALUES (?, ?)
            """
            self._execute_many(query, question_hashes)
            return True
        except Exception as e:
            logger.error(f"Error marking questions processed batch for {file_path}: {e}")
            return False

    def get_qa_samples_for_file(self, file_path: str) -> list[dict[str, str]]:
        """Get all Q&A samples for a specific file."""
        try:
            query = "SELECT question, answer FROM qa_samples WHERE file_path = ?"
            cursor = self._execute_query(query, (file_path,))
            return [{"question": row["question"], "answer": row["answer"]} for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting Q&A samples for {file_path}: {e}")
            return []

    def get_total_samples_count(self) -> int:
        """Get total count of all Q&A samples."""
        try:
            query = "SELECT COUNT(*) as total FROM qa_samples"
            cursor = self._execute_query(query)
            result = cursor.fetchone()
            return result["total"] if result else 0
        except Exception as e:
            logger.error(f"Error getting total samples count: {e}")
            return 0

    def close_db(self):
        """Close the database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            try:
                self._local.connection.close()
                self._local.connection = None
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")

    def vacuum_database(self):
        """Optimize database by running VACUUM command."""
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuum completed")
        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")

    def get_stats(self) -> dict[str, int]:
        """Get database statistics."""
        try:
            stats = {}

            # Count QA samples
            cursor = self._execute_query("SELECT COUNT(*) as count FROM qa_samples")
            stats["qa_samples"] = cursor.fetchone()["count"]

            # Count unique files
            cursor = self._execute_query("SELECT COUNT(DISTINCT file_path) as count FROM qa_samples")
            stats["unique_files"] = cursor.fetchone()["count"]

            # Count failed files
            cursor = self._execute_query("SELECT COUNT(*) as count FROM failed_files")
            stats["failed_files"] = cursor.fetchone()["count"]

            # Count processed questions
            cursor = self._execute_query("SELECT COUNT(*) as count FROM processed_questions")
            stats["processed_questions"] = cursor.fetchone()["count"]

            return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    def batch_insert_qa_pairs(self, file_path: str, qa_pairs: list[tuple[str, str]]) -> bool:
        """Batch insert multiple Q&A pairs for a file."""
        if not qa_pairs:
            return True

        try:
            # Prepare data for batch insert
            batch_data = [(file_path, question, answer) for question, answer in qa_pairs]

            # Insert QA pairs
            qa_query = "INSERT INTO qa_samples (file_path, question, answer) VALUES (?, ?, ?)"
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(qa_query, batch_data)

                # Also mark questions as processed
                question_hashes = [(file_path, hashlib.sha256(qp[0].encode("utf-8")).hexdigest()) for qp in qa_pairs]
                processed_query = """
                    INSERT OR IGNORE INTO processed_questions (file_path, question_hash)
                    VALUES (?, ?)
                """
                cursor.executemany(processed_query, question_hashes)

                conn.commit()

            logger.info(f"Batch inserted {len(qa_pairs)} QA pairs for {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error batch inserting QA pairs for {file_path}: {e}")
            return False
