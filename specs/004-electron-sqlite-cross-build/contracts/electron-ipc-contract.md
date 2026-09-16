# 接口契约 (Contract): Electron 主进程与渲染进程 IPC 通信协议

- **功能编号**: 004
- **特性名称**: `004-electron-sqlite-cross-build`

---

## 1. ContextBridge 接口类型定义 (`src/preload/index.d.ts`)

```typescript
export interface ElectronAPI {
  // 窗口控制
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  closeWindow: () => void;

  // 原生系统对话框与文件选择
  showOpenDialog: (options: {
    title?: string;
    filters?: Array<{ name: string; extensions: string[] }>;
    properties?: Array<'openFile' | 'openDirectory' | 'multiSelections'>;
  }) => Promise<{ canceled: boolean; filePaths: string[] }>;

  // 后台引擎状态查询
  getEngineStatus: () => Promise<{
    running: boolean;
    port: number;
    pid?: number;
    platform: 'win32' | 'darwin' | 'linux';
  }>;

  // 系统原生路径
  getAppPaths: () => Promise<{
    userData: string;
    downloads: string;
    desktop: string;
  }>;

  // 打开外部文件或系统目录
  openPathInExplorer: (fullPath: string) => Promise<string>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
```

---

## 2. IPC 通道定义与响应格式

| 通道名称 (Channel) | 调用方向 | 入参 | 响应格式 | 核心职责 |
| :--- | :--- | :--- | :--- | :--- |
| `window:minimize` | Renderer → Main | 无 | `void` | 最小化窗口 |
| `window:maximize` | Renderer → Main | 无 | `void` | 最大化/还原窗口 |
| `window:close` | Renderer → Main | 无 | `void` | 触发安全退出 |
| `dialog:open-files` | Renderer → Main (Invoke) | `DialogOptions` | `{ canceled: boolean, filePaths: string[] }` | 调用原生文件选择器挑选视频 |
| `engine:get-status` | Renderer → Main (Invoke) | 无 | `{ running: boolean, port: number, pid: number }` | 获取 Python 引擎健康状态 |
| `shell:open-path` | Renderer → Main (Invoke) | `{ path: string }` | `{ success: boolean, message?: string }` | 在资源管理器/访达中定位导出成片 |
