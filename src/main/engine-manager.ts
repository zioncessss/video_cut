import { spawn, ChildProcess } from 'child_process';
import { existsSync } from 'fs';
import { resolve } from 'path';
import net from 'net';
import http from 'http';
import { app } from 'electron';

export class EngineManager {
  private static process: ChildProcess | null = null;
  private static port: number = 18888;
  private static apiBase: string = `http://127.0.0.1:${EngineManager.port}/api/v1`;
  private static storageDir: string = '';
  private static isChecking: boolean = false;

  /** 选取一个空闲端口（sidecar 动态端口通信，见 specs/004 research.md） */
  private static pickFreePort(): Promise<number> {
    return new Promise((res, rej) => {
      const srv = net.createServer();
      srv.listen(0, '127.0.0.1', () => {
        const addr = srv.address();
        const port = typeof addr === 'object' && addr ? addr.port : 18888;
        srv.close(() => res(port));
      });
      srv.on('error', rej);
    });
  }

  /** 渲染层 API 基地址（preload 经 IPC 同步获取） */
  public static getApiBase(): string {
    return this.apiBase;
  }

  public static getStorageDir(): string {
    return this.storageDir;
  }

  public static async isEngineRunning(): Promise<boolean> {
    const checkPath = (path: string): Promise<boolean> => {
      return new Promise((res) => {
        const req = http.get(`http://127.0.0.1:${this.port}${path}`, (response) => {
          res(response.statusCode === 200);
        });
        req.on('error', () => res(false));
        req.setTimeout(1000, () => {
          req.destroy();
          res(false);
        });
      });
    };

    const healthyV1 = await checkPath('/api/v1/health');
    if (healthyV1) return true;
    return await checkPath('/api/health');
  }

  public static async startEngine(projectRoot: string): Promise<void> {
    if (await this.isEngineRunning()) {
      console.log(`[EngineManager] Python engine already running on port ${this.port}`);
      this.apiBase = `http://127.0.0.1:${this.port}/api/v1`;
      return;
    }

    const isWin = process.platform === 'win32';
    // 双模式：打包形态优先 resources/engine/videocut-engine/（onedir 产物）；开发态回退 .venv uvicorn
    const sidecarDir = resolve(projectRoot, 'resources', 'engine', 'videocut-engine');
    const sidecarPath = resolve(sidecarDir, isWin ? 'videocut-engine.exe' : 'videocut-engine');
    const useSidecar = (app.isPackaged || process.env.FORCE_SIDECAR === '1') && existsSync(sidecarPath);

    // 动态空闲端口：避免固定端口被占用导致引擎静默起不来
    try {
      this.port = await this.pickFreePort();
    } catch {
      this.port = 18888;
    }
    this.apiBase = `http://127.0.0.1:${this.port}/api/v1`;

    const venvPython = isWin
      ? resolve(projectRoot, '.venv/Scripts/python.exe')
      : resolve(projectRoot, '.venv/bin/python');
    const pythonExecutable = useSidecar ? sidecarPath : venvPython;
    if (!existsSync(pythonExecutable)) {
      // 真实执行铁律：引擎不存在必须显式报错，绝不静默降级开白窗
      throw new Error(`未找到算力引擎：既无 sidecar 产物 (${sidecarPath})，也无开发环境 (${venvPython})`);
    }
    const cwd = projectRoot;

    console.log(`[EngineManager] Starting Python engine (${useSidecar ? 'sidecar' : 'dev'}) using: ${pythonExecutable} on port ${this.port}`);

    const env = {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      VIDEOCUT_PORT: String(this.port),
      VIDEOCUT_HOST: '127.0.0.1'
    };
    if (useSidecar) {
      // 便携数据目录：安装根下 storage/（已决策数据不迁 userData）
      this.storageDir = resolve(projectRoot, 'storage');
      env.VIDEOCUT_STORAGE_DIR = this.storageDir;
    } else {
      env.PYTHONPATH = resolve(projectRoot, 'backend');
    }

    // Windows 下设置 windowsHide: true 且无黑框；sidecar 模式直接运行可执行入口
    const uvicornArgs = useSidecar
      ? []
      : ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(this.port)];
    if (!useSidecar && process.env.NODE_ENV !== 'production') {
      uvicornArgs.push('--reload');
    }
    if (useSidecar) {
      // sidecar 模式：随包 ffmpeg/ffprobe 优先于系统 PATH
      const engineBin = resolve(sidecarDir, 'bin');
      env.PATH = `${engineBin};${env.PATH ?? ''}`;
    }

    this.process = spawn(
      pythonExecutable,
      uvicornArgs,
      {
        cwd,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
        detached: false
      }
    );

    this.process.stdout?.on('data', (data) => {
      console.log(`[PythonEngine] ${data.toString().trim()}`);
    });

    this.process.stderr?.on('data', (data) => {
      console.error(`[PythonEngine Error] ${data.toString().trim()}`);
    });

    this.process.on('exit', (code) => {
      console.log(`[EngineManager] Python engine exited with code ${code}`);
      this.process = null;
    });

    // 轮询等待就绪（sidecar 冷启动含模型初始化，放宽到 30 秒）
    const timeoutMs = useSidecar ? 30000 : 15000;
    const startWait = Date.now();
    while (Date.now() - startWait < timeoutMs) {
      await new Promise((r) => setTimeout(r, 500));
      if (await this.isEngineRunning()) {
        console.log(`[EngineManager] Python engine is now healthy and ready on ${this.apiBase}`);
        return;
      }
    }
    // 真实执行铁律：引擎起不来必须显式抛错，由主进程弹窗告知用户，绝不静默降级开窗
    throw new Error(`算力引擎在 ${timeoutMs / 1000}s 内未就绪（端口 ${this.port}）。请检查 resources/engine 引擎产物或 .venv 开发环境后重启应用。`);
  }

  public static stopEngine(): void {
    if (this.process && !this.process.killed) {
      console.log('[EngineManager] Gracefully shutting down Python engine...');
      try {
        if (process.platform === 'win32' && this.process.pid) {
          spawn('taskkill', ['/pid', String(this.process.pid), '/T', '/F']);
        } else {
          this.process.kill('SIGTERM');
        }
      } catch (err) {
        console.error('[EngineManager] Failed to terminate engine process:', err);
      }
      this.process = null;
    }
  }

  public static getPort(): number {
    return this.port;
  }

  public static getPid(): number | undefined {
    return this.process?.pid;
  }
}