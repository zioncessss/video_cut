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

