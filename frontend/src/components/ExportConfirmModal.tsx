import React, { useState, useEffect } from 'react';
import { 
  X, 
  ShieldAlert, 
  CheckCircle2, 
  Film, 
  Sparkles, 
  ChevronDown, 
  ChevronUp, 
  AlertCircle,
  Image as ImageIcon,
  Check,
  Folder,
  FolderOpen
} from 'lucide-react';
import { 
  BannedWordsCheckResult, 
  CoverDesignConfig, 
  SuggestedCoverTitle,
  setProjectCover 
} from '../services/api';
import { CoverPreviewSelector } from './CoverPreviewSelector';

interface ExportConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (
    filterBannedWords: boolean,
    coverConfig?: CoverDesignConfig,
    exportDir?: string,
    includeCover?: boolean,
    embedCover?: boolean
  ) => void;
  bannedWordsCheck: BannedWordsCheckResult | null;
  isChecking: boolean;
  isRendering: boolean;
  videoSpeed?: number;
  projectId?: string;
  initialCoverConfig?: Partial<CoverDesignConfig>;
  suggestedTitles?: SuggestedCoverTitle[];
  currentVideoTime?: number;
  embedCoverAsFirstFrame?: boolean;
  onToggleEmbedFirstFrame?: (embed: boolean) => void;
  projectTitle?: string;
}

