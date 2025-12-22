# Installation Guide

This guide provides step-by-step instructions for installing and setting up the LLM Data Pipeline project with configurable token limits, enhanced performance, and best practice enforcement.

## Features

- **Optimized Token Capability**: 4,096 default tokens for optimal performance/detail balance with virtually unlimited processing capability (up to 100,000 tokens)
- **Smart Large File Processing**: Intelligent chunking of large files to maintain context while respecting context windows
- **Enhanced Prompts**: Encourages detailed answers with code examples and implementations
- **Improved UI**: File size display with appropriate units (B/KB/MB) and optimized statistics
- **Performance Optimizations**: Larger cache size (256 entries), smart chunking for large files, and improved processing efficiency
- **MLX Improvements**: Timeout handling and parameter compatibility fixes
- **Security Enhancements**: Path validation to prevent directory traversal and command injection protection

## Prerequisites

- Python 3.10 or higher
- Git
- For Apple Silicon: MLX support enabled (automatic on macOS)
- Sufficient disk space for models and data

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/cicdllm.git
cd cicdllm
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

For basic installation:
```bash
pip install -e .
```

For Apple Silicon (MLX) support:
```bash
pip install -e ".[mlx]"
```

For development:
```bash
pip install -e ".[dev]"
```

For everything:
```bash
pip install -e ".[all]"
```

### 4. Configure the Application

The configuration file is located at `cicdllm.yaml` in the root directory. Key settings include:

- `generation.default_max_tokens`: Set to 4096 by default, configurable up to 32,768
- `llm.mlx_model_name`: Default model for Apple Silicon
- `pipeline.repos_dir_name`: Directory for cloned repositories
- `filtering.excluded_extensions`: Extensions to exclude from processing

### 5. Quick Start

Run the interactive wizard to get started:
```bash
python3 main.py quickstart
```

Or launch the TUI directly:
```bash
python3 main.py tui
```

## Configuration Options

### Token Limits
- Default: 4096 tokens (balanced for performance and detail)
- Maximum: 100,000 tokens (effectively unlimited)
- Adjustable in `cicdllm.yaml` under `generation.default_max_tokens`
- **Note**: Higher values generate more detailed answers but take longer to process

### Performance Settings
- Cache size: 256 entries (optimized from 128)
- Concurrent file processing: Configurable via `processing.max_concurrent_files`
- File batch size: Configurable via `processing.file_batch_size`

## Performance & Security Tools

The project includes performance optimization and security scanning tools for development:

### Installing Performance & Security Tools
```bash
# Install development dependencies including performance and security tools
pip install -e ".[dev]"
```

### Pre-tokenization Features
The project now includes advanced pre-tokenization capabilities:

```bash
# Example of using pre-tokenization for efficient LLM communication
python -c "from src.core.tokenizer_cache import get_pretokenizer; pretokenizer = get_pretokenizer(); print('Pre-tokenizer ready for efficient LLM communication')"
```

### Running Security Scans
```bash
# Static analysis with Semgrep
semgrep scan --config=auto .

# Dependency vulnerability scanning
pip-audit --desc on
```

## Troubleshooting

### Common Issues

1. **MLX Not Available on Non-Apple Platforms**: MLX dependencies are automatically filtered for macOS only
2. **Token Limit Errors**: Increase the `default_max_tokens` value in configuration if you need longer responses
3. **Memory Issues**: Reduce `processing.max_concurrent_files` in the configuration
4. **Model Loading Failures**: Ensure sufficient RAM and check model compatibility
5. **Security Scan Failures**: Run `pip-audit` and `semgrep` to identify and fix security issues

### Getting Help

- Check the README.md for detailed usage instructions
- Review the configuration file for all available options
- Use the TUI configuration editor (press 'G' in TUI) for interactive configuration
- See CONTRIBUTING.md for development and security best practices
- See SECURITY.md for security policies and procedures