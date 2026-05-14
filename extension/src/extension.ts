import * as vscode from 'vscode';
import * as path from 'path';
import { RepoRelicPanel } from './webviewPanel';
import { PythonRunner } from './pythonRunner';
import { SetupWizard } from './setupWizard';

export function activate(context: vscode.ExtensionContext) {

    // ── First-time setup wizard ──────────────────────────────────────────
    const setupDone = context.globalState.get<boolean>('reporelic.setupDone', false);
    if (!setupDone) {
        SetupWizard.show(context);
    }

    // ── Main analyze command ─────────────────────────────────────────────
    let disposable = vscode.commands.registerCommand(
        'reporelic.analyze',
        async (uri: vscode.Uri) => {

            if (!uri) {
                vscode.window.showErrorMessage(
                    'Please right-click a folder to analyze.'
                );
                return;
            }

            const targetPath = uri.fsPath;
            const config = vscode.workspace.getConfiguration('reporelic');

            const repoPath = config.get<string>('repoPath', '');
            if (!repoPath) {
                const action = await vscode.window.showErrorMessage(
                    'RepoRelic: repo path not set. Open setup wizard?',
                    'Open Setup'
                );
                if (action === 'Open Setup') {
                    await context.globalState.update('reporelic.setupDone', false);
                    SetupWizard.show(context);
                }
                return;
            }

            const engineDir     = path.join(repoPath, 'engine');
            const llmProvider   = config.get<string>('llmProvider',   'openai');
            const openaiApiKey  = config.get<string>('openaiApiKey',  '');
            const openaiBaseUrl = config.get<string>('openaiBaseUrl', 'https://api.openai.com/v1');
            const geminiApiKey  = config.get<string>('geminiApiKey',  '');
            const pythonPath    = config.get<string>('pythonPath',    '');

            // Show panel
            RepoRelicPanel.createOrShow(context.extensionUri);

            // Start engine
            const runner = new PythonRunner(engineDir, targetPath, {
                pythonPath,
                env: {
                    LLM_PROVIDER:    llmProvider,
                    OPENAI_API_KEY:  openaiApiKey,
                    OPENAI_BASE_URL: openaiBaseUrl,
                    GEMINI_API_KEY:  geminiApiKey,
                },
            });

            runner.onProgress((msg) => {
                RepoRelicPanel.currentPanel?.updateProgress(msg);
            });

            runner.onComplete((reportPath) => {
                vscode.window.showInformationMessage(
                    `✅ RepoRelic done! Report: ${reportPath}`
                );
                RepoRelicPanel.currentPanel?.showComplete(reportPath);
            });

            runner.onError((err) => {
                RepoRelicPanel.currentPanel?.showError(err);
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
        }
    );

    // ── Re-open setup wizard command ─────────────────────────────────────
    let setupCmd = vscode.commands.registerCommand(
        'reporelic.openSetup',
        async () => {
            await context.globalState.update('reporelic.setupDone', false);
            SetupWizard.show(context);
        }
    );

    context.subscriptions.push(disposable, setupCmd);
}

export function deactivate() {}