export const ExportConfirmModal: React.FC<ExportConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  bannedWordsCheck,
  isChecking,
  isRendering,
  videoSpeed = 1.0,
  projectId = '',
  initialCoverConfig,
  suggestedTitles = [],
  currentVideoTime = 0,
  embedCoverAsFirstFrame = true,
  onToggleEmbedFirstFrame,
  projectTitle = '',
}) => {
  const [exportDir, setExportDir] = useState<string>(() => {
    try {
      return localStorage.getItem('videocut_export_dir') || '';
    } catch {
      return '';
    }
  });

  // 当弹窗打开时，若有已保存的历史导出路径，自动同步并使用
  useEffect(() => {
    if (isOpen) {
      try {
        const saved = localStorage.getItem('videocut_export_dir');
        if (saved) {
          setExportDir(saved);
        }
      } catch {}
    }
  }, [isOpen]);

  const updateExportDir = (dir: string) => {
    setExportDir(dir);
    try {
      if (dir) {
        localStorage.setItem('videocut_export_dir', dir);
      } else {
        localStorage.removeItem('videocut_export_dir');
      }
    } catch {}
  };
  const cleanTitle = (projectTitle || '成片')
    .replace(/[\\/*?:"<>|\r\n\t]+/g, '_')
    .replace(/^[ ._]+|[ ._]+$/g, '') || '成片';
  const [filterBannedWords, setFilterBannedWords] = useState<boolean>(true);
  const [showDetailList, setShowDetailList] = useState<boolean>(false);
  const [includeCover, setIncludeCover] = useState<boolean>(true);
  const [embedCover, setEmbedCover] = useState<boolean>(embedCoverAsFirstFrame ?? true);
  const [currentCoverConfig, setCurrentCoverConfig] = useState<CoverDesignConfig | null>(null);
  const [isSavingCover, setIsSavingCover] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'cover' | 'compliance'>('cover');

  // 当外部传入 embedCoverAsFirstFrame 改变时同步
  useEffect(() => {
    if (embedCoverAsFirstFrame !== undefined) {
      setEmbedCover(embedCoverAsFirstFrame);
    }
  }, [embedCoverAsFirstFrame]);

  const handleToggleEmbed = (val: boolean) => {
    setEmbedCover(val);
    onToggleEmbedFirstFrame?.(val);
  };

  // 键盘交互：Esc 关闭弹窗（导出进行中禁止关闭）；未保存的草稿微调随关闭放弃
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isRendering && !isSavingCover) {
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, isRendering, isSavingCover, onClose]);

  if (!isOpen) return null;

  const handleSelectExportDir = async (): Promise<string | null> => {
    if (window.electronAPI?.showOpenDialog) {
      try {
        const res = await window.electronAPI.showOpenDialog({
          title: '选择成片与封面的导出目标文件夹',
          properties: ['openDirectory']
        });
        if (!res.canceled && res.filePaths && res.filePaths.length > 0) {
          const selected = res.filePaths[0];
          updateExportDir(selected);
          return selected;
        }
      } catch (err) {
        console.error('选择目标文件夹失败:', err);
      }
    }
    return null;
  };

  // 提取去重后的替换对
  const uniquePairs: Array<{ orig: string; repl: string }> = [];
  if (bannedWordsCheck?.matches) {
    const seen = new Set<string>();
    for (const m of bannedWordsCheck.matches) {
      const key = `${m.original_word}->${m.replacement_word}`;
      if (!seen.has(key)) {
        seen.add(key);
        uniquePairs.push({ orig: m.original_word, repl: m.replacement_word });
      }
    }
  }

  const handleStartExport = async () => {
    let targetExportDir = exportDir;

    // 若未曾选择过导出位置，确认导出时主动弹出文件夹选择对话框，引导用户选择目标文件夹
    if (!targetExportDir && window.electronAPI?.showOpenDialog) {
      const selected = await handleSelectExportDir();
      if (!selected) {
        // 用户主动取消了文件夹选择，中止导出以避免保存到未知位置
        return;
      }
      targetExportDir = selected;
    }

    // 1. 如果开启了封面导出且配置了封面，先调用接口落盘高清 cover.jpg
    if (includeCover && projectId && currentCoverConfig) {
      setIsSavingCover(true);
      try {
        await setProjectCover(projectId, currentCoverConfig);
      } catch (err) {
        console.warn('生成并保存高清封面警告 (成片导出将继续):', err);
      } finally {
        setIsSavingCover(false);
      }
    }

    // 2. 触发成片导出：只要生成封面，直接无条件压入成片首帧 (1.0s)
    onConfirm(
      filterBannedWords,
      includeCover ? (currentCoverConfig || undefined) : undefined,
      targetExportDir || undefined,
      includeCover,
      includeCover
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-slate-900/65 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-4xl max-h-[92vh] bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-md shadow-blue-500/20">
              <Film className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-800">导出成片与视频封面设计</h3>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-blue-700 font-semibold">
                  美图/剪映口播方案
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                可选择多款爆款封面模板、套用 AI 文案、抽帧或本地选图，导出时零额外开销同步生成
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={isRendering || isSavingCover}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 顶部标签切换 & 视频基本参数 */}
        <div className="px-6 py-2.5 bg-slate-50/50 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('cover')}
              className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'cover'
                  ? 'bg-white text-blue-600 shadow-sm border border-slate-200/80'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>爆款封面设计与模板</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('compliance')}
              className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'compliance'
                  ? 'bg-white text-blue-600 shadow-sm border border-slate-200/80'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
              <span>违禁词合规清洗</span>
              {bannedWordsCheck?.has_banned_words && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 font-mono">
                  {bannedWordsCheck.total_matches}
                </span>
              )}
            </button>
          </div>

          {/* 视频参数小徽章 */}
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="px-2 py-0.5 rounded bg-slate-200/60 font-medium text-slate-700">
              9:16 (1080×1920)
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-200/60 font-medium text-slate-700">
              {videoSpeed}x 倍速
            </span>
          </div>
        </div>

        {/* Modal Body: 滚动展示 */}
        <div className="p-6 overflow-y-auto max-h-[calc(92vh-150px)] space-y-4">
          {/* 自选导出目标目录设置卡片 */}
          <div className="p-3.5 rounded-xl border border-blue-200/90 bg-gradient-to-r from-blue-50/70 via-indigo-50/40 to-blue-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <div className="p-2.5 rounded-xl bg-blue-600 text-white shadow-xs shrink-0">
                <FolderOpen className="w-4 h-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold text-slate-900 shrink-0">成片导出目标文件夹:</span>
                  {exportDir ? (
                    <span
                      className="text-xs text-blue-900 font-mono font-medium bg-white px-2.5 py-0.5 rounded-md border border-blue-200 truncate max-w-full inline-block shadow-2xs"
                      title={exportDir}
                    >
                      {exportDir}
                    </span>
                  ) : (
                    <span className="text-xs text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-md border border-amber-200 font-medium">
                      尚未选定（确认导出时将主动提示选取，或点击右侧选择）
                    </span>
                  )}
                  {exportDir && (
                    <span className="text-[10px] text-emerald-700 bg-emerald-100/90 px-1.5 py-0.2 rounded font-medium shrink-0">
                      已记住该位置
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {exportDir
                    ? '已记住此导出位置，后续导出默认保存至此；成片及高清封面将自动另存至该位置'
                    : '成片及高清封面将自动另存至您指定的文件夹，方便快速查找'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {exportDir && (
                <button
                  type="button"
                  onClick={() => updateExportDir('')}
                  className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                  title="清空已记住的文件夹"
                >
                  重置
                </button>
              )}
              {window.electronAPI?.showOpenDialog ? (
                <button
                  type="button"
                  onClick={handleSelectExportDir}
                  disabled={isRendering || isSavingCover}
                  className="px-3.5 py-1.5 text-xs font-semibold text-blue-700 hover:text-white bg-white hover:bg-blue-600 rounded-xl transition-all border border-blue-300 shadow-2xs flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  <span>{exportDir ? '更改文件夹' : '选择目标文件夹'}</span>
                </button>
              ) : (
                <input
                  type="text"
                  value={exportDir}
                  onChange={(e) => updateExportDir(e.target.value)}
                  placeholder="键入自定义导出路径"
                  className="text-xs px-2.5 py-1 bg-white border border-slate-200 rounded-lg outline-none focus:border-blue-500 w-44 font-mono"
                />
              )}
            </div>
          </div>

          {activeTab === 'cover' ? (
            /* 1. 封面设计全功能模块 */
            <div className="space-y-4">
              {/* 封面导出控制卡片 */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-white flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg shrink-0 ${includeCover ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'}`}>
                    <ImageIcon className="w-4 h-4" />
                  </div>
                    <div>
                    <div className="flex items-center gap-2">
                      <label className="text-xs font-bold text-slate-800 cursor-pointer flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={includeCover}
                          onChange={(e) => setIncludeCover(e.target.checked)}
                          className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300 cursor-pointer"
                        />
                        <span>生成并压入成片封面 (首帧+独立文件)</span>
                      </label>
                      <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${includeCover ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'bg-slate-100 text-slate-500'}`}>
                        {includeCover ? '已启用' : '已停用'}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {includeCover
                        ? '封面仅作为视频首帧（1帧无停顿，开播直接播放），同时在同级目录生成同名高清封面图（cover.jpg）'
                        : '仅导出 .mp4 纯净成片视频，不压入首帧封面，不输出封面图片'}
                    </p>
                  </div>
                </div>
              </div>

              {includeCover ? (
                <CoverPreviewSelector
                  projectId={projectId}
                  initialConfig={initialCoverConfig}
                  suggestedTitles={suggestedTitles}
                  currentVideoTime={currentVideoTime}
                  onConfigChange={(cfg) => setCurrentCoverConfig(cfg)}
                  embedCoverAsFirstFrame={embedCover}
                  onToggleEmbedFirstFrame={handleToggleEmbed}
                />
              ) : (
                <div className="p-8 text-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 space-y-2">
                  <div className="w-10 h-10 mx-auto rounded-full bg-slate-100 text-slate-400 flex items-center justify-center">
                    <Film className="w-5 h-5" />
                  </div>
                  <h4 className="text-xs font-bold text-slate-700">当前选择不导出封面</h4>
                  <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
                    系统将直接输出纯净成片视频，不会在视频头部压入封面帧，也不会输出独立封面图文件。如需封面请在上方勾选开启。
                  </p>
                </div>
              )}

              {/* 底部附带简要合规状态提示 */}
              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-slate-600">
                  <ShieldAlert className="w-4 h-4 text-amber-500" />
                  <span>平台合规清洗：已开启（可切换至“违禁词合规清洗”选项卡查看明细）</span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('compliance')}
                  className="text-blue-600 hover:underline font-medium text-xs"
                >
                  查看合规词
                </button>
              </div>
            </div>
          ) : (
            /* 2. 违禁词合规明细卡片 */
            <div className="space-y-4">
              <div className="p-5 rounded-2xl border border-amber-200 bg-amber-50/40 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-xl bg-amber-100 text-amber-700">
                      <ShieldAlert className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-800">
                          抖音合规违禁词清洗
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-amber-200 text-amber-900">
                          形似/拆字方案
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        将敏感词智能替换为形似字（如“贺照”、“銭”），打破短视频平台 OCR 审核风控且不影响观众理解。
                      </p>
                    </div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={filterBannedWords}
                      onChange={(e) => setFilterBannedWords(e.target.checked)}
                      disabled={isRendering}
                      className="sr-only peer"
                    />
                    <div className="w-10 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {/* 预检状态展示 */}
                {isChecking ? (
                  <div className="py-3 text-xs text-slate-400 flex items-center gap-2">
                    <span className="animate-spin inline-block w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                    正在分析工程字幕违禁词...
                  </div>
                ) : bannedWordsCheck?.has_banned_words ? (
                  <div className="mt-2 pt-3 border-t border-amber-200/70 space-y-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-amber-900 font-semibold flex items-center gap-1.5">
                        <AlertCircle className="w-4 h-4 text-amber-600" />
                        检测到 {bannedWordsCheck.total_matches} 处平台敏感词汇
                      </span>
                      <button
                        type="button"
                        onClick={() => setShowDetailList(!showDetailList)}
                        className="text-blue-600 hover:text-blue-700 flex items-center gap-0.5 font-medium"
                      >
                        {showDetailList ? '收起明细' : '展开句段明细'}
                        {showDetailList ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>

                    {/* 替换词徽章 */}
                    <div className="flex flex-wrap gap-1.5">
                      {uniquePairs.map((p, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-white border border-amber-200 text-slate-700 shadow-2xs"
                        >
                          <span className="line-through text-slate-400">{p.orig}</span>
                          <span className="text-slate-400">→</span>
                          <span className="font-semibold text-blue-600">{p.repl}</span>
                        </span>
                      ))}
                    </div>

                    {/* 展开的具体字幕对照 */}
                    {showDetailList && (
                      <div className="max-h-48 overflow-y-auto space-y-2 p-3 bg-white rounded-xl border border-amber-100 text-[11px] mt-2">
                        {bannedWordsCheck.matches.map((m, idx) => (
                          <div key={idx} className="pb-1.5 border-b border-slate-50 last:border-none">
                            <span className="text-slate-400 font-mono">#{m.subtitle_index} </span>
                            <span className="text-slate-600 line-through mr-1">{m.original_word}</span>
                            <span className="text-blue-600 font-medium mr-1.5">[{m.replacement_word}]</span>
                            <span className="text-slate-500">原句: {m.sanitized_line}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-xs text-emerald-600 pt-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>未检测到高危违禁词，字幕处于纯净状态</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-50/90 border-t border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex flex-col gap-1 min-w-0 max-w-xl">
            <div className="flex items-center gap-1.5 text-xs text-slate-600 truncate">
              <span>✨ 导出成片：</span>
              <span className="font-semibold text-slate-800">{cleanTitle}.mp4</span>
              {includeCover && (
                <>
                  <span className="text-slate-300">|</span>
                  <span className="font-semibold text-slate-800">{cleanTitle}_cover.jpg</span>
                  {embedCover && <span className="ml-1 text-[11px] text-indigo-600 font-medium">(含首帧封面)</span>}
                </>
              )}
            </div>

            {/* 主动且醒目地提示导出位置 */}
            <div className="flex items-center gap-2 text-xs">
              <div
                className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg border font-mono truncate max-w-full text-xs ${
                  exportDir
                    ? 'bg-blue-50 border-blue-200 text-blue-900 font-medium'
                    : 'bg-amber-50 border-amber-200 text-amber-900'
                }`}
                title={exportDir || '未指定文件夹（点击确认导出将主动提示选取）'}
              >
                <FolderOpen className={`w-3.5 h-3.5 shrink-0 ${exportDir ? 'text-blue-600' : 'text-amber-600'}`} />
                <span className="shrink-0 font-sans font-semibold">
                  {exportDir ? '导出位置:' : '导出位置提示:'}
                </span>
                <span className="truncate">
                  {exportDir || '未选择目标文件夹（确认导出时将主动提示选取）'}
                </span>
              </div>
              {window.electronAPI?.showOpenDialog && (
                <button
                  type="button"
                  onClick={handleSelectExportDir}
                  disabled={isRendering || isSavingCover}
                  className="text-xs text-blue-600 hover:text-blue-800 hover:underline shrink-0 font-medium cursor-pointer"
                >
                  {exportDir ? '更改位置' : '选取文件夹'}
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isRendering || isSavingCover}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleStartExport}
              disabled={isRendering || isSavingCover}
              className="px-5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-md shadow-blue-500/20 hover:shadow-lg hover:shadow-blue-500/30 transition-all flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              title={exportDir ? `确认并导出至: ${exportDir}` : '确认并选取导出文件夹'}
            >
              {isRendering || isSavingCover ? (
                <>
                  <span className="animate-spin inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full"></span>
                  {isSavingCover ? '正在合成封面...' : '正在导出成片...'}
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>确认并导出成片</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};