import { contextBridge, ipcRenderer } from 'electron';

export interface ElectronAPI {
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  closeWindow: () => void;
  showOpenDialog: (options?: {
    title?: string;
    filters?: Array<{ name: string; extensions: string[] }>;
    properties?: Array<'openFile' | 'openDirectory' | 'multiSelections'>;
  }) => Promise<{ canceled: boolean; filePaths: string[] }>;
  getEngineStatus: () => Promise<{
    running: boolean;
    port: number;
    pid?: number;
    platform: 'win32' | 'darwin' | 'linux';
  }>;
  getAppPaths: () => Promise<{
    userData: string;
    downloads: string;
    desktop: string;
  }>;
  openPathInExplorer: (fullPath: string) => Promise<{ success: boolean; message?: string }>;
  apiBase: string;
}

const api: ElectronAPI = {
  minimizeWindow: () => ipcRenderer.send('window:minimize'),
  maximizeWindow: () => ipcRenderer.send('window:maximize'),
  closeWindow: () => ipcRenderer.send('window:close'),
  showOpenDialog: (options) => ipcRenderer.invoke('dialog:open-files', options),
  getEngineStatus: () => ipcRenderer.invoke('engine:get-status'),
  getAppPaths: () => ipcRenderer.invoke('app:get-paths'),
  openPathInExplorer: (fullPath: string) => ipcRenderer.invoke('shell:open-path', fullPath),
  // sidecar 动态端口：preload 阶段一次性同步获取，渲染层所有请求以此为准
  apiBase: ipcRenderer.sendSync('app:api-base-sync')
};

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electronAPI', api);
  } catch (error) {
    console.error(error);
  }
} else {
  // @ts-ignore
  window.electronAPI = api;
}