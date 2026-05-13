# RepoRelic — Implementation Plan

A VS Code extension that spawns a Python analysis engine to statically analyze Python codebases, generate tests for risky functions via Gemini, execute them, diagnose failures, and produce a `report.md`.

---

## Question 16: Monorepo vs Separate Repos

| Aspect | **Monorepo** (recommended ✅) | **Separate Repos** |
|---|---|---|
| Version sync | Extension + engine always match | Must coordinate releases manually |
| Packaging | Extension bundles the engine folder | Engine installed separately (pip) |
| CI/CD | One pipeline builds & tests both | Two pipelines, cross-repo triggers |
| Dev experience | One `git clone`, one workspace | Two clones, context switching |
| Standalone CLI | Still possible via `python -m engine` | Cleaner separation |
| Team size fit | Perfect for small teams | Better for large orgs with separate owners |

**Decision:** Monorepo in `d:\RepoRelic`. The Python engine lives alongside the extension. Users get everything in one install. The engine can still be run standalone via CLI for CI/CD use.

---

## Project Structure

```
d:\RepoRelic/
├── .vscode/
│   └── launch.json                  # F5 debugging config
├── extension/                       # VS Code extension (TypeScript)
│   ├── src/
│   │   ├── extension.ts             # activate(), command registration
│   │   ├── pythonRunner.ts          # Spawns engine, reads JSON-lines stdout
│   │   ├── depChecker.ts            # Checks/installs Python deps
│   │   ├── webviewPanel.ts          # Webview provider (progress + report)
│   │   └── statusBar.ts            # Stage progress in status bar
│   ├── media/
│   │   └── webview.html             # Webview HTML template
│   ├── package.json                 # Extension manifest + contributions
│   ├── tsconfig.json
│   └── webpack.config.js
├── engine/                          # Python analysis engine
│   ├── __init__.py
│   ├── __main__.py                  # `python -m engine <path>` entry
│   ├── orchestrator.py              # Runs stages 1-8 sequentially
│   ├── config.py                    # Settings, thresholds, paths
│   ├── progress.py                  # JSON-line progress emitter
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── s1_understand.py         # AST file map
│   │   ├── s2_static.py             # Static analysis (pylint, radon, ast)
│   │   ├── s3_depgraph.py           # Import/call dependency graph
│   │   ├── s4_knowledge.py          # Enriched knowledge graph
│   │   ├── s5_testgen.py            # LLM test generation
│   │   ├── s6_executor.py           # pytest runner
│   │   ├── s7_diagnosis.py          # LLM failure diagnosis
│   │   └── s8_report.py             # Markdown report writer
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gemini_client.py         # google-generativeai wrapper
│   │   ├── rate_limiter.py          # Caveman token/RPM limiter
│   │   └── prompts/
│   │       ├── test_gen.j2          # Jinja2 prompt for test generation
│   │       └── diagnosis.j2         # Jinja2 prompt for failure diagnosis
│   ├── models/
│   │   ├── __init__.py
│   │   ├── file_map.py              # Dataclasses for stage 1
│   │   ├── analysis.py              # Dataclasses for stage 2
│   │   └── report.py                # Report data model
│   ├── utils/
│   │   ├── __init__.py
│   │   └── ast_helpers.py           # AST parsing utilities
│   └── requirements.txt
├── .gitignore
├── README.md
└── CHANGELOG.md
```

---

## Communication Protocol (Extension ↔ Engine)

The extension spawns `python -m engine <target_path>` and communicates via **JSON-lines on stdout**:

```jsonc
// Progress update
{"type": "progress", "stage": 1, "name": "Understand Codebase", "status": "running", "message": "Parsing 42 files..."}
{"type": "progress", "stage": 1, "name": "Understand Codebase", "status": "done", "message": "Found 128 functions in 42 files"}

// Permission request (stage 6) — engine blocks on stdin
{"type": "permission", "action": "run_tests", "message": "Ready to execute 12 generated test files. Allow?"}
// Extension sends back via stdin:
{"approved": true}

// Final result
{"type": "complete", "report_path": ".reporelic/report.md"}

// Error
{"type": "error", "stage": 3, "message": "networkx not installed"}
```

---

## Proposed Changes — Phase by Phase

We build in **5 phases**, each producing a testable, working increment.

---

### Phase 1: Scaffolding & Core Infrastructure

