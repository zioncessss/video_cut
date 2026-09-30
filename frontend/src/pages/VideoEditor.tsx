import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { VideoPlayer } from '../components/VideoPlayer';
import { SubtitleList, SubtitleItem, SaveStatus } from '../components/SubtitleList';
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
  redecideScenes,
  BrollReplacement,
  PruneSpan,
  toggleSubtitlePrune,
  API_BASE,
  getMediaUrl,
  updateProjectSubtitles,
  updateProjectTitle,
  uploadProjectCoverFile,
  setProjectCover,
  checkBannedWords,
  BannedWordsCheckResult,
  CoverDesignConfig,
  SuggestedCoverTitle,
  deleteMaterial,
  deleteProjectByMaterial
} from '../services/api';
import { ExportConfirmModal } from '../components/ExportConfirmModal';
import { formatRegionBadge } from '../constants/regions';
import {
  Sparkles,
  RefreshCw,
  CheckCircle2,
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
  Upload,
  AlertTriangle,
  Maximize2,
  Trash2,
  MapPin
} from 'lucide-react';
import { useDialog } from '../components/common/CustomDialog';

interface CorrectionItem {
  subtitle_id: string;
  original_text: string;
  corrected_text: string;
  changes?: Array<{ from: string; to: string; reason: string }>;
}

interface VideoEditorProps {
  onProjectLoaded?: (projectId: string) => void;
  onTalkingHeadChanged?: (talkingHeadId: string) => void;
  initialProjectId?: string | null;
  initialSelectedTalkingHeadId?: string | null;
  isActive?: boolean;
}

export const sanitizeStrategy = (strat: EditingStrategy): EditingStrategy => {
  const cloned = { ...strat };
  const wmText = (cloned.watermark_text || '').trim();
  if (wmText === '@顺达驾校官方教学' || !wmText) {
    cloned.enable_watermark = false;
    cloned.watermark_text = '';
  } else {
    cloned.watermark_text = wmText;
  }
  if (cloned.banner_main_title === '驾考拿证必看宝典' || cloned.banner_main_title === '科目二一把过秘籍') {
    cloned.banner_main_title = '';
  }
  return cloned;
};

const DEFAULT_STRATEGY: EditingStrategy = {
  subtitle_theme: 'cinema_shadow',
  highlight_color: '#FBBF24',
  subtitle_font_family: 'notoserif',
  subtitle_font_size: 72,
  font_size: 'medium',
  show_subtitles: true,
  subtitle_position_x: 50,
  subtitle_position_y: 74,
  subtitle_width_percent: 100,
  enable_highlight: true,
  highlight_scale: true,
  custom_highlight_words: [],
  enable_top_banner: false,
  banner_main_title: '',
  banner_style: 'capsule',
  banner_font_size: 48,
  banner_position_x: 50,
  banner_position_y: 10,
  enable_watermark: false,
  watermark_text: '',
  watermark_position: 'top_right',
  watermark_font_size: 32,
  watermark_position_x: 96,
  watermark_position_y: 3,
  watermark_opacity: 0.45,
  broll_pacing: 'standard',
  video_speed: 1.0,
  filter_preset: 'clean_natural',
  filter_strength: 1.0,
};

