# Security Best Practices and Scanning

## Security Scanning Tools

This project uses industry-standard security scanning tools to identify vulnerabilities and maintain code quality:

### Static Analysis with Semgrep
Semgrep is used for static analysis to identify security vulnerabilities, coding errors, and maintainability issues in the codebase.

To run Semgrep on this project:
```bash
# Install semgrep (if not already installed)
pip install semgrep

# Run semgrep with default rules
semgrep scan --config=auto .

# Or run with specific security-focused rules
semgrep scan --config=security-audit .
```

### Dependency Vulnerability Scanning with pip-audit
pip-audit is used to scan Python dependencies for known security vulnerabilities.

To run pip-audit on this project:
```bash
# Install pip-audit (if not already installed)
pip install pip-audit

# Run pip-audit on the project
pip-audit --desc on
```

## Security Features Implemented

### 1. Input Validation and Path Sanitization
- File paths are validated to prevent directory traversal attacks
- Only files within allowed directories are processed
- Path validation includes checks against common temp directories for security

### 2. Proper Resource Management
- All database connections use proper cleanup with try/finally blocks
- File handles are properly closed after use
- Memory management improvements to prevent leaks during long-running operations

### 3. Encoding Safety
- Multi-encoding detection for file processing to handle various character encodings safely
- Fallback mechanisms to prevent crashes on files with unusual encodings
- Safe encoding handling with error replacement strategies

### 4. Timeout Protection
- Network requests have configurable timeouts to prevent hanging operations
- File processing operations have timeout protection
- LLM API calls include timeout handling with retry logic

### 5. Concurrency Safety
- Thread-local database connections to prevent race conditions
- Proper isolation between concurrent operations
- Safe handling of shared resources during parallel processing

## Security Configuration

### Dependency Management
The project uses pinned dependencies in pyproject.toml to ensure reproducible builds and reduce supply chain risks:

```toml
[project]
dependencies = [
    # Core dependencies with pinned major versions
    "PyYAML~=6.0",
    "httpx~=0.28.0",
    "rich~=14.0",
    # ... other dependencies
]
```

### Secure File Handling
- Files are read with appropriate encoding detection
- Path traversal is prevented through validation
- Temporary files are cleaned up automatically

## Security Testing

### Automated Security Checks
Security scanning should be integrated into the CI/CD pipeline:

```yaml
# Example GitHub Actions workflow for security scanning
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.14'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install semgrep pip-audit
      - name: Run Semgrep
        run: semgrep scan --config=auto --error
      - name: Run pip-audit
        run: pip-audit --desc on
```

## Security Recommendations

### For Developers
1. Always validate file paths and inputs
2. Use parameterized queries to prevent SQL injection
3. Implement proper timeout handling for all network operations
4. Regularly update dependencies to address known vulnerabilities
5. Run security scans before merging code

### For Operations
1. Run pip-audit regularly to check for dependency vulnerabilities
2. Use Semgrep in CI/CD pipelines to catch security issues early
3. Monitor logs for potential security events
4. Keep the runtime environment updated with security patches

## Reporting Security Issues

If you discover a security vulnerability in this project, please report it responsibly by contacting the maintainers directly. Do not create public issues for security vulnerabilities.

## Security Audit Results

Last updated: December 2025

- Static analysis with Semgrep: ✅ PASS
- Dependency vulnerability scan with pip-audit: ✅ PASS
- Memory leak fixes: ✅ IMPLEMENTED
- Race condition fixes: ✅ IMPLEMENTED
- Encoding safety: ✅ IMPLEMENTED
- Timeout handling: ✅ IMPLEMENTED
- Disk space management: ✅ IMPLEMENTED