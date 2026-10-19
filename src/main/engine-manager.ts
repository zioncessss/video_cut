import { spawn, spawnSync, ChildProcess } from 'child_process';
import { existsSync, mkdirSync, copyFileSync, writeFileSync, unlinkSync, statSync, cpSync, chmodSync, readdirSync } from 'fs';
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
    // 资源根路径：打包态为 process.resourcesPath，开发态为项目根 resources
    const resourcesDir = app.isPackaged
      ? process.resourcesPath
      : resolve(projectRoot, 'resources');
    const sidecarDir = resolve(resourcesDir, 'engine', 'videocut-engine');
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

    // macOS/Linux 权限自愈防线：解压或打包可能丢失可执行权限 (+x)，运行时主动防御性补齐
    if (!isWin) {
      try {
        chmodSync(pythonExecutable, 0o755);
      } catch (permErr) {
        console.warn(`[EngineManager] 自动修复 pythonExecutable 执行权限失败:`, permErr);
      }
      if (useSidecar) {
        // 递归为 sidecar 目录下的所有文件添加可执行/可读权限，彻底杜绝 zip 解压丢失 +x 导致 dyld 报 Permission denied
        try {
          const makeExecutableRecursively = (dir: string) => {
            if (!existsSync(dir)) return;
            const entries = readdirSync(dir, { withFileTypes: true });
            for (const entry of entries) {
              const fullPath = resolve(dir, entry.name);
              try {
                chmodSync(fullPath, 0o755);
              } catch {}
              if (entry.isDirectory()) {
                makeExecutableRecursively(fullPath);
              }
            }
          };
          makeExecutableRecursively(sidecarDir);
        } catch (e) {
          console.warn(`[EngineManager] 递归修复 sidecarDir 权限异常:`, e);
        }

        const engineBin = resolve(resourcesDir, 'engine', 'bin');
        for (const binName of ['ffmpeg', 'ffprobe']) {
          const binPath = resolve(engineBin, binName);
          if (existsSync(binPath)) {
            try {
              chmodSync(binPath, 0o755);
            } catch (permErr) {
              console.warn(`[EngineManager] 自动修复 ${binName} 执行权限失败:`, permErr);
            }
          }
        }
      }
    }

    const cwd = app.isPackaged && process.platform === 'darwin' ? app.getPath('userData') : projectRoot;

    // macOS 架构主动防御检查：若在 Intel Mac 上运行了 arm64 sidecar，提前抛出明确提示
    if (process.platform === 'darwin' && useSidecar && existsSync(pythonExecutable)) {
      try {
        const fileCheck = spawnSync('file', [pythonExecutable], { encoding: 'utf-8' });
        const out = fileCheck.stdout || '';
        if (process.arch === 'x64' && out.includes('arm64') && !out.includes('x86_64')) {
          console.error('[EngineManager] 架构不匹配：当前为 Intel (x64) 系统，但内置引擎为 arm64 架构！');
          throw new Error('【芯片架构不匹配】当前 Mac 为 Intel (x86_64) 处理器，但安装了 Apple Silicon (arm64) 版安装包。请前往 GitHub Release 下载专属的 VideoCut-*-x64-mac.dmg 版本！');
        }
      } catch (err: any) {
        if (err.message && err.message.includes('芯片架构不匹配')) throw err;
      }
    }

    console.log(`[EngineManager] Starting Python engine (${useSidecar ? 'sidecar' : 'dev'}) using: ${pythonExecutable} on port ${this.port}`);

    // 存储目录铁律：数据优先存放在软件程序根目录的 storage 下，不在系统 C 盘 AppData 占用宝贵空间；
    // macOS 打包态（/Applications 或只读 AppTranslocation）直接写入标准用户数据区，防御 EROFS 只读报错
    let chosenStorage = (app.isPackaged && process.platform === 'darwin')
      ? resolve(app.getPath('userData'), 'storage')
      : resolve(projectRoot, 'storage');
    try {
      mkdirSync(chosenStorage, { recursive: true });
      const testFile = resolve(chosenStorage, '.write_probe');
      writeFileSync(testFile, 'ok');
      unlinkSync(testFile);
    } catch (permErr) {
      console.warn(`[EngineManager] 程序根目录 ${chosenStorage} 不可写（可能安装在 Program Files 且无管理员权限），自动降级使用用户可写数据目录:`, permErr);
      chosenStorage = resolve(app.getPath('userData'), 'storage');
      mkdirSync(chosenStorage, { recursive: true });
    }
    this.storageDir = chosenStorage;

    // 自愈与更新防丢机制：若当前数据目录中数据库为空或缺失（如更新后被抹除），自动从持久备份区恢复用户数据
    const persistentBackupDir = process.env.LOCALAPPDATA
      ? resolve(process.env.LOCALAPPDATA, 'videocut_persistent_storage')
      : '';
    const currentDb = resolve(this.storageDir, 'videocut.db');
    const isCurrentDbEmpty = !existsSync(currentDb) || (statSync(currentDb).size <= 90 * 1024);

    if (isCurrentDbEmpty) {
      // 多路径自动探查候选数据源：
      // 1. 系统独立持久存储区 (%LOCALAPPDATA%\videocut_persistent_storage)
      // 2. 之前记录的 active_storage_dir
      // 3. 用户数据目录 (app.getPath('userData')/storage)
      const candidateDirs: string[] = [];
      if (persistentBackupDir) {
        candidateDirs.push(persistentBackupDir);
        const activePtr = resolve(persistentBackupDir, 'active_storage_dir.txt');
        if (existsSync(activePtr)) {
          try {
            const hist = readFileSync(activePtr, 'utf-8').trim();
            if (hist && existsSync(hist)) candidateDirs.push(hist);
          } catch {}
        }
      }
      try {
        candidateDirs.push(resolve(app.getPath('userData'), 'storage'));
        if (!app.isPackaged) {
          candidateDirs.push(resolve(projectRoot, 'storage'));
          candidateDirs.push(resolve(projectRoot, '../../storage'));
        }
      } catch {}

      let bestCandidate: string | null = null;
      let maxDbSize = 90 * 1024;
      for (const cand of candidateDirs) {
        if (!existsSync(cand)) continue;
        if (resolve(cand) === resolve(this.storageDir)) continue;
        const candDb = resolve(cand, 'videocut.db');
        if (existsSync(candDb)) {
          const s = statSync(candDb).size;
          if (s > maxDbSize) {
            maxDbSize = s;
            bestCandidate = cand;
          }
        }
      }

      if (bestCandidate) {
        try {
          console.log(`[EngineManager] 当前数据目录为空，自动从数据源 ${bestCandidate} (DB大小: ${(maxDbSize / 1024).toFixed(1)}KB) 自愈恢复用户工程与素材...`);
          cpSync(bestCandidate, this.storageDir, { recursive: true });
          console.log(`[EngineManager] 用户数据自愈恢复完成！`);
          // 同时备份到持久备份区，建立金牌安全存档
          if (persistentBackupDir && resolve(bestCandidate) !== resolve(persistentBackupDir)) {
            mkdirSync(persistentBackupDir, { recursive: true });
            cpSync(bestCandidate, persistentBackupDir, { recursive: true });
            console.log(`[EngineManager] 已同步写入持久备份区 ${persistentBackupDir}`);
          }
        } catch (e) {
          console.warn('[EngineManager] 自动恢复备份数据失败:', e);
        }
      }
    }

    const env = {
      ...process.env,
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      VIDEOCUT_PORT: String(this.port),
      VIDEOCUT_HOST: '127.0.0.1',
      VIDEOCUT_STORAGE_DIR: this.storageDir
    };

    if (useSidecar) {
      // 确保存储目录就绪并安全同步初始词库与违禁词字典（如果目标目录尚不存在）
      try {
        mkdirSync(this.storageDir, { recursive: true });
        const defaultStorage = resolve(resourcesDir, 'default_storage');
        if (existsSync(defaultStorage)) {
          const glossarySrc = resolve(defaultStorage, 'glossary.json');
          const glossaryDst = resolve(this.storageDir, 'glossary.json');
          if (existsSync(glossarySrc) && !existsSync(glossaryDst)) {
            copyFileSync(glossarySrc, glossaryDst);
          }
          const bannedSrc = resolve(defaultStorage, 'banned_words.json');
          const bannedDst = resolve(this.storageDir, 'banned_words.json');
          if (existsSync(bannedSrc) && !existsSync(bannedDst)) {
            copyFileSync(bannedSrc, bannedDst);
          }
        }
      } catch (err) {
        console.warn('[EngineManager] Failed to seed default storage:', err);
      }
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
    if (isWin) {
      // Windows 环境：随包 ffmpeg/ffprobe 优先；若缺失则自动探测 WinGet、Chocolatey、Scoop 常见安装路径
      const userHome = process.env.USERPROFILE || '';
      const winCandidates = [
        resolve(resourcesDir, 'engine', 'bin'),
        resolve(projectRoot, 'resources', 'engine', 'bin'),
        resolve(userHome, 'AppData', 'Local', 'Microsoft', 'WinGet', 'Links'),
        'C:\\ProgramData\\chocolatey\\bin',
        resolve(userHome, 'scoop', 'shims'),
        'C:\\ffmpeg\\bin'
      ];
      const pathSep = ';';
      let currentPath = env.PATH || '';
      for (const p of winCandidates) {
        if (existsSync(p) && !currentPath.split(';').includes(p)) {
          currentPath = `${p}${pathSep}${currentPath}`;
        }
      }
      env.PATH = currentPath;
    } else if (useSidecar) {
      const engineBin = resolve(resourcesDir, 'engine', 'bin');
      env.PATH = `${engineBin}:${env.PATH ?? ''}`;
    }

    if (process.platform === 'darwin') {
      // macOS GUI 应用默认 PATH 缺少 Homebrew 与系统工具目录，补齐以防 codex/node/ffmpeg 探测失败
      const macBinPaths = ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'];
      const pathSep = ':';
      const currentPath = env.PATH || '';
      const toAdd = macBinPaths.filter((p) => !currentPath.split(':').includes(p) && existsSync(p));
      if (toAdd.length > 0) {
        env.PATH = `${currentPath}${currentPath ? pathSep : ''}${toAdd.join(pathSep)}`;
      }

      // 自动解除 macOS Gatekeeper 针对内部 engine 及 FFmpeg 二进制的隔离拦截属性 (com.apple.quarantine)
      try {
        const engineDir = resolve(resourcesDir, 'engine');
        if (existsSync(engineDir)) {
          spawnSync('xattr', ['-dr', 'com.apple.quarantine', engineDir], { stdio: 'ignore' });
        }
      } catch (_) {}
    }

    if (process.platform === 'darwin' || process.platform === 'linux') {
      // 深度防御：确保 sidecar 可执行文件及随包 FFmpeg 具备 0o755 执行权限（防范解压归档丢失 +x）
      try {
        if (existsSync(pythonExecutable)) {
          chmodSync(pythonExecutable, 0o755);
        }
        const engineBin = resolve(resourcesDir, 'engine', 'bin');
        if (existsSync(engineBin)) {
          const binFiles = readdirSync(engineBin);
          for (const bf of binFiles) {
            try {
              chmodSync(resolve(engineBin, bf), 0o755);
            } catch (_) {}
          }
        }
      } catch (err) {
        console.warn('[EngineManager] Failed to ensure executable permissions:', err);
      }
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

    let lastStderr = '';
    this.process.stdout?.on('data', (data) => {
      console.log(`[PythonEngine] ${data.toString().trim()}`);
    });

    this.process.stderr?.on('data', (data) => {
      const msg = data.toString().trim();
      lastStderr = (lastStderr + '\n' + msg).slice(-2000);
      console.error(`[PythonEngine Error] ${msg}`);
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
      if (!this.process) {
        break;
      }
    }
    // 真实执行铁律：引擎起不来必须显式抛错，由主进程弹窗告知用户，绝不静默降级开窗
    const detail = lastStderr ? `\n\n引擎报错明细：\n${lastStderr}` : '';
    throw new Error(`算力引擎在 ${timeoutMs / 1000}s 内未能就绪（端口 ${this.port}）。${detail}\n\n请检查 resources/engine 产物、系统架构兼容性或 .venv 开发环境后重启应用。`);
  }

  public static stopEngine(): void {
    if (this.storageDir) {
      try {
        const persistentBackupDir = process.env.LOCALAPPDATA
          ? resolve(process.env.LOCALAPPDATA, 'videocut_persistent_storage')
          : '';
        const currentDb = resolve(this.storageDir, 'videocut.db');
        if (persistentBackupDir && existsSync(currentDb) && statSync(currentDb).size > 90 * 1024) {
          mkdirSync(persistentBackupDir, { recursive: true });
          const syncFiles = ['videocut.db', 'videocut.db-wal', 'videocut.db-shm', 'settings.json', 'glossary.json', 'banned_words.json', 'materials_meta.json'];
          for (const f of syncFiles) {
            const src = resolve(this.storageDir, f);
            if (existsSync(src)) {
              cpSync(src, resolve(persistentBackupDir, f));
            }
          }
          const projDir = resolve(this.storageDir, 'projects');
          if (existsSync(projDir)) {
            cpSync(projDir, resolve(persistentBackupDir, 'projects'), { recursive: true });
          }
          writeFileSync(resolve(persistentBackupDir, 'active_storage_dir.txt'), this.storageDir, 'utf-8');
        }
      } catch (e) {
        console.warn('[EngineManager] 同步持久备份数据失败:', e);
      }
    }

    if (this.process && !this.process.killed) {
      console.log('[EngineManager] Gracefully shutting down Python engine...');
      try {
        if (process.platform === 'win32' && this.process.pid) {
          spawn('taskkill', ['/pid', String(this.process.pid), '/T', '/F']);
        } else {
          const proc = this.process;
          proc.kill('SIGTERM');
          setTimeout(() => {
            try {
              if (proc.pid && !proc.killed) {
                process.kill(proc.pid, 'SIGKILL');
              }
            } catch {}
          }, 1500);
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