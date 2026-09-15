import React, { useState, useEffect } from 'react';
import { AssetLibrary } from './pages/AssetLibrary';
import { VideoEditor } from './pages/VideoEditor';
import { BatchCut } from './pages/BatchCut';
import { Settings } from './pages/Settings';
import { Folder, Film, Layers, Settings as SettingsIcon, Sparkles } from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'library' | 'editor' | 'batch' | 'settings'>('library');

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
    { id: 'settings', label: '设置', icon: SettingsIcon },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-gray-900 flex flex-col font-sans antialiased selection:bg-blue-100 selection:text-blue-900">
      {/* 顶部现代化浅色导航栏 */}
      <header className="h-16 bg-white/80 backdrop-blur-md border-b border-gray-200/80 sticky top-0 z-50 px-6 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold text-sm tracking-tight text-gray-900">VideoCut</span>
            <span className="ml-1.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-200/60 font-mono">Harness Web</span>
          </div>
        </div>

        {/* 核心导航标签 */}
        <nav className="flex items-center space-x-1 bg-gray-100/80 p-1 rounded-xl border border-gray-200/60">
          {navItems.map(item => {
            const Icon = item.icon;
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id as any)}
                className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
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

        <div className="flex items-center space-x-2 text-xs text-gray-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="font-mono text-[11px] text-gray-500">Engine Ready</span>
        </div>
      </header>

      {/* 主体页面渲染 */}
      <main className="flex-1 overflow-auto">
        {currentTab === 'library' && <AssetLibrary />}
        {currentTab === 'editor' && <VideoEditor />}
        {currentTab === 'batch' && <BatchCut />}
        {currentTab === 'settings' && <Settings />}
      </main>
    </div>
  );
};