> Get the monorepo skeleton working: extension spawns Python, Python replies, webview shows output.

#### [NEW] `extension/package.json`
- Extension manifest with `name: reporelic`, `activationEvents`, and `contributes`:
  - Command: `reporelic.analyze`
  - Context menus: `explorer/context` (right-click folder/file)
  - Configuration: `reporelic.pythonPath`, `reporelic.geminiApiKey`

#### [NEW] `extension/src/extension.ts`
- Register `reporelic.analyze` command
- On invoke: resolve target path from context menu URI
- Call `PythonRunner.spawn()` → pipe stdout to `WebviewPanel`

#### [NEW] `extension/src/pythonRunner.ts`
- `spawn('python', ['-m', 'engine', targetPath], {cwd: extensionPath})`
- Parse JSON-lines from stdout, emit typed events
- Write to stdin for permission responses
- Handle process exit/error

#### [NEW] `extension/src/depChecker.ts`
- Run `python -m engine --check-deps` → returns JSON list of missing packages
- If missing: show VS Code info message with "Install" button
- On approve: run `pip install -r requirements.txt` in terminal

#### [NEW] `extension/src/webviewPanel.ts`
- Simple HTML webview with:
  - 8-stage progress tracker (icons: ⏳ → ✅ / ❌)
  - Live log area
  - "Open Report" button when done

#### [NEW] `extension/src/statusBar.ts`
- Status bar item: `$(sync~spin) RepoRelic: Stage 3/8 — Dependency Graph`

#### [NEW] `engine/__main__.py`
- Arg parser: `<target_path>`, `--check-deps`, `--config`
- Calls `orchestrator.run(target_path)`

#### [NEW] `engine/orchestrator.py`
- Sequential stage runner with try/catch per stage
- Emits progress JSON-lines via `progress.py`

#### [NEW] `engine/progress.py`
- `emit(stage, name, status, message)` → `json.dumps()` to stdout
- `request_permission(action, message)` → write to stdout, block on stdin

#### [NEW] `engine/config.py`
- Dataclass with defaults: `complexity_threshold=10`, `max_tokens_per_minute=30000`, `delay_between_calls=2.0`, `output_dir=".reporelic"`

---

### Phase 2: Stages 1–4 (Pure Analysis, No LLM)

> All offline analysis — understand, lint, graph, enrich.

#### [NEW] `engine/models/file_map.py`
- Dataclasses: `FunctionInfo(name, lineno, end_lineno, args, docstring, decorators, is_method)`, `ClassInfo(name, lineno, methods, bases)`, `FileMap(path, functions, classes, imports)`

#### [NEW] `engine/models/analysis.py`
- Dataclasses: `StaticIssue(file, line, code, message, severity)`, `ComplexityScore(function, file, score, rank)`, `AnalysisResult(issues, complexity_scores)`

#### [NEW] `engine/utils/ast_helpers.py`
- `parse_file(path) → ast.Module` with error handling
- `extract_functions(tree) → list[FunctionInfo]`
- `extract_classes(tree) → list[ClassInfo]`
- `extract_imports(tree) → list[ImportInfo]`
- `get_function_source(path, lineno, end_lineno) → str`

#### [NEW] `engine/stages/s1_understand.py`
- Walk target path with `pathlib.Path.rglob("*.py")`
- Skip `__pycache__`, `.venv`, `.git`, `.reporelic`
- Parse each file → build `list[FileMap]`
- Emit progress: file count, function count, class count

#### [NEW] `engine/stages/s2_static.py`
- **AST-based checks:** unused imports (compare imported names vs used names), bare `except:`, mutable default args
- **Radon:** `cc_visit()` for cyclomatic complexity per function, rank A-F
- **Pylint:** programmatic run with `TextReporter` to `StringIO`, parse output
- **Pyflakes:** run via subprocess, parse output
- Aggregate into `AnalysisResult`

#### [NEW] `engine/stages/s3_depgraph.py`
- `ImportGraphBuilder(ast.NodeVisitor)`:
  - `visit_Import` / `visit_ImportFrom` → resolve to file paths
  - Build `nx.DiGraph` with file nodes and import edges
- `CallGraphBuilder(ast.NodeVisitor)`:
  - Track current function scope
  - `visit_Call` → record caller→callee edges
