# LLM Data Pipeline

A comprehensive pipeline for scraping Git repositories, processing code files, and generating Question-Answer (Q&A) pairs for Fine-tuning Large Language Models (LLMs). Features a Terminal User Interface (TUI), native Apple Silicon (MLX) support, configurable token limits, and robust error handling.

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Quickstart](#-quickstart)
- [Usage](#-usage)
  - [Terminal UI (TUI)](#terminal-ui-tui)
  - [Command Line Interface (CLI)](#command-line-interface-cli)
- [Configuration](#%EF%%8F-configuration)
- [MLX Support (Apple Silicon)](#-mlx-support-apple-silicon)
- [Development](#-development)
- [License](#-license)

## ✨ Features

- **Repository Scraping**: efficient cloning and updating of Git repositories from a list.
- **Intelligent Processing**:
  - Filters files by extension and size.
  - Generates Q&A pairs using local LLMs with examples and detailed explanations.
  - Supports **llama.cpp** servers and native **MLX** models.
  - **Optimized token capability** with 4,096 default tokens for optimal performance/detail balance and virtually unlimited processing capability.
  - **Smart large file processing** with intelligent chunking to handle files larger than context window.
- **Interactive TUI**:
  - Real-time dashboard with battery, disk, and memory monitoring.
  - Progress tracking for scraping and processing with file size information.
  - Interactive configuration editor.
  - **Fuzzy-searchable Command Palette** (`C` key).
- **Customizable Prompts**:
  - Theme-based prompts (e.g., `devops`, `scientific`) that encourage examples.
  - Hot-reload support without restarting.
- **Robustness**:
  - Automated retry mechanisms with exponential backoff.
  - Circuit breakers for API stability.
  - State management to resume interrupted jobs.
  - MLX timeout handling and parameter compatibility fixes.
- **Exporting**:
  - Export datasets to JSONL (Alpaca/ChatML formats), CSV, or Parquet.
- **Performance**:
  - Multiprocessing support.
  - Apple Silicon GPU acceleration via MLX.
  - Optimized caching with increased cache size (256 entries).
  - Improved tokenization and file processing efficiency.

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/cicdllm.git
    cd cicdllm
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the package** (recommended - using pyproject.toml):
    ```bash
    # Basic installation (core dependencies only)
    pip install -e .

    # With MLX support for Apple Silicon (M1/M2/M3/M4)
    pip install -e ".[mlx]"

    # With development tools (pytest, ruff, etc.)
    pip install -e ".[dev]"

    # Everything (all optional dependencies)
    pip install -e ".[all]"
    ```

    **Alternative** (legacy - using requirements.txt):
    ```bash
    pip install -r requirements.txt           # Core dependencies
    pip install -r requirements-dev.txt       # Development tools
    ```

    > **Note**: MLX dependencies are automatically filtered to macOS only. On other platforms, they will be skipped.

## 🚀 Quickstart

The easiest way to get started is using the interactive wizard:

```bash
python3 main.py quickstart
```

This wizard will guide you through:
1.  Setting up your `repos.txt` list.
2.  Choosing your LLM backend (llama.cpp or MLX).
3.  Testing connectivity.

## 💻 Usage

### Terminal UI (TUI)

Launch the interactive dashboard:

```bash
python3 main.py tui
```

**Key Bindings:**
- `S`: **Scrape** repositories.
- `P`: **Prepare** data (process files).
- `G`: **Config** menu (edit settings).
- `R`: **Refresh** stats.
- `Q` / `Esc`: **Quit**.

### Command Line Interface (CLI)

You can also run individual steps via the CLI.

**1. Scrape Repositories**
Clone or update repositories listed in `repos.txt`:
```bash
python3 main.py scrape
```

**2. Prepare Data (Generate Q&A)**
Process files and generate dataset entries:
```bash
python3 main.py prepare
```

**3. Export Data**
Export the processed data to a file:
```bash
# Export to Alpaca JSONL format
python3 main.py export --template alpaca-jsonl --output-file data.jsonl

# Export to CSV
python3 main.py export --template csv --output-file data.csv
```

**4. View Status**
See pipeline statistics:
```bash
python3 main.py status
# Or real-time view
python3 main.py status-realtime
```

**5. Retry Failed Files**
Retry processing for files that failed previously:
```bash
python3 main.py retry
```

## 🛠️ Configuration

The pipeline is configured via `cicdllm.yaml`. You can edit this file directly or use the TUI (`python3 main.py tui` -> `G`).

**Key Settings:**
```yaml
llm:
  # Backend selection: 'mlx' (Apple Silicon) or 'llama_cpp' (Standard)
  backend: mlx

  # For llama_cpp backend:
  base_url: http://localhost:11434
  model_name: ollama/llama3.2:3b

  # For MLX backend:
  mlx_model_name: mlx-community/Qwen2.5-Coder-14B-Instruct-4bit
  mlx_quantize: true

pipeline:
  data_dir: data
  repos_dir_name: repos
```

Manage config via CLI:
```bash
# Show current config
python3 main.py config show

# Set a value
python3 main.py config set llm.max_retries 5
```

## 🖥️ TUI Dashboard

Launch the interactive dashboard to monitor your pipeline:

```bash
python3 main.py tui
```

**New Features:**
- **Backend Visualization:** clearly displays active model and backend (MLX/Llama.cpp).
- **Deferred Loading:** MLX models only load when processing starts, saving memory.
- **Simplified Stats:** clean, two-column layout for pipeline statistics.
- **Real-time Monitoring:** tracks battery, disk, memory, and processing rates.

**Key Bindings:**
- `S`: **Scrape** repositories.
- `P`: **Prepare** data (process files).
- `G`: **Config** menu (edit settings).
- `R`: **Refresh** stats.
- `Q` / `Esc`: **Quit**.

## 🍎 MLX Support (Apple Silicon)

This project has first-class support for Apple Silicon via the MLX framework.

**Manage Models:**
```bash
# Download a model
python3 main.py mlx download mlx-community/Qwen2.5-Coder-7B-Instruct-4bit

# List local models
python3 main.py mlx list
```

**Configuration:**
Set `llm.backend` to `mlx` in your config to enable native GPU acceleration.

## 💻 Development

**Running Tests:**
```bash
pytest
```

**Linting & Formatting:**
```bash
ruff check .
ruff format .
```

**Security Scanning:**
```bash
# Static analysis with Semgrep
semgrep scan --config=auto .

# Dependency vulnerability scanning
pip-audit --desc on
```

**Project Structure:**
- `src/core/`: Core functionality (configuration, error handling, logging, protocols, utilities)
- `src/data/`: Data management (database, file operations, state management)
- `src/llm/`: LLM-related code (clients, prompt management, MLX integration)
- `src/pipeline/`: Pipeline orchestration (services, CLI, exporters, preflight checks)
- `src/ui/`: User interface components (TUI, widgets, progress tracking)
- `src/utils/`: Utility functions (memory management, patches, resets, status utilities)
- `tests/`: Unit tests.
- `data/`: Database and state files.
- `repos/`: Cloned repositories.

**Security Best Practices:**
- Input validation and path sanitization
- Proper resource management with cleanup
- Multi-encoding detection for file processing
- Timeout protection for network operations
- Concurrency safety with thread-local connections
- Regular dependency updates and vulnerability scanning

**Performance Optimizations:**
- Pre-tokenization for efficient LLM communication
- Context window validation before API calls
- Smart content truncation based on actual tokenization
- Resilient connection handling with exception-based error recovery
- Caching of tokenization results for repeated operations
- Batch processing with optimal chunk sizes
- Pydantic-based configuration with strict validation

For more detailed security information, see [SECURITY.md](SECURITY.md).

## 📄 License

[MIT License](LICENSE)
