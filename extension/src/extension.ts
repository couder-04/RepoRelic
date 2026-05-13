import * as vscode from 'vscode';
import { RepoRelicPanel } from './webviewPanel';
import { PythonRunner } from './pythonRunner';

export function activate(context: vscode.ExtensionContext) {
    let disposable = vscode.commands.registerCommand('reporelic.analyze', async (uri: vscode.Uri) => {
        if (!uri) {
            vscode.window.showErrorMessage('Please right-click a folder to analyze.');
            return;
        }

        const targetPath = uri.fsPath;
        
        // Show panel
        RepoRelicPanel.createOrShow(context.extensionUri);
        
        // Start engine
        const engineDir = vscode.Uri.joinPath(context.extensionUri, '..', 'engine').fsPath;
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
                // Fallback if panel is closed
                runner.sendPermissionResponse(false);
            }
        });

        runner.start();
    });

    context.subscriptions.push(disposable);
}

export function deactivate() {}
