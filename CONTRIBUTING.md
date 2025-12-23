# Contributing to LLM Data Pipeline

Thank you for your interest in contributing to the LLM Data Pipeline project! This document outlines the guidelines for contributing to this repository.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Security Scanning](#security-scanning)
- [Testing](#testing)
- [Style Guidelines](#style-guidelines)
- [Pull Request Process](#pull-request-process)
- [Security Policy](#security-policy)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to keep our community approachable and respectable.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
   ```bash
   git clone https://github.com/yourusername/cicdllm.git
   cd cicdllm
   ```
3. Create a virtual environment and install dependencies
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[all]"  # Install with all optional dependencies
   ```

## Development Workflow

1. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b bugfix/issue-description
   ```

2. Make your changes, ensuring you follow the style guidelines

3. Add tests for your changes (if applicable)

4. Run all tests to ensure everything works:
   ```bash
   pytest
   ```

5. Run security scans:
   ```bash
   semgrep scan --config=auto .
   pip-audit --desc on
   ```

6. Run linting and formatting:
   ```bash
   ruff check .
   ruff format .
   ```

## Security Scanning

This project uses security scanning tools to maintain code quality and security:

### Static Analysis with Semgrep
Run static analysis to identify potential security issues:
```bash
semgrep scan --config=auto .
```

### Dependency Vulnerability Scanning
Check for known vulnerabilities in dependencies:
```bash
pip-audit --desc on
```

All pull requests should pass both security scans before being merged.

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_specific_file.py
```

### Adding Tests
- Add tests for new functionality
- Update existing tests if you change behavior
- Ensure tests are clear and well-documented
- Aim for high test coverage, especially for critical functionality

## Style Guidelines

### Python Code
- Follow PEP 8 style guidelines
- Use Ruff for linting and formatting
- Use type hints for all function parameters and return values
- Write docstrings for all public functions, classes, and modules
- Use descriptive variable and function names

### Commit Messages
- Use conventional commit format: `type(scope): description`
- Use imperative mood: "Add feature" not "Added feature"
- Keep the first line under 72 characters
- Use the body to explain the what and why (if needed)

Examples:
- `feat(cli): add config validation command`
- `fix(database): resolve connection leak in status utils`
- `refactor(utils): improve file encoding detection`

### Documentation
- Update README.md if you change functionality
- Add docstrings to all public APIs
- Keep documentation up-to-date with code changes

## Pull Request Process

1. Ensure your branch is up-to-date with the main branch:
   ```bash
   git checkout main
   git pull origin main
   git checkout your-branch
   git rebase main
   ```

2. Run all checks locally:
   ```bash
   pytest
   ruff check .
   ruff format .
   semgrep scan --config=auto .
   pip-audit --desc on
   ```

3. Create your pull request with a clear title and description
4. Link to any relevant issues
5. Wait for review and address feedback
6. Your PR will be merged once approved

## Security Policy

### Reporting Security Issues
If you discover a security vulnerability, please report it responsibly by contacting the maintainers directly. Do not create public issues for security vulnerabilities.

### Security Best Practices Implemented
This project follows several security best practices:

- **Input Validation**: All file paths and inputs are validated to prevent directory traversal and injection attacks
- **Resource Management**: Proper cleanup of database connections and file handles
- **Encoding Safety**: Multi-encoding detection for safe file processing
- **Timeout Protection**: Network requests and operations have configurable timeouts
- **Concurrency Safety**: Thread-local database connections to prevent race conditions

For more details about security features, see [SECURITY.md](SECURITY.md).

### Dependency Management
- Dependencies are pinned to major versions in pyproject.toml
- Regular security scanning with pip-audit
- Updates are made regularly to address known vulnerabilities

## Questions?

If you have questions about contributing, feel free to open an issue or contact the maintainers.

Thank you for contributing to the LLM Data Pipeline project!
