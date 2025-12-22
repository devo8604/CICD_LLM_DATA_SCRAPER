"""
Test cases for the pre-tokenization utilities.
"""

import pytest
from src.core.tokenizer_cache import TokenizerCache, PreTokenizer, get_pretokenizer


def test_tokenizer_cache_initialization():
    """Test that tokenizer cache initializes properly."""
    cache = TokenizerCache("gpt2")
    assert cache.model_name == "gpt2"
    assert cache._token_cache == {}


def test_token_counting():
    """Test token counting functionality."""
    cache = TokenizerCache("gpt2")
    
    # Test with empty string
    assert cache.count_tokens("") == 0
    
    # Test with simple text
    text = "Hello world!"
    tokens = cache.count_tokens(text)
    assert tokens >= 0  # Should return a non-negative number
    
    # Test caching - same text should return same result
    tokens2 = cache.count_tokens(text)
    assert tokens == tokens2


def test_truncation():
    """Test text truncation functionality."""
    cache = TokenizerCache("gpt2")
    
    # Test with text that should be truncated
    long_text = "This is a very long text that should be truncated to fit within the token limit. " * 10
    truncated = cache.truncate_to_tokens(long_text, max_tokens=20)
    
    # The truncated text should be shorter than the original
    assert len(truncated) <= len(long_text)
    assert "This is a very long text" in truncated  # Should preserve beginning


def test_split_to_tokens():
    """Test splitting text to token chunks."""
    cache = TokenizerCache("gpt2")
    
    text = "This is a test text. " * 50  # Create a longer text
    chunks = cache.split_to_tokens(text, max_tokens=20)
    
    assert len(chunks) > 0
    assert all(len(chunk) > 0 for chunk in chunks)


def test_prepare_prompt_with_context():
    """Test preparing prompts with context limits."""
    cache = TokenizerCache("gpt2")
    
    system_msg = "You are a helpful assistant."
    user_msg = "What is the meaning of life?"
    
    prompt = cache.prepare_prompt_with_context(
        system_msg, 
        user_msg, 
        max_context_tokens=1000,
        max_output_tokens=100
    )
    
    assert "System:" in prompt
    assert "You are a helpful assistant" in prompt
    assert "What is the meaning of life?" in prompt


def test_pretokenizer_validation():
    """Test pre-tokenizer validation functionality."""
    pretokenizer = PreTokenizer("gpt2")
    
    # Test with a small prompt that should be valid
    is_valid, message = pretokenizer.validate_request_size(
        "Hello, how are you?", 
        max_context_tokens=1000, 
        expected_output_tokens=100
    )
    
    assert is_valid
    assert "valid" in message.lower()


def test_pretokenizer_prepare_and_validate():
    """Test prepare and validate functionality."""
    pretokenizer = PreTokenizer("gpt2")
    
    is_valid, message, prompt = pretokenizer.prepare_and_validate(
        "You are a helpful assistant.",
        "What is the capital of France?",
        max_context_tokens=1000,
        expected_output_tokens=50
    )
    
    assert is_valid
    assert prompt is not None
    assert "System:" in prompt
    assert "capital of France" in prompt


def test_global_instance():
    """Test global pre-tokenizer instance."""
    instance1 = get_pretokenizer()
    instance2 = get_pretokenizer()
    
    # Should return the same instance
    assert instance1 is instance2


if __name__ == "__main__":
    # Run tests manually if executed as script
    test_tokenizer_cache_initialization()
    test_token_counting()
    test_truncation()
    test_split_to_tokens()
    test_prepare_prompt_with_context()
    test_pretokenizer_validation()
    test_pretokenizer_prepare_and_validate()
    test_global_instance()
    print("All tests passed!")