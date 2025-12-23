# Architecture Document

## Enhanced Development Standards

The system implements enhanced prompts that encourage:
- Creation of comprehensive unit tests for all new functionality
- Fixing all warnings and errors before delivery
- Updating all relevant documentation with implementation details
- Following Python best practices and PEP 8 guidelines
- Implementing secure coding practices with proper input validation
- Adding proper error handling and logging
- Including type hints for better code maintainability
- Optimizing for performance and memory efficiency
- Ensuring backward compatibility when modifying existing functions
- Adding proper documentation strings for all functions and classes

## System Overview

The LLM Data Pipeline is a comprehensive system for scraping Git repositories and generating Question-Answer pairs for LLM fine-tuning. The system is designed with configurable token limits and enhanced performance.

## Core Components

### 1. Pipeline Core
- **Repository Manager**: Handles Git operations (clone, pull, sync)
- **File Processor**: Discovers, filters, and processes source files with configurable token limits
- **LLM Orchestrator**: Manages LLM interactions with enhanced prompt engineering
- **State Manager**: Tracks processing progress and handles resumption
- **Export Service**: Formats and exports training data

### 2. User Interface
- **TUI (Terminal User Interface)**: Interactive dashboard with real-time monitoring
- **CLI (Command Line Interface)**: Scriptable interface for automation
- **Configuration Editor**: Interactive configuration management

### 3. Data Layer
- **Database Manager**: SQLite-based persistent storage
- **File Manager**: Handles file operations and caching
- **State Manager**: Tracks processing state for resumption

### 4. LLM Integration
- **MLX Client**: Apple Silicon optimized LLM client with configurable token limits
- **LLM Client**: Generic LLM client interface
- **Prompt Manager**: Theme-based prompt management with hot-reload support

## Key Architecture Improvements

### 1. Optimized Token Capability
- **Default**: 4,096 tokens (optimized for performance vs detail balance)
- **Effectively Unlimited**: Virtually unlimited processing capability with 100,000 max token limit
- **Configurable**: Set via `generation.default_max_tokens` in configuration
- **Benefits**: Provides good detail while maintaining reasonable processing speed
- **Smart Large File Processing**: Intelligent chunking for files exceeding context window limits

### 2. Enhanced Prompt Engineering
- **Examples-Driven**: Prompts encourage answers with code examples and implementations
- **Context-Aware**: Questions and answers are contextually relevant to source code
- **Modular**: Theme-based prompts with hot-reload capability

### 3. Performance Optimizations
- **Larger Cache**: Increased from 128 to 256 entries for better performance
- **Efficient Tokenization**: Improved file processing with better tokenization
- **MLX Improvements**: Fixed timeout and parameter compatibility issues
- **Memory Management**: Better VRAM and RAM usage for Apple Silicon

### 4. User Experience Improvements
- **File Size Display**: Shows file sizes in appropriate units (B/KB/MB)
- **Statistics Optimization**: Removed "Current File" from pipeline statistics container
- **Progress Tracking**: Enhanced with detailed timing information
- **UI Responsiveness**: Improved TUI performance and feedback

## Data Flow

### Processing Pipeline
1. **Repository Cloning**: Git repositories are cloned or updated from `repos.txt`
2. **File Discovery**: Source files are discovered and filtered by extension/size
3. **Question Generation**: LLM generates questions based on source code content
4. **Answer Generation**: LLM generates answers to questions with code examples
5. **Storage**: QA pairs are stored in database with file tracking
6. **Export**: Processed data can be exported to various formats (JSONL, CSV, Parquet)

### Configuration Flow
1. **Configuration Loading**: `cicdllm.yaml` is loaded at startup
2. **Validation**: Configuration is validated using Pydantic models
3. **Injection**: Configuration is injected into components via DI container
4. **Runtime Access**: Components access configuration via AppConfig wrapper

## Technology Stack

### Core Technologies
- **Python 3.10+**: Primary programming language
- **MLX**: Apple Silicon optimized LLM framework
- **Textual**: Terminal User Interface framework
- **Pydantic**: Configuration validation and data modeling
- **SQLite**: Embedded database for state management

### Key Libraries
- **huggingface-hub**: Model downloads and management
- **rich**: Rich text and progress display
- **tqdm**: Progress bar implementation
- **tokenizers**: Token counting and processing
- **psutil**: System resource monitoring

## Performance Characteristics

### Scalability
- **Concurrent Processing**: Configurable via `processing.max_concurrent_files`
- **Memory Usage**: Optimized for laptop and desktop environments
- **Battery Awareness**: Automatic pausing when battery is low
- **Resource Management**: Aggressive memory cleanup and VRAM optimization

### Performance Metrics
- **Processing Rate**: Files per minute with detailed progress tracking
- **Token Efficiency**: Optimized for configurable token limits up to 32,768
- **Memory Footprint**: Minimized through lazy loading and caching
- **Response Time**: Fast feedback through improved UI and logging

## Error Handling & Resilience

### Error Recovery
- **Automated Retries**: Exponential backoff with circuit breaker pattern
- **State Persistence**: Progress tracking allows resumption after interruption
- **Graceful Degradation**: Continues operation despite individual file failures
- **Timeout Management**: Proper handling of MLX and network timeouts

### Security & Resource Management
- **Static Analysis**: Semgrep scanning for security vulnerabilities
- **Dependency Scanning**: pip-audit for vulnerability detection in dependencies
- **Input Validation**: Path sanitization and file validation to prevent directory traversal
- **Resource Cleanup**: Automatic cleanup of temporary files and logs to prevent disk exhaustion
- **Encoding Safety**: Multi-encoding detection for safe file processing
- **Memory Management**: Proper resource cleanup with try/finally blocks

### Performance Optimization
- **Pre-tokenization**: Advanced tokenization utilities for efficient LLM communication
- **Context Validation**: Request validation before sending to LLMs to prevent oversized requests
- **Smart Truncation**: Content truncation based on actual tokenization rather than estimates
- **Resilient Connection Handling**: Exception-based error recovery with connection reset capabilities
- **Token Caching**: Caching of tokenization results for repeated operations
- **Chunking Algorithms**: Intelligent text splitting that respects token limits

### Monitoring & Logging
- **Comprehensive Logging**: Detailed logs with timing information
- **Real-time Monitoring**: TUI dashboard with resource usage tracking
- **Progress Tracking**: Hierarchical progress (Total → Repository → File)
- **Failure Analysis**: Detailed error reporting and categorization

## Configuration Architecture

### Configuration Model
- **Pydantic-Based**: Strong typing and validation
- **Layered Access**: AppConfig wraps AppConfigModel for backward compatibility
- **Environment Support**: Environment variable overrides
- **Hot-Reload**: Configuration changes without restart

### Key Configuration Areas
- **LLM Settings**: Model selection, token limits, timeouts
- **Processing Settings**: Concurrency, batch sizes, file filters
- **Performance Settings**: Caching, memory management, resource limits
- **UI Settings**: Display options, refresh rates, monitoring thresholds
