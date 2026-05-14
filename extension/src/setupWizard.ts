import * as vscode from 'vscode';

export class SetupWizard {
    public static async show(context: vscode.ExtensionContext): Promise<void> {
        const panel = vscode.window.createWebviewPanel(
            'reporelicSetup',
            'RepoRelic — First Time Setup',
            vscode.ViewColumn.One,
            { enableScripts: true }
        );

        panel.webview.html = SetupWizard._getHtml();

        panel.webview.onDidReceiveMessage(async (message) => {
            if (message.command === 'save') {
                const config = vscode.workspace.getConfiguration('reporelic');
                const d = message.data;

                await config.update('repoPath',      d.repoPath,      vscode.ConfigurationTarget.Global);
                await config.update('pythonPath',    d.pythonPath,    vscode.ConfigurationTarget.Global);
                await config.update('llmProvider',   d.llmProvider,   vscode.ConfigurationTarget.Global);
                await config.update('openaiApiKey',  d.openaiApiKey,  vscode.ConfigurationTarget.Global);
                await config.update('openaiBaseUrl', d.openaiBaseUrl, vscode.ConfigurationTarget.Global);
                await config.update('geminiApiKey',  d.geminiApiKey,  vscode.ConfigurationTarget.Global);

                await context.globalState.update('reporelic.setupDone', true);
                panel.dispose();

                vscode.window.showInformationMessage(
                    '✅ RepoRelic ready! Right-click any Python folder → Analyze with RepoRelic'
                );
            }

            if (message.command === 'skip') {
                await context.globalState.update('reporelic.setupDone', true);
                panel.dispose();
            }
        });
    }

