# TODO List for LLM Data Pipeline

This file tracks upcoming features, improvements, and maintenance tasks for the LLM Data Pipeline project.

## 🎯 Priority Action Items (From Codebase Analysis)

Based on comprehensive codebase analysis (Dec 2025), these items should be addressed in priority order:

### Week 1 (Critical)
1. **🚨 Fix Database Filename Bug** - ✅ COMPLETED (see Known Issues & Bugs)
2. **📦 Add pyproject.toml** - ✅ COMPLETED (see Packaging & Distribution)
3. **🔄 Consolidate Config Systems** - ✅ COMPLETED (see Configuration Management)

### Week 2-3 (High Priority)
4. **🪵 Replace print() with logging** - 130 print statements need migration (see Code Quality Issues)
5. **🔐 Pin Dependency Versions** - ✅ COMPLETED (see Packaging & Distribution)
6. **📝 Fix Pydantic Deprecations** - ✅ COMPLETED (see Code Quality Issues)

### Month 1 (Important)
7. **🧪 Improve Test Coverage** - Focus on pipeline_tui (39%), file_manager (46%), mlx_client (54%) (see Testing & Reliability)
8. **📚 Add CONTRIBUTING.md** - Help onboard contributors (see Documentation & Tooling)
9. **🔍 Add Pre-commit Hooks & CI** - Automate code quality (see Testing & Reliability)
10. **📊 Add Dependency Scanning** - Monitor security vulnerabilities (see Packaging & Distribution)
11. **⚙️ Configure Token Limits** - Make token limits configurable and increase default to 32768 with virtually unlimited capability (see Performance & Optimization)
12. **💬 Enhance Prompts with Examples** - Update prompts to encourage detailed answers with code examples (see Performance & Optimization)
13. **📊 Remove Current File from Stats** - Remove "Current File" display from pipeline statistics container (see User Experience & Interface)
14. **📏 Add File Size Display** - Show file sizes in appropriate units (B/KB/MB) in UI (see User Experience & Interface)

### Summary Stats
- **Overall Health**: Strong (76% test coverage, 513 passing tests)
- **Architecture**: Excellent (recent modular refactoring)
- **Critical Issues**: 3 (database bug, config duplication, global config)
- **Code Quality Issues**: 6 (print/logging, Pydantic, large classes, etc.)
- **Technical Debt**: Medium (dependency management, mixed patterns)

## 🚀 User Experience & Interface

- [x] **Interactive Startup Menu**: Add menu on startup of TUI where user selects what they want to do (scrape, prepare, export, etc.)
- [ ] **TUI-First Interface Migration**: Deprecate CLI as primary interface and make TUI the default with all CLI commands accessible through TUI
  - **Stage 1**: Enhance TUI with all CLI command equivalents through interactive panels and modal dialogs
  - **Stage 2**: Implement keyboard shortcuts and command palette for power users familiar with CLI
  - **Stage 3**: Add TUI status indicators for all command states (running, completed, failed)
  - **Stage 4**: Create command history and bookmarking features within TUI
  - **Stage 5**: Add export/import functionality for TUI configurations and settings
  - **Stage 6**: Migrate all help documentation from CLI to TUI tooltips and contextual help
  - **Stage 7**: Maintain backward compatibility by keeping CLI commands accessible via TUI
  - **Stage 8**: Gradual deprecation messaging in CLI pointing users to TUI functionality
  - **Stage 9**: Final transition where TUI becomes primary entry point and CLI becomes secondary
- [x] **Responsive TUI Layout**: Automatically adapt layout for different terminal sizes (narrow, medium, wide) - *Implemented via Python on_resize handling*
- [x] **Repository Progress Tracking**: Visual progress reporting for repository cloning/updating operations
- [x] **Real-time Dashboard Enhancements**: Add more detailed analytics and visualization in TUI - *Added Sparklines, Processing Rate (files/min), Elapsed Time, and ETA*
- [x] **Interactive Command Palette**: Add searchable command palette for quick access to all functionality - *Implemented fuzzy-searchable overlay with key actions*
- [x] **Customizable Prompts**: Put system and user prompt in separate user editable files - *Externalized thematic prompts to prompts/ directory with hot-reload support*

## ⚡ Performance & Optimization
...
## 🐛 Known Issues & Bugs

### 🚨 Critical (Fix Immediately)

