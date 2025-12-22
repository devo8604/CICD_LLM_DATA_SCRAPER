#!/usr/bin/env python3
"""
Test script to validate the config injection fixes.
"""

import sys
from pathlib import Path

# Add src to path for imports
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from src.core.config import AppConfig
from src.data.db_manager import DBManager
from src.llm.llm_client import LLMClient
from src.pipeline.exporters import DataExporter
from src.pipeline.export_service import ExportService


def test_llm_client_requires_config():
    """Test that LLMClient now requires config injection."""
    print("Testing LLMClient config injection...")
    
    # This should raise a ValueError now
    try:
        client = LLMClient("http://localhost", "test-model", 3, 1)
        print("ERROR: LLMClient allowed creation without config")
        return False
    except ValueError as e:
        if "Config must be provided through dependency injection" in str(e):
            print("✓ LLMClient properly requires config injection")
        else:
            print(f"ERROR: Unexpected error: {e}")
            return False
    
    # This should work when config is provided
    try:
        config = AppConfig()
        client = LLMClient("http://localhost", "test-model", 3, 1, config=config)
        print("✓ LLMClient works when config is provided")
    except Exception as e:
        print(f"ERROR: LLMClient failed with config: {e}")
        return False
    
    return True


def test_data_exporter_requires_config():
    """Test that DataExporter now requires config injection."""
    print("\nTesting DataExporter config injection...")
    
    # Mock DBManager
    mock_db = object()  # Using a simple object as mock
    
    # This should raise a ValueError now
    try:
        exporter = DataExporter(mock_db)
        print("ERROR: DataExporter allowed creation without config")
        return False
    except ValueError as e:
        if "Config must be provided" in str(e):
            print("✓ DataExporter properly requires config injection")
        else:
            print(f"ERROR: Unexpected error: {e}")
            return False
    
    # This should work when config is provided
    try:
        config = AppConfig()
        exporter = DataExporter(mock_db, config)
        print("✓ DataExporter works when config is provided")
    except Exception as e:
        print(f"ERROR: DataExporter failed with config: {e}")
        return False
    
    return True


def test_export_service_accepts_config():
    """Test that ExportService now accepts and uses config."""
    print("\nTesting ExportService config injection...")
    
    # Mock DBManager
    mock_db = object()  # Using a simple object as mock
    
    try:
        config = AppConfig()
        service = ExportService(mock_db, config)
        print("✓ ExportService properly accepts config")
    except Exception as e:
        print(f"ERROR: ExportService failed to accept config: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("Running validation tests for config injection fixes...\n")
    
    success = True
    success &= test_llm_client_requires_config()
    success &= test_data_exporter_requires_config()
    success &= test_export_service_accepts_config()
    
    if success:
        print("\n✓ All config injection fixes validated successfully!")
        sys.exit(0)
    else:
        print("\n✗ Some validation tests failed!")
        sys.exit(1)