    private static _getHtml(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RepoRelic Setup</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI', system-ui, sans-serif;
    display: flex;
    justify-content: center;
    padding: 40px 20px;
    min-height: 100vh;
}
.container { width: 100%; max-width: 580px; }
.header { text-align: center; margin-bottom: 32px; }
.logo {
    font-family: 'Courier New', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #00c8ff;
    letter-spacing: 0.12em;
    margin-bottom: 10px;
}
.logo span { color: #00ff9d; }
.subtitle { font-size: 13px; color: #8b949e; line-height: 1.6; }
.card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 24px;
    margin-bottom: 14px;
}
.card-title {
    font-size: 11px;
    font-weight: 700;
    color: #00c8ff;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 18px;
    padding-bottom: 10px;
    border-bottom: 1px solid #30363d;
}
.field { margin-bottom: 16px; }
.field:last-child { margin-bottom: 0; }
label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: #8b949e;
    margin-bottom: 6px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
label .req { color: #f85149; margin-left: 2px; }
label .opt { color: #3fb950; font-weight: 400; margin-left: 6px; font-size: 10px; text-transform: none; }
input, select {
    width: 100%;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 9px 12px;
    color: #e6edf3;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    outline: none;
    transition: border-color 0.2s;
}
input:focus, select:focus { border-color: #00c8ff; }
input::placeholder { color: #484f58; }
select option { background: #161b22; }
.hint {
    font-size: 11px;
    color: #484f58;
    margin-top: 5px;
    line-height: 1.5;
}
.hint code {
    background: #1c2128;
    padding: 1px 5px;
    border-radius: 3px;
    color: #79c0ff;
}
.info-box {
    background: #1c2128;
    border: 1px solid #30363d;
    border-left: 3px solid #00c8ff;
    border-radius: 4px;
    padding: 10px 14px;
    font-size: 11px;
    color: #8b949e;
    line-height: 1.6;
    margin-top: 10px;
}
.info-box a { color: #58a6ff; text-decoration: none; }
.actions { display: flex; gap: 10px; margin-top: 20px; }
.btn-primary {
    flex: 1;
    background: #00c8ff22;
    color: #00c8ff;
    border: 1px solid #00c8ff55;
    border-radius: 6px;
    padding: 11px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.05em;
    transition: background 0.2s;
}
.btn-primary:hover { background: #00c8ff33; }
.btn-skip {
    background: transparent;
    color: #484f58;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 11px 18px;
    font-size: 12px;
    cursor: pointer;
}
.btn-skip:hover { color: #8b949e; border-color: #484f58; }
.footer-note { font-size: 11px; color: #484f58; text-align: center; margin-top: 10px; }
.footer-note span { color: #f85149; }
</style>
</head>
<body>
<div class="container">

    <div class="header">
        <div class="logo">REPO RELIC &bull; <span>SETUP</span></div>
        <div class="subtitle">
            One-time setup — takes 2 minutes.<br>
            After this, just right-click any Python folder to analyze it.
        </div>
    </div>

    <!-- REPO PATH -->
    <div class="card">
        <div class="card-title">📁 RepoRelic Location</div>
        <div class="field">
            <label>Repo Path <span class="req">*</span></label>
            <input type="text" id="repoPath"
                placeholder="/Users/you/code_playground/RepoRelic" />
            <div class="hint">
                Where you cloned RepoRelic on this machine.<br>
                <code>git clone https://github.com/couder-04/RepoRelic.git</code>
            </div>
        </div>
        <div class="field">
            <label>Python Path <span class="req">*</span></label>
            <input type="text" id="pythonPath"
                placeholder="/Users/you/code_playground/RepoRelic/.venv/bin/python3" />
            <div class="hint">
                Python 3.11+ inside your RepoRelic venv.<br>
                Run: <code>cd RepoRelic && python3 -m venv .venv && source .venv/bin/activate && pip install -r engine/requirements.txt</code>
            </div>
        </div>
    </div>

    <!-- LLM PROVIDER -->
    <div class="card">
        <div class="card-title">🤖 AI Provider</div>
        <div class="field">
            <label>Provider <span class="req">*</span></label>
            <select id="llmProvider" onchange="onProviderChange()">
                <option value="openai">OpenAI / DeepSeek / Any OpenAI-compatible</option>
                <option value="gemini">Google Gemini</option>
            </select>
        </div>

        <div id="openai-section">
            <div class="field">
                <label>API Key <span class="req">*</span></label>
                <input type="password" id="openaiApiKey"
                    placeholder="sk-... or your DeepSeek API key" />
            </div>
            <div class="field">
                <label>Base URL <span class="req">*</span></label>
                <input type="text" id="openaiBaseUrl"
                    value="https://api.openai.com/v1" />
                <div class="hint">
                    DeepSeek: <code>https://api.deepseek.com/v1</code> &nbsp;|&nbsp;
                    OpenAI: <code>https://api.openai.com/v1</code>
                </div>
            </div>
            <div class="info-box">
                💡 Recommended: Use <b>DeepSeek</b> — it's free to start, great at code, and much cheaper than OpenAI.<br>
                Get a key at <a href="#">platform.deepseek.com</a>
            </div>
        </div>

        <div id="gemini-section" style="display:none">
            <div class="field">
                <label>Gemini API Key <span class="req">*</span></label>
                <input type="password" id="geminiApiKey" placeholder="AIzaSy..." />
                <div class="hint">
                    Free at <code>aistudio.google.com</code> — no credit card needed.
                </div>
            </div>
        </div>
    </div>

    <div class="actions">
        <button class="btn-primary" onclick="save()">✓ Save &amp; Finish Setup</button>
        <button class="btn-skip" onclick="skip()">Skip</button>
    </div>
    <div class="footer-note"><span>*</span> Required &nbsp;|&nbsp; Settings saved to VS Code user config</div>

</div>
<script>
const vscode = acquireVsCodeApi();

function onProviderChange() {
    const v = document.getElementById('llmProvider').value;
    document.getElementById('openai-section').style.display = v === 'openai' ? 'block' : 'none';
    document.getElementById('gemini-section').style.display = v === 'gemini' ? 'block' : 'none';
}

function save() {
    const repoPath   = document.getElementById('repoPath').value.trim();
    const pythonPath = document.getElementById('pythonPath').value.trim();
    const provider   = document.getElementById('llmProvider').value;
    const openaiKey  = document.getElementById('openaiApiKey').value.trim();
    const baseUrl    = document.getElementById('openaiBaseUrl').value.trim();
    const geminiKey  = document.getElementById('geminiApiKey').value.trim();

    if (!repoPath) { alert('Please enter the RepoRelic repo path.'); return; }
    if (!pythonPath) { alert('Please enter the Python path.'); return; }
    if (provider === 'openai' && !openaiKey) { alert('Please enter your API key.'); return; }
    if (provider === 'gemini' && !geminiKey) { alert('Please enter your Gemini API key.'); return; }

    vscode.postMessage({
        command: 'save',
        data: { repoPath, pythonPath, llmProvider: provider,
                openaiApiKey: openaiKey,
                openaiBaseUrl: baseUrl || 'https://api.openai.com/v1',
                geminiApiKey: geminiKey }
    });
}

function skip() { vscode.postMessage({ command: 'skip' }); }
</script>
</body>
</html>`;
    }
}