- [x] **Database Filename Bug** [FIXED]: Database files being created with object representation names - caused by passing DBManager instance instead of db_path. Fixed with validation in DBManager.__init__ and corrected main.py. Added regression test.
- [x] **Global Config Instance**: Module-level config instantiation in `llm_client.py` violates DI pattern - should always inject via DIContainer [COMPLETED: LLMClient now requires config through DI and cannot create its own instance]
- [x] **Circular Import Risk**: `main.py` manipulates `sys.path` to add `src/` - should use proper packaging instead [COMPLETED: Improved path manipulation with duplicate check and better documentation]
- [x] **Memory Leaks**: Investigate and fix memory leaks occurring during long-running processing sessions [COMPLETED: Fixed database connection leaks and improved resource management]
- [x] **Race Conditions**: Resolve race conditions in concurrent file processing that occasionally corrupt database entries [COMPLETED: Ensured thread-safe database operations with proper locking and isolation]
- [x] **Timeout Handling**: Improve timeout handling in network requests and LLM calls to prevent hanging [COMPLETED: Enhanced timeout mechanisms with better error handling and recovery]
- [x] **Disk Space Management**: Implement automatic cleanup of temporary files to prevent disk exhaustion [COMPLETED: Added DiskCleanupManager with scheduled cleanup functionality]
- [x] **Encoding Issues**: Fix character encoding problems when processing files with non-standard encodings [COMPLETED: Added multi-encoding detection and fallback mechanisms]

### ⚠️ High Priority

- [x] **Progress Bar Issue**: Progress bars do not show actual progress, remaining stuck at 0% throughout processing
- [ ] **Memory Leaks**: Investigate and fix memory leaks occurring during long-running processing sessions
- [ ] **Race Conditions**: Resolve race conditions in concurrent file processing that occasionally corrupt database entries
- [ ] **Timeout Handling**: Improve timeout handling in network requests and LLM calls to prevent hanging
- [ ] **Disk Space Management**: Implement automatic cleanup of temporary files to prevent disk exhaustion
- [ ] **Encoding Issues**: Fix character encoding problems when processing files with non-standard encodings
- [x] Termination Dialog Bug: Termination dialog does not show up in the TUI when ESC is pressed.
- [x] Missing Log Window Bug: There isnt a log window at the bottom of the TUI.

### 📝 Code Quality Issues

- [x] **DataExporter Creates Duplicate DB Connection**: `DataExporter` creates its own `DBManager` instance instead of accepting one, causing two database connections to the same file. Refactor to accept DBManager instance. [COMPLETED: Fixed to require config injection and updated all dependencies]
- [ ] **Mixed Print/Logging**: 130 print() statements vs 105 logging calls - standardize on logging throughout codebase
- [ ] **Adopt Structured Logging**: Consider using structlog or similar for better log analysis and debugging
- [x] **Pydantic Deprecation**: ✅ COMPLETED - Migrated from Pydantic V1 to V2 (@validator → @field_validator, .dict() → .model_dump())
- [ ] **Large Classes**: Refactor oversized classes (`PipelineTUIApp`: 625 lines, `MLXClient`: 291 lines) into smaller components
- [ ] **Magic Strings/Numbers**: Extract hardcoded values (file paths, config values like `0.8` for RAM) to constants
- [ ] **Inconsistent Error Handling**: Standardize on exception-based errors vs None returns - document strategy
- [ ] **Mixed Async Patterns**: Inconsistent use of asyncio vs threading - choose one pattern and standardize
- [ ] **Add Type Hints**: Some files have excellent type hints, others are sparse - aim for 100% type hint coverage
- [ ] **Remove Empty Pass Statements**: 50 instances found - replace with docstrings where appropriate

## 🧪 Testing & Reliability

### Current Status: 76% Coverage, 513 Tests Passing ✅

- [x] **Error Recovery**: Implemented automated retry mechanisms with exponential backoff and circuit breaker patterns (3 attempts with progressive delays)

### Immediate Improvements Needed

- [ ] **Fix Resource Leaks in Tests**: Unclosed database connections detected in test output - ensure all connections properly closed
- [ ] **Improve Low Coverage Modules**:
  - `pipeline_tui.py` (39% coverage) - add more UI interaction tests
  - `file_manager.py` (46% coverage) - test edge cases and error paths
  - `mlx_client.py` (54% coverage) - create better mocks for MLX operations
- [ ] **Add Integration Test Suite**: Create separate integration tests that test full pipeline end-to-end (currently only unit tests)
- [ ] **Add Pre-commit Hooks**: Enforce code quality with ruff, type checking, and test requirements before commits
- [ ] **Add CI/CD Pipeline**: Automate testing, linting, and code quality checks on every push

