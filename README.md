# RepoRelic

A VS Code extension that analyzes Python codebases, generates tests for risky 
functions using Gemini AI, executes them, diagnoses failures, and produces a report.

## Features
- Static analysis (complexity, linting, dependency graph)
- AI-powered test generation via Gemini
- Automatic failure diagnosis
- Full markdown report in `.reporelic/report.md`

## Requirements
- Python 3.8+
- A Gemini API Key (free at aistudio.google.com)

## How to Use
1. Right-click any Python folder in the Explorer
2. Click **Analyze with RepoRelic**
3. Watch the 8-stage progress in the panel
4. Approve test execution when prompted
5. Open the generated `report.md`

## Configuration
| Setting | Default | Description |
|---------|---------|-------------|
| `reporelic.pythonPath` | `python` | Path to your Python executable |
| `reporelic.geminiApiKey` | `` | Your Gemini API key |