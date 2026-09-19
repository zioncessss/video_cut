import React, { useState, useEffect } from 'react';
import { AssetLibrary } from './pages/AssetLibrary';
import { VideoEditor } from './pages/VideoEditor';
import { BatchCut } from './pages/BatchCut';
import { Settings } from './pages/Settings';
import { HarnessChatDrawer } from './components/HarnessChatDrawer';
import { Folder, Film, Layers, Settings as SettingsIcon, Sparkles, Minus, Square, X } from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'library' | 'editor' | 'batch' | 'settings'>('library');
  const [selectedTalkingHeadId, setSelectedTalkingHeadId] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [isChatDrawerOpen, setIsChatDrawerOpen] = useState<boolean>(false);
  const [strategyPlan, setStrategyPlan] = useState<{
    explanation: string;
    updated_subtitles?: any[];
    updated_brolls?: any[];
  } | null>(null);

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

  const handleApplyStrategy = (plan: any) => {
    setStrategyPlan(plan);
    // 如果当前不在工作台，自动切换回工作台以便用户直观看到修改
    if (currentTab !== 'editor') {
      setCurrentTab('editor');
    }
  };

  return (
    <div className="h-screen bg-[#F8FAFC] text-gray-900 flex flex-col font-sans antialiased selection:bg-blue-100 selection:text-blue-900 overflow-hidden">
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

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 text-xs text-gray-400 mr-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="font-mono text-[11px] text-gray-500">
              {window.electronAPI ? 'Desktop Engine Ready' : 'Web Engine Ready'}
            </span>
          </div>

          {/* Harness 对话副驾驶主唤起按钮（顶部常驻，绝不遮挡底部工作台任何操作） */}
          <button
            onClick={() => setIsChatDrawerOpen((prev) => !prev)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer active:scale-95 ${
              isChatDrawerOpen
                ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm'
                : 'bg-white hover:bg-blue-50 text-blue-700 border border-blue-200/80 shadow-xs'
            }`}
            title="打开/收起 Harness 创意与剪辑副驾驶"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-500 animate-pulse" />
            <span>对话副驾驶</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-100/80 text-blue-800 font-mono">GLM</span>
          </button>

          {/* Electron 原生窗口控制按钮组 */}
          {window.electronAPI && (
            <div className="flex items-center space-x-1 border-l border-gray-200 pl-3">
              <button
                onClick={() => window.electronAPI?.minimizeWindow()}
                title="最小化"
                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors cursor-pointer"
              >
                <Minus className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => window.electronAPI?.maximizeWindow()}
                title="最大化 / 还原"
                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors cursor-pointer"
              >
                <Square className="w-3 h-3" />
              </button>
              <button
                onClick={() => window.electronAPI?.closeWindow()}
                title="关闭"
                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </header>

      {/* 主体页面渲染 */}
      <main className={`flex-1 ${currentTab === 'editor' ? 'overflow-hidden' : 'overflow-auto'}`}>
        {currentTab === 'library' && (
          <AssetLibrary
            onSelectForEditor={(matId) => {
              setSelectedTalkingHeadId(matId);
              setCurrentTab('editor');
            }}
          />
        )}
        {currentTab === 'editor' && (
          <VideoEditor
            initialProjectId={activeProjectId}
            initialSelectedTalkingHeadId={selectedTalkingHeadId}
            onProjectLoaded={(pid) => setActiveProjectId(pid)}
            externalStrategyPlan={strategyPlan}
            onOpenChatDrawer={() => setIsChatDrawerOpen(true)}
          />
        )}
        {currentTab === 'batch' && (
          <BatchCut
            onNavigateToEditor={(projId, matId) => {
              if (matId) setSelectedTalkingHeadId(matId);
              setActiveProjectId(projId);
              setCurrentTab('editor');
            }}
          />
        )}
        {currentTab === 'settings' && <Settings />}
      </main>

      {/* 全局常驻 Harness 对话副驾驶抽屉 */}
      <HarnessChatDrawer
        currentProjectId={activeProjectId}
        onApplyStrategyToProject={handleApplyStrategy}
        isOpen={isChatDrawerOpen}
        onOpenChange={setIsChatDrawerOpen}
        showFloatingTrigger={false}
      />
    </div>
  );
};