- Combine into a single `nx.DiGraph`

#### [NEW] `engine/stages/s4_knowledge.py`
- Take the graph from stage 3
- Enrich each function node with: `signature`, `docstring`, `complexity_score`, `static_issues[]`, `is_risky` flag
- **Risky function criteria:** complexity ≥ threshold, OR no docstring + >20 lines, OR has static errors, OR uses bare except
- Serialize graph to `.reporelic/knowledge_graph.json`

---

### Phase 3: LLM Integration (Stages 5, 7)

> Gemini client, rate limiting, test generation, failure diagnosis.

#### [NEW] `engine/llm/gemini_client.py`
- Wrapper around `google.generativeai`
- `configure(api_key)` → `genai.configure()`
- `generate(prompt, max_tokens) → str` with retry + exponential backoff
- Model: `gemini-2.0-flash` (fast + cheap) for test gen, `gemini-2.5-pro` for diagnosis

#### [NEW] `engine/llm/rate_limiter.py`
- **Caveman strategy:**
  - Track `tokens_used_this_minute` and `requests_this_minute`
  - Before each call: if budget exceeded → `time.sleep()` until window resets
  - Configurable: `max_rpm`, `max_tpm`, `delay_between_calls`
  - Log: `"Rate limit: sleeping 4.2s (28k/30k TPM used)"`

#### [NEW] `engine/llm/prompts/test_gen.j2`
```jinja2
You are a Python testing expert. Generate a pytest test file for this function.

## Function
- Name: {{ func.name }}
- File: {{ func.file }}
- Signature: {{ func.signature }}
- Docstring: {{ func.docstring or "None" }}
- Complexity: {{ func.complexity }} ({{ func.rank }})
- Known issues: {{ func.issues | join(", ") or "None" }}

## Source Code
```python
{{ func.source }}
```

## Requirements
- Focus on edge cases and boundary conditions
- Include at least one happy path and one error path
- Use descriptive test names
- Handle imports appropriately
- Output ONLY valid Python code, no explanation
```

#### [NEW] `engine/llm/prompts/diagnosis.j2`
```jinja2
A generated test failed. Diagnose the root cause.

## Failed Test
{{ test_code }}

## Error
{{ traceback }}

## Function Under Test
- Name: {{ func.name }}
- Source:
```python
{{ func.source }}
```
- Known static issues: {{ func.issues | join(", ") or "None" }}

Explain: (1) why it failed, (2) is it a real bug or a test issue, (3) suggested fix.
```

#### [NEW] `engine/stages/s5_testgen.py`
- Filter knowledge graph for `is_risky == True` functions
- For each: render `test_gen.j2` → call Gemini → write to `.reporelic/generated_tests/test_<module>_<func>.py`
- Rate limit between calls
- Emit progress per function

#### [NEW] `engine/stages/s7_diagnosis.py`
- For each failed test from stage 6:
  - Look up the function in the knowledge graph
  - Render `diagnosis.j2` → call Gemini
  - Parse response into structured diagnosis
- Rate limit between calls

---

### Phase 4: Test Execution (Stage 6)

> Run generated tests safely with permission gate.

#### [NEW] `engine/stages/s6_executor.py`
- Before running: emit `permission` request → block on stdin approval
- If denied: skip stage, note in report
- If approved:
  - Discover project virtualenv (look for `.venv/`, `venv/`, check `sys.prefix`)
  - Run: `subprocess.run([venv_python, '-m', 'pytest', test_dir, '--tb=short', '-q', '--no-header'], capture_output=True)`
  - Parse stdout for: passed/failed counts, failing test names
  - Parse stderr for tracebacks
  - Return structured `TestResult(file, test_name, status, traceback)`

---

### Phase 5: Report & Polish (Stage 8)

> Generate the final report, polish the webview.

#### [NEW] `engine/stages/s8_report.py`
- Build `report.md` with sections:

