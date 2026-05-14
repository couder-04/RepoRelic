import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export interface PythonRunnerOptions {
    pythonPath?: string;
    env?: NodeJS.ProcessEnv;
}

export class PythonRunner {
    private engineDir: string;
    private targetPath: string;
    private options: PythonRunnerOptions;
    private process?: ChildProcess;

    private progressCallback?: (msg: any) => void;
    private completeCallback?: (reportPath: string) => void;
    private errorCallback?: (err: string) => void;
    private permissionCallback?: (msg: any) => void;

    constructor(engineDir: string, targetPath: string, options: PythonRunnerOptions = {}) {
        this.engineDir = engineDir;
        this.targetPath = targetPath;
        this.options = options;
    }

    onProgress(cb: (msg: any) => void) { this.progressCallback = cb; }
    onComplete(cb: (reportPath: string) => void) { this.completeCallback = cb; }
    onError(cb: (err: string) => void) { this.errorCallback = cb; }
    onPermissionRequest(cb: (msg: any) => void) { this.permissionCallback = cb; }

    start() {
        const repoRoot = path.dirname(this.engineDir);

        const pythonCmd = this.options.pythonPath && this.options.pythonPath.trim()
            ? this.options.pythonPath
            : (() => {
                const isPythonExecutable = (p: string): boolean => {
                    try {
                        const stat = fs.statSync(p);
                        if (stat.isFile() || stat.isSymbolicLink()) {
                            fs.accessSync(p, fs.constants.X_OK);
                            return true;
                        }
                        return false;
                    } catch { return false; }
                };

                const repoVenv = path.join(repoRoot, '.venv', 'bin', 'python3');
                if (isPythonExecutable(repoVenv)) return repoVenv;

                return process.platform === 'darwin' ? 'python3' : 'python';
            })();

        const env = {
            ...process.env,
            ...(this.options.env ?? {}),
            PYTHONUNBUFFERED: '1',
        };

        console.log('RepoRelic spawning:', pythonCmd, 'cwd:', repoRoot, 'target:', this.targetPath);

        this.process = spawn(pythonCmd, ['-m', 'engine', this.targetPath], {
            cwd: repoRoot,
            env,
        });

        // Initial debug message to webview
        this.progressCallback?.({
            type: 'progress', stage: 1, status: 'running',
            message: 'Python engine started',
        });

        // ── STDOUT ──────────────────────────────────────────────────────
        let stdoutBuffer = '';

        this.process.stdout?.on('data', (data: Buffer) => {
            stdoutBuffer += data.toString();
            const lines = stdoutBuffer.split('\n');
            stdoutBuffer = lines.pop() || '';

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;
                try {
                    const msg = JSON.parse(trimmed);
                    this.handleMessage(msg);
                } catch {
                    // Forward non-JSON lines as progress messages
                    this.progressCallback?.({
                        type: 'progress', stage: 1, status: 'running',
                        message: trimmed,
                    });
                }
            }
        });

        // ── STDERR ──────────────────────────────────────────────────────
        this.process.stderr?.on('data', (data: Buffer) => {
            const msg = data.toString();

            // Ignore known harmless warnings
            const isWarning =
                msg.includes('UserWarning') ||
                msg.includes('DeprecationWarning') ||
                msg.includes('FutureWarning') ||
                msg.includes('pkg_resources') ||
                msg.includes('pygame') ||
                msg.includes('Hello from the pygame') ||
                msg.includes('ExperimentalWarning') ||
                msg.includes('punycode');

            if (isWarning) {
                console.log('stderr (ignored warning):', msg.trim());
                return;
            }

            console.error('PYTHON STDERR:', msg);

            // Show real errors in webview log
            this.progressCallback?.({
                type: 'progress', stage: 1, status: 'running',
                message: `[stderr] ${msg.trim()}`,
            });
        });

        // ── PROCESS EXIT ────────────────────────────────────────────────
        this.process.on('close', (code) => {
            console.log('RepoRelic process closed with code:', code);

            // Flush any remaining buffered output
            if (stdoutBuffer.trim()) {
                try {
                    const msg = JSON.parse(stdoutBuffer.trim());
                    this.handleMessage(msg);
                } catch {
                    this.progressCallback?.({
                        type: 'progress', stage: 1, status: 'running',
                        message: stdoutBuffer.trim(),
                    });
                }
            }

            if (code !== 0) {
                this.errorCallback?.(`Process exited with code ${code}`);
            }
        });

        // ── PROCESS ERROR ───────────────────────────────────────────────
        this.process.on('error', (err) => {
            console.error('Failed to start process:', err);
            this.errorCallback?.(`Failed to start Python engine: ${err.message}`);
        });
    }

    sendPermissionResponse(approved: boolean) {
        if (this.process && this.process.stdin) {
            this.process.stdin.write(JSON.stringify({ approved }) + '\n');
        }
    }

    stop() {
        if (this.process) {
            this.process.kill();
            this.process = undefined;
        }
    }

    private handleMessage(msg: any) {
        switch (msg.type) {
            case 'progress':
                this.progressCallback?.(msg);
                break;
            case 'complete':
                this.completeCallback?.(msg.report_path);
                break;
            case 'permission':
                this.permissionCallback?.(msg);
                break;
            case 'error':
                this.errorCallback?.(msg.message);
                break;
            default:
                this.progressCallback?.({
                    type: 'progress', stage: 1, status: 'running',
                    message: JSON.stringify(msg),
                });
        }
    }
}