### Advanced Testing

- [ ] **Property-Based Testing**: Implement Hypothesis-based testing for edge case validation
- [ ] **Fuzz Testing**: Add automated fuzz testing for input validation and security vulnerabilities
- [ ] **Chaos Engineering**: Implement fault injection testing to ensure resilience under failure conditions
- [ ] **Golden Master Testing**: Create reference test suites for regression detection
- [ ] **Mutation Testing**: Implement mutation testing to measure test effectiveness
- [ ] **Mock MLX Operations**: Create comprehensive mocks for MLX to test without Apple Silicon hardware

## 🌐 Internationalization & Accessibility

- [ ] **Multi-language Support**: Enable processing of repositories in non-English languages with translation capabilities
- [ ] **Unicode Normalization**: Implement robust Unicode handling for international character sets
- [ ] **Screen Reader Support**: Add semantic markup and ARIA labels for accessibility compliance
- [ ] **Localization Framework**: Support translated UI elements and localized date/time formats

## 📊 Advanced Analytics & Monitoring

- [ ] **Real-time Metrics**: Implement Prometheus/Grafana integration for live performance dashboards
- [ ] **Anomaly Detection**: Add ML-based detection for unusual patterns in processed data or processing times
- [ ] **Predictive Scaling**: Implement ML models to predict resource requirements based on repository characteristics
- [ ] **Cost Optimization Engine**: Add AWS/GCP cost tracking and optimization recommendations
- [ ] **Drift Detection**: Monitor for model performance drift over time and trigger retraining

## 📈 Machine Learning Enhancements

- [ ] **Active Learning**: Implement uncertainty sampling for prioritizing data that would most improve model performance
- [ ] **Few-shot Generation**: Add meta-learning capabilities to adapt quickly to new domains with limited data
- [ ] **Synthetic Data Augmentation**: Generate synthetic Q&A pairs to improve training diversity
- [ ] **Model Feedback Loop**: Implement online learning to continuously refine the Q&A generation model
- [ ] **Multimodal Embeddings**: Create unified embedding spaces combining code, comments, and documentation

## 🌐 Cross-Platform Compatibility

- [ ] **Cross-Platform Validation**: Ensure consistent functionality across macOS, Linux, and Windows platforms
- [ ] **Windows-Specific Features**: Implement Windows power management, file path handling, and system monitoring
- [ ] **Linux-Specific Features**: Optimize for Linux filesystems, process management, and system resources
- [ ] **macOS-Specific Features**: Maintain existing Apple Silicon and battery management optimizations
- [ ] **Platform Abstraction Layer**: Create abstraction layer for platform-specific operations (file access, system calls, etc.)
- [ ] **Cross-Platform Testing Matrix**: Establish testing matrix covering all supported platforms and hardware configurations

## ☁️ Cloud & Deployment

- [ ] **Kubernetes Operator**: Create Kubernetes operator for automated deployment and management
- [ ] **Serverless Architecture**: Implement AWS Lambda/Google Cloud Functions for event-driven processing
- [ ] **CI/CD Pipelines**: Complete automated testing, building, and deployment pipelines
- [ ] **Infrastructure as Code**: Implement Terraform/Pulumi for cloud resource management
- [ ] **Blue-Green Deployments**: Implement zero-downtime deployment strategies

## 📦 Packaging & Distribution

### Critical Dependency Management

- [x] **Add pyproject.toml**: ✅ COMPLETED - Migrated to modern `pyproject.toml` with PEP 621 metadata
- [x] **Pin Dependency Versions**: ✅ COMPLETED - All dependencies use `~=` for major version pinning
- [x] **Create requirements-dev.txt**: ✅ COMPLETED - Separate development dependencies file created
- [x] **Document Platform Requirements**: ✅ COMPLETED - MLX marked as macOS-only with `sys_platform == 'darwin'`
- [x] **Package Metadata**: ✅ COMPLETED - Added proper package metadata, classifiers, and project URLs
- [ ] **Add Dependency Scanning**: Configure Dependabot or similar for automated security vulnerability monitoring
- [ ] **Add Security Scanning**: Implement automated vulnerability scanning for dependencies

### Distribution & Deployment

- [ ] **Package Application for Distribution**: Create distributable packages (PyInstaller, Docker, etc.) for easy installation
- [ ] **Cross-Platform Builds**: Generate executable builds for Windows, macOS, and Linux
- [ ] **Docker Containerization**: Create optimized Docker images for containerized deployment
- [ ] **PyInstaller Executables**: Package as standalone executables for each platform
- [ ] **Package Managers**: Support installation via Homebrew, apt, and other platform package managers
- [ ] **Distribution Pipelines**: Automate build and distribution through CI/CD pipelines