```markdown
# RepoRelic Analysis Report
> Generated: {timestamp} | Target: {path} | Files: {n} | Functions: {n}

## 📊 Summary
| Metric | Value |
|--------|-------|
| Files analyzed | 42 |
| Functions found | 128 |
| Risky functions | 12 |
| Static issues | 34 |
| Tests generated | 12 |
| Tests passed | 9 |
| Tests failed | 3 |

## ⚠️ Static Issues
### Critical
- `app/auth.py:45` — Bare except clause (catches SystemExit, KeyboardInterrupt)
...

## 🔴 Risky Functions
| Function | File | Complexity | Issues |
|----------|------|-----------|--------|
| `process_data` | `core/pipeline.py` | C (15) | No docstring, mutable default |
...

## 🧪 Test Results
### ✅ Passed (9)
...
### ❌ Failed (3)
#### `test_process_data_empty_input`
- **Error:** TypeError: cannot unpack non-iterable NoneType
- **Diagnosis:** The function doesn't handle empty input...
- **Suggested Fix:** Add `if not data: return []` guard...

## 📈 Dependency Graph
Top 5 most-imported modules:
1. `core/utils.py` — imported by 12 files
...
```

#### [MODIFY] `extension/media/webview.html`
- Add "Open Report" button that sends message to extension
- Show summary stats when analysis completes
- Add collapsible stage details

---

## Dependency Management

### Python (`engine/requirements.txt`)
```
networkx>=3.1
radon>=6.0
pylint>=3.0
pyflakes>=3.1
google-generativeai>=0.8
jinja2>=3.1
```

### Node (`extension/package.json`)
```json
"devDependencies": {
  "@types/vscode": "^1.85.0",
  "typescript": "^5.3.0",
  "webpack": "^5.89.0",
  "webpack-cli": "^5.1.0",
  "ts-loader": "^9.5.0"
}
```

### Dep Checking Flow
1. Extension runs `python -m engine --check-deps`
2. Engine tries `import networkx, radon, ...` in try/except
3. Returns JSON: `{"missing": ["radon", "pyflakes"], "found": ["networkx", ...]}`
4. Extension shows: *"RepoRelic needs: radon, pyflakes. Install now?"*
5. On approve → run `pip install radon pyflakes` in integrated terminal

---

## Rate Limiting Strategy (Caveman)

```python
class CavemanRateLimiter:
    def __init__(self, max_rpm=15, max_tpm=30000, min_delay=2.0):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.min_delay = min_delay
        self.requests = []       # timestamps
        self.tokens_used = []    # (timestamp, count) pairs

    def wait_if_needed(self, estimated_tokens: int):
        # 1. Always wait min_delay since last call
        # 2. Check RPM window — if at limit, sleep until oldest expires
        # 3. Check TPM window — if adding this would exceed, sleep
        # 4. Log the wait reason and duration

    def record_usage(self, tokens_used: int):
        # Track actual usage after call completes
```

---

## Verification Plan

### Automated Tests
1. **Engine unit tests:** pytest tests for each stage using fixture Python projects
2. **Integration test:** Run full pipeline on a small sample project in `tests/fixtures/sample_project/`
3. **Extension:** Compile with `npm run compile`, check for TypeScript errors

### Manual Verification
1. Press F5 → Extension Development Host
2. Right-click a Python folder → "Analyze with RepoRelic"
3. Verify: progress in status bar, webview updates, report generated in `.reporelic/`
4. Verify: permission prompt appears before test execution
5. Verify: dep checker prompts if packages missing

---

## Build Order (Recommended)

| Order | Phase | What you get | Est. effort |
|-------|-------|-------------|-------------|
| 1 | Phase 1 | Extension spawns Python, webview shows progress | 1-2 days |
| 2 | Phase 2 | Full offline analysis (stages 1-4), knowledge graph | 2-3 days |
| 3 | Phase 3 | LLM test generation + diagnosis | 1-2 days |
| 4 | Phase 4 | Test execution with permission gate | 1 day |
| 5 | Phase 5 | Report generation, webview polish | 1 day |

**Total estimated: ~6-9 days of focused work**

---

## Open Questions

> [!IMPORTANT]
> **Gemini Model Choice:** Should we use `gemini-2.0-flash` for everything (cheaper/faster) or split between Flash for test gen and Pro for diagnosis? Flash is ~10x cheaper.

> [!IMPORTANT]
> **API Key Storage:** Should the Gemini API key be stored in VS Code settings (plaintext) or use VS Code's `SecretStorage` API (encrypted)? SecretStorage is more secure but slightly more complex.

> [!NOTE]
> **Scope of "risky":** Current criteria: complexity ≥ 10, OR no docstring + >20 lines, OR has static errors, OR bare except. Want to adjust these thresholds?
