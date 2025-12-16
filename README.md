# LLM Data Pipeline

An automated pipeline for generating high-quality question-and-answer training data from Git repositories. This tool processes source code files and uses Large Language Models to create Q&A pairs suitable for fine-tuning code-focused LLMs.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Basic Usage](#basic-usage)
- [Configuration](#configuration)
  - [Option 1: llama.cpp (Recommended)](#option-1-llamacpp-recommended-for-most-users)
  - [Option 2: MLX (Apple Silicon)](#option-2-mlx-apple-silicon-only)
  - [MLX Model Management](#mlx-model-management)
- [Commands](#commands)
  - [scrape - Clone/Update Repositories](#scrape---cloneupdate-repositories)
  - [prepare - Generate Q&A Pairs](#prepare---generate-qa-pairs)
  - [retry - Retry Failed Files](#retry---retry-failed-files)
  - [export - Export Training Data](#export---export-training-data)
- [Directory Structure](#directory-structure)
- [Database Schema](#database-schema)
  - [TrainingSamples](#trainingsamples)
  - [ConversationTurns](#conversationturns)
  - [FileHashes](#filehashes)
  - [FailedFiles](#failedfiles)
- [Troubleshooting](#troubleshooting)
  - [MLX Issues (Apple Silicon)](#mlx-issues-apple-silicon)
  - [llama.cpp Issues](#llamacpp-issues)
  - [General Issues](#general-issues)
- [Performance Tips](#performance-tips)
- [File Exclusions](#file-exclusions)
- [Examples](#examples)
  - [Process a Specific Repository](#process-a-specific-repository)
  - [Resume After Interruption](#resume-after-interruption)
  - [Retry Failed Files](#retry-failed-files-1)
- [License](#license)
- [Contributing](#contributing)
- [Support](#support)

## Features

- 🔄 **Automated Repository Management**: Clone and update Git repositories from a simple text file
- 🤖 **Intelligent Q&A Generation**: Uses LLMs to generate contextual questions and answers from code
- 💾 **Smart Caching**: Tracks file hashes to avoid reprocessing unchanged files
- 🔁 **Resume Support**: Automatically resumes from where it left off if interrupted
- 🍎 **MLX Support**: Native Apple Silicon acceleration (M1/M2/M3 Macs)
- 🦙 **llama.cpp Compatible**: Works with any OpenAI-compatible API endpoint
- 📊 **Multiple Export Formats**: CSV, Alpaca, ChatML, Llama3, Mistral, Gemma formats
- 🔋 **Battery Management**: Automatically pauses on low battery (macOS)
- 🗃️ **SQLite Storage**: All data stored in a portable SQLite database

## Quick Start

### Prerequisites

- Python 3.14 or higher
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cicdllm
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Basic Usage

1. **Create a `repos.txt` file** with Git repository URLs (one per line):
   ```
   https://github.com/user/repo1
   https://github.com/user/repo2
   ```

2. **Configure your LLM backend** (see [Configuration](#configuration))

3. **Clone repositories**:
   ```bash
   python3 main.py scrape
   ```

4. **Generate Q&A pairs**:
   ```bash
   python3 main.py prepare
   ```

5. **Export training data**:
   ```bash
   python3 main.py export --template alpaca-jsonl --output-file training_data.jsonl
   ```

## Configuration

The pipeline supports two LLM backends:

### Option 1: llama.cpp (Recommended for most users)

Edit `src/config.py`:

```python
# LLM Client Settings
USE_MLX = False  # Use llama.cpp
LLM_BASE_URL = "http://localhost:11454"  # Your llama.cpp server
LLM_MODEL_NAME = "your-model-name"
```

Start your llama.cpp server:
```bash
# Example with llama-server
llama-server -m path/to/model.gguf --port 11454
```

### Option 2: MLX (Apple Silicon only)

For M1/M2/M3 Macs with native acceleration:

```bash
# Install MLX dependencies
pip install mlx mlx-lm
```

Edit `src/config.py`:
```python
USE_MLX = True  # Enable MLX
MLX_MODEL_NAME = "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
```

#### MLX Model Management

```bash
# List locally cached models
python3 main.py mlx list

# Download a model
python3 main.py mlx download mlx-community/Qwen2.5-Coder-14B-Instruct-4bit

# Get model information
python3 main.py mlx info mlx-community/Qwen2.5-Coder-14B-Instruct-4bit

# Remove a model
python3 main.py mlx remove mlx-community/Qwen2.5-Coder-14B-Instruct-4bit
```

## Commands

### `scrape` - Clone/Update Repositories

```bash
python3 main.py scrape [OPTIONS]
```

Clones or updates all repositories listed in `repos.txt`.

**Options:**
- `--data-dir`: Directory for data storage (default: `data`)
- `--max-log-files`: Maximum log files to keep (default: 5)

### `prepare` - Generate Q&A Pairs

```bash
python3 main.py prepare [OPTIONS]
```

Processes files and generates question-answer pairs.

**Options:**
- `--max-tokens`: Maximum tokens for LLM responses (default: 500)
- `--temperature`: Sampling temperature 0.0-2.0 (default: 0.7)
- `--max-file-size`: Maximum file size in bytes (default: 5MB)
- `--data-dir`: Directory for data storage
- `--max-log-files`: Maximum log files to keep

**Features:**
- ✅ Skips unchanged files (uses SHA256 hashing)
- ✅ Automatically resumes from interruption
- ✅ Tracks failed files for retry
- ✅ Excludes binary files, images, and large files
- ✅ Progress bars for repositories and files

### `retry` - Retry Failed Files

```bash
python3 main.py retry [OPTIONS]
```

Attempts to reprocess files that failed during `prepare`.

### `export` - Export Training Data

```bash
python3 main.py export --template <FORMAT> --output-file <PATH>
```

**Required Arguments:**
- `--template`: Output format (see below)
- `--output-file`: Path to output file

**Supported Formats:**
- `csv` - Comma-separated values
- `alpaca-jsonl` - Alpaca instruction format (JSONL)
- `chatml-jsonl` - ChatML format (JSONL)
- `llama3` - Llama 3 chat template
- `mistral` - Mistral instruction format
- `gemma` - Gemma chat template

**Example:**
```bash
python3 main.py export --template alpaca-jsonl --output-file output.jsonl
```

## Directory Structure

```
cicdllm/
├── data/
│   └── pipeline.db          # SQLite database with Q&A pairs
├── logs/                    # Log files (rotated)
├── repos/                   # Cloned repositories
│   └── <org>/
│       └── <repo>/
├── src/                     # Source code
│   ├── services/           # Service layer
│   ├── config.py           # Configuration
│   ├── data_pipeline.py    # Main pipeline
│   ├── db_manager.py       # Database operations
│   ├── llm_client.py       # LLM API client
│   ├── mlx_client.py       # MLX client (Apple Silicon)
│   └── ...
├── tests/                   # Unit tests
├── main.py                  # Entry point
├── repos.txt               # Repository URLs
└── requirements.txt        # Python dependencies
```

## Database Schema

The pipeline uses SQLite to store all generated data:

### TrainingSamples

Stores Q&A sample metadata.

| Column                 | Type        | Description                    |
| ---------------------- | ----------- | ------------------------------ |
| `sample_id`            | `INTEGER`   | Primary key                    |
| `dataset_source`       | `VARCHAR`   | Source file path               |
| `creation_date`        | `TIMESTAMP` | When created                   |
| `model_type_intended`  | `VARCHAR`   | Intended model type            |
| `sample_quality_score` | `REAL`      | Quality score                  |
| `is_multiturn`         | `BOOLEAN`   | Multi-turn conversation flag   |

### ConversationTurns

Stores individual Q&A turns.

| Column          | Type      | Description                     |
| --------------- | --------- | ------------------------------- |
| `turn_id`       | `INTEGER` | Primary key                     |
| `sample_id`     | `INTEGER` | Foreign key to TrainingSamples  |
| `turn_index`    | `INTEGER` | Turn order                      |
| `role`          | `VARCHAR` | 'user' or 'assistant'           |
| `content`       | `TEXT`    | Question or answer text         |
| `is_label`      | `BOOLEAN` | Label flag                      |
| `metadata_json` | `TEXT`    | Additional metadata (JSON)      |

### FileHashes

Tracks processed files to avoid reprocessing.

| Column           | Type       | Description                 |
| ---------------- | ---------- | --------------------------- |
| `file_path`      | `TEXT`     | Primary key, file path      |
| `content_hash`   | `TEXT`     | SHA256 hash                 |
| `last_processed` | `DATETIME` | Last processing time        |
| `sample_id`      | `INTEGER`  | Foreign key to TrainingSamples |

### FailedFiles

Stores failed file information for retry.

| Column      | Type        | Description         |
| ----------- | ----------- | ------------------- |
| `failed_id` | `INTEGER`   | Primary key         |
| `file_path` | `TEXT`      | Failed file path    |
| `reason`    | `TEXT`      | Failure reason      |
| `failed_at` | `TIMESTAMP` | Failure timestamp   |

## Troubleshooting

### MLX Issues (Apple Silicon)

**Memory Errors:**
```
[METAL] Command buffer execution failed: Insufficient Memory
```

**Solutions:**
- Use smaller models (e.g., 7B instead of 30B parameters)
- Close other memory-intensive applications
- Recommended models by RAM:
  - 8GB: 1B-3B parameter models
  - 16GB: 3B-7B parameter models
  - 24GB+: 7B-14B parameter models
  - 32GB+: 14B+ parameter models

**Model Loading Failures:**
- Verify internet connectivity
- Check model name is correct
- Try a different model from MLX Community

### llama.cpp Issues

**Connection Refused:**
```bash
# Verify server is running
curl http://localhost:11454/v1/models

# Check port matches config
# src/config.py: LLM_BASE_URL = "http://localhost:11454"
```

**Model Not Found:**
- Ensure model is loaded in llama.cpp
- Check `LLM_MODEL_NAME` matches exactly
- List available models: `curl http://localhost:11454/v1/models`

### General Issues

**Empty Q&A Pairs:**
- Check LLM is responding correctly
- Increase `--max-tokens` if answers are truncated
- Adjust `--temperature` for better variety

**Processing Stuck:**
- Check logs in `logs/` directory
- Verify LLM server is responding
- Use `Ctrl+C` to interrupt (state is saved automatically)

**Database Locked:**
- Ensure only one pipeline instance is running
- Close any SQLite browser connections

## Performance Tips

1. **File Size Limits**: Adjust `MAX_FILE_SIZE` in config for your needs
2. **Concurrent Processing**: Set `MAX_CONCURRENT_FILES` > 1 for parallel processing
3. **Batch Size**: Adjust `FILE_BATCH_SIZE` for optimal throughput
4. **LLM Timeouts**: Increase `LLM_REQUEST_TIMEOUT` for slower models
5. **Battery Management**: On macOS, pipeline pauses when battery < 15%

## File Exclusions

The following file types are automatically excluded:

- Images: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`
- Archives: `.zip`, `.tar`, `.gz`
- Binary: `.bin`, `.pack`, `.idx`, `.rev`
- Documents: `.pdf`, `.pptx`
- System: `.DS_Store`

Configure in `src/config.py`:
```python
EXCLUDED_FILE_EXTENSIONS = (
    ".png", ".jpg", # ... add more
)
```

## Examples

### Process a Specific Repository

```bash
# Create repos.txt with one repository
echo "https://github.com/user/awesome-project" > repos.txt

# Scrape and process
python3 main.py scrape
python3 main.py prepare --max-tokens 1000 --temperature 0.8

# Export to Alpaca format
python3 main.py export --template alpaca-jsonl --output-file alpaca_data.jsonl
```

### Resume After Interruption

The pipeline automatically saves state. Simply run the command again:

```bash
# If interrupted during prepare
python3 main.py prepare  # Resumes from last position
```

### Retry Failed Files

```bash
# After prepare completes
python3 main.py retry  # Reprocesses all failed files
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## Support

For issues and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review logs in the `logs/` directory
- Open an issue on GitHub