export const VideoEditor: React.FC<VideoEditorProps> = ({
  onProjectLoaded,
  onTalkingHeadChanged,
  initialProjectId,
  initialSelectedTalkingHeadId,
  isActive = true,
}) => {
  const { showAlert, showToast, showConfirm } = useDialog();
  const [talkingHeads, setTalkingHeads] = useState<Material[]>([]);
  const [selectedThId, setSelectedThId] = useState<string>(initialSelectedTalkingHeadId || '');
  const [projectId, setProjectId] = useState<string>(initialProjectId || '');
  const [projectTitle, setProjectTitle] = useState<string>('');
  const [isEditingTitle, setIsEditingTitle] = useState<boolean>(false);
  const [tempTitle, setTempTitle] = useState<string>('');
  const [targetRegion, setTargetRegion] = useState<string | null>(null);
  const [allProjects, setAllProjects] = useState<ProjectSummary[]>([]);
  const [showProjectPicker, setShowProjectPicker] = useState<boolean>(false);
  const [projectFilterTab, setProjectFilterTab] = useState<'all' | 'edited' | 'unedited'>('all');
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const [subtitles, setSubtitles] = useState<SubtitleItem[]>([]);
  const [compactSubtitles, setCompactSubtitles] = useState<SubtitleItem[]>([]);
  const [brolls, setBrolls] = useState<BrollReplacement[]>([]);
  const [pruneSpans, setPruneSpans] = useState<PruneSpan[]>([]);
  const [materialsMap, setMaterialsMap] = useState<Record<string, Material>>({});
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [oneClickStage, setOneClickStage] = useState<string>('');
  const [pipelineProgress, setPipelineProgress] = useState<PipelineProgress | null>(null);
  const pollingProgressTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [rendering, setRendering] = useState<boolean>(false);
  const [outputVideoUrl, setOutputVideoUrl] = useState<string>('');
  const [coverUrl, setCoverUrl] = useState<string>('');
  const [settingCover, setSettingCover] = useState<boolean>(false);
  const coverFileInputRef = useRef<HTMLInputElement>(null);
  const [outputTimestamp, setOutputTimestamp] = useState<number>(Date.now());
  const [previewMode, setPreviewMode] = useState<'interactive' | 'rendered'>('interactive');
  const [isPlayerEnlarged, setIsPlayerEnlarged] = useState<boolean>(false);
  const [exportInfo, setExportInfo] = useState<{
    url: string;
    filename: string;
    absolutePath: string;
    sizeMb: number;
  } | null>(null);
  const [copiedPath, setCopiedPath] = useState<boolean>(false);
  const [folderOpened, setFolderOpened] = useState<boolean>(false);
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

  // 字幕与策略实时保存状态与成片变更检测
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [hasUnrenderedChanges, setHasUnrenderedChanges] = useState<boolean>(false);
  const latestSubtitlesRef = useRef<SubtitleItem[]>([]);
  const latestStrategyRef = useRef<EditingStrategy>(DEFAULT_STRATEGY);
  const saveStatusTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 011: 导出确认弹窗与违禁词预检状态
  const [isExportModalOpen, setIsExportModalOpen] = useState<boolean>(false);
  const [bannedWordsCheck, setBannedWordsCheck] = useState<BannedWordsCheckResult | null>(null);
  const [isCheckingBannedWords, setIsCheckingBannedWords] = useState<boolean>(false);

  // 012: 封面设计与 AI 爆款文案状态
  const [coverConfig, setCoverConfig] = useState<CoverDesignConfig | null>(null);
  const [suggestedCoverTitles, setSuggestedCoverTitles] = useState<SuggestedCoverTitle[]>([]);

  useEffect(() => {
    latestSubtitlesRef.current = subtitles;
  }, [subtitles]);

  useEffect(() => {
    latestStrategyRef.current = strategy;
  }, [strategy]);

  const loadedProjectIdRef = useRef<string | null>(initialProjectId || null);
  const loadedThIdRef = useRef<string | null>(initialSelectedTalkingHeadId || null);
  const cutAbortControllerRef = useRef<AbortController | null>(null);
  const loadAbortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      cutAbortControllerRef.current?.abort();
      loadAbortControllerRef.current?.abort();
      if (pollingProgressTimerRef.current) {
        clearInterval(pollingProgressTimerRef.current);
        pollingProgressTimerRef.current = null;
      }
    };
  }, []);

  const loadProjectById = async (pid: string) => {
    if (!pid) return;
    if (loadAbortControllerRef.current) {
      loadAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    loadAbortControllerRef.current = controller;

    loadedProjectIdRef.current = pid;
    setLoadingProject(true);
    try {
      const proj = await fetchProjectById(pid, controller.signal);
      if (controller.signal.aborted) return;
      if (proj && proj.id) {
        setProjectId(proj.id);
        setProjectTitle(proj.title || '');
        setTargetRegion(proj.target_region || null);
        loadedProjectIdRef.current = proj.id;
        if (proj.talking_head_id) {
          setSelectedThId(proj.talking_head_id);
          loadedThIdRef.current = proj.talking_head_id;
          onTalkingHeadChanged?.(proj.talking_head_id);
        }
        if (onProjectLoaded) onProjectLoaded(proj.id);
        setSubtitles(proj.subtitles || []);
        setCompactSubtitles(proj.compact_subtitles || []);
        setBrolls(proj.broll_replacements || []);
        setPruneSpans(proj.prune_spans || []);
        if (proj.strategy) setStrategy(sanitizeStrategy(proj.strategy));
        if (proj.aspect_ratio === '16:9' || proj.aspect_ratio === '9:16') {
          setAspectRatio(proj.aspect_ratio as any);
        }
        if (proj.cover_image_path) {
          setCoverUrl(getMediaUrl(proj.cover_image_path.replace(/^\//, '')));
        } else {
          setCoverUrl('');
        }
        if (proj.cover_config) setCoverConfig(proj.cover_config);
        if (proj.suggested_cover_titles) setSuggestedCoverTitles(proj.suggested_cover_titles);
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
        setAiFeedback(`已秒级载入工程 ${proj.title}（共 ${proj.subtitles?.length || 0} 句字幕，${proj.broll_replacements?.length || 0} 处分镜）`);
      }
    } catch (e: any) {
      if (axios.isCancel(e) || e?.name === 'CanceledError' || controller.signal.aborted) {
        return;
      }
      console.error('载入指定工程失败:', e);
    } finally {
      if (!controller.signal.aborted) {
        setLoadingProject(false);
      }
    }
  };

  const loadProjectForMaterial = async (matId: string) => {
    if (!matId) return;
    if (loadAbortControllerRef.current) {
      loadAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    loadAbortControllerRef.current = controller;

    loadedThIdRef.current = matId;
    setLoadingProject(true);
    try {
      const proj = await fetchProjectByMaterial(matId, controller.signal);
      if (controller.signal.aborted) return;
      if (proj && proj.id) {
        setProjectId(proj.id);
        setProjectTitle(proj.title || '');
        setTargetRegion(proj.target_region || null);
        loadedProjectIdRef.current = proj.id;
        if (onProjectLoaded) onProjectLoaded(proj.id);
        setSubtitles(proj.subtitles || []);
        setCompactSubtitles(proj.compact_subtitles || []);
        setBrolls(proj.broll_replacements || []);
        setPruneSpans(proj.prune_spans || []);
        if (proj.strategy) setStrategy(sanitizeStrategy(proj.strategy));
        if (proj.aspect_ratio === '16:9' || proj.aspect_ratio === '9:16') {
          setAspectRatio(proj.aspect_ratio as any);
        }
        if (proj.cover_image_path) {
          setCoverUrl(getMediaUrl(proj.cover_image_path.replace(/^\//, '')));
        } else {
          setCoverUrl('');
        }
        if (proj.cover_config) setCoverConfig(proj.cover_config);
        if (proj.suggested_cover_titles) setSuggestedCoverTitles(proj.suggested_cover_titles);
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
        setAiFeedback(`已秒级载入工程磁盘缓存（共 ${proj.subtitles?.length || 0} 句字幕，${proj.broll_replacements?.length || 0} 处分镜）`);
        return;
      }
    } catch (e: any) {
      if (axios.isCancel(e) || e?.name === 'CanceledError' || controller.signal.aborted) {
        return;
      }
      // 404 说明未提取过或工程未建立
      setProjectId('');
      setProjectTitle('');
      setTargetRegion(null);
      loadedProjectIdRef.current = '';
      if (onProjectLoaded) onProjectLoaded('');
      setSubtitles([]);
      setCompactSubtitles([]);
      setBrolls([]);
      setOutputVideoUrl('');
      setCoverUrl('');
      setExportInfo(null);
      setPreviewMode('interactive');
      setIsCachedProject(false);
    } finally {
      if (!controller.signal.aborted) {
        setLoadingProject(false);
      }
    }
  };

  const handleUploadTalkingHead = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    try {
      setAnalyzing(true);
      const newMat = await uploadMaterial('talking_head', file);
      const allMats = await fetchMaterials();
      const map: Record<string, Material> = {};
      allMats.forEach(m => { map[m.id] = m; });
      setMaterialsMap(map);
      const updatedMaterials = allMats.filter(m => m.category === 'talking_head');
      setTalkingHeads(updatedMaterials);
      setSelectedThId(newMat.id);
      loadedThIdRef.current = newMat.id;
      onTalkingHeadChanged?.(newMat.id);
      await loadProjectForMaterial(newMat.id);
      setAiFeedback(`口播视频 ${file.name} 上传就绪！点击「智能初剪与纠偏」即可开启剪辑。`);
      fetchAllProjects().then(setAllProjects).catch(() => {});
    } catch (err: any) {
      showAlert({
        title: '上传口播视频失败',
        message: err?.response?.data?.detail || err.message,
        type: 'error'
      });
    } finally {
      setAnalyzing(false);
      if (uploadInputRef.current) uploadInputRef.current.value = '';
    }
  };

  // 组件初次挂载：载入素材列表、工程列表、硬件信息与默认工程/素材（仅执行一次，避免切标签或更新状态时重复刷新覆盖）
  useEffect(() => {
    fetchAllProjects().then(setAllProjects).catch(() => {});
    fetchMaterials().then(allMats => {
      const map: Record<string, Material> = {};
      allMats.forEach(m => { map[m.id] = m; });
      setMaterialsMap(map);
      const data = allMats.filter(m => m.category === 'talking_head');
      setTalkingHeads(data);
      if (initialProjectId) {
        loadProjectById(initialProjectId);
      } else if (initialSelectedTalkingHeadId && data.some(d => d.id === initialSelectedTalkingHeadId)) {
        setSelectedThId(initialSelectedTalkingHeadId);
        loadedThIdRef.current = initialSelectedTalkingHeadId;
        onTalkingHeadChanged?.(initialSelectedTalkingHeadId);
        loadProjectForMaterial(initialSelectedTalkingHeadId);
      } else if (data.length > 0 && !selectedThId) {
        setSelectedThId(data[0].id);
        loadedThIdRef.current = data[0].id;
        onTalkingHeadChanged?.(data[0].id);
        loadProjectForMaterial(data[0].id);
      }
    });
    fetchHardwareMetrics().then(setHardwareInfo).catch(() => {});
    fetchSettings().then(s => {
      setActiveEngine(s.active_harness || 'codex');
      setActiveModel(s.llm_model || 'GLM-5.3-Flash');
    }).catch(() => {});
  }, []);

  // 响应外部 project ID 变更（如从批量混剪列表点击进入指定工程）
  useEffect(() => {
    if (initialProjectId && initialProjectId !== loadedProjectIdRef.current) {
      if (saveStatus === 'dirty') {
        commitSubtitlesSave(latestSubtitlesRef.current);
      }
      if (strategySaveTimeoutRef.current && projectId) {
        clearTimeout(strategySaveTimeoutRef.current);
        strategySaveTimeoutRef.current = null;
        updateProjectStrategy(projectId, sanitizeStrategy(latestStrategyRef.current)).catch(() => {});
      }
      loadProjectById(initialProjectId);
    }
  }, [initialProjectId]);

  // 响应外部素材变更（如从素材库选择口播视频进入工作台）
  useEffect(() => {
    if (
      initialSelectedTalkingHeadId &&
      initialSelectedTalkingHeadId !== loadedThIdRef.current &&
      !initialProjectId
    ) {
      if (saveStatus === 'dirty') {
        commitSubtitlesSave(latestSubtitlesRef.current);
      }
      if (strategySaveTimeoutRef.current && projectId) {
        clearTimeout(strategySaveTimeoutRef.current);
        strategySaveTimeoutRef.current = null;
        updateProjectStrategy(projectId, sanitizeStrategy(latestStrategyRef.current)).catch(() => {});
      }
      setSelectedThId(initialSelectedTalkingHeadId);
      loadedThIdRef.current = initialSelectedTalkingHeadId;
      onTalkingHeadChanged?.(initialSelectedTalkingHeadId);
      const curMat = talkingHeads.find(t => t.id === initialSelectedTalkingHeadId);
      if (curMat && curMat.width && curMat.height && curMat.width > curMat.height) {
        setAspectRatio('16:9');
      }
      loadProjectForMaterial(initialSelectedTalkingHeadId);
    }
  }, [initialSelectedTalkingHeadId, initialProjectId]);

  const handleAnalyze = async (force: boolean = false) => {
    return handleOneClickCutAndCorrect(force);
  };

  const handleOneClickCutAndCorrect = async (force: boolean = false) => {
    if (!selectedThId) {
      showAlert({
        title: '提示',
        message: '请先选择或上传口播主视频',
        type: 'info'
      });
      return;
    }
    if (cutAbortControllerRef.current) {
      cutAbortControllerRef.current.abort();
    }
    if (pollingProgressTimerRef.current) {
      clearInterval(pollingProgressTimerRef.current);
      pollingProgressTimerRef.current = null;
    }
    const controller = new AbortController();
    cutAbortControllerRef.current = controller;

    setAnalyzing(true);
    setCorrectionsSummary(null);
    setOneClickStage('正在抽取高质量音频...');
    setPipelineProgress({
      project_id: selectedThId,
      stage: 'audio_extracting',
      percent: 15,
      message: '正在抽取高质量音频...',
    });

    const pollTimer = setInterval(async () => {
      try {
        if (controller.signal.aborted) {
          clearInterval(pollTimer);
          return;
        }
        const prog = await fetchProjectProgress(selectedThId, { signal: controller.signal });
        if (prog && prog.stage && !controller.signal.aborted) {
          setPipelineProgress(prog);
          if (prog.message) {
            setOneClickStage(prog.message);
          }
        }
      } catch (e) {
        // 静默忽略轮询偶发异常
      }
    }, 800);
    pollingProgressTimerRef.current = pollTimer;

    try {
      // 1. 语音提取 + 词级时间戳 + 黄金片段切分合并 + 大模型行业专词纠偏一体化完成（跳过耗时全量预压制）
      const res = await analyzeAndCutVideo(selectedThId, {
        aspectRatio: aspectRatio,
        autoBroll: true,
        forceRetranscribe: force,
        autoRender: false,
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setProjectId(res.id);
      setProjectTitle(res.title || '');
      setTargetRegion(res.target_region || null);
      loadedProjectIdRef.current = res.id;
      if (onProjectLoaded) {
        onProjectLoaded(res.id);
      }
      const currentSubs = res.subtitles || [];
      setSubtitles(currentSubs);
      setCompactSubtitles(res.compact_subtitles || []);
      if (res.broll_replacements) {
        setBrolls(res.broll_replacements);
      }
      setPruneSpans(res.prune_spans || []);
      if (res.strategy) {
        setStrategy(sanitizeStrategy(res.strategy));
      }
      if (res.cover_image_path) {
        setCoverUrl(getMediaUrl(res.cover_image_path.replace(/^\//, '')));
      } else {
        setCoverUrl('');
      }
      if (res.output_video_path) {
        const mediaUrl = getMediaUrl(res.output_video_path);
        setOutputVideoUrl(mediaUrl);
        setOutputTimestamp(Date.now());
        setExportInfo({
          url: mediaUrl,
          filename: res.output_filename || res.output_video_path.split('/').pop() || 'output.mp4',
          absolutePath: res.output_absolute_path || '',
          sizeMb: res.output_file_size_mb || 0,
        });
        setPreviewMode('rendered');
      } else {
        setPreviewMode('interactive');
      }
      setIsCachedProject(true);

      if (res.last_engine_used) {
        setLastEngineUsed(res.last_engine_used);
      }
      const actualCorrections = (res.corrections_summary || []).filter(
        c => c.original_text && c.corrected_text && c.original_text.trim() !== c.corrected_text.trim()
      );
      if (res.output_video_path) {
        if (actualCorrections.length > 0) {
          setCorrectionsSummary(actualCorrections);
          setAiFeedback(`智能剪辑与成片预览完成！已通过 ${res.last_engine_used || activeEngine} 智能修正 ${actualCorrections.length} 处专有词并自动保存。`);
        } else {
          setCorrectionsSummary(null);
          const costStr = res.correction_latency_ms ? `，耗时 ${Math.round(res.correction_latency_ms)}ms` : '';
          setAiFeedback(`智能剪辑与成片预览完成！ASR 识别准确度极高，未发现需要修正的同音错字${costStr}。`);
        }
      } else {
        if (actualCorrections.length > 0) {
          setCorrectionsSummary(actualCorrections);
          setAiFeedback(`智能初剪就绪（秒级极速）！已生成爆款标题、大模型高光词与双层分镜，修正 ${actualCorrections.length} 处专有名词。您可在此实时微调，确认后点击「⚡ 合成成片」出片。`);
        } else {
          setCorrectionsSummary(null);
          setAiFeedback(`智能初剪就绪（秒级极速）！已生成爆款标题、大模型高光词与双层分镜。您可在此实时微调，确认后点击「⚡ 合成成片」出片。`);
        }
      }
    } catch (err: any) {
      if (axios.isCancel(err) || err?.name === 'CanceledError' || controller.signal.aborted) {
        return;
      }
      const errDetail = err?.response?.data?.detail || err?.message || '智能剪辑失败，请检查服务日志与网络连接';
      showAlert({
        title: '智能剪辑失败',
        message: errDetail,
        type: 'error'
      });
    } finally {
      if (!controller.signal.aborted) {
        if (pollingProgressTimerRef.current) {
          clearInterval(pollingProgressTimerRef.current);
          pollingProgressTimerRef.current = null;
        }
        setAnalyzing(false);
        setOneClickStage('');
        setPipelineProgress(null);
      }
    }
  };

  const handleFastSceneDecision = async () => {
    if (!projectId) {
      showAlert({
        title: '提示',
        message: '请先选择或上传口播主视频创建工程',
        type: 'info'
      });
      return;
    }
    setAnalyzing(true);
    setOneClickStage('AI 双层分镜极速编排中（练车/场地/体验素材对齐）...');
    try {
      const res = await redecideScenes(projectId, 0.65);
      if (res && res.data) {
        if (res.data.subtitles) setSubtitles(res.data.subtitles);
        if (res.data.broll_replacements) setBrolls(res.data.broll_replacements);
        if (res.data.project?.target_region) setTargetRegion(res.data.project.target_region);
        const costStr = res.data.latency_ms ? `，耗时 ${Math.round(res.data.latency_ms)}ms` : '';
        setAiFeedback(`智能分镜编排完成！已通过 ${res.data.engine_used} 匹配 ${res.data.broll_replacements?.length || 0} 个空镜分镜（约 65% 黄金覆盖率${costStr}）。`);
      }
      setPreviewMode('interactive');
    } catch (err: any) {
      showAlert({
        title: '分镜编排失败',
        message: `智能分镜编排失败: ${err?.response?.data?.detail || err.message}`,
        type: 'error'
      });
    } finally {
      setAnalyzing(false);
      setOneClickStage('');
    }
  };

  const subtitleSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 统一字幕持久化提交（落库权威 SQLite，更新 saveStatus）
  const commitSubtitlesSave = async (subsToSave?: SubtitleItem[]): Promise<boolean> => {
    if (!projectId) return false;
    const data = subsToSave || latestSubtitlesRef.current;
    if (!data || data.length === 0) return false;
    if (subtitleSaveTimeoutRef.current) {
      clearTimeout(subtitleSaveTimeoutRef.current);
      subtitleSaveTimeoutRef.current = null;
    }
    setSaveStatus('saving');
    try {
      await updateProjectSubtitles(projectId, data);
      setSaveStatus('saved');
      setLastSavedAt(Date.now());
      if (saveStatusTimerRef.current) clearTimeout(saveStatusTimerRef.current);
      saveStatusTimerRef.current = setTimeout(() => {
        setSaveStatus(prev => (prev === 'saved' ? 'idle' : prev));
      }, 3000);
      return true;
    } catch (e) {
      console.error('Auto save subtitle failed', e);
      setSaveStatus('error');
      return false;
    }
  };

  // 失焦即存 (Immediate Flush on Blur)
  const handleTextBlur = async () => {
    if (saveStatus === 'dirty') {
      await commitSubtitlesSave(latestSubtitlesRef.current);
    }
  };

  // 单句文本不可变更新 + 500ms 防抖提交
  const handleTextChange = (idx: number, newText: string) => {
    if (previewMode === 'rendered') {
      setHasUnrenderedChanges(true);
    }
    const updated = subtitles.map((s, i) =>
      i === idx ? { ...s, corrected_text: newText, is_manual_edited: true } : s
    );
    latestSubtitlesRef.current = updated;
    setSubtitles(updated);
    setSaveStatus('dirty');
    setHasUnrenderedChanges(true);

    if (!projectId) return;
    if (subtitleSaveTimeoutRef.current) {
      clearTimeout(subtitleSaveTimeoutRef.current);
    }
    subtitleSaveTimeoutRef.current = setTimeout(async () => {
      await commitSubtitlesSave(updated);
    }, 500);
  };

  // 高亮词增删（手动来源标记 manual），不可变更新
  const handleHighlightWordsChange = (idx: number, words: { word: string; source: 'glossary' | 'ai' | 'manual' }[]) => {
    if (previewMode === 'rendered') {
      setHasUnrenderedChanges(true);
    }
    const updated = subtitles.map((s, i) =>
      i === idx ? { ...s, highlight_words: words as any, is_manual_edited: true } : s
    );
    latestSubtitlesRef.current = updated;
    setSubtitles(updated);
    setSaveStatus('dirty');
    setHasUnrenderedChanges(true);

    if (!projectId) return;
    if (subtitleSaveTimeoutRef.current) {
      clearTimeout(subtitleSaveTimeoutRef.current);
    }
    subtitleSaveTimeoutRef.current = setTimeout(async () => {
      await commitSubtitlesSave(updated);
    }, 500);
  };

  const handleTogglePrune = async (index: number, sub: SubtitleItem) => {
    if (!projectId || !sub.id) return;
    try {
      const res = await toggleSubtitlePrune(projectId, sub.id, !sub.is_pruned);
      if (res && res.success) {
        const updated = subtitles.map((item, i) =>
          i === index
            ? {
                ...item,
                is_pruned: res.is_pruned,
                prune_reason: res.is_pruned ? (item.prune_reason || 'manual') : null,
              }
            : item
        );
        latestSubtitlesRef.current = updated;
        setSubtitles(updated);
        setPruneSpans(res.prune_spans || []);
        if (res.compact_subtitles) {
          setCompactSubtitles(res.compact_subtitles);
        }
        setHasUnrenderedChanges(true);
        showToast(res.is_pruned ? '已标记剔除该片段' : '已恢复该片段', 'info');
      }
    } catch (e: any) {
      showAlert('切换剔除状态失败: ' + (e.message || '网络异常'));
    }
  };

  // 策略自动防抖保存 (600ms)，确保面板滑动或拖拽松开后 100% 自动固化到单一权威 SQLite 库
  const strategySaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleStrategyChange = (newStrategy: EditingStrategy) => {
    if (previewMode === 'rendered') {
      setHasUnrenderedChanges(true);
    }
    setStrategy(newStrategy);
    latestStrategyRef.current = newStrategy;
    setHasUnrenderedChanges(true);
    if (!projectId) return;
    setSaveStatus('dirty');
    if (strategySaveTimeoutRef.current) {
      clearTimeout(strategySaveTimeoutRef.current);
    }
    strategySaveTimeoutRef.current = setTimeout(async () => {
      try {
        setSaveStatus('saving');
        await updateProjectStrategy(projectId, sanitizeStrategy(newStrategy));
        setSaveStatus('saved');
        setLastSavedAt(Date.now());
        if (saveStatusTimerRef.current) clearTimeout(saveStatusTimerRef.current);
        saveStatusTimerRef.current = setTimeout(() => {
          setSaveStatus('idle');
        }, 3000);
      } catch (e) {
        console.error('Debounced strategy save failed', e);
        setSaveStatus('error');
      }
    }, 600);
  };

  const handleStrategyCommit = async (committedStrategy: EditingStrategy) => {
    if (previewMode === 'rendered') {
      setHasUnrenderedChanges(true);
    }
    if (strategySaveTimeoutRef.current) {
      clearTimeout(strategySaveTimeoutRef.current);
    }
    setStrategy(committedStrategy);
    latestStrategyRef.current = committedStrategy;
    setHasUnrenderedChanges(true);
    if (projectId) {
      try {
        setSaveStatus('saving');
        await updateProjectStrategy(projectId, sanitizeStrategy(committedStrategy));
        setSaveStatus('saved');
        setLastSavedAt(Date.now());
        if (saveStatusTimerRef.current) clearTimeout(saveStatusTimerRef.current);
        saveStatusTimerRef.current = setTimeout(() => {
          setSaveStatus('idle');
        }, 3000);
      } catch (e) {
        console.error('Immediate strategy save failed', e);
        setSaveStatus('error');
      }
    }
  };

  // 切出工作台时（isActive === false）立即强制冲刷落盘未保存的字幕与策略；切回时增量同步素材
  useEffect(() => {
    if (isActive === false) {
      if (saveStatus === 'dirty' || subtitleSaveTimeoutRef.current) {
        if (subtitleSaveTimeoutRef.current) {
          clearTimeout(subtitleSaveTimeoutRef.current);
          subtitleSaveTimeoutRef.current = null;
        }
        commitSubtitlesSave(latestSubtitlesRef.current);
      }
      if (strategySaveTimeoutRef.current) {
        clearTimeout(strategySaveTimeoutRef.current);
        strategySaveTimeoutRef.current = null;
        if (projectId && latestStrategyRef.current) {
          updateProjectStrategy(projectId, sanitizeStrategy(latestStrategyRef.current)).catch(() => {});
        }
      }
    } else if (isActive === true) {
      // 切回工作台时：静默增量刷新素材与工程列表，确保素材库新上传的文件即刻就绪，不干扰当前编辑
      fetchAllProjects().then(setAllProjects).catch(() => {});
      fetchMaterials().then(allMats => {
        const map: Record<string, Material> = {};
        allMats.forEach(m => { map[m.id] = m; });
        setMaterialsMap(map);
        setTalkingHeads(allMats.filter(m => m.category === 'talking_head'));
      }).catch(() => {});
    }
  }, [isActive, saveStatus, projectId]);

  // 组件卸载防丢安全兜底 (Unmount Flush)
  useEffect(() => {
    return () => {
      if (subtitleSaveTimeoutRef.current) {
        clearTimeout(subtitleSaveTimeoutRef.current);
      }
      if (latestSubtitlesRef.current && latestSubtitlesRef.current.length > 0 && projectId) {
        updateProjectSubtitles(projectId, latestSubtitlesRef.current).catch(() => {});
      }
      if (strategySaveTimeoutRef.current) {
        clearTimeout(strategySaveTimeoutRef.current);
      }
      if (latestStrategyRef.current && projectId) {
        updateProjectStrategy(projectId, sanitizeStrategy(latestStrategyRef.current)).catch(() => {});
      }
    };
  }, [projectId]);

  const handleOpenExportModal = async () => {
    if (!projectId) return;
    setIsExportModalOpen(true);
    setIsCheckingBannedWords(true);
    try {
      const checkRes = await checkBannedWords(projectId);
      setBannedWordsCheck(checkRes);
    } catch (e) {
      console.error('Failed to check banned words', e);
    } finally {
      setIsCheckingBannedWords(false);
    }
  };

  // 重新合成：仅作为剪辑台调整字幕/策略/分镜时的日常预览压制，绝对不做违禁词处理，不弹窗打扰
  const handleRecompose = () => {
    handleExecuteRender(false);
  };

  const handleExecuteRender = async (
    filterBannedWords: boolean = true,
    newCoverConfig?: CoverDesignConfig,
    exportDir?: string,
    includeCover: boolean = true,
    embedCoverFirstFrame: boolean = false
  ) => {
    if (!projectId) return;
    setRendering(true);
    setAiFeedback(null);
    try {
      if (newCoverConfig) {
        setCoverConfig(newCoverConfig);
      }
      // 1. 前置守卫：强制取消未完成防抖，链式同步落盘最新字幕与策略
      if (subtitleSaveTimeoutRef.current) {
        clearTimeout(subtitleSaveTimeoutRef.current);
        subtitleSaveTimeoutRef.current = null;
      }
      if (strategySaveTimeoutRef.current) {
        clearTimeout(strategySaveTimeoutRef.current);
        strategySaveTimeoutRef.current = null;
      }

      setSaveStatus('saving');
      const subsToSave = latestSubtitlesRef.current.length > 0 ? latestSubtitlesRef.current : subtitles;
      const rawStrat = latestStrategyRef.current || strategy;
      const stratToSave = sanitizeStrategy(rawStrat);
      setStrategy(stratToSave);
      latestStrategyRef.current = stratToSave;

      await updateProjectSubtitles(projectId, subsToSave);
      await updateProjectStrategy(projectId, stratToSave);
      setSaveStatus('saved');
      setLastSavedAt(Date.now());

      // 2. 发起高质量复合渲染 (Lanczos 算法 + CRF 18 高清画质 + 原生 Emoji 横幅 + ASS 高亮字幕)
      const targetSpeed = Number((latestStrategyRef.current?.video_speed ?? strategy.video_speed) || 1.0);
      const res = await renderProject(projectId, targetSpeed, filterBannedWords, exportDir, includeCover, embedCoverFirstFrame);
      if (res.status === 'failed' || !res.output_video_path) {
        throw new Error('渲染引擎未生成有效成片，请检查后台日志或素材');
      }
      if (res.title) {
        setProjectTitle(res.title);
      }
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
      if (res.cover_image_path) {
        setCoverUrl(getMediaUrl(res.cover_image_path.replace(/^\//, '')));
      }
      if (res.cover_config) {
        setCoverConfig(res.cover_config);
      }
      if (res.suggested_cover_titles) {
        setSuggestedCoverTitles(res.suggested_cover_titles);
      }
      if (res.compact_subtitles) {
        setCompactSubtitles(res.compact_subtitles);
      }
      if (res.prune_spans) {
        setPruneSpans(res.prune_spans);
      }
      if (res.subtitles) {
        setSubtitles(res.subtitles);
      }
      // 若当前导出了封面且压入了片头，播放指针归零使预览直接呈现最新封面；否则若处于片头空白无字幕阶段，对齐第一条字幕
      if (includeCover && embedCoverFirstFrame) {
        setCurrentTime(0);
      } else {
        const firstActiveStart = res.compact_subtitles?.[0]?.start_time ?? subtitles[0]?.start_time ?? 0.2;
        if (currentTime < firstActiveStart) {
          setCurrentTime(firstActiveStart);
        }
      }
      setPreviewMode('rendered');
      setHasUnrenderedChanges(false);
      setIsExportModalOpen(false);
      const exportFeedback = exportDir
        ? `🎉 成片已导出并另存至目标目录：${exportDir}`
        : filterBannedWords
        ? '🎉 最终成片已完成合规清洗并导出成功！'
        : '🎉 新成片已复合压制完成并替代前序版本！已自动切换为高清成片预览。';
      setAiFeedback(exportFeedback);
      showToast(exportDir ? `成片与封面已保存至: ${exportDir}` : '成片导出成功！', 'success');
    } catch (err: any) {
      showAlert({
        title: '渲染合成失败',
        message: `渲染合成失败: ${err?.response?.data?.detail || err.message || '请检查后端服务与 FFmpeg 可用性'}`,
        type: 'error'
      });
    } finally {
      setRendering(false);
    }
  };

  const handleSaveTitle = async (newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed || trimmed === projectTitle || !projectId) {
      setIsEditingTitle(false);
      return;
    }
    try {
      await updateProjectTitle(projectId, trimmed);
      setProjectTitle(trimmed);
      fetchAllProjects().then(setAllProjects).catch(() => {});
      showToast('视频标题已更新', 'success');
    } catch (e: any) {
      showAlert({ title: '修改标题失败', message: e?.message || '网络异常', type: 'error' });
    } finally {
      setIsEditingTitle(false);
    }
  };

  const handleOpenFolder = async () => {
    try {
      await openFolder(exportInfo?.absolutePath);
      setFolderOpened(true);
      setAiFeedback(`已在系统文件管理器中高亮定位：${exportInfo?.filename || '导出目录'}`);
      setTimeout(() => setFolderOpened(false), 3000);
    } catch (e) {
      showToast('打开所在文件夹失败，请检查系统权限', 'error');
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
      const cleanTitle = (projectTitle || exportInfo.filename || '成片')
        .replace(/[\\/*?:"<>|\r\n\t]+/g, '_')
        .replace(/^[ ._]+|[ ._]+$/g, '')
        .replace(/\.mp4$/i, '');
      a.download = `${cleanTitle}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  const editedTalkingHeads = talkingHeads.filter(t => allProjects.some(p => p.talking_head_id === t.id));
  const uneditedTalkingHeads = talkingHeads.filter(t => !allProjects.some(p => p.talking_head_id === t.id));
  const filteredTalkingHeads =
    projectFilterTab === 'edited'
      ? editedTalkingHeads
      : projectFilterTab === 'unedited'
        ? uneditedTalkingHeads
        : talkingHeads;

  const handleDeleteTalkingHead = async (material: Material, e: React.MouseEvent) => {
    e.stopPropagation();
    const matchedProj = allProjects.find(p => p.talking_head_id === material.id);
    const titleText = matchedProj?.title || material.filename;

    const confirmed = await showConfirm({
      title: '确认删除视频与工程',
      message: `确定要彻底删除「${titleText}」吗？相关工程配置与素材文件将从磁盘彻底删除，此操作不可撤销。`,
      isDestructive: true,
      confirmText: '彻底删除'
    });
    if (!confirmed) return;

    try {
      if (matchedProj) {
        try {
          await deleteProjectByMaterial(material.id);
        } catch (e: any) {
          if (e?.response?.status !== 404) throw e;
        }
      }
      try {
        await deleteMaterial(material.id);
      } catch (e: any) {
        if (e?.response?.status !== 404) throw e;
      }

      setTalkingHeads(prev => prev.filter(m => m.id !== material.id));
      setAllProjects(prev => prev.filter(p => p.talking_head_id !== material.id));
      showToast('视频工程及素材已删除');

      if (material.id === selectedThId) {
        const remaining = talkingHeads.filter(m => m.id !== material.id);
        if (remaining.length > 0) {
          const nextMat = remaining[0];
          setSelectedThId(nextMat.id);
          loadedThIdRef.current = nextMat.id;
          onTalkingHeadChanged?.(nextMat.id);
          const nextProj = allProjects.find(p => p.talking_head_id === nextMat.id);
          if (nextProj) {
            loadProjectById(nextProj.id);
          } else {
            loadProjectForMaterial(nextMat.id);
          }
        } else {
          setSelectedThId('');
          setProjectId('');
          setProjectTitle('');
          setSubtitles([]);
          setCompactSubtitles([]);
          setBrolls([]);
          setPruneSpans([]);
        }
      }
    } catch (err: any) {
      console.error('删除视频素材失败:', err);
      showAlert({
        title: '删除失败',
        message: err?.response?.data?.detail || '删除视频素材失败，请稍后重试。',
        type: 'error'
      });
    }
  };

  const handleCleanUneditedTalkingHeads = async () => {
    const unedited = talkingHeads.filter(t => !allProjects.some(p => p.talking_head_id === t.id));
    if (unedited.length === 0) return;

    const confirmed = await showConfirm({
      title: '清理所有待剪辑素材',
      message: `检测到 ${unedited.length} 个未初剪、无工程的口播素材。确定要将它们全部从本地磁盘彻底清理吗？`,
      isDestructive: true,
      confirmText: '一键清理'
    });
    if (!confirmed) return;

    try {
      let successCount = 0;
      for (const item of unedited) {
        try {
          await deleteMaterial(item.id);
          successCount++;
        } catch (e) {
          console.error(`清理素材 ${item.id} 失败:`, e);
        }
      }
      const uneditedIds = new Set(unedited.map(m => m.id));
      setTalkingHeads(prev => prev.filter(m => !uneditedIds.has(m.id)));
      showToast(`已成功清理 ${successCount} 个待剪辑素材`);

      if (uneditedIds.has(selectedThId)) {
        const remaining = talkingHeads.filter(m => !uneditedIds.has(m.id));
        if (remaining.length > 0) {
          const nextMat = remaining[0];
          setSelectedThId(nextMat.id);
          loadedThIdRef.current = nextMat.id;
          onTalkingHeadChanged?.(nextMat.id);
          const nextProj = allProjects.find(p => p.talking_head_id === nextMat.id);
          if (nextProj) {
            loadProjectById(nextProj.id);
          } else {
            loadProjectForMaterial(nextMat.id);
          }
        } else {
          setSelectedThId('');
          setProjectId('');
          setProjectTitle('');
          setSubtitles([]);
          setCompactSubtitles([]);
          setBrolls([]);
          setPruneSpans([]);
        }
      }
    } catch (err: any) {
      showAlert({ title: '清理失败', message: '清理过程中出现异常。', type: 'error' });
    }
  };

  const currentMaterial = talkingHeads.find(t => t.id === selectedThId);
  const displayTitle = projectTitle || currentMaterial?.filename || '选择视频工程';

  const rawVideoUrl = selectedThId && currentMaterial
    ? getMediaUrl(currentMaterial.filepath || '')
    : '';

  const currentPreviewUrl = (previewMode === 'rendered' && outputVideoUrl)
    ? `${outputVideoUrl}?v=${outputTimestamp}`
    : rawVideoUrl;

  return (
    <div className="flex flex-col h-full max-h-full max-w-7xl mx-auto p-3 overflow-hidden">
      {/* 顶部操作条：口播素材选择、智能剪辑触发 */}
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

          {/* 视频工程卡片选择按钮（展示真实视频标题） */}
          <div className="flex items-center space-x-1">
            <button
              type="button"
              onClick={() => {
                fetchAllProjects().then(setAllProjects).catch(() => {});
                fetchMaterials().then(allMats => {
                  const map: Record<string, Material> = {};
                  allMats.forEach(m => { map[m.id] = m; });
                  setMaterialsMap(map);
                  setTalkingHeads(allMats.filter(m => m.category === 'talking_head'));
                }).catch(() => {});
                setShowProjectPicker(true);
              }}
              title={displayTitle}
              className="flex items-center space-x-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl px-3 py-1.5 text-xs text-gray-800 transition-all cursor-pointer shadow-xs max-w-[280px]"
            >
              <Film className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
              <span className="font-semibold truncate">
                {displayTitle}
              </span>
              {selectedThId && (
                <span className="text-[10px] text-gray-400 font-mono flex-shrink-0">
                  ({talkingHeads.find(t => t.id === selectedThId)?.duration?.toFixed(1)}s)
                </span>
              )}
              <ChevronDown className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
            </button>
            {projectId && !isEditingTitle && (
              <button
                type="button"
                onClick={() => {
                  setTempTitle(projectTitle || displayTitle);
                  setIsEditingTitle(true);
                }}
                className="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
                title="修改视频标题"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
            )}
            {isEditingTitle && (
              <div className="flex items-center space-x-1 bg-white border border-indigo-300 rounded-xl px-2 py-1 shadow-xs">
                <input
                  type="text"
                  value={tempTitle}
                  autoFocus
                  onChange={(e) => setTempTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveTitle(tempTitle);
                    if (e.key === 'Escape') setIsEditingTitle(false);
                  }}
                  className="text-xs px-1 py-0.5 border-b border-indigo-400 outline-none w-44 text-gray-800 font-medium"
                  placeholder="输入视频标题"
                />
                <button
                  type="button"
                  onClick={() => handleSaveTitle(tempTitle)}
                  className="p-1 text-emerald-600 hover:bg-emerald-50 rounded cursor-pointer"
                  title="保存标题"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditingTitle(false)}
                  className="p-1 text-gray-400 hover:bg-gray-100 rounded cursor-pointer"
                  title="取消"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* 目标城市车牌属地徽章（AI 自动识别，同城防穿帮） */}
          {targetRegion && (
            <span
              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/80 shadow-2xs whitespace-nowrap cursor-default"
              title={`AI 智能识别城市车牌: ${formatRegionBadge(targetRegion)}（严格同城分镜，0 跨市穿帮）`}
            >
              <MapPin className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
              <span>{formatRegionBadge(targetRegion)}</span>
            </span>
          )}

          {/* 剪辑工作台单独上传口播视频直接开剪按钮 */}
          <button
            type="button"
            onClick={() => uploadInputRef.current?.click()}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium border border-gray-200 transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-gray-500" />
            <span>上传口播</span>
          </button>

          {/* 比例切换 (9:16 / 16:9) */}
          <div className="flex items-center space-x-0.5 bg-gray-100 p-0.5 rounded-lg border border-gray-200/80">
            <button
              type="button"
              onClick={() => setAspectRatio('9:16')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                aspectRatio === '9:16' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              9:16 竖屏
            </button>
            <button
              type="button"
              onClick={() => setAspectRatio('16:9')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                aspectRatio === '16:9' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              16:9 横屏
            </button>
          </div>
        </div>

        {/* 智能剪辑与出片按钮区 */}
        <div className="flex items-center space-x-2.5">

          {/* 智能剪辑主按钮 */}
          {loadingProject ? (
            <div className="flex items-center space-x-1.5 bg-gray-100 text-gray-500 text-xs font-medium px-3.5 py-1.5 rounded-xl">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-gray-400" />
              <span>载入工程中...</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleOneClickCutAndCorrect(true)}
                disabled={analyzing || !selectedThId}
                className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-semibold px-3.5 py-1.5 rounded-xl transition-all shadow-xs disabled:opacity-50 cursor-pointer"
                title="运行 ASR 提取、大模型分镜与高光词极速编排"
              >
                {analyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-200" />}
                <span>{analyzing ? (oneClickStage || '智能剪辑中...') : '智能初剪'}</span>
              </button>

              {projectId && (
                <>
                  <button
                    onClick={handleRecompose}
                    disabled={rendering || analyzing}
                    className="flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white text-xs font-semibold px-3.5 py-1.5 rounded-xl transition-all shadow-xs disabled:opacity-50 cursor-pointer"
                    title="调用 FFmpeg 复合压制生成高清成片预览（不做违禁词处理）"
                  >
                    {rendering ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Film className="w-3.5 h-3.5 text-emerald-200" />}
                    <span>{rendering ? '正在合成...' : (outputVideoUrl ? `⚡ 重新合成 (${Number(strategy.video_speed || 1.0).toFixed(2)}x)` : '⚡ 合成成片')}</span>
                  </button>

                  {/* 导出倍速自选控件：支持键入任意数值 (如 1.08, 1.15) */}
                  <div
                    className="flex items-center space-x-1 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl px-2 py-1 text-xs transition-colors"
                    title="自定义成片压制导出倍速（支持键入任意数值，步长 0.01）"
                  >
                    <span className="text-gray-500 font-medium whitespace-nowrap text-[11px]">倍速:</span>
                    <div className="flex items-center bg-white border border-gray-200 rounded-lg px-1.5 py-0.5 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500/20 shadow-2xs">
                      <input
                        type="number"
                        step="0.01"
                        min="0.5"
                        max="2.5"
                        value={strategy.video_speed ?? 1.0}
                        onChange={e => {
                          const val = parseFloat(e.target.value);
                          const nextSpeed = isNaN(val) ? 1.0 : Math.max(0.5, Math.min(2.5, Math.round(val * 100) / 100));
                          handleStrategyChange({ ...strategy, video_speed: nextSpeed });
                        }}
                        className="w-10 text-center text-xs font-mono font-bold text-indigo-700 outline-none bg-transparent"
                        title="键入任意倍率（如 1.08、1.12、1.15、1.25）"
                      />
                      <span className="text-gray-400 text-[10px] font-mono">x</span>
                    </div>
                    {/* 快捷芯片 */}
                    <div className="hidden lg:flex items-center space-x-0.5 border-l border-gray-200/80 pl-1">
                      {[1.0, 1.15, 1.25].map(v => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => handleStrategyChange({ ...strategy, video_speed: v })}
                          className={`px-1 py-0.5 rounded text-[10px] font-mono transition-colors cursor-pointer ${
                            Math.abs((strategy.video_speed || 1.0) - v) < 0.005
                              ? 'text-indigo-700 font-bold bg-indigo-50'
                              : 'text-gray-400 hover:text-gray-700'
                          }`}
                        >
                          {v}x
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 导出成片主按钮（放在顶部！） */}
                  <button
                    onClick={handleOpenExportModal}
                    disabled={rendering || !projectId}
                    className="bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-semibold px-3.5 py-1.5 rounded-xl transition-all shadow-xs disabled:opacity-50 flex items-center space-x-1.5 whitespace-nowrap cursor-pointer"
                    title="选择导出目录、配置爆款封面与清洗违禁词并导出成片"
                  >
                    {rendering ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Film className="w-3.5 h-3.5" />
                    )}
                    <span>{rendering ? '压制导出中...' : '🎬 导出成片'}</span>
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 智能初剪长任务 4 阶段进度条指示组件 */}
      {analyzing && (() => {
        const currentPercent = pipelineProgress?.percent ?? 15;
        const currentMessage = pipelineProgress?.message || oneClickStage || '正在抽取高质量音频...';
        const steps = [
          { step: 1, label: '抽取音频', targetPercent: 15, matchStages: ['audio_extracting'] },
          { step: 2, label: '语音转写', targetPercent: 45, matchStages: ['asr_transcribing'] },
          { step: 3, label: 'AI专词纠偏', targetPercent: 70, matchStages: ['llm_correcting'] },
          { step: 4, label: '双层分镜', targetPercent: 90, matchStages: ['scene_deciding', 'broll_matching', 'video_composing'] },
        ];

        return (
          <div className="mb-4 bg-gradient-to-r from-indigo-50/90 via-sky-50/80 to-indigo-50/90 border border-indigo-200/80 rounded-2xl p-4 shadow-sm animate-in fade-in duration-300">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-semibold text-gray-900">智能初剪与纠偏进行中</span>
                    <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                      {currentPercent}%
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-600 mt-0.5">{currentMessage}</p>
                </div>
              </div>
              <div className="text-[11px] font-mono text-gray-400">
                AI Harness Pipeline
              </div>
            </div>

            {/* 动态推进进度条 */}
            <div className="w-full bg-indigo-100/70 rounded-full h-2 mb-3.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-indigo-600 via-sky-500 to-indigo-600 h-2 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${Math.min(100, Math.max(8, currentPercent))}%` }}
              />
            </div>

            {/* 四阶段指示节点 */}
            <div className="grid grid-cols-4 gap-2">
              {steps.map((st) => {
                const isDone = currentPercent > st.targetPercent || currentPercent === 100;
                const isCurrent =
                  !isDone &&
                  (pipelineProgress?.stage
                    ? st.matchStages.includes(pipelineProgress.stage)
                    : currentPercent >= st.targetPercent - 20);

                return (
                  <div
                    key={st.step}
                    className={`flex items-center space-x-2 px-2.5 py-1.5 rounded-xl border transition-all text-xs ${
                      isDone
                        ? 'bg-white/80 border-emerald-200 text-emerald-800'
                        : isCurrent
                        ? 'bg-white border-indigo-300 text-indigo-900 shadow-xs ring-1 ring-indigo-200'
                        : 'bg-white/40 border-gray-200/60 text-gray-400'
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                        isDone
                          ? 'bg-emerald-500 text-white'
                          : isCurrent
                          ? 'bg-indigo-600 text-white animate-pulse'
                          : 'bg-gray-200 text-gray-500'
                      }`}
                    >
                      {isDone ? '✓' : st.step}
                    </div>
                    <div className="min-w-0 flex-1 truncate">
                      <span className="font-medium text-[11px] truncate block">{st.label}</span>
                    </div>
                    <span className="text-[10px] font-mono opacity-60 shrink-0">{st.targetPercent}%</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* 智能纠错结果明细提示（仅当真正存在错字修正时展示，杜绝无意义自嗨提示） */}
      {correctionsSummary && correctionsSummary.filter(c => c.original_text && c.corrected_text && c.original_text.trim() !== c.corrected_text.trim()).length > 0 && (() => {
        const actualList = correctionsSummary.filter(c => c.original_text && c.corrected_text && c.original_text.trim() !== c.corrected_text.trim());
        return (
          <div className="mb-4 bg-amber-50/90 border border-amber-200 rounded-2xl p-4 shadow-sm text-xs text-amber-950 animate-in fade-in">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold flex items-center space-x-1.5">
                <Sparkles className="w-4 h-4 text-amber-600" />
                <span>已通过 {lastEngineUsed || activeEngine} 完成智能语义纠错（共修正 {actualList.length} 处）：</span>
              </span>
              <button
                onClick={() => setCorrectionsSummary(null)}
                className="text-amber-600 hover:text-amber-800 text-xs"
              >
                ✕ 收起
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {actualList.map((item, i) => (
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
        );
      })()}

      {/* 主体工作台：左侧播放器（即时策略预览），右侧选项卡（时间轴 vs 策略组合工坊） - 始终保持左右双栏工作台布局 */}
      <div className="flex-1 grid grid-cols-12 gap-3.5 min-h-0 overflow-hidden">
        <div className="col-span-5 h-full min-h-0 flex flex-col items-center justify-center overflow-hidden">
          {/* 极简模式切换与封面工具栏 */}
          <div className="w-full flex items-center justify-between px-1 pb-1.5 text-xs flex-shrink-0">
            {/* Segmented Switch: 实时编辑 | 成片预览 */}
            <div className="inline-flex p-0.5 bg-gray-100 rounded-lg border border-gray-200/80">
              <button
                type="button"
                onClick={() => setPreviewMode('interactive')}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  previewMode === 'interactive'
                    ? 'bg-white text-gray-900 shadow-xs font-semibold'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                实时编辑
              </button>
              <button
                type="button"
                disabled={!outputVideoUrl}
                onClick={() => setPreviewMode('rendered')}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer flex items-center space-x-1 ${
                  previewMode === 'rendered'
                    ? 'bg-white text-indigo-600 shadow-xs font-semibold'
                    : outputVideoUrl
                    ? 'text-gray-500 hover:text-gray-800'
                    : 'text-gray-300 cursor-not-allowed'
                }`}
                title={outputVideoUrl ? '查看已压制成片' : '尚未导出成片'}
              >
                <span>成片预览</span>
                {outputVideoUrl && <span className="w-1.5 h-1.5 rounded-full bg-indigo-600"></span>}
              </button>
            </div>

            {/* 封面操作与缩略图 */}
            <div className="flex items-center space-x-2 text-[11px]">
              {coverUrl && (
                <img src={coverUrl} alt="封面" className="w-6 h-6 object-cover rounded border border-gray-200" title="当前工程封面" />
              )}
              {projectId && (
                <>
                  <input
                    type="file"
                    ref={coverFileInputRef}
                    accept="image/*"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setSettingCover(true);
                      try {
                        const data = await uploadProjectCoverFile(projectId, file);
                        setCoverUrl(getMediaUrl(data.cover_url.replace(/^\//, '')));
                        showToast('封面上传成功', 'success');
                        setAiFeedback('封面图片已上传成功。');
                      } catch (err: any) {
                        showToast(err?.response?.data?.detail || '上传封面失败', 'error');
                      } finally {
                        setSettingCover(false);
                        if (coverFileInputRef.current) coverFileInputRef.current.value = '';
                      }
                    }}
                  />
                  <button
                    onClick={() => coverFileInputRef.current?.click()}
                    disabled={settingCover}
                    className="text-gray-600 hover:text-indigo-600 px-1.5 py-0.5 rounded hover:bg-gray-100 font-medium transition-colors flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                  >
                    <Upload className="w-3 h-3 text-gray-500" />
                    <span>上传封面</span>
                  </button>
                </>
              )}
              {outputVideoUrl && previewMode === 'rendered' && projectId && (
                <button
                  onClick={async () => {
                    setSettingCover(true);
                    try {
                      const data = await setProjectCover(projectId, 'frame', currentTime);
                      setCoverUrl(getMediaUrl(data.cover_url.replace(/^\//, '')));
                      showToast('已将当前画面设为封面', 'success');
                      setAiFeedback('已将当前画面设为封面。');
                    } catch (err: any) {
                      showToast(err?.response?.data?.detail || '设置封面失败', 'error');
                    } finally {
                      setSettingCover(false);
                    }
                  }}
                  disabled={settingCover}
                  className="text-gray-600 hover:text-indigo-600 px-1.5 py-0.5 rounded hover:bg-gray-100 font-medium transition-colors flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                >
                  <ImageIcon className="w-3 h-3 text-gray-500" />
                  <span>{settingCover ? '截取中...' : '截取当前帧'}</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => setIsPlayerEnlarged(prev => !prev)}
                className="text-gray-600 hover:text-indigo-600 px-1.5 py-0.5 rounded hover:bg-gray-100 font-medium transition-colors flex items-center space-x-1 cursor-pointer"
                title="放大观看 (Esc 退出)"
              >
                <Maximize2 className="w-3 h-3 text-gray-500" />
                <span>放大观看</span>
              </button>
            </div>
          </div>

          {/* 成片模式下内容已修改告警条 */}
          {previewMode === 'rendered' && hasUnrenderedChanges && (
            <div className="w-full mb-1.5 px-3 py-1.5 bg-amber-50 border border-amber-300/80 rounded-xl flex items-center justify-between text-[11px] text-amber-900 shadow-xs animate-in fade-in flex-shrink-0">
              <div className="flex items-center space-x-1.5 truncate mr-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                <span className="truncate font-medium">字幕或策略已修改，当前画面仍为上一版成片</span>
              </div>
              <div className="flex items-center space-x-1.5 flex-shrink-0">
                <button
                  onClick={() => setPreviewMode('interactive')}
                  className="px-2 py-0.5 bg-white border border-amber-300 rounded-lg text-amber-800 hover:bg-amber-100 font-medium transition-all cursor-pointer"
                >
                  实时预览
                </button>
                <button
                  onClick={handleRecompose}
                  disabled={rendering}
                  className="px-2.5 py-0.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg font-semibold hover:from-blue-700 hover:to-indigo-700 shadow-xs disabled:opacity-50 cursor-pointer"
                >
                  {rendering ? '合成中...' : `⚡ 重新合成 (${Number(strategy.video_speed || 1.0).toFixed(2)}x)`}
                </button>
              </div>
            </div>
          )}

          <VideoPlayer
            videoUrl={currentPreviewUrl}
            brolls={brolls}
            materialsMap={materialsMap}
            subtitles={previewMode === 'rendered' ? (compactSubtitles && compactSubtitles.length > 0 ? compactSubtitles : subtitles) : subtitles}
            currentTime={currentTime}
            onTimeUpdate={setCurrentTime}
            aspectRatio={aspectRatio}
            onAspectRatioChange={setAspectRatio}
            strategy={strategy}
            onStrategyChange={handleStrategyChange}
            onStrategyCommit={handleStrategyCommit}
            isRendered={previewMode === 'rendered'}
            isActive={isActive}
            pruneSpans={pruneSpans}
            isEnlarged={isPlayerEnlarged}
            onToggleEnlarge={() => setIsPlayerEnlarged(prev => !prev)}
          />
        </div>

        <div className="col-span-7 h-full min-h-0 flex flex-col overflow-hidden bg-white rounded-2xl border border-gray-200/80 shadow-sm p-3">
          {/* 工作区模式切换 Tabs */}
          <div className="flex items-center justify-between border-b border-gray-100 pb-2 mb-2.5 flex-shrink-0">
            <div className="flex items-center space-x-2 bg-gray-100 p-1 rounded-xl">
              <button
                type="button"
                onClick={() => setActiveTab('subtitles')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'subtitles'
                    ? 'bg-white text-gray-900 shadow-xs font-semibold'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <ListOrdered className="w-3.5 h-3.5 text-indigo-600" />
                <span>字幕与分镜 ({subtitles.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('strategy')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'strategy'
                    ? 'bg-white text-indigo-600 shadow-xs font-semibold'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <Sliders className="w-3.5 h-3.5 text-indigo-600" />
                <span>策略工坊</span>
              </button>
            </div>
          </div>

          {/* 模式内容容器 */}
          <div className="flex-1 overflow-y-auto pr-1">
            {activeTab === 'subtitles' ? (
              <SubtitleList
                subtitles={subtitles}
                compactSubtitles={compactSubtitles}
                isCompactMode={previewMode === 'rendered'}
                currentTime={currentTime}
                saveStatus={saveStatus}
                lastSavedAt={lastSavedAt}
                onSelectTime={setCurrentTime}
                onTextChange={handleTextChange}
                onTextBlur={handleTextBlur}
                onHighlightWordsChange={handleHighlightWordsChange}
                onRetrySave={() => commitSubtitlesSave(latestSubtitlesRef.current)}
                onTogglePrune={handleTogglePrune}
              />
            ) : (
              <StrategyStudio
                strategy={strategy}
                onChange={handleStrategyChange}
                pruneSpans={pruneSpans}
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

      {/* 视频工程卡片网格选择抽屉/弹窗 */}
      {showProjectPicker && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[80vh] shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-wrap gap-2">
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2">
                  <Film className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-sm font-bold text-gray-900">选择视频工程</h3>
                </div>
                {/* 过滤 Tab 切换 */}
                <div className="flex items-center bg-gray-100 p-0.5 rounded-lg text-xs font-medium">
                  <button
                    type="button"
                    onClick={() => setProjectFilterTab('all')}
                    className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                      projectFilterTab === 'all'
                        ? 'bg-white text-gray-900 shadow-xs'
                        : 'text-gray-500 hover:text-gray-800'
                    }`}
                  >
                    全部 ({talkingHeads.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setProjectFilterTab('edited')}
                    className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                      projectFilterTab === 'edited'
                        ? 'bg-white text-blue-600 shadow-xs'
                        : 'text-gray-500 hover:text-gray-800'
                    }`}
                  >
                    已剪辑 ({editedTalkingHeads.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setProjectFilterTab('unedited')}
                    className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                      projectFilterTab === 'unedited'
                        ? 'bg-white text-amber-600 shadow-xs'
                        : 'text-gray-500 hover:text-gray-800'
                    }`}
                  >
                    待剪辑 ({uneditedTalkingHeads.length})
                  </button>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {uneditedTalkingHeads.length > 0 && (
                  <button
                    type="button"
                    onClick={handleCleanUneditedTalkingHeads}
                    className="flex items-center space-x-1 px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-600 text-xs rounded-lg font-medium cursor-pointer transition-colors"
                    title="一键清理所有未初剪的口播素材"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>清理待剪辑 ({uneditedTalkingHeads.length})</span>
                  </button>
                )}
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
              {filteredTalkingHeads.length === 0 ? (
                <div className="py-12 text-center text-xs text-gray-400">
                  {projectFilterTab === 'edited'
                    ? '暂无已剪辑工程，可在全部或待剪辑中选择视频进行智能剪辑'
                    : projectFilterTab === 'unedited'
                    ? '没有待剪辑的视频素材'
                    : '暂无口播视频，点击右上角「上传新口播」添加'}
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {filteredTalkingHeads.map(t => {
                    const isSelected = t.id === selectedThId;
                    const matchedProj = allProjects.find(p => p.talking_head_id === t.id);
                    const coverUrl = matchedProj?.cover_image_path ? getMediaUrl(matchedProj.cover_image_path) : '';
                    const cardTitle = matchedProj?.title || t.filename;
                    return (
                      <div
                        key={t.id}
                        onClick={() => {
                          if (saveStatus === 'dirty') {
                            commitSubtitlesSave(latestSubtitlesRef.current);
                          }
                          if (strategySaveTimeoutRef.current && projectId) {
                            clearTimeout(strategySaveTimeoutRef.current);
                            strategySaveTimeoutRef.current = null;
                            updateProjectStrategy(projectId, sanitizeStrategy(latestStrategyRef.current)).catch(() => {});
                          }
                          setSelectedThId(t.id);
                          loadedThIdRef.current = t.id;
                          onTalkingHeadChanged?.(t.id);
                          const curMat = talkingHeads.find(item => item.id === t.id);
                          if (curMat && curMat.width && curMat.height && curMat.width > curMat.height) {
                            setAspectRatio('16:9');
                          }
                          if (matchedProj) {
                            loadProjectById(matchedProj.id);
                          } else {
                            loadProjectForMaterial(t.id);
                          }
                          setShowProjectPicker(false);
                        }}
                        className={`group relative border rounded-xl p-2.5 transition-all cursor-pointer flex flex-col justify-between ${
                          isSelected
                            ? 'border-blue-500 bg-blue-50/40 ring-2 ring-blue-500/20'
                            : 'border-gray-200 hover:border-blue-300 bg-white hover:bg-gray-50'
                        }`}
                      >
                        <div className="aspect-video bg-gray-900 rounded-lg overflow-hidden mb-2 relative flex items-center justify-center">
                          {coverUrl ? (
                            <img src={coverUrl} alt={cardTitle} className="w-full h-full object-cover" />
                          ) : (
                            <Film className="w-6 h-6 text-gray-600" />
                          )}
                          <span className="absolute bottom-1 right-1 text-[10px] px-1 py-0.5 rounded bg-black/70 text-white font-mono">
                            {t.duration ? `${t.duration.toFixed(1)}s` : ''}
                          </span>
                          {/* 删除按钮 */}
                          <button
                            type="button"
                            onClick={(e) => handleDeleteTalkingHead(t, e)}
                            title="删除此视频及工程"
                            className="absolute top-1.5 right-1.5 p-1.5 rounded-lg bg-black/60 hover:bg-red-600 text-white transition-all opacity-80 sm:opacity-0 sm:group-hover:opacity-100 cursor-pointer shadow-sm z-10"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-gray-800 truncate" title={cardTitle}>
                            {cardTitle}
                          </p>
                          <div className="flex items-center justify-between text-[10px] text-gray-400 mt-1">
                            <span className="truncate mr-1 text-gray-400 font-mono" title={t.filename}>{t.filename}</span>
                            <div className="flex items-center space-x-1 flex-shrink-0">
                              {matchedProj?.target_region && (
                                <span className="inline-flex items-center space-x-0.5 px-1 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                                  <MapPin className="w-2.5 h-2.5 text-emerald-600" />
                                  <span>{formatRegionBadge(matchedProj.target_region)}</span>
                                </span>
                              )}
                              <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                matchedProj
                                  ? matchedProj.status === 'completed'
                                    ? 'bg-green-50 text-green-700'
                                    : 'bg-blue-50 text-blue-700'
                                  : 'bg-gray-100 text-gray-500'
                              }`}>
                                {matchedProj ? (matchedProj.status === 'completed' ? '已合成成片' : '已初剪') : '待剪辑'}
                              </span>
                            </div>
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
      {/* 011 & 012: 导出成片确认、视频封面设计与违禁词预检弹窗 */}
      <ExportConfirmModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        onConfirm={(filterBanned, newCoverCfg, exportDir, incCover, embCover) =>
          handleExecuteRender(filterBanned, newCoverCfg, exportDir, incCover ?? true, embCover ?? true)
        }
        bannedWordsCheck={bannedWordsCheck}
        isChecking={isCheckingBannedWords}
        isRendering={rendering}
        videoSpeed={Number((latestStrategyRef.current?.video_speed ?? strategy.video_speed) || 1.0)}
        projectId={projectId}
        initialCoverConfig={coverConfig || undefined}
        suggestedTitles={suggestedCoverTitles}
        currentVideoTime={currentTime}
        embedCoverAsFirstFrame={strategy.embed_cover_as_first_frame ?? true}
        onToggleEmbedFirstFrame={(val) => {
          setStrategy((prev) => ({ ...prev, embed_cover_as_first_frame: val }));
        }}
        projectTitle={projectTitle || displayTitle}
      />
    </div>
  );
};