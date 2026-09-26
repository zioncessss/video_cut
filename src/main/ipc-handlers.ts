import { ipcMain, dialog, shell, BrowserWindow, app } from 'electron';
import { resolve, isAbsolute } from 'path';
import { EngineManager } from './engine-manager';

export function registerIpcHandlers(mainWindow: BrowserWindow): void {
  // 窗口控制
  ipcMain.on('window:minimize', () => {
    mainWindow.minimize();
  });

  ipcMain.on('window:maximize', () => {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  });

  ipcMain.on('window:close', () => {
    mainWindow.close();
  });

  ipcMain.handle('window:is-maximized', () => {
    return mainWindow.isMaximized();
  });

  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window:maximized-change', true);
  });

  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window:maximized-change', false);
  });

  // 原生系统对话框
  ipcMain.handle('dialog:open-files', async (_event, options) => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: options?.title || '选择视频素材文件',
      filters: options?.filters || [
        { name: 'Video Files', extensions: ['mp4', 'mov', 'mkv', 'avi', 'flv'] },
        { name: 'All Files', extensions: ['*'] }
      ],
      properties: options?.properties || ['openFile', 'multiSelections']
    });
    return { canceled: res.canceled, filePaths: res.filePaths };
  });

  // 渲染层 API 基地址（sidecar 动态端口经此同步给前端，一次性 sendSync 开销可忽略）
  ipcMain.on('app:api-base-sync', (event) => {
    event.returnValue = EngineManager.getApiBase();
  });

  // 后台引擎状态
  ipcMain.handle('engine:get-status', async () => {
    const running = await EngineManager.isEngineRunning();
    return {
      running,
      port: EngineManager.getPort(),
      pid: EngineManager.getPid(),
      platform: process.platform as 'win32' | 'darwin' | 'linux'
    };
  });

  // 获取系统原生路径
  ipcMain.handle('app:get-paths', async () => {
    return {
      userData: app.getPath('userData'),
      downloads: app.getPath('downloads'),
      desktop: app.getPath('desktop')
    };
  });

  // 在系统资源管理器/访达中打开文件或目录
  ipcMain.handle('shell:open-path', async (_event, fullPath: string) => {
    try {
      const storageDir = EngineManager.getStorageDir();
      const storageParent = storageDir ? resolve(storageDir, '..') : (app.isPackaged ? resolve(app.getPath('userData')) : resolve(__dirname, '../../'));
      let target = fullPath;
      if (!isAbsolute(fullPath)) {
        if (fullPath.startsWith('storage')) {
          target = resolve(storageParent, fullPath);
        } else if (storageDir) {
          target = resolve(storageDir, fullPath);
        } else {
          target = resolve(storageParent, fullPath);
        }
      }
      const err = await shell.openPath(target);
      return { success: !err, message: err };
    } catch (e: any) {
      return { success: false, message: e.message };
    }
  });
}