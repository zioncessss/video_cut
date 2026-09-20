import axios from 'axios';

// API 基地址解析优先级：Electron bridge（sidecar 动态端口）→ 构建期环境变量 → 默认开发端口
export const API_BASE: string =
  (typeof window !== 'undefined' &&
    (window as unknown as { electronAPI?: { apiBase?: string } }).electronAPI?.apiBase) ||
  ((import.meta as any).env && (import.meta as any).env.VITE_API_BASE) ||
  'http://localhost:18888/api/v1';

export const getMediaUrl = (filepath: string): string => {
  if (!filepath) return '';
  if (filepath.startsWith('http://') || filepath.startsWith('https://')) return filepath;
  const cleanPath = filepath.replace(/^[/\\]+/, '').replace(/\\/g, '/');
  const baseUrl = API_BASE.replace(/\/api\/v1\/?$/, '');
  return `${baseUrl}/${cleanPath}`;
};

export interface Material {
  id: string;
  category: 'talking_head' | 'venue' | 'experience' | 'medical' | 'lesson';
  filename: string;
  filepath: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  created_at: number;
}

export const fetchMaterials = async (category?: string): Promise<Material[]> => {
  const params = category ? { category } : {};
  const res = await axios.get(`${API_BASE}/materials`, { params });
  return res.data;
};

