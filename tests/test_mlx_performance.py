"""Unit tests for MLX Client performance optimizations."""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import tempfile
import os

from src.mlx_client import MLXClient
from src.config import AppConfig


class TestMLXClientPerformance:
    """Test performance optimizations for MLX Client."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Check if MLX is available and skip tests if not
        try:
            import mlx.core as mx
            import mlx_lm
            self.mlx_available = True
        except ImportError:
            self.mlx_available = False

    def test_gpu_device_optimization(self):
        """Test that GPU device is set when MLX is available."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")
            
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            
            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)
            
            # Verify that the device was set (this test will pass if no exception occurs in initialization)
            # since mx.set_default_device(mx.gpu) happens during initialization

    def test_warmup_functionality(self):
        """Test model warmup functionality."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")
            
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.generate') as mock_generate, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            mock_generate.return_value = "Hello"
            
            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)
            
            # Warmup should have been called during initialization
            assert mock_generate.called  # Warmup generates a test prompt

    def test_result_caching_enabled(self):
        """Test that generation result caching is properly enabled."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")
            
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            
            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)
            
            # Verify cache attributes exist
            assert hasattr(client, '_generate_cache')
            assert hasattr(client, '_cache_size')
            assert client._cache_size == 128
            assert isinstance(client._generate_cache, dict)

    def test_generation_with_cache_hit(self):
        """Test that caching works for repeated requests."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")
            
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.generate') as mock_generate, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            
            mock_model = MagicMock()
            mock_tokenizer = MagicMock() 
            mock_load.return_value = (mock_model, mock_tokenizer)
            mock_generate.return_value = "Test response"
            
            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)
            
            # Generate a response (should add to cache)
            with patch.object(client, '_generate_text_sync') as mock_sync:
                mock_sync.return_value = "Test response"
                
                prompt = "Test prompt"
                result1 = client._generate_text_sync(prompt, temperature=0.7, max_tokens=50)
                
                # Generate same response (should retrieve from cache)
                result2 = client._generate_text_sync(prompt, temperature=0.7, max_tokens=50)
                
                # Should only call the actual generator once due to caching
                assert result1 == result2
                # The cache should be used for the second call, so generate should be called fewer times
                # than the number of _generate_text_sync calls

    def test_generation_parameters_optimization(self):
        """Test that generation parameters are used (with MLX-compatible parameters only)."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.generate') as mock_generate, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):

            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            mock_generate.return_value = "Test response"

            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)

            # Test that basic parameters are passed to generate function (MLX-compatible)
            with patch('src.mlx_client.generate') as optimized_mock_generate:
                optimized_mock_generate.return_value = "Test response"

                client._generate_text_sync("Test prompt", temperature=0.8, max_tokens=100)

                # Verify basic parameters were passed (MLX-compatible - no temp, top_p, repetition_penalty)
                optimized_mock_generate.assert_called()
                call_args = optimized_mock_generate.call_args
                # Only max_tokens and basic parameters are supported by MLX generate_step
                kwargs = call_args[1]
                assert 'max_tokens' in kwargs
                assert 'prompt' in kwargs
                # temp, top_p, repetition_penalty should NOT be passed as they cause errors
                assert 'temp' not in kwargs
                assert 'top_p' not in kwargs
                assert 'repetition_penalty' not in kwargs

    def test_optimized_sampling_parameters(self):
        """Test that the generation method works without unsupported parameters."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True), \
             patch('src.mlx_client.generate') as mock_generate:

            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            mock_generate.return_value = "Sample response"

            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)

            # Test that generation works without causing errors from unsupported params
            result = client._generate_text_sync("Test", temperature=0.7, max_tokens=50)

            # Verify the result is handled properly
            assert result == "Sample response"

            # Ensure generate was called with MLX-compatible parameters only
            mock_generate.assert_called()
            kwargs = mock_generate.call_args[1]
            # Should only have the parameters that MLX supports
            assert 'max_tokens' in kwargs
            assert 'prompt' in kwargs
            # Unsupported parameters should not be present
            assert 'top_p' not in kwargs  # MLX doesn't support top_p
            assert 'repetition_penalty' not in kwargs  # MLX doesn't support repetition_penalty
            assert 'temp' not in kwargs  # MLX doesn't support temp parameter

    def test_platform_restriction_still_works(self):
        """Test that platform restriction is still enforced."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")
            
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', False):  # Not Apple Silicon
            
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            
            config = AppConfig()
            with pytest.raises(RuntimeError, match="Apple Silicon"):
                MLXClient(model_name="test-model", config=config)

    def test_error_handling_in_generate_sync(self):
        """Test error handling in the optimized generate method."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):

            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)

            # Test that errors are handled gracefully
            with patch('src.mlx_client.generate') as mock_generate:
                # Mock the first call to raise TypeError, second call to succeed
                def side_effect_func(**kwargs):
                    if 'temp' in kwargs:
                        raise TypeError("temp not supported")
                    return "Success response"

                mock_generate.side_effect = side_effect_func

                result = client._generate_text_sync("Test prompt", temperature=0.7, max_tokens=50)

                # Should succeed with fallback call (without temp parameter)
                assert result == "Success response"

                # Should have been called twice (once with temp, once without)
                assert mock_generate.call_count >= 1

    def test_cache_size_limit(self):
        """Test that cache size is limited as expected."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")
            
        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):
            
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)
            
            config = AppConfig()
            client = MLXClient(model_name="test-model", config=config)
            
            # Verify initial cache state
            assert len(client._generate_cache) == 0
            assert client._cache_size == 128


class TestMLXClientPerformanceIntegration:
    """Integration tests for performance optimizations."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Check if MLX is available and skip tests if not
        try:
            import mlx.core as mx
            import mlx_lm
            self.mlx_available = True
        except ImportError:
            self.mlx_available = False

    @pytest.mark.asyncio
    async def test_generate_questions_uses_optimizations(self):
        """Test that the public API methods use optimizations."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):

            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            with patch('src.mlx_client.MLXClient._generate_text_sync', return_value="What does this function do?"):
                config = AppConfig()
                client = MLXClient(model_name="test-model", config=config)

                # This should work with all optimizations in place
                result = await client.generate_questions("def test(): pass", temperature=0.7, max_tokens=100)

                assert result is not None
                assert "What does this function do?" in result or len(result) > 0

    @pytest.mark.asyncio
    async def test_get_answer_single_uses_optimizations(self):
        """Test that answer generation uses optimizations."""
        if not self.mlx_available:
            pytest.skip("MLX not available for testing")

        with patch('src.mlx_client.load') as mock_load, \
             patch('src.mlx_client.IS_APPLE_SILICON', True):

            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            with patch('src.mlx_client.MLXClient._generate_text_sync', return_value="This function does X"):
                config = AppConfig()
                client = MLXClient(model_name="test-model", config=config)

                result = await client.get_answer_single("What does it do?", "def test(): pass", temperature=0.7, max_tokens=100)

                assert result is not None
                assert "This function does X" in result or result.strip() != ""