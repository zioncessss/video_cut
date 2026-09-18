import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { VideoPlayer } from '../components/VideoPlayer';
import { SubtitleList, SubtitleItem } from '../components/SubtitleList';
import { StrategyStudio } from '../components/StrategyStudio';
import {
  fetchMaterials,
  fetchHardwareMetrics,
  fetchSettings,
  updateProjectStrategy,
  fetchProjectByMaterial,
  fetchProjectById,
  fetchAllProjects,
  uploadMaterial,
  analyzeAndCutVideo,
  renderProject,
  openFolder,
  fetchProjectProgress,
  PipelineProgress,
  Material,
  ProjectSummary,
  EditingStrategy,
  API_BASE,
  getMediaUrl
} from '../services/api';
import {
  Sparkles,
  Wand2,
  RefreshCw,
  Cpu,
  CheckCircle2,
  ShieldAlert,
  Sliders,
  ListOrdered,
  Database,
  RotateCcw,
  FolderOpen,
  Download,
  Copy,
  Check,
  Film,
  Edit3,
  Image as ImageIcon,
  ChevronDown,
  Plus,
  X,
  Upload
} from 'lucide-react';

interface CorrectionItem {
  subtitle_id: string;
  original_text: string;
  corrected_text: string;
  changes?: Array<{ from: string; to: string; reason: string }>;
}

interface VideoEditorProps {
  onProjectLoaded?: (projectId: string) => void;
  externalStrategyPlan?: {
    explanation: string;
    updated_subtitles?: any[];
    updated_brolls?: any[];
  } | null;
  initialProjectId?: string | null;
  initialSelectedTalkingHeadId?: string | null;
}

const DEFAULT_STRATEGY: EditingStrategy = {
  subtitle_theme: 'glow_gold',
  font_size: 'medium',
  subtitle_font_size: 72,
  show_subtitles: true,
  subtitle_position_y: 82,
  subtitle_position_x: 50,
  enable_highlight: true,
  highlight_color: '#FACC15',
  highlight_scale: true,
  custom_highlight_words: ['科目二', '一把过', '金牌教练', '体检', '十分钟', '轻松'],
  enable_top_banner: true,
  banner_main_title: '科目二一把过秘籍',
  banner_sub_title: '教练手把手教学',
  banner_style: 'capsule',
  banner_font_size: 48,
  banner_position_x: 50,
  banner_position_y: 10,
  enable_watermark: true,
  watermark_text: '@顺达驾校官方教学',
  watermark_position: 'top_right',
  watermark_font_size: 32,
  watermark_position_x: 96,
  watermark_position_y: 3,
  watermark_opacity: 0.45,
  broll_pacing: 'standard'
};

