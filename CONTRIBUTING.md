# Contributing to LLM Data Pipeline

Thank you for your interest in contributing! This document provides guidelines and information for developers working on the LLM Data Pipeline.

## Table of Contents

- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Code Style](#code-style)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Adding New Features](#adding-new-features)

## Development Setup

### Prerequisites

- Python 3.14+
- Git
- Virtual environment tool (venv or virtualenv)

### Setup Instructions

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/your-username/cicdllm.git
   cd cicdllm
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   # Production dependencies
   pip install -r requirements.txt

   # Development dependencies
   pip install -r requirements-dev.txt
   ```

4. **Verify installation**:
   ```bash
   # Run tests
   source venv/bin/activate && pytest tests/

   # Check code style
   source venv/bin/activate && black --check main.py src/
   ```

## Architecture Overview

The project follows a **service-oriented architecture** with clear separation of concerns.

### Core Components

```
┌─────────────────┐
│    main.py      │  Entry point
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PipelineFactory │  Creates components with dependency injection
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DataPipeline   │  Orchestrates the workflow
└────────┬────────┘
         │
         ├──────────┬──────────┬──────────────┐
         ▼          ▼          ▼              ▼
    ┌────────┐ ┌────────┐ ┌─────────┐ ┌─────────────┐
    │  LLM   │ │   DB   │ │  File   │ │  Services   │
    │ Client │ │Manager │ │ Manager │ │   Layer     │
    └────────┘ └────────┘ └─────────┘ └─────────────┘
```

### Service Layer

The application uses specialized services for better modularity:

1. **FileProcessingService** (`src/services/file_processing_service.py`)
   - Handles individual file processing
   - Generates Q&A pairs from file content
   - Manages file hashing and duplicate detection

2. **RepositoryService** (`src/services/repository_service.py`)
   - Manages Git repository operations
   - Clones and updates repositories
   - Handles repository discovery

3. **StateManagementService** (`src/services/state_management_service.py`)
   - Manages pipeline state persistence
   - Enables resume functionality
   - Tracks processing progress

4. **BatchProcessingService** (`src/services/batch_processing_service.py`)
   - Manages concurrent file processing
   - Handles batch operations
   - Coordinates parallel workflows

### Data Management

- **DBManager** (`src/db_manager.py`): Facade for database operations
  - Delegates to `StateManager` for state management
  - Delegates to `TrainingDataRepository` for training data operations

- **StateManager** (`src/state_manager.py`): Pipeline state persistence

- **TrainingDataRepository** (`src/training_data_repository.py`): Training data CRUD operations

### LLM Clients

- **LLMClient** (`src/llm_client.py`): OpenAI-compatible API client (llama.cpp, etc.)
- **MLXClient** (`src/mlx_client.py`): Apple Silicon MLX client

### Lazy Initialization

The pipeline uses **lazy initialization** for the LLM client:

- Commands like `scrape` and `export` don't need an LLM, so the client is only initialized when first accessed
- This reduces startup time and prevents unnecessary connections

```python
# In DataPipeline
@property
def llm_client(self) -> LLMClient:
    """Lazy initialization of LLM client."""
    if self._llm_client is None:
        factory = PipelineFactory(self.config)
        self._llm_client = factory.create_llm_client()
    return self._llm_client
```

## Code Style

This project uses **Black** for code formatting.

### Formatting Code

```bash
# Format all code
source venv/bin/activate && black main.py src/

# Check formatting without changes
source venv/bin/activate && black --check main.py src/
```

### Code Style Guidelines

- **Line Length**: 88 characters (Black default)
- **Imports**: Organized with standard library first, then third-party, then local
- **Type Hints**: Use type hints for function signatures
- **Docstrings**: Use for all public functions and classes

Example:

```python
def process_file(
    file_path: str,
    temperature: float = 0.7,
    max_tokens: int = 500
) -> tuple[bool, int]:
    """
    Process a single file and generate Q&A pairs.

    Args:
        file_path: Path to the file to process
        temperature: Sampling temperature for generation
        max_tokens: Maximum tokens for responses

    Returns:
        Tuple of (success, qa_count)
    """
    # Implementation
    pass
```

## Testing

The project uses **pytest** for testing with comprehensive test coverage.

### Running Tests

```bash
# Run all tests
source venv/bin/activate && pytest tests/

# Run with coverage
source venv/bin/activate && pytest tests/ --cov=src --cov-report=html

# Run specific test file
source venv/bin/activate && pytest tests/test_config.py

# Run specific test
source venv/bin/activate && pytest tests/test_config.py::TestAppConfig::test_default_llm_settings
```

### Test Structure

Tests are organized by module:

```
tests/
├── conftest.py                      # Test configuration and fixtures
├── test_config.py                   # Config tests (28 tests)
├── test_llm_client.py              # LLM client tests (22 tests)
├── test_db_manager.py              # Database tests (22 tests)
├── test_file_manager.py            # File manager tests (15 tests)
├── test_cli.py                     # CLI tests (29 tests)
├── test_pipeline_factory.py        # Factory tests
├── test_data_pipeline.py           # Pipeline tests
├── test_mlx_client.py              # MLX client tests
└── test_*_service.py               # Service tests
```

### Writing Tests

Follow these guidelines when writing tests:

1. **Use descriptive test names**:
   ```python
   def test_get_file_hash_returns_none_when_file_not_found(self):
       """Test that get_file_hash returns None for nonexistent files."""
   ```

2. **Arrange-Act-Assert pattern**:
   ```python
   def test_add_qa_sample(self):
       # Arrange
       db_manager = DBManager(db_path)

       # Act
       sample_id = db_manager.add_qa_sample("test.py", "Q?", "A")

       # Assert
       assert sample_id > 0
   ```

3. **Use fixtures for setup**:
   ```python
   @pytest.fixture
   def temp_db():
       with tempfile.TemporaryDirectory() as tmpdir:
           db_path = Path(tmpdir) / "test.db"
           yield db_path
   ```

4. **Test both success and failure cases**

5. **Mock external dependencies**:
   ```python
   @patch('src.llm_client.httpx.AsyncClient')
   def test_api_call_with_mock(self, mock_client):
       # Test implementation
   ```

## Project Structure

```
cicdllm/
├── src/                             # Source code
│   ├── services/                    # Service layer
│   │   ├── __init__.py
│   │   ├── file_processing_service.py
│   │   ├── repository_service.py
│   │   ├── state_management_service.py
│   │   └── batch_processing_service.py
│   ├── cli.py                       # CLI argument parsing
│   ├── config.py                    # Configuration settings
│   ├── data_pipeline.py             # Main pipeline orchestrator
│   ├── db_manager.py                # Database facade
│   ├── exporters.py                 # Data export functionality
│   ├── file_manager.py              # File discovery and filtering
│   ├── llm_client.py                # LLM API client
│   ├── mlx_client.py                # MLX client (Apple Silicon)
│   ├── mlx_manager.py               # MLX model management
│   ├── log_manager.py               # Log file management
│   ├── logging_config.py            # Logging configuration
│   ├── pipeline_factory.py          # Component factory
│   ├── protocols.py                 # Protocol definitions
│   ├── state_manager.py             # State persistence
│   ├── training_data_repository.py  # Training data operations
│   └── utils.py                     # Utility functions
├── tests/                           # Unit tests
│   ├── conftest.py                  # pytest configuration
│   └── test_*.py                    # Test files
├── main.py                          # Application entry point
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── README.md                        # User documentation
└── CONTRIBUTING.md                  # This file
```

### Key Files

- **main.py**: Entry point, CLI argument handling, command dispatch
- **src/config.py**: All configuration settings (LLM, performance, paths, etc.)
- **src/pipeline_factory.py**: Creates components with dependency injection
- **src/data_pipeline.py**: Main orchestrator, coordinates all services

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-new-export-format`
- `fix/database-connection-leak`
- `docs/update-setup-instructions`
- `refactor/simplify-state-management`

### Commit Messages

Follow conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(export): add support for parquet format

Implement parquet export format for more efficient data storage.
Includes compression options and schema validation.

Closes #123

fix(llm-client): handle timeout errors correctly

Previously, timeout errors would crash the pipeline. Now they're
properly caught and logged, allowing the pipeline to continue with
other files.

Fixes #456
```

## Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write code following the style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Format and test**:
   ```bash
   # Format code
   source venv/bin/activate && black main.py src/ tests/

   # Run tests
   source venv/bin/activate && pytest tests/
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat(scope): descriptive message"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a pull request**:
   - Provide a clear description of the changes
   - Reference any related issues
   - Ensure all tests pass
   - Request review from maintainers

### PR Checklist

- [ ] Code follows project style guidelines (formatted with Black)
- [ ] Tests added/updated for new functionality
- [ ] All tests pass locally
- [ ] Documentation updated (README.md, docstrings, etc.)
- [ ] Commit messages follow conventional format
- [ ] No breaking changes (or clearly documented)

## Adding New Features

### Adding a New LLM Client

1. **Create a new client class** implementing `LLMInterface`:

   ```python
   # src/my_llm_client.py
   from src.protocols import LLMInterface

   class MyLLMClient(LLMInterface):
       async def generate_questions(self, text: str, temperature: float, max_tokens: int):
           # Implementation
           pass

       async def get_answer_single(self, question: str, context: str, temperature: float, max_tokens: int):
           # Implementation
           pass
   ```

2. **Update PipelineFactory** to support the new client:

   ```python
   # src/pipeline_factory.py
   def create_llm_client(self):
       if self.config.USE_MY_LLM:
           return MyLLMClient(...)
       elif self.config.USE_MLX:
           return MLXClient(...)
       else:
           return LLMClient(...)
   ```

3. **Add configuration** in `src/config.py`:

   ```python
   USE_MY_LLM: bool = False
   MY_LLM_API_KEY: str = ""
   ```

4. **Write tests** in `tests/test_my_llm_client.py`

### Adding a New Export Format

1. **Add format to DataExporter** in `src/exporters.py`:

   ```python
   def _export_my_format(self, output_file: str):
       """Export data in my custom format."""
       # Implementation
       pass
   ```

2. **Update the format mapping**:

   ```python
   format_methods = {
       "csv": self._export_csv,
       "my-format": self._export_my_format,
       # ...
   }
   ```

3. **Add CLI option** in `src/cli.py`:

   ```python
   export_parser.add_argument(
       "--template",
       choices=["csv", "llama3", "my-format", ...],
       # ...
   )
   ```

4. **Update documentation** in README.md

5. **Write tests** in `tests/test_exporters.py`

### Adding a New Service

1. **Create service file** in `src/services/`:

   ```python
   # src/services/my_service.py
   class MyService:
       def __init__(self, dependency1, dependency2, config):
           self.dependency1 = dependency1
           self.dependency2 = dependency2
           self.config = config

       def do_something(self):
           # Implementation
           pass
   ```

2. **Integrate with DataPipeline**:

   ```python
   # src/data_pipeline.py
   def __init__(self, ...):
       # ...
       self.my_service = MyService(dep1, dep2, self.config)
   ```

3. **Write comprehensive tests**

## Development Tips

### Debugging

1. **Enable debug logging**:
   ```python
   # In main.py or relevant service
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Use the interactive debugger**:
   ```python
   import pdb; pdb.set_trace()
   ```

3. **Check logs**:
   ```bash
   tail -f logs/pipeline_log_*.txt
   ```

### Database Inspection

```bash
# Open database
sqlite3 data/pipeline.db

# Useful queries
.schema
SELECT COUNT(*) FROM TrainingSamples;
SELECT COUNT(*) FROM ConversationTurns;
SELECT * FROM FailedFiles;
```

### Testing with Different Backends

```python
# Test with mock LLM
@patch('src.pipeline_factory.LLMClient')
def test_with_mock_llm(mock_client):
    mock_client.return_value = MagicMock()
    # Test implementation
```

## Architecture Decisions

### Why Service-Oriented Architecture?

- **Modularity**: Each service has a single responsibility
- **Testability**: Services can be tested in isolation
- **Flexibility**: Easy to swap implementations
- **Maintainability**: Changes are localized to specific services

### Why Lazy Initialization?

- **Performance**: Don't initialize expensive resources (LLM client) unless needed
- **Resource Management**: Commands like `scrape` don't need an LLM connection
- **Startup Time**: Faster startup for operations that don't require all components

### Why SQLite?

- **Portability**: Single file database, easy to backup and move
- **No Setup**: No database server required
- **Performance**: Sufficient for the workload
- **Reliability**: ACID-compliant, battle-tested

## Questions?

- Check existing issues on GitHub
- Review the codebase for examples
- Ask in pull request discussions
- Open a discussion issue for architectural questions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
