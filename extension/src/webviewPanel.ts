import * as vscode from 'vscode';

export class RepoRelicPanel {
    public static currentPanel: RepoRelicPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _reportPath: string | undefined;
    public onPermissionResponse: ((approved: boolean) => void) | undefined;

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (RepoRelicPanel.currentPanel) {
            RepoRelicPanel.currentPanel._panel.reveal(column);
            RepoRelicPanel.currentPanel._update();
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'reporelic',
            'RepoRelic Analysis',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            }
        );

        RepoRelicPanel.currentPanel = new RepoRelicPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._update();

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'openReport':
                        if (this._reportPath) {
                            vscode.window.showTextDocument(vscode.Uri.file(this._reportPath));
                        }
                        return;
                    case 'permissionResponse':
                        if (this.onPermissionResponse) {
                            this.onPermissionResponse(message.approved);
                        }
                        return;
                }
            },
            null,
            this._disposables
        );
    }

    public updateProgress(msg: any) {
        this._panel.webview.postMessage({ command: 'progress', data: msg });
    }

    public askPermission(text: string) {
        this._panel.webview.postMessage({ command: 'permission', text });
    }

    public showComplete(reportPath: string) {
        this._reportPath = reportPath;
        this._panel.webview.postMessage({ command: 'complete', reportPath });
    }

    public showError(err: string) {
        this._panel.webview.postMessage({ command: 'error', message: err });
    }

    public dispose() {
        RepoRelicPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) x.dispose();
        }
    }

    private _update() {
        this._panel.webview.options = { enableScripts: true };
        this._panel.webview.html = this._getHtml();
    }

    private _getHtml(): string {
        const initTime = new Date().toLocaleTimeString();
        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
<title>RepoRelic</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background:#1e1e1e; color:#d4d4d4; font-family:'Courier New',monospace; height:100vh; display:flex; flex-direction:column; overflow:hidden; }
header { padding:18px 28px 14px; border-bottom:1px solid #2a2a2a; display:flex; align-items:baseline; justify-content:space-between; }
.title { font-size:15px; font-weight:700; letter-spacing:0.12em; color:#00c8ff; }
.title span { color:#00ff9d; }
#status-badge { font-size:11px; letter-spacing:0.08em; color:#888; }
.stages { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#2a2a2a; border-bottom:1px solid #2a2a2a; }
.stage { background:#252526; padding:14px 18px; display:flex; align-items:center; justify-content:space-between; transition:background 0.2s; }
.stage-info { display:flex; flex-direction:column; gap:3px; }
.stage-label { font-size:9px; letter-spacing:0.15em; color:#555; text-transform:uppercase; }
.stage-name { font-size:13px; font-weight:600; color:#888; transition:color 0.3s; }
.stage-dot { width:8px; height:8px; border-radius:50%; background:#3a3a3a; transition:background 0.3s; flex-shrink:0; }
.stage.running { background:#1e2a1e; }
.stage.running .stage-name { color:#00ff9d; }
.stage.running .stage-dot { background:#00ff9d; box-shadow:0 0 6px #00ff9d88; animation:pulse 1s ease-in-out infinite; }
.stage.done { background:#1e2320; }
.stage.done .stage-name { color:#4ec9a0; }
.stage.done .stage-dot { background:#4ec9a0; }
.stage.error { background:#2a1e1e; }
.stage.error .stage-name { color:#f48771; }
.stage.error .stage-dot { background:#f48771; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
#log { flex:1; overflow-y:auto; padding:14px 20px; font-size:12px; line-height:1.7; background:#111; }
.log-line { display:flex; gap:10px; margin-bottom:2px; }
.log-time { color:#555; flex-shrink:0; }
.log-tag { flex-shrink:0; font-weight:700; }
.log-tag.SYSTEM { color:#00c8ff; }
.log-tag.PROGRESS { color:#00ff9d; }
.log-tag.COMPLETE { color:#4ec9a0; }
.log-tag.ERROR { color:#f48771; }
.log-tag.PERMISSION { color:#dcdcaa; }
.log-msg { color:#c8c8c8; flex:1; word-break:break-all; }
#permission-box { display:none; padding:12px 20px; background:#252500; border-top:1px solid #555500; align-items:center; gap:12px; }
#permission-box.visible { display:flex; }
#permission-text { flex:1; font-size:12px; color:#dcdcaa; }
.perm-btn { padding:5px 14px; border:none; border-radius:3px; font-family:inherit; font-size:11px; font-weight:700; cursor:pointer; }
.perm-btn.allow { background:#00ff9d22; color:#00ff9d; border:1px solid #00ff9d44; }
.perm-btn.deny { background:#f4877122; color:#f48771; border:1px solid #f4877144; }
#complete-bar { display:none; padding:10px 20px; background:#1a2e1a; border-top:1px solid #00ff9d33; align-items:center; justify-content:space-between; }
#complete-bar.visible { display:flex; }
#complete-bar span { font-size:12px; color:#4ec9a0; }
#open-report-btn { padding:5px 14px; background:#00ff9d22; color:#00ff9d; border:1px solid #00ff9d55; border-radius:3px; font-family:inherit; font-size:11px; font-weight:700; cursor:pointer; }
</style>
</head>
<body>
<header>
    <div class="title">REPO RELIC &bull; <span>ENGINE</span></div>
    <div id="status-badge">Ready</div>
</header>
<div class="stages">
    <div class="stage" id="stage-1"><div class="stage-info"><span class="stage-label">Stage 1</span><span class="stage-name">Understand</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-2"><div class="stage-info"><span class="stage-label">Stage 2</span><span class="stage-name">Static Analysis</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-3"><div class="stage-info"><span class="stage-label">Stage 3</span><span class="stage-name">Dep Graph</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-4"><div class="stage-info"><span class="stage-label">Stage 4</span><span class="stage-name">Knowledge</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-5"><div class="stage-info"><span class="stage-label">Stage 5</span><span class="stage-name">Test Gen</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-6"><div class="stage-info"><span class="stage-label">Stage 6</span><span class="stage-name">Execution</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-7"><div class="stage-info"><span class="stage-label">Stage 7</span><span class="stage-name">Diagnosis</span></div><div class="stage-dot"></div></div>
    <div class="stage" id="stage-8"><div class="stage-info"><span class="stage-label">Stage 8</span><span class="stage-name">Reporting</span></div><div class="stage-dot"></div></div>
</div>
<div id="log"></div>
<div id="permission-box">
    <span id="permission-text"></span>
    <button class="perm-btn allow" id="allow-btn">ALLOW</button>
    <button class="perm-btn deny" id="deny-btn">DENY</button>
</div>
<div id="complete-bar">
    <span>&#10003; Analysis complete</span>
    <button id="open-report-btn">OPEN REPORT</button>
</div>
<script>
(function() {
    const vscode = acquireVsCodeApi();
    const log = document.getElementById('log');
    const statusBadge = document.getElementById('status-badge');
    const permBox = document.getElementById('permission-box');
    const permText = document.getElementById('permission-text');
    const completeBar = document.getElementById('complete-bar');

    function appendLog(tag, msg, time) {
        const t = time || new Date().toLocaleTimeString();
        const line = document.createElement('div');
        line.className = 'log-line';
        line.innerHTML =
            '<span class="log-time">[' + t + ']</span>' +
            '<span class="log-tag ' + tag + '">' + tag + '</span>' +
            '<span class="log-msg">' + String(msg).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span>';
        log.appendChild(line);
        log.scrollTop = log.scrollHeight;
    }

    function setStage(n, state) {
        const el = document.getElementById('stage-' + n);
        if (el) {
            el.classList.remove('running', 'done', 'error');
            if (state) el.classList.add(state);
        }
    }

    appendLog('SYSTEM', 'Engine initialized. Awaiting pipeline...', '${initTime}');

    document.getElementById('allow-btn').addEventListener('click', function() {
        vscode.postMessage({ command: 'permissionResponse', approved: true });
        permBox.classList.remove('visible');
        appendLog('PERMISSION', 'Access granted.');
    });

    document.getElementById('deny-btn').addEventListener('click', function() {
        vscode.postMessage({ command: 'permissionResponse', approved: false });
        permBox.classList.remove('visible');
        appendLog('PERMISSION', 'Access denied.');
    });

    document.getElementById('open-report-btn').addEventListener('click', function() {
        vscode.postMessage({ command: 'openReport' });
    });

    window.addEventListener('message', function(event) {
        const msg = event.data;
        console.log('RepoRelic webview received:', JSON.stringify(msg));
        switch (msg.command) {
            case 'progress': {
                const d = msg.data;
                if (d.stage) {
                if (d.status === 'done') {

                    setStage(d.stage, 'done');

                } else if (d.status === 'error') {

                    setStage(d.stage, 'error');

                } else {

                    setStage(d.stage, 'running');
                }
                }
                statusBadge.textContent = 'Running';
                appendLog('PROGRESS', d.message || JSON.stringify(d));
                break;
            }
            case 'complete': {
                for (var i = 1; i <= 8; i++) setStage(i, 'done');
                statusBadge.textContent = 'Complete';
                appendLog('COMPLETE', 'Report: ' + msg.reportPath);
                completeBar.classList.add('visible');
                break;
            }
            case 'error': {
                statusBadge.textContent = 'Error';
                appendLog('ERROR', msg.message);
                document.querySelectorAll('.stage.running').forEach(function(el) {
                    el.classList.remove('running');
                    el.classList.add('error');
                });
                break;
            }
            case 'permission': {
                permText.textContent = msg.text;
                permBox.classList.add('visible');
                appendLog('PERMISSION', 'Permission requested.');
                break;
            }
        }
    });
})();
</script>
</body>
</html>`;
    }
}