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
  /** sidecar 动态端口解析出的 API 基地址（preload 阶段同步获取） */
  apiBase: string;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}