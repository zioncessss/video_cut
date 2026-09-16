import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { VideoPlayer } from '../components/VideoPlayer';
import { SubtitleList, SubtitleItem } from '../components/SubtitleList';
import { fetchMaterials, fetchHardwareMetrics, fetchSettings, Material, API_BASE } from '../services/api';
import { Sparkles, Wand2, RefreshCw, Cpu, Check, AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';

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
}

export const VideoEditor: React.FC<VideoEditorProps> = ({
  onProjectLoaded,
  externalStrategyPlan,
}) => {
  const [talkingHeads, setTalkingHeads] = useState<Material[]>([]);
  const [selectedThId, setSelectedThId] = useState<string>('');
  const [projectId, setProjectId] = useState<string>('');
  const [subtitles, setSubtitles] = useState<SubtitleItem[]>([]);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [rendering, setRendering] = useState<boolean>(false);
  const [outputVideoUrl, setOutputVideoUrl] = useState<string>('');
  const [aiInstruction, setAiInstruction] = useState<string>('');
  const [applyingInstruction, setApplyingInstruction] = useState<boolean>(false);
  const [correcting, setCorrecting] = useState<boolean>(false);
  const [hardwareInfo, setHardwareInfo] = useState<any>(null);
  const [activeEngine, setActiveEngine] = useState<string>('codex');
  const [activeModel, setActiveModel] = useState<string>('GLM-5.3-Flash');
  const [lastEngineUsed, setLastEngineUsed] = useState<string | null>(null);
  const [aiFeedback, setAiFeedback] = useState<string | null>(null);
  const [correctionsSummary, setCorrectionsSummary] = useState<CorrectionItem[] | null>(null);

  useEffect(() => {
    fetchMaterials('talking_head').then(data => {
      setTalkingHeads(data);
      if (data.length > 0) {
        setSelectedThId(data[0].id);
      }
    });
    fetchHardwareMetrics().then(setHardwareInfo).catch(() => {});
    fetchSettings().then(s => {
      setActiveEngine(s.active_harness || 'codex');
      setActiveModel(s.llm_model || 'GLM-5.3-Flash');
    }).catch(() => {});
  }, []);

  const handleAnalyze = async () => {
    if (!selectedThId) {
      alert('请先选择或上传口播主视频');
      return;
    }
    setAnalyzing(true);
    setCorrectionsSummary(null);
    try {
      const res = await axios.post(`${API_BASE}/projects/analyze-and-cut`, {
        talking_head_id: selectedThId,
        aspect_ratio: '9:16',
        auto_broll: true
      });
      setProjectId(res.data.id);
      if (onProjectLoaded) {
        onProjectLoaded(res.data.id);
      }
      setSubtitles(res.data.subtitles);
    } catch (err) {
      alert('智能识别与初剪失败，请确保后端服务正常运行');
    } finally {
      setAnalyzing(false);
    }
  };

  // 监听来自全局 Harness 对话框的策略变更意图，热更新工程
  useEffect(() => {
    if (externalStrategyPlan) {
      if (externalStrategyPlan.updated_subtitles && externalStrategyPlan.updated_subtitles.length > 0) {
        setSubtitles(externalStrategyPlan.updated_subtitles);
      }
      if (externalStrategyPlan.explanation) {
        setAiFeedback(`[副驾驶策略应用] ${externalStrategyPlan.explanation}`);
      }
    }
  }, [externalStrategyPlan]);

  const handleCorrectSubtitles = async () => {
    if (subtitles.length === 0) {
      alert('当前没有字幕，请先进行初剪识别');
      return;
    }
    setCorrecting(true);
    setCorrectionsSummary(null);
    try {
      const res = await axios.post(`${API_BASE}/editor/correct`, {
        subtitles: subtitles,
        domain: 'driving_school'
      });
      const data = res.data.data;
      if (data.subtitles) {
        setSubtitles(data.subtitles);
      }
      setLastEngineUsed(data.harness_engine_used);
      if (data.corrections && data.corrections.length > 0) {
        setCorrectionsSummary(data.corrections);
      } else {
        setAiFeedback(`智能纠错完成（耗时 ${data.latency_ms}ms），未发现明显错别字。`);
      }
    } catch (err) {
      alert('智能纠错请求失败');
    } finally {
      setCorrecting(false);
    }
  };

  const handleTextChange = (idx: number, newText: string) => {
    const updated = [...subtitles];
    updated[idx].corrected_text = newText;
    setSubtitles(updated);
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
    try {
      await axios.put(`${API_BASE}/projects/${projectId}/subtitles`, {
        subtitles: subtitles
      });
      const res = await axios.post(`${API_BASE}/projects/${projectId}/render`);
      if (res.data.output_video_path) {
        setOutputVideoUrl(`http://localhost:18888/${res.data.output_video_path}`);
        alert('视频渲染完成！');
      }
    } catch (err) {
      alert('渲染合成失败');
    } finally {
      setRendering(false);
    }
  };

  const currentPreviewUrl = outputVideoUrl || (
    selectedThId && talkingHeads.find(t => t.id === selectedThId)
      ? `http://localhost:18888/${talkingHeads.find(t => t.id === selectedThId)?.filepath}`
      : ''
  );

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] max-w-7xl mx-auto p-6">
      {/* 顶部操作条：口播素材选择、引擎状态徽章、纠错与初剪触发 */}
      <div className="flex flex-wrap items-center justify-between bg-white border border-gray-200/80 rounded-2xl p-4 shadow-sm mb-4 gap-3">
        <div className="flex items-center space-x-3">
          <label className="text-xs font-semibold text-gray-700">口播主视频:</label>
          <select
            value={selectedThId}
            onChange={e => setSelectedThId(e.target.value)}
            className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-1 focus:ring-blue-500"
          >
            {talkingHeads.length === 0 && <option value="">暂无口播视频，请先在素材库上传</option>}
            {talkingHeads.map(t => (
              <option key={t.id} value={t.id}>{t.filename} ({t.duration.toFixed(1)}s)</option>
            ))}
          </select>
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

          {/* 智能纠错按钮 */}
          <button
            onClick={handleCorrectSubtitles}
            disabled={correcting || subtitles.length === 0}
            className="flex items-center space-x-1.5 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200/80 text-xs font-medium px-3.5 py-2 rounded-xl transition-colors disabled:opacity-40"
          >
            {correcting ? <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-700" /> : <Sparkles className="w-3.5 h-3.5 text-amber-600" />}
            <span>{correcting ? 'AI 专有词纠错中...' : '智能纠错'}</span>
          </button>

          {/* 初剪触发 */}
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !selectedThId}
            className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium px-4 py-2 rounded-xl transition-colors shadow-sm disabled:opacity-50"
          >
            {analyzing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            <span>{analyzing ? '识别与分析中...' : 'AI 智能识别与初剪'}</span>
          </button>
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

      {/* 主体工作台：左侧播放器，右侧时间轴字幕 */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-4 min-h-0">
        <div className="md:col-span-5 h-full flex flex-col justify-center">
          <VideoPlayer
            videoUrl={currentPreviewUrl}
            subtitles={subtitles}
            currentTime={currentTime}
            onTimeUpdate={setCurrentTime}
            aspectRatio="9:16"
          />
        </div>

        <div className="md:col-span-7 h-full overflow-hidden">
          <SubtitleList
            subtitles={subtitles}
            currentTime={currentTime}
            onSelectTime={setCurrentTime}
            onTextChange={handleTextChange}
          />
        </div>
      </div>

      {/* AI 调整反馈提示 */}
      {aiFeedback && (
        <div className="mt-3 bg-blue-50/80 border border-blue-200/80 rounded-xl px-4 py-2 flex items-center justify-between text-xs text-blue-900 shadow-sm animate-in fade-in">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span className="font-medium">{aiFeedback}</span>
          </div>
          <button onClick={() => setAiFeedback(null)} className="text-blue-500 hover:text-blue-700 text-xs ml-4">
            ✕
          </button>
        </div>
      )}

      {/* 底部浮动交互条：AI Prompt 指令输入框 + 生成按钮 + 硬件监控 */}
      <div className="mt-4 bg-white border border-gray-200/80 rounded-2xl p-3 shadow-sm flex items-center space-x-3">
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
          className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition-colors shadow-sm disabled:opacity-50"
        >
          {rendering ? '合成压制中...' : '生成预览 (Generate Preview)'}
        </button>

        {hardwareInfo && (
          <div className="hidden lg:flex items-center space-x-2 border-l pl-3 text-xs text-gray-500 font-mono">
            <Cpu className="w-3.5 h-3.5 text-emerald-600" />
            <span>负载: {hardwareInfo.cpu_usage_percent || hardwareInfo.cpu_percent || 15}%</span>
          </div>
        )}
      </div>
    </div>
  );
};
