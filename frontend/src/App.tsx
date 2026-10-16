import React, { useState, useEffect } from 'react';
import { AssetLibrary } from './pages/AssetLibrary';
import { VideoEditor } from './pages/VideoEditor';
import { BatchCut } from './pages/BatchCut';
import { ComplianceWords } from './pages/ComplianceWords';
import { Settings } from './pages/Settings';
import { DialogProvider } from './components/common/CustomDialog';
import appLogo from './assets/icon.png';
import { Folder, Film, Layers, ShieldCheck, Settings as SettingsIcon, Minus, Square, Copy, X } from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'library' | 'editor' | 'batch' | 'compliance' | 'settings'>('editor');
  const [selectedTalkingHeadId, setSelectedTalkingHeadId] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [isMaximized, setIsMaximized] = useState<boolean>(false);

  // 监听 Electron 窗口最大化/还原状态
  useEffect(() => {
    if (window.electronAPI?.isMaximized) {
      window.electronAPI.isMaximized().then(setIsMaximized).catch(() => {});
    }
    if (window.electronAPI?.onMaximizedChange) {
      const unsubscribe = window.electronAPI.onMaximizedChange((max) => {
        setIsMaximized(max);
      });
      return () => {
        if (typeof unsubscribe === 'function') unsubscribe();
      };
    }
  }, []);

  // 全局防御：防止浏览器在页面任何区域被拖入文件时执行默认的“跳转并打开视频”行为
  useEffect(() => {
    const preventWindowDrop = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('dragover', preventWindowDrop);
    window.addEventListener('drop', preventWindowDrop);
    return () => {
      window.removeEventListener('dragover', preventWindowDrop);
      window.removeEventListener('drop', preventWindowDrop);
    };
  }, []);

  const navItems = [
    { id: 'library', label: '素材库', icon: Folder },
    { id: 'editor', label: '剪辑工作台', icon: Film },
    { id: 'batch', label: '批量混剪', icon: Layers },
    { id: 'compliance', label: '词库管理', icon: ShieldCheck },
    { id: 'settings', label: '设置', icon: SettingsIcon },
  ];

  return (
    <DialogProvider>
      <div className="h-screen bg-[#F8FAFC] text-gray-900 flex flex-col font-sans antialiased selection:bg-blue-100 selection:text-blue-900 overflow-hidden">
        {/* 顶部现代化浅色无边框沉浸式导航栏 */}
        <header
          onDoubleClick={(e) => {
            if ((e.target as HTMLElement).closest('.app-no-drag')) return;
            window.electronAPI?.maximizeWindow();
          }}
          className="app-drag-region h-16 bg-white/80 backdrop-blur-md border-b border-gray-200/80 sticky top-0 z-50 px-6 flex items-center justify-between select-none"
        >
          {/* 统一软件图标与品牌 */}
          <div className="app-no-drag flex items-center space-x-3">
            <img
              src={appLogo}
              alt="VideoCut"
              className="w-8 h-8 object-contain drop-shadow-sm select-none pointer-events-none"
            />
            <div>
              <span className="font-bold text-sm tracking-tight text-gray-900">VideoCut</span>
              <span className="ml-1.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-200/60 font-mono">
                {window.electronAPI ? 'Desktop' : 'Web'}
              </span>
            </div>
          </div>

          {/* 核心导航标签 */}
          <nav className="app-no-drag flex items-center space-x-1 bg-gray-100/80 p-1 rounded-xl border border-gray-200/60">
            {navItems.map(item => {
              const Icon = item.icon;
              const active = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentTab(item.id as any)}
                  className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    active
                      ? 'bg-white text-blue-600 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <div className="app-no-drag flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs text-gray-400 mr-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="font-mono text-[11px] text-gray-500">
                {window.electronAPI ? 'Desktop Engine Ready' : 'Web Engine Ready'}
              </span>
            </div>

            {/* Electron 无边框窗口控制按钮组 */}
            {window.electronAPI && (
              <div className="flex items-center space-x-1 border-l border-gray-200 pl-3">
                <button
                  type="button"
                  onClick={() => window.electronAPI?.minimizeWindow()}
                  title="最小化"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors cursor-pointer"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => window.electronAPI?.maximizeWindow()}
                  title={isMaximized ? "还原" : "最大化"}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors cursor-pointer"
                >
                  {isMaximized ? (
                    <Copy className="w-3 h-3 rotate-180" />
                  ) : (
                    <Square className="w-3 h-3" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => window.electronAPI?.closeWindow()}
                  title="关闭"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-white hover:bg-red-600 transition-colors cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </header>

      {/* 主体页面渲染 (常驻保活容器，杜绝切路由导致工作台重置与未保存数据丢失) */}
      <main className="flex-1 relative overflow-hidden min-h-0">
        <div className={`h-full w-full overflow-auto ${currentTab === 'library' ? '' : 'hidden'}`}>
          <AssetLibrary
            isActive={currentTab === 'library'}
            onSelectForEditor={(matId) => {
              setSelectedTalkingHeadId(matId);
              setActiveProjectId(null);
              setCurrentTab('editor');
            }}
            onNavigateToBatch={() => setCurrentTab('batch')}
          />
        </div>
        <div className={`h-full w-full overflow-hidden ${currentTab === 'editor' ? '' : 'hidden'}`}>
          <VideoEditor
            isActive={currentTab === 'editor'}
            initialProjectId={activeProjectId}
            initialSelectedTalkingHeadId={selectedTalkingHeadId}
            onProjectLoaded={(pid) => setActiveProjectId(pid)}
            onTalkingHeadChanged={(thId) => setSelectedTalkingHeadId(thId)}
          />
        </div>
        <div className={`h-full w-full overflow-auto ${currentTab === 'batch' ? '' : 'hidden'}`}>
          <BatchCut
            onNavigateToEditor={(projId, matId) => {
              if (matId) setSelectedTalkingHeadId(matId);
              setActiveProjectId(projId);
              setCurrentTab('editor');
            }}
          />
        </div>
        <div className={`h-full w-full overflow-auto ${currentTab === 'compliance' ? '' : 'hidden'}`}>
          <ComplianceWords />
        </div>
        <div className={`h-full w-full overflow-auto ${currentTab === 'settings' ? '' : 'hidden'}`}>
          <Settings />
        </div>
      </main>
      </div>
    </DialogProvider>
  );
};
