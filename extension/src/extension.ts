import * as vscode from 'vscode';
import * as path from 'path';
import { RepoRelicPanel } from './webviewPanel';
import { PythonRunner } from './pythonRunner';

export function activate(context: vscode.ExtensionContext) {
    let disposable = vscode.commands.registerCommand('reporelic.analyze', async (uri: vscode.Uri) => {
        if (!uri) {
            vscode.window.showErrorMessage('Please right-click a folder to analyze.');
            return;
        }

        const targetPath = uri.fsPath;

        // Get repo path from settings
        const config = vscode.workspace.getConfiguration('reporelic');
        let repoPath = config.get<string>('repoPath', '');

        if (!repoPath) {
            vscode.window.showErrorMessage(
                'RepoRelic: Please set "reporelic.repoPath" in VS Code settings to your local RepoRelic repo path. e.g. /Users/you/code_playground/RepoRelic'
            );
            return;
        }

        const engineDir = path.join(repoPath, 'engine');

        // Show panel
        RepoRelicPanel.createOrShow(context.extensionUri);

        // Start engine
        const runner = new PythonRunner(engineDir, targetPath);

        runner.onProgress((msg) => {
            RepoRelicPanel.currentPanel?.updateProgress(msg);
        });

        runner.onComplete((reportPath) => {
            vscode.window.showInformationMessage(`Analysis complete! Report saved to ${reportPath}`);
            RepoRelicPanel.currentPanel?.showComplete(reportPath);
        });

        runner.onError((err) => {
            vscode.window.showErrorMessage(`RepoRelic Error: ${err}`);
        });

        runner.onPermissionRequest((msg) => {
            if (RepoRelicPanel.currentPanel) {
                RepoRelicPanel.currentPanel.askPermission(msg.message);
                RepoRelicPanel.currentPanel.onPermissionResponse = (approved) => {
                    runner.sendPermissionResponse(approved);
                };
            } else {
                runner.sendPermissionResponse(false);
            }
        });

        runner.start();
    });

    context.subscriptions.push(disposable);
}

export function deactivate() {}