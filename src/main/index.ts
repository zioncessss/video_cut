import { app, BrowserWindow, shell, Tray, Menu, dialog } from 'electron';
import { join, resolve } from 'path';
import { is } from '@electron-toolkit/utils';
import { EngineManager } from './engine-manager';
import { registerIpcHandlers } from './ipc-handlers';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

// 单实例锁：二次启动时聚焦已有窗口（T015 托盘安全策略的一部分）
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

function getIconPath(): string {
  // 打包态 icon 在 resources/；开发态在项目根 resources/
  return app.isPackaged
    ? join(process.resourcesPath, 'icon.png')
    : resolve(__dirname, '../../resources/icon.png');
}

function createTray(): void {
  try {
    tray = new Tray(getIconPath());
    tray.setToolTip('VideoCut 智能剪辑');
    const menu = Menu.buildFromTemplate([
      {
        label: '显示主窗口',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          } else {
            createWindow();
          }
        }
      },
      {
        label: '打开成片目录',
        click: () => {
          shell.openPath(EngineManager.getStorageDir() || resolve(process.cwd(), 'storage'));
        }
      },
      { type: 'separator' },
      {
        label: '退出并停止引擎',
        click: () => {
          app.quit();
        }
      }
    ]);
    tray.setContextMenu(menu);
    tray.on('double-click', () => {
      mainWindow?.show();
    });
  } catch (err) {
    console.error('[Main] Tray init failed:', err);
  }
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1380,
    height: 900,
    minWidth: 1080,
    minHeight: 700,
    show: false,
    autoHideMenuBar: true,
    frame: false,
    backgroundColor: '#F8FAFC',
    icon: getIconPath(),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false // 允许本地视频与切片安全读取
    }
  });

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url);
    return { action: 'deny' };
  });

  registerIpcHandlers(mainWindow);

  // 加载页面
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL']);
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'));
  }
}

app.whenReady().then(async () => {
  const projectRoot = app.isPackaged
    ? resolve(process.resourcesPath, '..')
    : resolve(__dirname, '../../');

  // 静默启动或检查 Python 算力引擎（真实执行铁律：失败必须显式告知，绝不静默开白窗）
  try {
    await EngineManager.startEngine(projectRoot);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    dialog.showErrorBox('算力引擎启动失败', `${message}\n\n请确认引擎产物 resources/engine/ 完整后重试。`);
    app.quit();
    return;
  }

  createWindow();
  createTray();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  EngineManager.stopEngine();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  EngineManager.stopEngine();
});