export const VideoEditor: React.FC<VideoEditorProps> = ({
  onProjectLoaded,
  externalStrategyPlan,
  initialProjectId,
  initialSelectedTalkingHeadId,
}) => {
  const [talkingHeads, setTalkingHeads] = useState<Material[]>([]);
  const [selectedThId, setSelectedThId] = useState<string>(initialSelectedTalkingHeadId || '');
  const [projectId, setProjectId] = useState<string>(initialProjectId || '');
  const [allProjects, setAllProjects] = useState<ProjectSummary[]>([]);
  const [showProjectPicker, setShowProjectPicker] = useState<boolean>(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const [subtitles, setSubtitles] = useState<SubtitleItem[]>([]);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [oneClickStage, setOneClickStage] = useState<string>('');
  const [rendering, setRendering] = useState<boolean>(false);
  const [outputVideoUrl, setOutputVideoUrl] = useState<string>('');
  const [coverUrl, setCoverUrl] = useState<string>('');
  const [settingCover, setSettingCover] = useState<boolean>(false);
  const [outputTimestamp, setOutputTimestamp] = useState<number>(Date.now());
  const [previewMode, setPreviewMode] = useState<'interactive' | 'rendered'>('interactive');
  const [exportInfo, setExportInfo] = useState<{
    url: string;
    filename: string;
    absolutePath: string;
    sizeMb: number;
  } | null>(null);
  const [copiedPath, setCopiedPath] = useState<boolean>(false);
  const [folderOpened, setFolderOpened] = useState<boolean>(false);
  const [aiInstruction, setAiInstruction] = useState<string>('');
  const [applyingInstruction, setApplyingInstruction] = useState<boolean>(false);
  const [hardwareInfo, setHardwareInfo] = useState<any>(null);
  const [activeEngine, setActiveEngine] = useState<string>('codex');
  const [activeModel, setActiveModel] = useState<string>('GLM-5.3-Flash');
  const [lastEngineUsed, setLastEngineUsed] = useState<string | null>(null);
  const [aiFeedback, setAiFeedback] = useState<string | null>(null);
  const [correctionsSummary, setCorrectionsSummary] = useState<CorrectionItem[] | null>(null);

  const [isCachedProject, setIsCachedProject] = useState<boolean>(false);
  const [loadingProject, setLoadingProject] = useState<boolean>(false);
  const [aspectRatio, setAspectRatio] = useState<'9:16' | '16:9'>('9:16');

  // 剪辑工作区 Tab 模式：'subtitles' (轨道字幕与空镜) vs 'strategy' (爱拍式策略工坊)
  const [activeTab, setActiveTab] = useState<'subtitles' | 'strategy'>('subtitles');
  const [strategy, setStrategy] = useState<EditingStrategy>(DEFAULT_STRATEGY);
  const [savingStrategy, setSavingStrategy] = useState<boolean>(false);

  const loadProjectById = async (pid: string) => {
    if (!pid) return;
    setLoadingProject(true);
    try {
      const proj = await fetchProjectById(pid);
      if (proj && proj.id) {
        setProjectId(proj.id);
        if (proj.talking_head_id) {
          setSelectedThId(proj.talking_head_id);
        }
        if (onProjectLoaded) onProjectLoaded(proj.id);
        setSubtitles(proj.subtitles || []);
        if (proj.strategy) setStrategy(proj.strategy);
        if (proj.aspect_ratio === '16:9' || proj.aspect_ratio === '9:16') {
          setAspectRatio(proj.aspect_ratio as any);
        }
        if (proj.output_video_path) {
          const mediaUrl = getMediaUrl(proj.output_video_path);
          setOutputVideoUrl(mediaUrl);
          setOutputTimestamp(Date.now());
          setExportInfo({
            url: mediaUrl,
            filename: proj.output_filename || proj.output_video_path.split('/').pop() || 'output.mp4',
            absolutePath: proj.output_absolute_path || '',
            sizeMb: proj.output_file_size_mb || 0,
          });
          setPreviewMode('rendered');
        } else {
          setOutputVideoUrl('');
          setExportInfo(null);
          setPreviewMode('interactive');
        }
        setIsCachedProject(true);
        setAiFeedback(`已秒级载入工程 ${proj.title}（共 ${proj.subtitles?.length || 0} 句字幕）`);
      }
    } catch (e) {
      console.error('载入指定工程失败:', e);
    } finally {
      setLoadingProject(false);
    }
  };

  const loadProjectForMaterial = async (matId: string) => {
    if (!matId) return;
    setLoadingProject(true);
    try {
      const proj = await fetchProjectByMaterial(matId);
      if (proj && proj.id) {
        setProjectId(proj.id);
        if (onProjectLoaded) onProjectLoaded(proj.id);
        setSubtitles(proj.subtitles || []);
        if (proj.strategy) setStrategy(proj.strategy);
        if (proj.aspect_ratio === '16:9' || proj.aspect_ratio === '9:16') {
          setAspectRatio(proj.aspect_ratio as any);
        }
        if (proj.output_video_path) {
          const mediaUrl = getMediaUrl(proj.output_video_path);
          setOutputVideoUrl(mediaUrl);
          setOutputTimestamp(Date.now());
          setExportInfo({
            url: mediaUrl,
            filename: proj.output_filename || proj.output_video_path.split('/').pop() || 'output.mp4',
            absolutePath: proj.output_absolute_path || '',
            sizeMb: proj.output_file_size_mb || 0,
          });
          setPreviewMode('rendered');
        } else {
          setOutputVideoUrl('');
          setExportInfo(null);
          setPreviewMode('interactive');
        }
        setIsCachedProject(true);
        setAiFeedback(`已秒级载入工程磁盘缓存（共 ${proj.subtitles?.length || 0} 句字幕）`);
        return;
      }
    } catch (e: any) {
      // 404 说明未提取过或工程未建立
      setProjectId('');
      setSubtitles([]);
      setOutputVideoUrl('');
      setExportInfo(null);
      setPreviewMode('interactive');
      setIsCachedProject(false);
    } finally {
      setLoadingProject(false);
    }
  };

  const handleUploadTalkingHead = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    try {
      setAnalyzing(true);
      const newMat = await uploadMaterial('talking_head', file);
      const updatedMaterials = await fetchMaterials('talking_head');
      setTalkingHeads(updatedMaterials);
      setSelectedThId(newMat.id);
      await loadProjectForMaterial(newMat.id);
      setAiFeedback(`口播视频 ${file.name} 上传就绪！点击「智能初剪与纠偏」即可开启剪辑。`);
      fetchAllProjects().then(setAllProjects).catch(() => {});
    } catch (err: any) {
      alert(`上传口播视频失败: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setAnalyzing(false);
      if (uploadInputRef.current) uploadInputRef.current.value = '';
    }
  };

  useEffect(() => {
    fetchAllProjects().then(setAllProjects).catch(() => {});
    fetchMaterials('talking_head').then(data => {
      setTalkingHeads(data);
      if (initialProjectId) {
        loadProjectById(initialProjectId);
      } else if (initialSelectedTalkingHeadId && data.some(d => d.id === initialSelectedTalkingHeadId)) {
        setSelectedThId(initialSelectedTalkingHeadId);
      } else if (data.length > 0 && !selectedThId) {
        setSelectedThId(data[0].id);
      }
    });
    fetchHardwareMetrics().then(setHardwareInfo).catch(() => {});
    fetchSettings().then(s => {
      setActiveEngine(s.active_harness || 'codex');
      setActiveModel(s.llm_model || 'GLM-5.3-Flash');
    }).catch(() => {});
  }, [initialSelectedTalkingHeadId, initialProjectId]);

  useEffect(() => {
    if (selectedThId && !initialProjectId) {
      const curMat = talkingHeads.find(t => t.id === selectedThId);
      if (curMat && curMat.width && curMat.height && curMat.width > curMat.height) {
        setAspectRatio('16:9');
      }
      loadProjectForMaterial(selectedThId);
    }
  }, [selectedThId]);

  const handleAnalyze = async (force: boolean = false) => {
    return handleOneClickCutAndCorrect(force);
  };

  const handleOneClickCutAndCorrect = async (force: boolean = false) => {
    if (!selectedThId) {
      alert('请先选择或上传口播主视频');
      return;
    }
    setAnalyzing(true);
    setCorrectionsSummary(null);
    setOneClickStage('正在抽取音频、ASR识别切分并调用AI纠偏...');
    try {
      // 1. 语音提取 + 词级时间戳 + 黄金片段切分合并 + 大模型行业专词纠偏一体化完成
      const res = await analyzeAndCutVideo(selectedThId, {
        aspectRatio: aspectRatio,
        autoBroll: true,
        forceRetranscribe: force
      });
      setProjectId(res.id);
      if (onProjectLoaded) {
        onProjectLoaded(res.id);
      }
      const currentSubs = res.subtitles || [];
      setSubtitles(currentSubs);
      if (res.strategy) {
        setStrategy(res.strategy);
      }
      if (res.output_video_path) {
        setOutputVideoUrl(getMediaUrl(res.output_video_path));
      }
      setIsCachedProject(true);

      if (res.last_engine_used) {
        setLastEngineUsed(res.last_engine_used);
      }
      if (res.corrections_summary && res.corrections_summary.length > 0) {
        setCorrectionsSummary(res.corrections_summary);
        setAiFeedback(`智能剪辑完成！已通过 ${res.last_engine_used || activeEngine} 智能修正 ${res.corrections_summary.length} 处专有词并自动保存。`);
      } else {
        const costStr = res.correction_latency_ms ? `，耗时 ${Math.round(res.correction_latency_ms)}ms` : '';
        setAiFeedback(`智能剪辑完成（未发现明显错别字${costStr}）。`);
      }

      setPreviewMode('interactive');
    } catch (err) {
      alert('智能剪辑失败，请确保后端服务正常运行');
    } finally {
      setAnalyzing(false);
      setOneClickStage('');
    }
  };

  // 监听来自全局 Harness 对话框的策略变更意图，热更新工程
  useEffect(() => {
    if (externalStrategyPlan) {
      if (externalStrategyPlan.updated_subtitles && externalStrategyPlan.updated_subtitles.length > 0) {
        setSubtitles(externalStrategyPlan.updated_subtitles);
        if (projectId) {
          axios.put(`${API_BASE}/projects/${projectId}/subtitles`, { subtitles: externalStrategyPlan.updated_subtitles }).catch(() => {});
        }
      }
      if (externalStrategyPlan.explanation) {
        setAiFeedback(`[副驾驶策略应用] ${externalStrategyPlan.explanation}`);
      }
    }
  }, [externalStrategyPlan, projectId]);

  const subtitleSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleTextChange = (idx: number, newText: string) => {
    if (previewMode === 'rendered') {
      setPreviewMode('interactive');
    }
    const updated = [...subtitles];
    updated[idx].corrected_text = newText;
    setSubtitles(updated);
    if (!projectId) return;
    if (subtitleSaveTimeoutRef.current) {
      clearTimeout(subtitleSaveTimeoutRef.current);
    }
    subtitleSaveTimeoutRef.current = setTimeout(async () => {
      try {
        await axios.put(`${API_BASE}/projects/${projectId}/subtitles`, { subtitles: updated });
      } catch (e) {
        console.error('Auto save subtitle failed', e);
      }
    }, 500);
  };

  // 高亮词增删（手动来源标记 manual），与文本编辑共用同一条防抖持久化链路
  const handleHighlightWordsChange = (idx: number, words: { word: string; source: 'glossary' | 'ai' | 'manual' }[]) => {
    if (previewMode === 'rendered') {
      setPreviewMode('interactive');
    }
    const updated = [...subtitles];
    updated[idx] = { ...updated[idx], highlight_words: words, is_manual_edited: true };
    setSubtitles(updated);
    if (!projectId) return;
    if (subtitleSaveTimeoutRef.current) {
      clearTimeout(subtitleSaveTimeoutRef.current);
    }
    subtitleSaveTimeoutRef.current = setTimeout(async () => {
      try {
        await axios.put(`${API_BASE}/projects/${projectId}/subtitles`, { subtitles: updated });
      } catch (e) {
        console.error('Auto save highlight words failed', e);
      }
    }, 500);
  };

  // 策略自动防抖保存 (600ms)，确保面板滑动或拖拽松开后 100% 固化到单一权威 SQLite 库
  const strategySaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleStrategyChange = (newStrategy: EditingStrategy) => {
    if (previewMode === 'rendered') {
      setPreviewMode('interactive');
    }
    setStrategy(newStrategy);
    if (!projectId) return;
    if (strategySaveTimeoutRef.current) {
      clearTimeout(strategySaveTimeoutRef.current);
    }
    strategySaveTimeoutRef.current = setTimeout(async () => {
      try {
        await updateProjectStrategy(projectId, newStrategy);
      } catch (e) {
        console.error('Debounced strategy save failed', e);
      }
    }, 600);
  };

  const handleStrategyCommit = async (committedStrategy: EditingStrategy) => {
    if (previewMode === 'rendered') {
      setPreviewMode('interactive');
    }
    if (strategySaveTimeoutRef.current) {
      clearTimeout(strategySaveTimeoutRef.current);
    }
    setStrategy(committedStrategy);
    if (projectId) {
      try {
        await updateProjectStrategy(projectId, committedStrategy);
      } catch (e) {
        console.error('Immediate strategy save failed', e);
      }
    }
  };

  const handleSaveStrategy = async () => {
    if (!projectId) {
      alert('请先执行智能剪辑创建工程，再保存策略');
      return;
    }
    setSavingStrategy(true);
    try {
      await updateProjectStrategy(projectId, strategy);
      setAiFeedback('剪辑策略已成功保存至当前工程！渲染时将以该样式导出。');
    } catch (err) {
      alert('保存策略失败');
    } finally {
      setSavingStrategy(false);
    }
  };

  const handleApplyInstruction = async () => {
    if (!projectId || !aiInstruction.trim()) return;
    setApplyingInstruction(true);
    setAiFeedback(null);
    try {
      const res = await axios.post(`${API_BASE}/instruction/apply`, {
        project_id: projectId,
        instruction: aiInstruction
      });
      if (res.data.updated_subtitles && res.data.updated_subtitles.length > 0) {
        setSubtitles(res.data.updated_subtitles);
      }
      setLastEngineUsed(res.data.harness_engine_used);
      setAiFeedback(res.data.explanation);
      setAiInstruction('');
    } catch (err) {
      alert('指令解析失败，请检查 Harness 状态');
    } finally {
      setApplyingInstruction(false);
    }
  };

  const handleRender = async () => {
    if (!projectId) return;
    setRendering(true);
    setAiFeedback(null);
    try {
      // 1. 同步最新字幕与策略
      await axios.put(`${API_BASE}/projects/${projectId}/subtitles`, {
        subtitles: subtitles
      });
      await updateProjectStrategy(projectId, strategy);

      // 2. 发起高质量复合渲染 (Lanczos 算法 + CRF 18 高清画质 + 原生 Emoji 横幅 + ASS 高亮字幕)
      const res = await renderProject(projectId);
      if (res.output_video_path) {
        const mediaUrl = getMediaUrl(res.output_video_path);
        const newTs = Date.now();
        setOutputTimestamp(newTs);
        setOutputVideoUrl(mediaUrl);
        setExportInfo({
          url: mediaUrl,
          filename: res.output_filename || res.output_video_path.split('/').pop() || 'output.mp4',
          absolutePath: res.output_absolute_path || '',
          sizeMb: res.output_file_size_mb || 0,
        });
        setPreviewMode('rendered');
        setAiFeedback('🎉 新成片已复合压制完成并替代前序版本！已自动切换为高清成片预览。');
      }
    } catch (err: any) {
      alert(`渲染合成失败: ${err?.response?.data?.detail || err.message || '请检查后端服务'}`);
    } finally {
      setRendering(false);
    }
  };

  const handleOpenFolder = async () => {
    try {
      await openFolder(exportInfo?.absolutePath);
      setFolderOpened(true);
      setAiFeedback(`已在系统文件管理器中高亮定位：${exportInfo?.filename || '导出目录'}`);
      setTimeout(() => setFolderOpened(false), 3000);
    } catch (e) {
      alert('打开所在文件夹失败，请检查系统权限');
    }
  };

  const handleCopyPath = () => {
    if (exportInfo?.absolutePath) {
      navigator.clipboard.writeText(exportInfo.absolutePath);
      setCopiedPath(true);
      setTimeout(() => setCopiedPath(false), 2000);
    }
  };

  const handleDownload = () => {
    if (exportInfo?.url) {
      const a = document.createElement('a');
      a.href = exportInfo.url;
      a.download = exportInfo.filename || 'export.mp4';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  const rawVideoUrl = selectedThId && talkingHeads.find(t => t.id === selectedThId)
    ? getMediaUrl(talkingHeads.find(t => t.id === selectedThId)?.filepath || '')
    : '';

  const currentPreviewUrl = (previewMode === 'rendered' && outputVideoUrl)
    ? `${outputVideoUrl}?v=${outputTimestamp}`
    : rawVideoUrl;

  return (
    <div className="flex flex-col h-full max-h-full max-w-7xl mx-auto p-3 overflow-hidden">
      {/* 顶部操作条：口播素材选择、引擎状态徽章、智能剪辑触发 */}
      <div className="flex flex-wrap items-center justify-between bg-white border border-gray-200/80 rounded-xl p-2.5 shadow-xs mb-2.5 gap-2 flex-shrink-0">
        <div className="flex items-center space-x-2">
          {/* 隐藏文件输入框用于快速上传口播视频 */}
          <input
            ref={uploadInputRef}
            type="file"
            accept="video/*,.mp4,.mov,.mkv,.avi,.webm"
            className="hidden"
            onChange={handleUploadTalkingHead}
          />

          {/* 视频工程卡片选择按钮（点击展开排列好的视频卡片） */}
          <button
            type="button"
            onClick={() => {
              fetchAllProjects().then(setAllProjects).catch(() => {});
              setShowProjectPicker(true);
            }}
            className="flex items-center space-x-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl px-3 py-1.5 text-xs text-gray-800 transition-all cursor-pointer shadow-xs"
            title="点击切换视频工程（卡片网格排列）"
          >
            <Film className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
            <span className="font-semibold max-w-[160px] truncate">
              {talkingHeads.find(t => t.id === selectedThId)?.filename || '选择/切换视频工程'}
            </span>
            {selectedThId && (
              <span className="text-[10px] text-gray-400 font-mono flex-shrink-0">
                ({talkingHeads.find(t => t.id === selectedThId)?.duration?.toFixed(1)}s)
              </span>
            )}
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          </button>

          {/* 剪辑工作台单独上传口播视频直接开剪按钮 */}
          <button
            type="button"
            onClick={() => uploadInputRef.current?.click()}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-medium border border-blue-200/60 transition-colors cursor-pointer shadow-xs"
            title="上传新口播视频就地开剪"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>+ 上传口播</span>
          </button>

          {/* 比例切换 (9:16 竖屏 / 16:9 横屏) */}
          <div className="flex items-center space-x-1 bg-gray-100 p-1 rounded-xl border border-gray-200/80">
            <button
              type="button"
              onClick={() => setAspectRatio('9:16')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                aspectRatio === '9:16' ? 'bg-white text-blue-600 shadow-xs' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              📱 9:16 竖屏
            </button>
            <button
              type="button"
              onClick={() => setAspectRatio('16:9')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                aspectRatio === '16:9' ? 'bg-white text-blue-600 shadow-xs' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              🖥️ 16:9 横屏
            </button>
          </div>
        </div>

        {/* 引擎状态与高阶操作按钮 */}
        <div className="flex items-center space-x-3">
          {/* 活跃 Harness 状态徽章 */}
          <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-xl text-[11px] font-mono">
            <span className="text-gray-500 font-sans">Harness:</span>
            {lastEngineUsed?.includes('fallback') ? (
              <span className="text-amber-600 font-semibold flex items-center">
                <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                降级 Embedded
              </span>
            ) : (
              <span className="text-emerald-600 font-semibold flex items-center">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                {activeEngine.toUpperCase()}
                {activeModel ? ` (${activeModel})` : ''}
              </span>
            )}
          </div>

          {/* 智能剪辑主动作按钮 */}
          {loadingProject ? (
            <div className="flex items-center space-x-1.5 bg-gray-100 text-gray-500 text-xs font-medium px-3.5 py-2 rounded-xl">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-gray-400" />
              <span>载入工程缓存中...</span>
            </div>
          ) : isCachedProject && subtitles.length > 0 ? (
            <div className="flex items-center space-x-2">
              <span className="flex items-center space-x-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200/80 text-xs font-medium px-3 py-2 rounded-xl">
                <Database className="w-3.5 h-3.5 text-emerald-600" />
                <span>工程已就绪 ({subtitles.length}句)</span>
              </span>
              <button
                onClick={() => handleOneClickCutAndCorrect(true)}
                disabled={analyzing || !selectedThId}
                className="flex items-center space-x-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold px-3.5 py-2 rounded-xl shadow-xs transition-all disabled:opacity-50 cursor-pointer"
                title="重跑全流程：音频抽取 -> ASR 黄金片段切分合并 -> 大模型专词纠偏 -> 高亮词 -> AI 分镜决策"
              >
                {analyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                <span>{analyzing ? (oneClickStage || '处理中...') : '智能剪辑'}</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => handleOneClickCutAndCorrect(false)}
              disabled={analyzing || !selectedThId}
              className="flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-sm disabled:opacity-50 cursor-pointer"
              title="一键全自动：音频提取 -> faster-whisper 识别与黄金片段切分合并 -> 大模型专词纠偏 -> 高亮词 -> AI 分镜决策"
            >
              {analyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-amber-300" />}
              <span>{analyzing ? (oneClickStage || 'AI 智能剪辑中...') : '⚡ 智能剪辑 (AI Auto Cut)'}</span>
            </button>
          )}
        </div>
      </div>

      {/* 智能纠错结果明细提示 */}
      {correctionsSummary && correctionsSummary.length > 0 && (
        <div className="mb-4 bg-amber-50/90 border border-amber-200 rounded-2xl p-4 shadow-sm text-xs text-amber-950 animate-in fade-in">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold flex items-center space-x-1.5">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>已通过 {lastEngineUsed || activeEngine} 完成智能语义纠错（共修正 {correctionsSummary.length} 处）：</span>
            </span>
            <button
              onClick={() => setCorrectionsSummary(null)}
              className="text-amber-600 hover:text-amber-800 text-xs"
            >
              ✕ 收起
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {correctionsSummary.map((item, i) => (
              <div key={i} className="bg-white/90 border border-amber-200/60 rounded-xl p-2.5 text-[11px] space-y-1">
                <div className="flex items-center justify-between">
                  <span className="line-through text-red-500">{item.original_text}</span>
                  <span className="text-gray-400">→</span>
                  <span className="font-semibold text-emerald-700">{item.corrected_text}</span>
                </div>
                {item.changes && item.changes.length > 0 && (
                  <p className="text-[10px] text-gray-500 truncate">{item.changes[0].reason}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 主体工作台：左侧播放器（即时策略预览），右侧选项卡（时间轴 vs 策略组合工坊） - 始终保持左右双栏工作台布局 */}
      <div className="flex-1 grid grid-cols-12 gap-3.5 min-h-0 overflow-hidden">
        <div className="col-span-5 h-full min-h-0 flex flex-col items-center justify-center overflow-hidden">
          {/* 实时模式 vs 成片模式 切换状态栏 */}
          <div className="w-full flex items-center justify-between px-2 pb-1 text-[11px] flex-shrink-0">
            {previewMode === 'rendered' ? (
              <div className="flex items-center space-x-1.5 text-emerald-700 bg-emerald-50 border border-emerald-200/80 px-2.5 py-0.5 rounded-full font-medium">
                <Film className="w-3 h-3 text-emerald-600" />
                <span>当前播放：已压制成片 (CRF 18 高清)</span>
              </div>
            ) : (
              <div className="flex items-center space-x-1.5 text-blue-700 bg-blue-50 border border-blue-200/80 px-2.5 py-0.5 rounded-full font-medium">
                <Edit3 className="w-3 h-3 text-blue-600" />
                <span>当前预览：实时交互编辑模式（画布可拖拽）</span>
              </div>
            )}
            <div className="flex items-center space-x-2">
              {outputVideoUrl && previewMode === 'rendered' && projectId && (
                <button
                  onClick={async () => {
                    setSettingCover(true);
                    try {
                      const { setProjectCover } = await import('../services/api');
                      const data = await setProjectCover(projectId, 'frame', currentTime);
                      setCoverUrl(getMediaUrl(data.cover_url.replace(/^\//, '')));
                      setAiFeedback('已将当前帧设为工程封面。');
                    } catch (err: any) {
                      const detail = err?.response?.data?.detail || '设置封面失败';
                      alert(detail);
                    } finally {
                      setSettingCover(false);
                    }
                  }}
                  disabled={settingCover}
                  className="text-purple-600 hover:text-purple-800 font-medium hover:underline flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                  title="将成片当前帧设为工程封面（AI 封面生成为规划中能力）"
                >
                  <ImageIcon className="w-3 h-3" />
                  <span>{settingCover ? '截取中...' : '设为封面'}</span>
                </button>
              )}
              {coverUrl && (
                <img src={coverUrl} alt="封面" className="w-8 h-8 object-cover rounded-md border border-gray-200" title="当前工程封面" />
              )}
              {outputVideoUrl && (
                previewMode === 'rendered' ? (
                  <button
                    onClick={() => setPreviewMode('interactive')}
                    className="text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center space-x-1 cursor-pointer"
                    title="切换回实时编辑模式，可继续拖拽横幅、水印、字幕排版"
                  >
                    <Edit3 className="w-3 h-3" />
                    <span>返回实时编辑</span>
                  </button>
                ) : (
                  <button
                    onClick={() => setPreviewMode('rendered')}
                    className="text-emerald-700 hover:text-emerald-900 font-medium hover:underline flex items-center space-x-1 cursor-pointer"
                    title="播放复合压制后的高清 MP4 成片"
                  >
                    <Film className="w-3 h-3" />
                    <span>查看已渲染成片</span>
                  </button>
                )
              )}
            </div>
          </div>

          <VideoPlayer
            videoUrl={currentPreviewUrl}
            subtitles={subtitles}
            currentTime={currentTime}
            onTimeUpdate={setCurrentTime}
            aspectRatio={aspectRatio}
            onAspectRatioChange={setAspectRatio}
            strategy={strategy}
            onStrategyChange={handleStrategyChange}
            onStrategyCommit={handleStrategyCommit}
            isRendered={previewMode === 'rendered'}
          />
        </div>

        <div className="col-span-7 h-full min-h-0 flex flex-col overflow-hidden bg-white rounded-2xl border border-gray-200/80 shadow-sm p-3">
          {/* 工作区模式切换 Tabs */}
          <div className="flex items-center justify-between border-b border-gray-100 pb-2 mb-2.5 flex-shrink-0">
            <div className="flex items-center space-x-2 bg-gray-100 p-1 rounded-xl">
              <button
                type="button"
                onClick={() => setActiveTab('subtitles')}
                className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'subtitles'
                    ? 'bg-white text-gray-800 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <ListOrdered className="w-3.5 h-3.5" />
                <span>字幕与时间轴轨道 ({subtitles.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('strategy')}
                className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'strategy'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>剪辑策略工坊 (Strategy Studio)</span>
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse"></span>
              </button>
            </div>

            <div className="text-[11px] text-gray-400">
              {activeTab === 'strategy' ? '支持像爱拍一样自由组合 4 种方案' : '单句 6~12 字黄金视读切分'}
            </div>
          </div>

          {/* 模式内容容器 */}
          <div className="flex-1 overflow-y-auto pr-1">
            {activeTab === 'subtitles' ? (
              <SubtitleList
                subtitles={subtitles}
                currentTime={currentTime}
                onSelectTime={setCurrentTime}
                onTextChange={handleTextChange}
                onHighlightWordsChange={handleHighlightWordsChange}
              />
            ) : (
              <StrategyStudio
                strategy={strategy}
                onChange={handleStrategyChange}
                onSave={handleSaveStrategy}
                saving={savingStrategy}
              />
            )}
          </div>
        </div>
      </div>

      {/* AI 调整反馈提示 */}
      {aiFeedback && (
        <div className="mt-1.5 bg-blue-50/80 border border-blue-200/80 rounded-xl px-3 py-1.5 flex items-center justify-between text-xs text-blue-900 shadow-sm animate-in fade-in flex-shrink-0">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
            <span className="font-medium">{aiFeedback}</span>
          </div>
          <button onClick={() => setAiFeedback(null)} className="text-blue-500 hover:text-blue-700 text-xs ml-4">
            ✕
          </button>
        </div>
      )}

      {/* 成片导出完成信息与操作卡片 */}
      {exportInfo && (
        <div className="mt-1.5 bg-gradient-to-r from-emerald-50 via-teal-50/70 to-emerald-50 border border-emerald-300/80 rounded-xl px-3 py-2 shadow-2xs flex items-center justify-between gap-2 text-xs animate-in fade-in flex-shrink-0">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-emerald-600 text-white flex items-center justify-center flex-shrink-0 shadow-2xs">
              <Film className="w-3.5 h-3.5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-2">
                <span className="font-bold text-emerald-950 truncate max-w-[220px]" title={exportInfo.filename}>
                  {exportInfo.filename}
                </span>
                {exportInfo.sizeMb > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] font-mono bg-emerald-200/80 text-emerald-900 rounded font-semibold">
                    {exportInfo.sizeMb} MB
                  </span>
                )}
                <span className="text-[10px] text-emerald-700 bg-emerald-100/90 px-1.5 py-0.5 rounded font-medium flex items-center">
                  <CheckCircle2 className="w-3 h-3 mr-0.5 text-emerald-600" />
                  CRF 18 高清
                </span>
              </div>
              <div className="flex items-center space-x-1.5 text-[11px] text-gray-500 font-mono mt-0.5">
                <span className="text-gray-400 flex-shrink-0">导出位置:</span>
                <span className="truncate max-w-[300px] lg:max-w-[450px] text-gray-700 font-sans" title={exportInfo.absolutePath}>
                  {exportInfo.absolutePath || 'storage/outputs/' + exportInfo.filename}
                </span>
                {exportInfo.absolutePath && (
                  <button
                    onClick={handleCopyPath}
                    title="复制文件绝对路径"
                    className="text-emerald-700 hover:text-emerald-900 p-0.5 hover:bg-emerald-100 rounded transition-colors flex items-center"
                  >
                    {copiedPath ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-1.5 flex-shrink-0">
            <button
              onClick={handleOpenFolder}
              className={`flex items-center space-x-1 border font-semibold px-2.5 py-1.5 rounded-lg shadow-2xs transition-colors cursor-pointer ${
                folderOpened
                  ? 'bg-emerald-100 text-emerald-900 border-emerald-400'
                  : 'bg-white hover:bg-emerald-50 text-emerald-800 border-emerald-300'
              }`}
              title="在系统资源管理器中定位并选中此视频文件"
            >
              <FolderOpen className="w-3.5 h-3.5 text-emerald-700" />
              <span>{folderOpened ? '✓ 已唤起文件管理器' : '打开所在文件夹'}</span>
            </button>

            <button
              onClick={handleDownload}
              className="flex items-center space-x-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-2.5 py-1.5 rounded-lg shadow-2xs transition-colors"
              title="在浏览器中直接下载此视频"
            >
              <Download className="w-3.5 h-3.5" />
              <span>下载成片</span>
            </button>
          </div>
        </div>
      )}

      {/* 底部浮动交互条：AI Prompt 指令输入框 + 生成按钮 + 硬件监控 */}
      <div className="mt-1.5 bg-white border border-gray-200/80 rounded-xl p-2 shadow-xs flex items-center space-x-2 flex-shrink-0">
        <div className="flex-1 flex items-center space-x-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-1.5 focus-within:ring-1 focus-within:ring-blue-500">
          {applyingInstruction ? (
            <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />
          ) : (
            <Wand2 className="w-4 h-4 text-blue-600" />
          )}
          <input
            type="text"
            value={aiInstruction}
            onChange={e => setAiInstruction(e.target.value)}
            placeholder="AI 智能微调指令 (例如: 把第1句开场白润色得热情昂扬，第2句空镜换成体检素材)"
            className="flex-1 bg-transparent text-xs text-gray-800 outline-none"
            onKeyDown={e => e.key === 'Enter' && handleApplyInstruction()}
          />
          <button
            onClick={handleApplyInstruction}
            disabled={applyingInstruction || !aiInstruction.trim()}
            className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium px-3 py-1 rounded-lg transition-colors disabled:opacity-40"
          >
            {applyingInstruction ? '应用中...' : '发送指令'}
          </button>
        </div>

        <button
          onClick={handleRender}
          disabled={rendering || !projectId}
          className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition-colors shadow-sm disabled:opacity-50 flex items-center space-x-1.5"
        >
          {rendering && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
          <span>{rendering ? '高清复合压制中 (CRF 18)...' : '生成成片预览 (Generate Preview)'}</span>
        </button>

        {hardwareInfo && (
          <div className="hidden lg:flex items-center space-x-2 border-l pl-3 text-xs text-gray-500 font-mono">
            <Cpu className="w-3.5 h-3.5 text-emerald-600" />
            <span>负载: {hardwareInfo.cpu_usage_percent || hardwareInfo.cpu_percent || 15}%</span>
          </div>
        )}
      </div>

      {/* 视频工程卡片网格选择抽屉/弹窗 */}
      {showProjectPicker && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[80vh] shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
              <div className="flex items-center space-x-2">
                <Film className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-bold text-gray-900">选择剪辑视频工程 (卡片排列)</h3>
                <span className="text-xs text-gray-400 font-mono">({talkingHeads.length} 个视频)</span>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowProjectPicker(false);
                    uploadInputRef.current?.click();
                  }}
                  className="flex items-center space-x-1 px-3 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs rounded-lg font-medium cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>上传新口播</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowProjectPicker(false)}
                  className="p-1 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="p-4 overflow-y-auto flex-1">
              {talkingHeads.length === 0 ? (
                <div className="py-12 text-center text-xs text-gray-400">
                  暂无口播视频，点击右上角「上传新口播」添加
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {talkingHeads.map(t => {
                    const isSelected = t.id === selectedThId;
                    const matchedProj = allProjects.find(p => p.talking_head_id === t.id);
                    const coverUrl = matchedProj?.cover_image_path ? getMediaUrl(matchedProj.cover_image_path) : '';
                    return (
                      <div
                        key={t.id}
                        onClick={() => {
                          setSelectedThId(t.id);
                          if (matchedProj) {
                            loadProjectById(matchedProj.id);
                          } else {
                            loadProjectForMaterial(t.id);
                          }
                          setShowProjectPicker(false);
                        }}
                        className={`border rounded-xl p-2.5 transition-all cursor-pointer flex flex-col justify-between ${
                          isSelected
                            ? 'border-blue-500 bg-blue-50/40 ring-2 ring-blue-500/20'
                            : 'border-gray-200 hover:border-blue-300 bg-white hover:bg-gray-50'
                        }`}
                      >
                        <div className="aspect-video bg-gray-900 rounded-lg overflow-hidden mb-2 relative flex items-center justify-center">
                          {coverUrl ? (
                            <img src={coverUrl} alt={t.filename} className="w-full h-full object-cover" />
                          ) : (
                            <Film className="w-6 h-6 text-gray-600" />
                          )}
                          <span className="absolute bottom-1 right-1 text-[10px] px-1 py-0.5 rounded bg-black/70 text-white font-mono">
                            {t.duration ? `${t.duration.toFixed(1)}s` : ''}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-gray-800 truncate" title={t.filename}>
                            {t.filename}
                          </p>
                          <div className="flex items-center justify-between text-[10px] text-gray-400 mt-1">
                            <span>{matchedProj ? (matchedProj.status === 'completed' ? '已合成成片' : '已初剪') : '待剪辑'}</span>
                            {isSelected && <span className="text-blue-600 font-bold">当前工程</span>}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};