## 🎨 Theming & Customization

- [ ] **Theming Support**: Add theme switching capability with multiple color schemes (light, dark, custom)
- [ ] **TUI Theme Selection**: Enable users to choose from predefined themes in the Text User Interface
- [ ] **Custom Theme Creation**: Allow users to define custom color schemes and visual styles
- [ ] **Theme Persistence**: Save and restore user-selected themes between sessions
- [ ] **Dynamic Theme Switching**: Enable real-time theme switching without restarting the application

## 🛠️ Configuration Management

- [x] **Auto RAM Calculation**: MLX configuration now automatically calculates 80% of system RAM if `mlx_max_ram_gb` is not specified
- [x] **Default Model Update**: Updated default MLX model to `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` for better performance
- [x] **Visible Configuration File**: Changed hidden .cicdllm.yaml to cicdllm.yaml for easier access and editing
- [x] **Comprehensive Configuration Example**: Created detailed config.example.yaml with all options documented and explained
- [x] **Restore main.py**: Restored main.py which was accidentally deleted during cleanup
- [x] **Restore requirements.txt**: Restored requirements.txt with all necessary dependencies
- [x] **TUI Config Menu**: Fully functional configuration management interface within the Text User Interface with keyboard navigation
- [ ] **Live Config Reloading**: Enable live reloading of configuration without restarting the application
- [x] **Interactive Config Editor**: Form-based configuration editor accessible from TUI with input dialogs for all value types
- [ ] **Config Presets**: Support configuration presets for different use cases or environments
- [x] **Config Validation**: Real-time validation for configuration values in the TUI with type checking
- [x] **Configurable Token Limits**: Updated `default_max_tokens` to 4096 with virtually unlimited capability, balancing performance and detail while allowing for extensive examples

### Configuration Architecture Improvements

- [x] **Consolidate Dual Config Systems**: ✅ COMPLETED - AppConfig now wraps AppConfigModel internally, using Pydantic for all validation while maintaining backward-compatible uppercase property access
- [x] **Pydantic V2 Migration**: ✅ COMPLETED - Migrated @validator to @field_validator and .dict() to .model_dump()
- [ ] **Generate Schema Documentation**: Auto-generate configuration documentation from Pydantic models for user reference
- [ ] **Add Config Validation on Startup**: Fail fast with clear error messages for invalid configuration values (partially done via Pydantic)
- [ ] **Create Config Diff Command**: Show what changed between current config and defaults
- [ ] **Add Config Migration Tool**: Automated migration for config format changes between versions

## Configuration Menu Implementation Status

The TUI Configuration Menu is now **FULLY FUNCTIONAL** and accessible by pressing 'G' in the main TUI.

### Features Implemented:
- ✅ Full-screen keyboard navigable interface with UP/DOWN arrow navigation
- ✅ Display of all configuration settings with current values (25+ settings)
- ✅ Visual highlighting of currently selected setting (cyan background)
- ✅ ENTER to edit values with type-aware input dialogs (text, integer, float, boolean)
- ✅ Asterisk indicators for unsaved changes
- ✅ S key to save changes to cicdllm.yaml
- ✅ R key to reset all values to defaults
- ✅ Q/ESC to close and cancel unsaved changes
- ✅ Sections organized by functionality (LLM, MLX, Pipeline, Logging, Battery, Processing, Performance)
- ✅ Optimized navigation for improved responsiveness
- ✅ Nord-themed color scheme with proper contrast
- ✅ Input validation with error messages for invalid values
- ✅ Automatic type conversion (text, integer, float, boolean)

### Performance Optimizations:
- ✅ Removed expensive scroll operations to reduce navigation overhead
- ✅ Optimized highlighting to only update changed rows (2 operations vs 25+)
- ✅ Fixed CSS heights to prevent layout recalculation
- ✅ Class-based styling instead of inline styles for better performance

### All Issues Resolved:
- ✅ Widget rendering and display fixed
- ✅ Color scheme corrected (no more white-on-white)
- ✅ Navigation lag significantly reduced
- ✅ All configuration values properly accessible and editable
- ✅ Changes properly persist to configuration file
- ✅ Modal input dialog for easy value editing

## 🦙 Local LLM Integration

