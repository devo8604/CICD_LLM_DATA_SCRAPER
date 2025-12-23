"""Test database indexes for TrainingDataRepository."""

import pytest

from src.data.training_data_repository import TrainingDataRepository


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database."""
    db_path = tmp_path / "test.db"
    return db_path


def test_indexes_created_on_initialization(temp_db):
    """Test that all indexes are created when repository is initialized."""
    repo = TrainingDataRepository(temp_db)

    with repo.get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        indexes = {row[0] for row in cursor.fetchall()}

    expected_indexes = {
        "idx_training_samples_dataset_source",
        "idx_conversation_turns_sample_id",
        "idx_conversation_turns_role",
        "idx_file_hashes_file_path",
    }

    assert expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}"


def test_indexes_idempotent(temp_db):
    """Test that creating repository multiple times doesn't fail."""
    # First initialization
    repo1 = TrainingDataRepository(temp_db)

    # Second initialization (indexes already exist)
    repo2 = TrainingDataRepository(temp_db)

    # Should not raise any errors
    assert repo1 is not None
    assert repo2 is not None


def test_dataset_source_index_improves_queries(temp_db):
    """Verify that the dataset_source index is used in queries."""
    repo = TrainingDataRepository(temp_db)

    # Add some sample data
    repo.add_qa_sample("test.py", "Q1", "A1")
    repo.add_qa_sample("test.py", "Q2", "A2")

    with repo.get_connection() as conn:
        # Check query plan for dataset_source lookup
        cursor = conn.execute("EXPLAIN QUERY PLAN SELECT sample_id FROM TrainingSamples WHERE dataset_source LIKE 'repo_file:test.py%'")
        plan = cursor.fetchall()

        # Verify index is being used
        plan_str = str(plan).lower()
        assert "idx_training_samples_dataset_source" in plan_str or "using index" in plan_str, f"Index not used in query plan: {plan}"


def test_sample_id_index_exists(temp_db):
    """Verify that the sample_id index exists and can be used."""
    repo = TrainingDataRepository(temp_db)

    with repo.get_connection() as conn:
        # Verify index exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_conversation_turns_sample_id'")
        result = cursor.fetchone()
        assert result is not None, "idx_conversation_turns_sample_id index not found"

        # Add sample data and verify JOIN still works
        repo.add_qa_sample("test.py", "Q1", "A1")

        # Test that JOIN works correctly (index will be used for larger datasets)
        cursor = conn.execute("SELECT * FROM TrainingSamples AS TS JOIN ConversationTurns AS CT ON TS.sample_id = CT.sample_id")
        results = cursor.fetchall()
        assert len(results) > 0, "JOIN query returned no results"


def test_all_indexes_exist_after_initialization(temp_db):
    """Test that all expected indexes are created."""
    repo = TrainingDataRepository(temp_db)

    with repo.get_connection() as conn:
        # Get all indexes
        cursor = conn.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name")
        indexes = cursor.fetchall()

    # Convert to dict for easier checking
    index_dict = {name: table for name, table in indexes}

    # Verify all expected indexes exist and point to correct tables
    assert "idx_training_samples_dataset_source" in index_dict
    assert index_dict["idx_training_samples_dataset_source"] == "TrainingSamples"

    assert "idx_conversation_turns_sample_id" in index_dict
    assert index_dict["idx_conversation_turns_sample_id"] == "ConversationTurns"

    assert "idx_conversation_turns_role" in index_dict
    assert index_dict["idx_conversation_turns_role"] == "ConversationTurns"

    assert "idx_file_hashes_file_path" in index_dict
    assert index_dict["idx_file_hashes_file_path"] == "FileHashes"
