import { app, BrowserWindow, shell, Tray, Menu, dialog, nativeImage } from 'electron';
import { join, resolve } from 'path';
import { is, electronApp } from '@electron-toolkit/utils';
import { EngineManager } from './engine-manager';
import { registerIpcHandlers } from './ipc-handlers';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

// 设置 Windows 下的 AppUserModelId（极为关键：确保 Windows 任务栏显示正确图标，而非 Electron 默认原子图标）
if (process.platform === 'win32') {
  electronApp.setAppUserModelId('com.videocut.desktop');
  app.setAppUserModelId('com.videocut.desktop');
}

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
  const isWin = process.platform === 'win32';
  const iconName = isWin ? 'icon.ico' : 'icon.png';
  return app.isPackaged
    ? join(process.resourcesPath, iconName)
    : resolve(__dirname, '../../resources', iconName);
}

function getAppIcon(): Electron.NativeImage {
  const iconPath = getIconPath();
  const icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) {
    // 兜底尝试 png
    const fallbackPath = app.isPackaged
      ? join(process.resourcesPath, 'icon.png')
      : resolve(__dirname, '../../resources/icon.png');
    return nativeImage.createFromPath(fallbackPath);
  }
  return icon;
}

function createTray(): void {
  try {
    let icon = getAppIcon();
    if (process.platform === 'darwin') {
      icon = icon.resize({ width: 18, height: 18 });
    }
    tray = new Tray(icon);
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
  const appIcon = getAppIcon();
  mainWindow = new BrowserWindow({
    width: 1380,
    height: 900,
    minWidth: 1080,
    minHeight: 700,
    show: false,
    autoHideMenuBar: true,
    frame: false,
    backgroundColor: '#F8FAFC',
    icon: appIcon,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false // 允许本地视频与切片安全读取
    }
  });

  if (process.platform === 'win32') {
    mainWindow.setIcon(appIcon);
  }

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

function setupApplicationMenu(): void {
  if (process.platform === 'darwin') {
    const template: Electron.MenuItemConstructorOptions[] = [
      {
        label: app.name,
        submenu: [
          { role: 'about' },
          { type: 'separator' },
          { role: 'services' },
          { type: 'separator' },
          { role: 'hide' },
          { role: 'hideOthers' },
          { role: 'unhide' },
          { type: 'separator' },
          { role: 'quit' }
        ]
      },
      {
        label: 'Edit',
        submenu: [
          { role: 'undo' },
          { role: 'redo' },
          { type: 'separator' },
          { role: 'cut' },
          { role: 'copy' },
          { role: 'paste' },
          { role: 'selectAll' }
        ]
      },
      {
        label: 'View',
        submenu: [
          { role: 'reload' },
          { role: 'forceReload' },
          { role: 'toggleDevTools' },
          { type: 'separator' },
          { role: 'resetZoom' },
          { role: 'zoomIn' },
          { role: 'zoomOut' },
          { type: 'separator' },
          { role: 'togglefullscreen' }
        ]
      },
      {
        label: 'Window',
        submenu: [
          { role: 'minimize' },
          { role: 'zoom' },
          { type: 'separator' },
          { role: 'front' },
          { type: 'separator' },
          { role: 'close' }
        ]
      }
    ];
    Menu.setApplicationMenu(Menu.buildFromTemplate(template));
  }
}

app.whenReady().then(async () => {
  setupApplicationMenu();
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

  app.on('activate', async function () {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (!await EngineManager.isEngineRunning()) {
        try {
          await EngineManager.startEngine(projectRoot);
        } catch (e) {
          console.error('[Main] Activate startEngine failed:', e);
        }
      }
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  EngineManager.stopEngine();
  app.quit();
});

app.on('before-quit', () => {
  EngineManager.stopEngine();
});