- [ ] **Integrated llama.cpp Support**: Add built-in llama.cpp server management with auto-download and startup
- [ ] **Local Model Management**: Enable downloading, managing, and switching between local models directly from the interface
- [ ] **Automatic Server Management**: Start/stop llama.cpp server automatically when needed
- [ ] **Model Download Assistant**: Guide users through model download process with size and RAM recommendations
- [ ] **Performance Tuning**: Optimize local inference settings based on system specifications

## 📚 Documentation & Tooling

### Critical Documentation Needs

- [ ] **Add CONTRIBUTING.md**: Include development setup, testing guidelines, code style, and PR submission process
- [ ] **Setup Sphinx or MkDocs**: Auto-generate API documentation from docstrings with examples
- [ ] **Create Troubleshooting Guide**: Document common errors, solutions, and debugging steps
- [ ] **Add Architecture Diagrams**: Visual representation of module interactions and data flow
- [ ] **Document MLX Setup**: Specific guide for Apple Silicon users with hardware requirements
- [ ] **Add Docstring Coverage Tracking**: Measure and enforce docstring coverage for public APIs

### Completed & Ongoing

- [x] **Update All Documentation**: All documentation updated with new features, commands, and functionality (README.md, TODO.md, CONTRIBUTING.md)
- [ ] **Documentation Generation**: Auto-generate API documentation and configuration guides from codebase
- [ ] **Migration Tooling**: Create migration scripts for upgrading older database schemas and deprecated configuration formats
- [ ] **Architecture Decision Records**: Document all major architectural decisions and their rationales
- [ ] **User Journey Maps**: Create detailed user journey documentation for each persona
- [ ] **API Reference**: Generate comprehensive API reference documentation with examples
- [ ] **Performance Benchmarks**: Document performance benchmarks across different hardware configurations

## 🎨 Multi-modal Support

- [ ] **Multi-modal Support**: Add support for processing image and video files with multimodal LLMs
- [ ] **Advanced Repository Filters**: Allow users to specify include/exclude patterns for specific file types, directories, or language subsets

## 📊 Analytics & Reporting

- [ ] **Performance Analytics Dashboard**: Add detailed metrics on processing speed, resource utilization, and cost estimates

## 🏗️ Refactoring Projects

- [ ] **Performance & Optimization**

## 🎯 Completed Items

- [x] Basic repository cloning and file processing pipeline
- [x] LLM integration with Q&A generation capabilities
- [x] Database storage for processed data and file tracking
- [x] Configuration management and validation
- [x] Progress tracking and monitoring with Text User Interface (TUI)
- [x] Export functionality with multiple format templates
- [x] Real-time progress tracking with Total → Current Repository → Current File hierarchy
- [x] Cross-platform support for Windows, macOS, and Linux
- [x] Error handling and retry mechanisms
- [x] Memory and battery-conscious processing for laptops
- [x] Robust document processing retry mechanism with exponential backoff
- [x] Enhanced Apple Silicon GPU usage with proper MLX device management
- [x] Termination popup dialog with immediate visual feedback
- [x] Auto RAM calculation for MLX (80% of system memory)
- [x] Updated default MLX model for better performance
- [x] All documentation updated with new features and functionality
- [x] Reset functionality with subcommands (db, logs, repos, all)
- [x] Repository progress tracking with visual feedback for scraping operations
- [x] Fully functional TUI configuration menu with keyboard navigation and input validation
- [x] Comprehensive Unit Test Coverage (increased to ~70% covering core logic, utilities, and TUI)
- [x] **⚙️ Configure Token Limits** - Made token limits configurable with default 4096 and virtually unlimited capability, balancing performance and detail (see Performance & Optimization)
- [x] **💬 Enhanced Prompts with Examples** - Updated prompts to encourage detailed answers with code examples (see Performance & Optimization)
- [x] **📊 Remove Current File from Stats** - Removed "Current File" display from pipeline statistics container (see User Experience & Interface)
- [x] **📏 Added File Size Display** - Added file sizes in appropriate units (B/KB/MB) in UI (see User Experience & Interface)
- [x] **⚡ MLX Performance Optimization** - Increased cache size from 128 to 256 entries for better performance
- [x] **🔧 MLX Timeout Handling** - Fixed MLX timeout and parameter compatibility issues
- [x] **📊 Improved Progress Tracking** - Enhanced progress tracking with detailed timing information

---
*Last Updated: December 20, 2025*
*Last Analysis: Comprehensive codebase analysis completed December 20, 2025*
*To contribute: Submit PRs addressing items from this list, prioritize items in the Priority Action Items section*