export const uploadMaterial = async (category: string, file: File): Promise<Material> => {
  const formData = new FormData();
  formData.append('category', category);
  formData.append('file', file);
  const res = await axios.post(`${API_BASE}/materials/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
};

export const importLocalMaterial = async (category: string, filePath: string): Promise<Material> => {
  const res = await axios.post(`${API_BASE}/materials/import-local`, {
    category,
    file_path: filePath
  });
  return res.data;
};

export const deleteMaterial = async (id: string): Promise<void> => {
  await axios.delete(`${API_BASE}/materials/${id}`);
};

export const fetchHardwareMetrics = async () => {
  const res = await axios.get(`${API_BASE}/system/resources`);
  return res.data;
};

export interface TestHarnessResult {
  success: boolean;
  engine: string;
  latency_ms: number;
  active_model: string;
  message: string;
}

export const testHarness = async (engine: string, modelOverride?: string): Promise<TestHarnessResult> => {
  const res = await axios.post(`${API_BASE}/settings/test-harness`, {
    engine,
    model_override: modelOverride || null,
  });
  return res.data.data;
};

export const fetchSettings = async () => {
  const res = await axios.get(`${API_BASE}/settings`);
  return res.data;
};

export const listModels = async (llmBaseUrl?: string, llmApiKey?: string): Promise<{ code: number; message: string; data: { models: string[] } }> => {
  const res = await axios.post(`${API_BASE}/settings/list-models`, {
    llm_base_url: llmBaseUrl || null,
    llm_api_key: llmApiKey || null,
  });
  return res.data;
};

export interface MiniMaxConnectionResult {
  code: number;
  message: string;
  data: {
    llm_status: string;
    llm_latency_ms: number;
    asr_status: string;
    asr_latency_ms: number;
    model_used: string;
  };
}

export const testMiniMaxConnection = async (payload?: {
  api_key?: string;
  base_url?: string;
  model?: string;
}): Promise<MiniMaxConnectionResult> => {
  const res = await axios.post(`${API_BASE}/settings/test-connection`, payload || {});
  return res.data;
};

export const updateSettings = async (settings: {
  active_harness: string;
  llm_model?: string;
  llm_api_key?: string;
  llm_base_url?: string;
  llm_protocol?: string;
  asr_provider?: string;
  minimax_api_key?: string;
  minimax_base_url?: string;
}) => {
  const res = await axios.post(`${API_BASE}/settings`, settings);
  return res.data;
};

export interface ChatMessageItem {
  role: 'user' | 'assistant';
  content: string;
  reasoning?: string;
  action?: {
    action_type: string;
    explanation: string;
    updated_subtitles?: any[];
    updated_brolls?: any[];
  } | null;
}

export const streamChatSSE = async (
  payload: {
    message: string;
    project_id?: string;
    history?: { role: string; content: string }[];
    model_override?: string;
  },
  onChunk: (chunk: { type: string; delta?: string; message?: string }) => void,
  onDone: () => void,
  onError: (err: any) => void
) => {
  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('ReadableStream not supported');

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.type === 'done') {
              onDone();
              return;
            }
            onChunk(data);
          } catch (e) {
            // ignore parse error on partial chunk
          }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err);
  }
};

export interface EditingStrategy {
  subtitle_theme: 'glow_gold' | 'glass_clean' | 'cinema_shadow' | 'viral_gold' | 'tech_emerald' | 'marker_pen' | 'minimal_white';
  font_size: 'small' | 'medium' | 'large' | 'xlarge';
  subtitle_font_family?: 'kaiti' | 'notoserif' | 'fangsong' | 'songti' | 'yahei' | 'hei'; // 字体风格: kaiti(书法楷体), notoserif(思源宋体), fangsong(清雅仿宋), songti(经典宋体), yahei(现代黑体)
  subtitle_font_size?: number; // 连续字号大小 (24~96px)
  show_subtitles?: boolean;
  subtitle_position_y?: number;  // 竖屏垂直百分比 10~95 (推荐 74% 口播黄金位)
  subtitle_position_x?: number;  // 竖屏水平百分比 5~95 (默认50)
  subtitle_width_percent?: number; // 文本框宽度百分比 30~95 (可拖拽拉宽/窄)
  enable_highlight: boolean;
  highlight_color: string;
  highlight_scale: boolean;
  custom_highlight_words: string[];
  enable_top_banner: boolean;
  banner_main_title: string;
  banner_sub_title?: string;
  banner_style: 'capsule' | 'full_width';
  banner_size?: 'small' | 'medium' | 'large';
  banner_font_size?: number; // 连续字号大小 (24~72px)
  banner_width_percent?: number; // 文本框宽度百分比 20~95 (可拖拽拉宽/窄)
  banner_position_x?: number; // 水平百分比 5~95 (默认50)
  banner_position_y?: number; // 垂直百分比 2~85 (默认6)
  enable_watermark: boolean;
  watermark_text: string;
  watermark_position: 'top_right' | 'top_left' | 'bottom_right' | 'bottom_left';
  watermark_opacity: number;
  watermark_size?: 'small' | 'medium' | 'large';
  watermark_font_size?: number; // 连续字号大小 (14~60px)
  watermark_position_x?: number; // 水平百分比 2~98
  watermark_position_y?: number; // 垂直百分比 2~98
  broll_pacing: 'fast' | 'standard' | 'talking_only';
  transition_style?: 'cut' | 'fade'; // 转场风格：硬切 / 叠化(时长取各句 scene_decision)
  video_speed?: number; // 视频剪辑倍速 (0.75~2.0)
  enable_auto_prune?: boolean;
  enable_head_prune?: boolean;
  enable_tail_prune?: boolean;
  enable_retake_prune?: boolean;
  enable_mid_silence_prune?: boolean;
  head_padding_seconds?: number;
  tail_padding_seconds?: number;
  mid_silence_threshold?: number;
  mid_silence_breath_gap?: number;
  retake_pause_min?: number;
  retake_similarity_min?: number;
}

export interface PruneSpan {
  id: string;
  start_time: number;
  end_time: number;
  reason: 'head_idle' | 'tail_idle' | 'retake_discard' | 'mid_silence' | 'manual' | string;
  source_subtitle_id?: string | null;
  target_subtitle_id?: string | null;
  duration: number;
  is_active: boolean;
}

export interface HighlightWord {
  word: string;
  source: 'glossary' | 'ai' | 'manual';
  color?: string;
  category?: string;
}

export interface SceneDecision {
  part: 'hook' | 'body' | 'cta';
  broll_category: 'venue' | 'experience' | 'lesson' | null;
  broll_duration: number;
  transition_seconds: number;
  material_id: string | null;
  reason: string;
}

export interface SubtitleSegment {
  id: string;
  start_time: number;
  end_time: number;
  raw_text: string;
  corrected_text: string;
  matched_category?: 'venue' | 'experience' | 'medical' | 'lesson' | null;
  matched_keywords?: string[];
  highlight_words?: HighlightWord[];
  scene_decision?: SceneDecision | null;
  broll_material_id?: string | null;
  is_manual_edited?: boolean;
  is_pruned?: boolean;
  prune_reason?: string | null;
  prune_span_id?: string | null;
}

export interface BrollReplacement {
  id?: string;
  start_time: number;
  end_time: number;
  material_id: string;
  material_category: 'venue' | 'experience' | 'lesson';
  playback_mode?: string;
}

export const updateProjectStrategy = async (
  projectId: string,
  strategy: EditingStrategy
) => {
  const res = await axios.put(`${API_BASE}/projects/${projectId}/strategy`, strategy);
  return res.data;
};

export const redecideScenes = async (
  projectId: string,
  targetCoverage: number = 0.65
): Promise<{
  code: number;
  message: string;
  data: {
    project: any;
    subtitles: SubtitleSegment[];
    broll_replacements: BrollReplacement[];
    engine_used: string;
    latency_ms: number;
    degraded: boolean;
  };
}> => {
  const res = await axios.post(`${API_BASE}/projects/${projectId}/scene-decision`, {
    target_coverage: targetCoverage,
  });
  return res.data;
};

// ===== 批量智能剪辑（005）=====

export interface BatchJobItem {
  material_id: string;
  project_id?: string | null;
  status: 'queued' | 'running' | 'completed' | 'failed';
  error?: string | null;
  progress: number;
}

export const submitBatch = async (materialIds: string[], aspectRatio: string = '9:16') => {
  const res = await axios.post(`${API_BASE}/batch/submit`, { material_ids: materialIds, aspect_ratio: aspectRatio });
  return res.data.data as { job_id: string; queued: number; concurrency: number };
};

export const fetchBatchJob = async (jobId: string) => {
  const res = await axios.get(`${API_BASE}/batch/jobs/${jobId}`);
  return res.data.data as {
    job_id: string;
    status: 'queued' | 'running' | 'finished';
    concurrency: number;
    completed_count: number;
    items: BatchJobItem[];
  };
};

// ===== 工程封面（005，AI 生成暂为规划占位）=====

export const setProjectCover = async (
  projectId: string,
  source: 'frame' | 'upload' | 'ai',
  timestamp?: number,
  imageBase64?: string
) => {
  const res = await axios.post(`${API_BASE}/projects/${projectId}/cover`, {
    source,
    timestamp,
    image_base64: imageBase64
  });
  return res.data.data as { cover_image_path: string; cover_source: string; cover_url: string };
};

export const uploadProjectCoverFile = async (projectId: string, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await axios.post(`${API_BASE}/projects/${projectId}/cover/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return res.data.data as { cover_image_path: string; cover_source: string; cover_url: string };
};

export const fetchProjectByMaterial = async (materialId: string) => {
  const res = await axios.get(`${API_BASE}/projects/by-material/${materialId}`);
  return res.data;
};

export const fetchProjectById = async (projectId: string) => {
  const res = await axios.get(`${API_BASE}/projects/${projectId}`);
  return res.data;
};

export const updateProjectSubtitles = async (
  projectId: string,
  subtitles: any[],
  brollReplacements?: any[]
) => {
  const res = await axios.put(`${API_BASE}/projects/${projectId}/subtitles`, {
    subtitles,
    broll_replacements: brollReplacements,
  });
  return res.data;
};

export const analyzeAndCutVideo = async (
  talkingHeadId: string,
  options?: {
    aspectRatio?: string;
    autoBroll?: boolean;
    forceRetranscribe?: boolean;
    autoRender?: boolean;
  }
) => {
  const res = await axios.post(`${API_BASE}/projects/analyze-and-cut`, {
    talking_head_id: talkingHeadId,
    aspect_ratio: options?.aspectRatio || '9:16',
    auto_broll: options?.autoBroll !== false,
    force_retranscribe: !!options?.forceRetranscribe,
    auto_render: !!options?.autoRender,
  });
  return res.data;
};

export const deleteProjectByMaterial = async (materialId: string) => {
  const res = await axios.delete(`${API_BASE}/projects/by-material/${materialId}`);
  return res.data;
};

export interface RenderProjectResult {
  id: string;
  title: string;
  status: string;
  output_video_path?: string;
  output_absolute_path?: string;
  output_filename?: string;
  output_file_size_mb?: number;
  subtitles?: any[];
  strategy?: EditingStrategy;
  cover_image_path?: string;
  cover_source?: string;
}

export const renderProject = async (projectId: string, videoSpeed?: number): Promise<RenderProjectResult> => {
  const params = videoSpeed !== undefined ? { video_speed: videoSpeed } : {};
  const res = await axios.post(`${API_BASE}/projects/${projectId}/render`, null, { params });
  return res.data;
};

export const openFolder = async (path?: string, projectId?: string): Promise<{ code: number; message: string; path?: string }> => {
  const res = await axios.post(`${API_BASE}/projects/open-folder`, { path, project_id: projectId });
  return res.data;
};

export interface ProjectSummary {
  id: string;
  title: string;
  talking_head_id: string;
  aspect_ratio: string;
  status: 'draft' | 'processing' | 'completed' | 'failed';
  output_video_path?: string;
  output_absolute_path?: string;
  output_filename?: string;
  output_file_size_mb?: number;
  task_dir?: string;
  cover_image_path?: string;
  cover_source?: string;
  created_at: number;
  updated_at: number;
  subtitles?: SubtitleSegment[];
  broll_replacements?: any[];
  strategy?: EditingStrategy;
  prune_spans?: PruneSpan[];
}

export const toggleSubtitlePrune = async (
  projectId: string,
  subtitleId: string,
  isPruned?: boolean
): Promise<{
  success: boolean;
  subtitle_id: string;
  is_pruned: boolean;
  prune_spans: PruneSpan[];
  total_effective_duration: number;
}> => {
  const res = await axios.post(`${API_BASE}/projects/${projectId}/subtitles/${subtitleId}/toggle-prune`, {
    is_pruned: isPruned
  });
  return res.data;
};

export const updatePruneConfig = async (
  projectId: string,
  config: {
    enable_head_prune?: boolean;
    enable_tail_prune?: boolean;
    enable_retake_prune?: boolean;
    enable_mid_silence_prune?: boolean;
    head_padding_seconds?: number;
    tail_padding_seconds?: number;
    mid_silence_threshold?: number;
    mid_silence_breath_gap?: number;
    retake_pause_min?: number;
    retake_similarity_min?: number;
  }
): Promise<{
  success: boolean;
  total_pruned_seconds: number;
  prune_spans: PruneSpan[];
}> => {
  const res = await axios.post(`${API_BASE}/projects/${projectId}/prune-config`, config);
  return res.data;
};

export const fetchAllProjects = async (): Promise<ProjectSummary[]> => {
  const res = await axios.get(`${API_BASE}/projects`);
  return res.data;
};

export const deleteProject = async (projectId: string, deleteFiles: boolean = true) => {
  const res = await axios.delete(`${API_BASE}/projects/${projectId}`, {
    params: { delete_files: deleteFiles }
  });
  return res.data;
};

export const batchDeleteProjects = async (projectIds: string[], deleteFiles: boolean = true) => {
  const res = await axios.post(`${API_BASE}/projects/batch-delete`, {
    project_ids: projectIds,
    delete_files: deleteFiles
  });
  return res.data;
};

export const uploadAndBatchCut = async (
  files: File[],
  aspectRatio: string = '9:16',
  concurrency?: number,
  videoSpeed: number = 1.0
) => {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  formData.append('aspect_ratio', aspectRatio);
  formData.append('video_speed', String(videoSpeed));
  if (concurrency) {
    formData.append('concurrency', String(concurrency));
  }
  const res = await axios.post(`${API_BASE}/batch/upload-and-cut`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return res.data.data as { job_id: string; queued: number; concurrency: number };
};

export const importAndBatchCut = async (
  filePaths: string[],
  aspectRatio: string = '9:16',
  concurrency?: number,
  videoSpeed: number = 1.0
) => {
  const res = await axios.post(`${API_BASE}/batch/import-and-cut`, {
    file_paths: filePaths,
    aspect_ratio: aspectRatio,
    concurrency,
    video_speed: videoSpeed
  });
  return res.data.data as { job_id: string; queued: number; concurrency: number };
};

export interface PipelineProgress {
  project_id: string;
  stage: 'idle' | 'audio_extracting' | 'asr_transcribing' | 'llm_correcting' | 'scene_deciding' | 'broll_matching' | 'completed' | 'failed';
  percent: number;
  message: string;
  updated_at: number;
}

export const fetchProjectProgress = async (projectId: string): Promise<PipelineProgress> => {
  const res = await axios.get(`${API_BASE}/projects/${projectId}/progress`);
  return res.data;
};


