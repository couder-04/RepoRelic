# Changelog

All notable changes to the RepoRelic extension are documented in this file.

## [0.0.3] — 2026-05-14

### Added
- **Multi-LLM support**: Now supports OpenAI, DeepSeek, Claude-compatible services, and Gemini
- **LLM provider dropdown**: VS Code setting `reporelic.llmProvider` to switch between `openai` and `gemini`
- **OpenAI base URL configuration**: Support for OpenAI-compatible endpoints (DeepSeek, GPT-OSS, etc.)
- **Refined test generation**:
  - Pre-check for missing dependencies before LLM call
  - Validate generated code for valid pytest syntax and assertions
  - Skip tests that don't meet production integrity requirements
- **Dependency remarks in report**: New `## 🚧 Missing Dependency Remarks` section listing functions skipped due to missing imports
- **Knowledge-graph refactoring suggestions**:
  - Detect isolated/unused functions (disconnected edges)
  - Identify duplicate function logic candidates for consolidation
  - Include refactor hints in the analysis report

### Changed
- Updated README with comprehensive LLM setup and configuration documentation
- Extended `reporelic.openaiApiKey` and `reporelic.openaiBaseUrl` settings for flexibility
- Test generation prompt now emphasizes production-grade edge-case coverage and dependency stability

### Fixed
- Extension LICENSE updated with correct copyright information

## [0.0.2] — 2026-05-13

### Added
- Initial framework for multi-provider LLM support (Gemini + DeepSeek)
- Rate limiting and token management for LLM calls

### Fixed
- Improved error handling in Python runner

## [0.0.1] — 2026-05-12

### Added
- Initial release with Gemini-powered test generation
- 8-stage analysis pipeline
- VS Code webview for progress tracking
- Report generation to Markdown
