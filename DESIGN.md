# LLM-Optimized System Design: Local LLM Data Pipeline (Git-to-Dataset)

## Enhanced LLM Prompts and Best Practices

### Development Standards
When generating code, documentation, and system components, the LLM is instructed to:
- All unit tests should be written first, then the application logic
- Always create comprehensive unit tests for all new functionality
- Fix all warnings and errors before delivery
- Update all relevant documentation with implementation details
- Follow Python best practices and PEP 8 guidelines
- Implement secure coding practices with proper input validation
- Add proper error handling and logging
- Include type hints for better code maintainability
- Optimize for performance and memory efficiency
- Ensure backward compatibility when modifying existing functions
- Add proper documentation strings for all functions and classes

## Core Purpose
**Objective:** Automated creation of fine-tuning datasets from Git repositories using local LLMs.
**Input:** Git repository URLs, source code files.
**Output:** Question-Answer (QA) pairs in JSONL format for model training.
**Constraint:** Must run entirely offline with local processing optimized for Apple Silicon.

## Architecture Overview

### System Components
```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Git Sources   │───▶│  Pipeline Core   │───▶│   LLM Backend    │
└─────────────────┘    └──────────────────┘    └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   Storage Layer  │
                       └──────────────────┘
```

### Core Modules
- **Repository Manager:** Handles Git operations (clone, pull, sync)
- **File Processor:** Discovers, filters, and processes source files
- **LLM Orchestrator:** Manages LLM interactions and generation with configurable token limits
- **State Manager:** Tracks processing progress and handles resumption
- **Export Service:** Formats and exports training data

## Data Model

### FileHashes Table
| Column | Type | Purpose |
|--------|------|---------|
| file_path | TEXT (PK) | File identifier |
| file_hash | TEXT | SHA256 content hash |
| last_processed | TIMESTAMP | When file was processed |

### TrainingSamples Table
| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER (PK, AutoInc) | Unique sample ID |
| file_path | TEXT (FK) | Source file reference |
| question | TEXT | Generated question |
| answer | TEXT | Generated answer |
| model_used | TEXT | Model name used |

### FailedFiles Table
| Column | Type | Purpose |
|--------|------|---------|
| file_path | TEXT (PK) | Failed file path |
| error_message | TEXT | Error details |
| retry_count | INTEGER | Number of retries |

### AppState Table
| Column | Type | Purpose |
|--------|------|---------|
| key | TEXT (PK) | State variable name |
| value | TEXT | State value |

## Configuration Schema

### YAML Structure
```yaml
llm:
  backend: "mlx" | "llama_cpp" | "ollama"
  model_name: "string"
  max_retries: 3
  context_window: 4096
  request_timeout: 300
  default_max_tokens: 4096  # Optimized for performance/detail balance, up to 100000 tokens

pipeline:
  repos_dir: "path/to/repos"
  allowed_extensions: [".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c"]
  ignore_patterns: ["*.test.*", "*.spec.*", "node_modules/", "target/", "build/"]
  max_concurrent_files: 4

resources:
  max_ram_gb: 8
  battery_pause_threshold: 20
  enable_battery_monitoring: true
```

## Processing Workflow

### Scrape Command
```
Input: repos.txt (list of Git URLs)
Output: Cloned repositories in repos_dir
```
1. Read repository URLs from `repos.txt`
2. For each repository:
   - If not exists → Clone with `git clone`
   - If exists → Update with `git pull`
3. Parallelize Git operations for efficiency

### Prepare Command (Main Pipeline)
```
Input: Discovered source files
Output: Generated QA pairs in database
```

#### Processing Steps
1. **Initialization**
   - Load configuration from YAML
   - Initialize database connection
   - Lazy-load LLM client only when needed

2. **File Discovery**
   - Walk `repos_dir` recursively
   - Apply extension and ignore pattern filters
   - Calculate SHA256 for each file

3. **Processing Loop**
   - Check `FileHashes` table for existing hash
   - Skip if already processed (idempotent behavior)
   - Load file content and truncate if needed
   - Generate questions using LLM
   - Generate answers for each question
   - Persist QA pairs to database

4. **Resource Management**
   - Monitor system resources (RAM, battery)
   - Unload model when not in use to free VRAM
   - Handle cancellation signals gracefully

