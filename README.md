# RepoRelic

A VS Code extension that analyzes Python codebases, generates tests for risky functions via LLM (OpenAI-compatible or Gemini), executes them, diagnoses failures, and produces a comprehensive markdown report.

## Features
- **8-stage static analysis** (complexity, linting, dependency graphs, knowledge enrichment)
- **LLM-powered test generation** (OpenAI, DeepSeek, Claude-compatible services, or Gemini)
- **Production-focused testing** with edge-case and boundary condition coverage
- **Automatic failure diagnosis** powered by LLM
- **Knowledge-graph refactoring suggestions** (disconnected functions, duplicate detection)
- **Full markdown report** in `.reporelic/report.md` with dependency remarks

## Requirements

### Extension
- VS Code 1.85.0 or later

### Python Engine
- **Python 3.8+** with the following packages:
  - `networkx >= 3.1`
  - `radon >= 6.0`
  - `pylint >= 3.0`
  - `pyflakes >= 3.1`
  - `google-genai >= 0.1.0` (for Gemini)
  - `openai >= 1.0.0` (for OpenAI-compatible endpoints)
  - `jinja2 >= 3.1`
  - `python-dotenv >= 1.0`

### LLM API Key
- **OpenAI or compatible**: API key from OpenAI, DeepSeek, GPT-OSS, or Claude-compatible service
- **Gemini**: Free API key from [aistudio.google.com](https://aistudio.google.com)

## Installation

### Step 1: Install Extension
- Install "RepoRelic" from the VS Code Marketplace

### Step 2: Set Repo Path
1. Clone or locate your RepoRelic repository locally
2. In VS Code settings, set `reporelic.repoPath` to the full path (e.g., `C:\Users\You\RepoRelic`)

### Step 3: Install Python Dependencies
In the RepoRelic repo root:
```bash
pip install -r engine/requirements.txt
```

### Step 4: Configure LLM
In VS Code settings:

- **For OpenAI / DeepSeek / Claude-compatible:**
  - `reporelic.llmProvider` → `openai`
  - `reporelic.openaiApiKey` → your API key
  - `reporelic.openaiBaseUrl` → (optional, defaults to OpenAI; set for DeepSeek/etc.)

- **For Gemini:**
  - `reporelic.llmProvider` → `gemini`
  - `reporelic.geminiApiKey` → your API key

## How to Use

1. Open any Python project in VS Code
2. Right-click a folder in the Explorer
3. Click **Analyze with RepoRelic**
4. Watch the 8-stage progress in the panel
5. Approve test execution when prompted
6. Open the generated `.reporelic/report.md`

## Configuration

| Setting | Default | Type | Description |
|---------|---------|------|-------------|
| `reporelic.pythonPath` | `python` | string | Path to Python executable (or `python3` if using system Python) |
| `reporelic.repoPath` | `` | string | **Required:** Full path to RepoRelic repo containing the `engine/` folder |
| `reporelic.llmProvider` | `openai` | enum | LLM provider: `openai` or `gemini` |
| `reporelic.openaiApiKey` | `` | string | API key for OpenAI-compatible providers (GPT, DeepSeek, Claude-compatible, etc.) |
| `reporelic.openaiBaseUrl` | `https://api.openai.com/v1` | string | Base URL for OpenAI-compatible API (e.g., DeepSeek, GPT-OSS) |
| `reporelic.geminiApiKey` | `` | string | API key for Google Gemini |
