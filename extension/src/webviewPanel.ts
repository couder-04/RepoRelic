import * as vscode from 'vscode';
import * as fs from 'fs';

export class RepoRelicPanel {
    public static currentPanel: RepoRelicPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (RepoRelicPanel.currentPanel) {
            RepoRelicPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'reporelic',
            'RepoRelic Analysis',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
            }
        );

        RepoRelicPanel.currentPanel = new RepoRelicPanel(panel, extensionUri);
    }

    private _reportPath: string | undefined;
    public onPermissionResponse: ((approved: boolean) => void) | undefined;

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        this._update();

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'openReport':
                        if (this._reportPath) {
                            const uri = vscode.Uri.file(this._reportPath);
                            vscode.window.showTextDocument(uri);
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

    public dispose() {
        RepoRelicPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) x.dispose();
        }
    }

    private _update() {
        const htmlPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'webview.html').fsPath;
        let html = fs.readFileSync(htmlPath, 'utf8');
        this._panel.webview.html = html;
    }
}
