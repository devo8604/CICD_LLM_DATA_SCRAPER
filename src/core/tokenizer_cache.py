"""
Advanced tokenization utilities for efficient LLM communication.
Provides pre-tokenization, caching, and context window management.
"""

import hashlib
from typing import List, Optional, Tuple
from pathlib import Path

try:
    from transformers import AutoTokenizer
    TOKENIZER_AVAILABLE = True
except ImportError:
    TOKENIZER_AVAILABLE = False


class TokenizerCache:
    """
    Caches tokenization results and provides efficient token operations.
    """
    
    def __init__(self, model_name: str = "gpt2"):
        """
        Initialize tokenizer cache.
        
        Args:
            model_name: Name of the model to load tokenizer for
        """
        self.model_name = model_name
        self.tokenizer = None
        self._token_cache = {}
        self._load_tokenizer()
    
    def _load_tokenizer(self):
        """Load the tokenizer for the specified model."""
        if TOKENIZER_AVAILABLE:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            except Exception:
                # Fallback to basic estimation if model not available
                self.tokenizer = None
        else:
            self.tokenizer = None
    
    def count_tokens(self, text: str) -> int:
        """
        Count actual tokens in text using the loaded tokenizer.
        Falls back to estimation if tokenizer is not available.
        
        Args:
            text: Input text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
            
        # Check cache first
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        if self.tokenizer:
            try:
                tokens = self.tokenizer.encode(text)
                token_count = len(tokens)
                self._token_cache[cache_key] = token_count
                return token_count
            except Exception:
                # Fallback to estimation
                pass
        
        # Use estimation as fallback
        token_count = len(text) // 4  # Rough estimation
        self._token_cache[cache_key] = token_count
        return token_count
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Input text to truncate
            max_tokens: Maximum number of tokens allowed
            
        Returns:
            Truncated text
        """
        if not text or max_tokens <= 0:
            return ""
        
        # First try with estimation to avoid tokenizing large texts unnecessarily
        estimated_tokens = len(text) // 4
        if estimated_tokens <= max_tokens:
            return text  # Likely within limit, return as-is
        
        # Use actual tokenization for precise truncation
        if self.tokenizer:
            try:
                tokens = self.tokenizer.encode(text)
                if len(tokens) <= max_tokens:
                    return text  # Already within limit
                
                truncated_tokens = tokens[:max_tokens]
                truncated_text = self.tokenizer.decode(truncated_tokens)
                return truncated_text
            except Exception:
                pass
        
        # Fallback: character-based truncation
        char_limit = max_tokens * 3
        return text[:char_limit]
    
    def split_to_tokens(self, text: str, max_tokens: int, overlap: int = 0) -> List[str]:
        """
        Split text into chunks that respect token limits.
        
        Args:
            text: Input text to split
            max_tokens: Maximum tokens per chunk
            overlap: Number of tokens to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return [""]
        
        if self.count_tokens(text) <= max_tokens:
            return [text]
        
        chunks = []
        if self.tokenizer:
            try:
                tokens = self.tokenizer.encode(text)
                
                start_idx = 0
                while start_idx < len(tokens):
                    end_idx = start_idx + max_tokens
                    chunk_tokens = tokens[start_idx:end_idx]
                    
                    # Add overlap if specified and not at the end
                    if overlap > 0 and end_idx < len(tokens):
                        overlap_end = min(end_idx + overlap, len(tokens))
                        chunk_tokens = tokens[start_idx:overlap_end]
                    
                    chunk_text = self.tokenizer.decode(chunk_tokens)
                    chunks.append(chunk_text)
                    
                    start_idx = end_idx  # Move past the current chunk
                    if overlap > 0:
                        start_idx = end_idx - overlap  # Account for overlap
                
                return chunks
            except Exception:
                pass
        
        # Fallback: character-based splitting
        char_limit = max_tokens * 3
        for i in range(0, len(text), char_limit - (overlap * 3)):
            chunks.append(text[i:i + char_limit])
        
        return chunks

    def prepare_prompt_with_context(self, 
                                  system_message: str, 
                                  user_message: str, 
                                  max_context_tokens: int,
                                  max_output_tokens: int = 100) -> str:
        """
        Prepare a complete prompt with system and user messages, ensuring it fits within context limits.
        
        Args:
            system_message: System message content
            user_message: User message content  
            max_context_tokens: Maximum context tokens for the model
            max_output_tokens: Expected output tokens to reserve space
            
        Returns:
            Prepared prompt string that fits within context limits
        """
        # Reserve tokens for prompt overhead and expected output
        reserved_tokens = 200 + max_output_tokens
        available_tokens = max_context_tokens - reserved_tokens
        
        # Calculate how to split available tokens between system and user messages
        total_needed = self.count_tokens(system_message) + self.count_tokens(user_message)
        
        if total_needed <= available_tokens:
            # Everything fits, return as-is
            return f"System: {system_message}\nUser: {user_message}"
        
        # Need to truncate - prioritize user message over system message
        user_ratio = 0.7  # Use 70% of available tokens for user message
        user_tokens = int(available_tokens * user_ratio)
        system_tokens = available_tokens - user_tokens
        
        truncated_system = self.truncate_to_tokens(system_message, system_tokens)
        truncated_user = self.truncate_to_tokens(user_message, user_tokens)
        
        return f"System: {truncated_system}\nUser: {truncated_user}"


class PreTokenizer:
    """
    High-level pre-tokenization interface that works with or without transformers.
    """
    
    def __init__(self, model_name: str = "gpt2"):
        self.cache = TokenizerCache(model_name)
    
    def validate_request_size(self, 
                            prompt: str, 
                            max_context_tokens: int, 
                            expected_output_tokens: int = 100) -> Tuple[bool, str]:
        """
        Validate if a request will fit within context limits.
        
        Args:
            prompt: The prompt to validate
            max_context_tokens: Maximum context tokens for the model
            expected_output_tokens: Expected output tokens to reserve
            
        Returns:
            Tuple of (is_valid, message)
        """
        prompt_tokens = self.cache.count_tokens(prompt)
        total_required = prompt_tokens + expected_output_tokens
        
        if total_required > max_context_tokens:
            return False, f"Request too large: {total_required} tokens needed, {max_context_tokens} available. Prompt: {prompt_tokens}, Output: {expected_output_tokens}"
        
        return True, f"Request valid: {total_required} tokens needed, {max_context_tokens} available"
    
    def prepare_and_validate(self, 
                           system_message: str,
                           user_message: str,
                           max_context_tokens: int,
                           expected_output_tokens: int = 100) -> Tuple[bool, str, Optional[str]]:
        """
        Prepare and validate a prompt in one step.
        
        Args:
            system_message: System message content
            user_message: User message content
            max_context_tokens: Maximum context tokens for the model
            expected_output_tokens: Expected output tokens to reserve
            
        Returns:
            Tuple of (is_valid, message, prepared_prompt_or_none)
        """
        prompt = self.cache.prepare_prompt_with_context(
            system_message, 
            user_message, 
            max_context_tokens, 
            expected_output_tokens
        )
        
        is_valid, message = self.validate_request_size(prompt, max_context_tokens, expected_output_tokens)
        
        if is_valid:
            return True, message, prompt
        else:
            return False, message, None


# Global instance for easy access
_pretokenizer_instance = None


def get_pretokenizer(model_name: str = "gpt2") -> PreTokenizer:
    """
    Get a global pre-tokenizer instance.
    
    Args:
        model_name: Model name for tokenizer (defaults to gpt2)
        
    Returns:
        PreTokenizer instance
    """
    global _pretokenizer_instance
    if _pretokenizer_instance is None:
        _pretokenizer_instance = PreTokenizer(model_name)
    return _pretokenizer_instance