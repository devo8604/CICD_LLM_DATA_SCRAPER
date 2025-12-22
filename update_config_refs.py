#!/usr/bin/env python3
"""
Script to update all config attribute references to use the new config.model pattern.
"""

import os
import re
from pathlib import Path


def get_config_mapping():
    """Map old config attributes to new ones."""
    mapping = {
        # LLM settings
        r'\.LLM_BASE_URL': '.model.llm.base_url',
        r'\.LLM_MODEL_NAME': '.model.llm.model_name',
        r'\.LLM_MAX_RETRIES': '.model.llm.max_retries',
        r'\.LLM_RETRY_DELAY': '.model.llm.retry_delay',
        r'\.LLM_MODEL_CACHE_TTL': '.model.llm.cache_ttl',
        r'\.LLM_REQUEST_TIMEOUT': '.model.llm.request_timeout',
        
        # Data Pipeline settings
        r'\.BASE_DIR': '.model.base_dir',
        r'\.DATA_DIR': '.model.pipeline.data_dir',
        r'\.REPOS_DIR_NAME': '.model.pipeline.repos_dir_name',
        r'\.REPOS_DIR': '.model.pipeline.repos_dir',
        r'\.DB_PATH': '.model.pipeline.db_path',
        r'\.PROMPT_THEME': '.model.pipeline.prompt_theme',
        r'\.MAX_FILE_SIZE': '.model.pipeline.max_file_size',
        
        # Logging settings
        r'\.MAX_LOG_FILES': '.model.logging.max_log_files',
        r'\.LOG_FILE_PREFIX': '.model.logging.log_file_prefix',
        
        # Generation settings
        r'\.DEFAULT_MAX_TOKENS': '.model.generation.default_max_tokens',
        r'\.DEFAULT_TEMPERATURE': '.model.generation.default_temperature',
        r'\.MIN_QUESTION_TOKENS': '.model.generation.min_question_tokens',
        r'\.MAX_QUESTION_TOKENS': '.model.generation.max_question_tokens',
        r'\.MIN_ANSWER_CONTEXT_TOKENS': '.model.generation.min_answer_context_tokens',
        r'\.MAX_ANSWER_CONTEXT_TOKENS': '.model.generation.max_answer_context_tokens',
        
        # Battery settings
        r'\.BATTERY_LOW_THRESHOLD': '.model.battery.low_threshold',
        r'\.BATTERY_HIGH_THRESHOLD': '.model.battery.high_threshold',
        r'\.BATTERY_CHECK_INTERVAL': '.model.battery.check_interval',
        
        # File filtering
        r'\.ALLOWED_EXTENSIONS': '.model.pipeline.allowed_extensions',
        r'\.ALLOWED_JSON_MD_FILES': '.model.pipeline.allowed_json_md_files',
        
        # Chat templates
        r'\.QWEN_TEMPLATE': '.model.templates.qwen_template',
        r'\.LLAMA3_CHAT_TEMPLATE': '.model.templates.llama3_template',
        r'\.MISTRAL_CHAT_TEMPLATE': '.model.templates.mistral_template',
        r'\.GEMMA_CHAT_TEMPLATE': '.model.templates.gemma_template',
        
        # State management
        r'\.STATE_SAVE_INTERVAL': '.model.pipeline.state_save_interval',
        
        # Processing settings
        r'\.MAX_CONCURRENT_FILES': '.model.processing.max_concurrent_files',
        r'\.FILE_BATCH_SIZE': '.model.processing.file_batch_size',
        r'\.CHUNK_READ_SIZE': '.model.processing.chunk_read_size',
        
        # Performance settings
        r'\.FILE_HASH_CACHE_SIZE': '.model.performance.file_hash_cache_size',
        r'\.DATABASE_CONNECTION_POOL_SIZE': '.model.performance.database_connection_pool_size',
        
        # MLX settings
        r'\.USE_MLX': '.model.use_mlx',
        r'\.MLX_MODEL_NAME': '.model.mlx.model_name',
        r'\.MLX_MAX_RAM_GB': '.model.mlx.max_ram_gb',
        r'\.MLX_QUANTIZE': '.model.mlx.quantize',
        r'\.MLX_TEMPERATURE': '.model.mlx.temperature',
    }
    return mapping


def update_file(filepath):
    """Update a single file with new config references."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    mapping = get_config_mapping()
    
    # Apply all mappings
    for old_attr, new_attr in mapping.items():
        # Use word boundary to avoid partial matches
        pattern = r'(\w+)\.' + old_attr
        replacement = r'\1' + new_attr
        content = re.sub(pattern, replacement, content)
    
    # Check if anything changed
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")
        return True
    return False


def main():
    """Main function to process all Python files."""
    root_dir = Path(__file__).parent
    src_dir = root_dir / "src"
    
    updated_count = 0
    
    # Find all Python files in src directory
    for py_file in src_dir.rglob("*.py"):
        if "test_" not in py_file.name and "__pycache__" not in str(py_file):
            try:
                if update_file(py_file):
                    updated_count += 1
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
    
    print(f"Updated {updated_count} files")


if __name__ == "__main__":
    main()