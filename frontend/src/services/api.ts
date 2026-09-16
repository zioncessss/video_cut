import axios from 'axios';

export const API_BASE = 'http://localhost:18888/api/v1';

export interface Material {
  id: string;
  category: 'talking_head' | 'venue' | 'medical' | 'lesson';
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

export const updateSettings = async (settings: {
  active_harness: string;
  llm_model?: string;
  llm_api_key?: string;
  llm_base_url?: string;
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
  show_subtitles?: boolean;
  subtitle_position_y?: number;  // 竖屏垂直百分比 10~95 (默认82)
  subtitle_position_x?: number;  // 竖屏水平百分比 10~90 (默认50)
  enable_highlight: boolean;
  highlight_color: string;
  highlight_scale: boolean;
  custom_highlight_words: string[];
  enable_top_banner: boolean;
  banner_main_title: string;
  banner_sub_title?: string;
  banner_style: 'capsule' | 'full_width';
  enable_watermark: boolean;
  watermark_text: string;
  watermark_position: 'top_right' | 'top_left' | 'bottom_right';
  watermark_opacity: number;
  broll_pacing: 'fast' | 'standard' | 'talking_only';
}

export const updateProjectStrategy = async (
  projectId: string,
  strategy: EditingStrategy
) => {
  const res = await axios.put(`${API_BASE}/projects/${projectId}/strategy`, strategy);
  return res.data;
};
