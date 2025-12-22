"""
Demonstration of pre-tokenization for efficient LLM communication.

This script shows how pre-tokenization can optimize LLM requests by:
1. Validating request size before sending to the LLM
2. Efficiently truncating content to fit within context windows
3. Caching tokenization results for repeated operations
"""

from src.core.tokenizer_cache import PreTokenizer, get_pretokenizer
from src.llm.llm_client import LLMClient
from src.core.config import AppConfig


def demonstrate_basic_tokenization():
    """Demonstrate basic tokenization features."""
    print("=== Basic Tokenization Demo ===")
    
    # Get a pre-tokenizer instance
    pretokenizer = get_pretokenizer("gpt2")
    
    # Sample text
    text = "This is a sample text to demonstrate tokenization capabilities. " * 10
    
    # Count tokens
    token_count = pretokenizer.cache.count_tokens(text)
    print(f"Text length: {len(text)} characters")
    print(f"Token count: {token_count} tokens")
    
    # Truncate to specific token limit
    truncated = pretokenizer.cache.truncate_to_tokens(text, max_tokens=20)
    truncated_token_count = pretokenizer.cache.count_tokens(truncated)
    print(f"Truncated to 20 tokens: {truncated_token_count} tokens, {len(truncated)} characters")
    print()


def demonstrate_request_validation():
    """Demonstrate request validation before sending to LLM."""
    print("=== Request Validation Demo ===")

    try:
        # Create a pretend LLM client context (without actually connecting)
        config = AppConfig()
        client = LLMClient(
            base_url="http://localhost:11434",  # Example URL
            model_name="llama2",
            max_retries=1,
            retry_delay=1,
            request_timeout=30,
            config=config
        )

        # Sample system and user messages
        system_msg = "You are a helpful coding assistant that provides accurate and concise answers."
        user_msg = "Explain how to implement a binary search algorithm in Python. Include time complexity analysis."

        # Validate request before sending
        is_valid, message, prepared_prompt = client.prepare_and_validate_request(
            system_msg,
            user_msg,
            expected_output_tokens=200
        )

        print(f"Request validation result: {message}")
        print(f"Request is valid: {is_valid}")
        if is_valid and prepared_prompt:
            print(f"Prepared prompt length: {len(prepared_prompt)} characters")
            print(f"Estimated prompt tokens: {client.pretokenizer.cache.count_tokens(prepared_prompt)}")
    except ValueError as e:
        if "No usable LLM model available" in str(e):
            print("LLM server not available, demonstrating with pre-tokenizer directly:")
            # Use pre-tokenizer directly for demonstration
            pretokenizer = get_pretokenizer("gpt2")
            system_msg = "You are a helpful coding assistant that provides accurate and concise answers."
            user_msg = "Explain how to implement a binary search algorithm in Python. Include time complexity analysis."

            is_valid, message, prepared_prompt = pretokenizer.prepare_and_validate(
                system_msg,
                user_msg,
                max_context_tokens=4096,  # Typical context window
                expected_output_tokens=200
            )

            print(f"Request validation result: {message}")
            print(f"Request is valid: {is_valid}")
            if is_valid and prepared_prompt:
                print(f"Prepared prompt length: {len(prepared_prompt)} characters")
                print(f"Estimated prompt tokens: {pretokenizer.cache.count_tokens(prepared_prompt)}")
        else:
            raise
    print()


def demonstrate_context_aware_processing():
    """Demonstrate context-aware content processing."""
    print("=== Context-Aware Processing Demo ===")
    
    pretokenizer = get_pretokenizer("gpt2")
    
    # Simulate a large document that needs to be processed
    large_document = "Introduction to machine learning. " * 100
    large_document += "Deep learning concepts. " * 100
    large_document += "Neural networks explained. " * 100
    large_document += "Training algorithms. " * 100
    
    print(f"Original document length: {len(large_document)} characters")
    print(f"Original document tokens: {pretokenizer.cache.count_tokens(large_document)} tokens")
    
    # Split into chunks that fit within a 100-token context
    chunks = pretokenizer.cache.split_to_tokens(large_document, max_tokens=100)
    print(f"Document split into {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
        print(f"Chunk {i+1}: {pretokenizer.cache.count_tokens(chunk)} tokens, {len(chunk)} characters")
    
    if len(chunks) > 3:
        print(f"... and {len(chunks) - 3} more chunks")
    print()


def demonstrate_efficiency_gains():
    """Demonstrate potential efficiency gains from pre-tokenization."""
    print("=== Efficiency Gains Demo ===")
    
    pretokenizer = get_pretokenizer("gpt2")
    
    # Simulate repeated tokenization of the same content (common in LLM apps)
    content = "The quick brown fox jumps over the lazy dog. " * 50  # Repeat phrase
    
    print("Without caching (naive approach):")
    import time
    
    # Simulate tokenizing the same content multiple times without caching
    start_time = time.time()
    for _ in range(10):
        token_count = len(content) // 4  # Simple estimation
    naive_time = time.time() - start_time
    print(f"  10 naive estimations took: {naive_time:.6f} seconds")
    
    print("With caching (pre-tokenization approach):")
    # First call will cache the result
    start_time = time.time()
    for _ in range(10):
        token_count = pretokenizer.cache.count_tokens(content)
    cached_time = time.time() - start_time
    print(f"  10 cached tokenizations took: {cached_time:.6f} seconds")
    
    if naive_time > 0:
        speedup = naive_time / cached_time if cached_time > 0 else float('inf')
        print(f"  Speedup: {speedup:.2f}x when cached")
    
    print(f"  First call tokens: {pretokenizer.cache.count_tokens(content)}")
    print(f"  Cached result tokens: {pretokenizer.cache.count_tokens(content)}")
    print()


def main():
    """Run all demonstrations."""
    print("Pre-tokenization for Efficient LLM Communication\n")
    
    demonstrate_basic_tokenization()
    demonstrate_request_validation()
    demonstrate_context_aware_processing()
    demonstrate_efficiency_gains()
    
    print("Pre-tokenization helps optimize LLM communication by:")
    print("• Validating requests before sending to save API costs and time")
    print("• Efficiently managing context windows to avoid oversized requests")
    print("• Caching tokenization results for repeated operations")
    print("• Providing accurate token counts instead of rough estimates")
    print("• Enabling smart text splitting while preserving semantic meaning")


if __name__ == "__main__":
    main()