### Export Command
```
Input: TrainingSamples from database
Output: Formatted training data (JSONL)
```
1. Query all training samples from database
2. Format according to specified template (Alpaca, ChatML, etc.)
3. Stream write to output file

## LLM Integration

### Two-Step Generation Process
1. **Question Generation**
   - Input: Source code content
   - Output: Multiple technical questions
   - Prompt: "Analyze this code and generate 5 specific technical questions"

2. **Answer Generation**
   - Input: Source code + each question
   - Output: Detailed answer
   - Prompt: "Answer the question using ONLY the provided context"

### Backend Support
- **MLX:** Apple Silicon optimization
- **Llama.cpp:** Cross-platform compatibility
- **Ollama:** Easy model management

### Connection Handling
- Exception-based error recovery for network and timeout issues
- Automatic connection reset on connection failures
- Specific handling for different error types (timeouts, network errors, HTTP errors)
- Graceful retry with exponential backoff
- No artificial timeouts to allow natural processing times

### Configuration Management
- Pydantic-based configuration model with validation
- Access to configuration via `config.model` property
- Support for backward-compatible property accessors in `AppConfig` (e.g., `config.DB_PATH`)
- Configuration is provided to services via dependency injection or direct passing

## TUI Interface

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│                        Header                               │
├─────────────────┬───────────────────────────────────────────┤
│ System Status   │ Pipeline Statistics                       │
│ (RAM, CPU, GPU) │ (Repos, Files, Q&A, etc.)                │
├─────────────────┼───────────────────────────────────────────┤
│ Detailed        │ Progress Bars                             │
│ Progress        │ (Total, Current Repo)                     │
│ (File, ETA)     │                                           │
├─────────────────────────────────────────────────────────────┤
│                         Logs                                │
└─────────────────────────────────────────────────────────────┘
```

### Real-time Updates
- Poll database for progress updates
- Calculate processing rates and ETA
- Display system resource usage

## Key Optimizations

### Performance
- Lazy model loading to minimize startup time
- Batch processing for efficiency
- Parallel file processing with concurrency limits
- Smart caching with increased size (256 entries) to avoid redundant work
- Optimized token capability with 4,096 default and up to 100,000 max tokens for optimal performance/detail ratio
- Smart large file processing with intelligent chunking for files exceeding context window limits
- Improved tokenization and file processing efficiency
- Resilient connection handling with exception-based error recovery and automatic connection reset

### Resource Management
- Aggressive memory cleanup between files
- Battery monitoring with automatic pausing
- VRAM optimization for Apple Silicon
- Graceful handling of system resource constraints

### Reliability
- Idempotent processing (safe to restart)
- Comprehensive error handling with retries
- MLX timeout handling and parameter compatibility fixes
- Database-based state tracking
- Cancellation support with clean shutdown

## Error Handling Strategy

### Retry Mechanism
- Exponential backoff for LLM failures
- Maximum retry count per file
- Move to next file if retries exhausted

### Failure Recovery
- Mark failed files in database
- Continue processing other files
- Allow reprocessing failed files separately

## Security Considerations

### Local Processing
- No external API calls or data transmission
- All processing happens on local machine
- Model weights stored locally

### File Access
- Respect gitignore patterns
- Skip sensitive file types by default
- Validate file extensions before processing

## Deployment Requirements

### System Requirements
- **Apple Silicon:** Recommended for MLX backend
- **RAM:** Minimum 8GB (16GB+ recommended for larger models)
- **Storage:** Sufficient space for repositories and model weights
- **OS:** macOS, Linux, or Windows with appropriate backend support

### Model Requirements
- Compatible with MLX, Llama.cpp, or Ollama
- Appropriate context window for source code processing
- Sufficient performance for reasonable processing times

## Key Implementation Notes

### LLM Client Management
- Singleton pattern to avoid repeated model loading
- Proper cleanup to free VRAM/RAM
- Backend-agnostic interface for flexibility

### File Processing
- Token counting to respect context limits
- Content truncation for large files
- Extension-based filtering for relevant files

### State Management
- Database-based progress tracking
- Safe cancellation and resumption
- Concurrent access handling
