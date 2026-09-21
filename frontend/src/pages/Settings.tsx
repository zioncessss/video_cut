import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE, testHarness, listModels, testMiniMaxConnection, TestHarnessResult, MiniMaxConnectionResult } from '../services/api';
import { useDialog } from '../components/common/CustomDialog';
import { Settings as SettingsIcon, CheckCircle2, AlertCircle, Save, Zap, Loader2, ListChecks, Sparkles, Mic, Activity } from 'lucide-react';

export const Settings: React.FC = () => {
  const { showAlert, showToast } = useDialog();
  const [activeHarness, setActiveHarness] = useState<string>('api');
  const [asrProvider, setAsrProvider] = useState<string>('minimax');
  const [llmModel, setLlmModel] = useState<string>('GLM-5.3-Flash');
  const [llmApiKey, setLlmApiKey] = useState<string>('');
  const [llmApiKeyMasked, setLlmApiKeyMasked] = useState<string>('');
  const [llmBaseUrl, setLlmBaseUrl] = useState<string>('');
  const [llmProtocol, setLlmProtocol] = useState<string>('openai');
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState<boolean>(false);
  const [modelFetchMsg, setModelFetchMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [engineConfig, setEngineConfig] = useState<any>(null);
  const [zcodePath, setZcodePath] = useState<string | null>(null);
  const [detected, setDetected] = useState<{ [key: string]: boolean }>({});
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<TestHarnessResult | null>(null);
  const [testingMiniMax, setTestingMiniMax] = useState<boolean>(false);
  const [miniMaxTestResult, setMiniMaxTestResult] = useState<MiniMaxConnectionResult | null>(null);
  const [miniMaxTestError, setMiniMaxTestError] = useState<string | null>(null);

  useEffect(() => {
    axios.get(`${API_BASE}/settings`).then(res => {
      setActiveHarness(res.data.active_harness);
      setAsrProvider(res.data.asr_provider || 'minimax');
      setLlmModel(res.data.llm_model || '');
      // 凭据红线：后端不下发 key 明文，仅回显掩码；输入框留空表示保持现有 key
      setLlmApiKey('');
      setLlmApiKeyMasked(res.data.llm_api_key_masked || '');
      setLlmBaseUrl(res.data.llm_base_url || '');
      setLlmProtocol(res.data.llm_protocol || 'openai');
      setEngineConfig(res.data.engine_config || null);
      setZcodePath(res.data.zcode_path || null);
      setDetected(res.data.detected_engines || {});
    }).catch(() => {});
  }, []);

  const handleFetchModels = async () => {
    setFetchingModels(true);
    setModelFetchMsg(null);
    try {
      const res = await listModels(llmBaseUrl, llmApiKey);
      if (res.code === 0 && res.data.models.length > 0) {
        setModelOptions(res.data.models);
        setModelFetchMsg({ ok: true, text: res.message });
        if (res.data.models.length > 0 && !res.data.models.includes(llmModel)) {
          // 当前模型不在列表中时不强制切换，仅提示可选
          setModelFetchMsg({ ok: true, text: `${res.message}（当前填写 "${llmModel}" 不在列表中，可在下方选择或保留手填）` });
        }
      } else {
        setModelOptions([]);
        setModelFetchMsg({ ok: false, text: res.message });
      }
    } catch (e: any) {
      setModelFetchMsg({ ok: false, text: e?.response?.data?.message || '获取模型列表失败：连接超时或服务不可达' });
    } finally {
      setFetchingModels(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testHarness('api', llmModel);
      setTestResult(res);
    } catch (e: any) {
      setTestResult({
        success: false,
        engine: 'api',
        latency_ms: 0,
        active_model: '',
        message: e?.response?.data?.message || '测试请求超时或连接失败'
      });
    } finally {
      setTesting(false);
    }
  };

  const applyMiniMaxPreset = () => {
    setActiveHarness('api');
    setLlmBaseUrl('https://api.minimaxi.com/v1');
    setLlmModel('MiniMax-Text-01');
    setLlmProtocol('openai');
    setAsrProvider('minimax');
  };

  const handleTestMiniMax = async () => {
    setTestingMiniMax(true);
    setMiniMaxTestResult(null);
    setMiniMaxTestError(null);
    try {
      const res = await testMiniMaxConnection({
        api_key: llmApiKey.trim() || undefined,
        base_url: llmBaseUrl.trim() || undefined,
        model: llmModel.trim() || undefined,
      });
      setMiniMaxTestResult(res);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.response?.data?.message || e.message || '连通性测试失败';
      setMiniMaxTestError(detail);
    } finally {
      setTestingMiniMax(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        active_harness: 'api',
        llm_model: llmModel,
        llm_base_url: llmBaseUrl,
        llm_protocol: llmProtocol,
        asr_provider: asrProvider,
      };
      // 凭据红线：仅在用户输入了新 key 时才提交；留空 = 保持后端已存储的 key
      if (llmApiKey.trim()) {
        payload.llm_api_key = llmApiKey.trim();
      }
      await axios.post(`${API_BASE}/settings`, payload);
      showToast('设置已成功保存并持久化！', 'success');
    } catch (e) {
      showAlert({ title: '保存失败', message: '保存设置失败，请检查网络或后台服务状态。', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
          <SettingsIcon className="w-6 h-6 text-gray-700" />
          <span>系统与大模型引擎设置 (Settings)</span>
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          字幕纠偏与网感优化由「直连大模型 API」高效驱动；语音转写由 MiniMax 云端极速识别支持。
        </p>
      </div>

      <div className="bg-white border border-gray-200/80 rounded-2xl p-6 shadow-sm space-y-6">
        {/* 字幕纠偏与智能分析引擎 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-2">
            字幕纠偏与智能引擎 (LLM Engine)
          </label>
          <div className="p-4 rounded-xl border border-blue-600 bg-blue-50/30 ring-2 ring-blue-600/10">
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-xs text-gray-900">直连大模型 API (OpenAI 兼容协议)</span>
              {detected.api ? (
                <span className="text-[10px] text-emerald-600 flex items-center font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> 已就绪
                </span>
              ) : (
                <span className="text-[10px] text-amber-600 flex items-center font-medium">
                  <AlertCircle className="w-3.5 h-3.5 mr-1" /> 待配置 API Key
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500">
              采用 OpenAI 兼容 <code className="font-mono bg-white px-1 py-0.5 rounded text-gray-700">/chat/completions</code> 协议，响应迅速、纠偏准确，支持各类主流大模型（如 MiniMax、GLM、DeepSeek 等）。
            </p>
          </div>
        </div>

        {/* ASR 语音识别引擎选择 */}
        <div className="pt-4 border-t border-gray-100">
          <label className="block text-sm font-semibold text-gray-800 mb-3 flex items-center space-x-1.5">
            <Mic className="w-4 h-4 text-indigo-600" />
            <span>语音识别 (ASR) 引擎模式</span>
          </label>
          <div className="p-4 rounded-xl border border-indigo-600 bg-indigo-50/30 ring-2 ring-indigo-600/10">
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-xs text-gray-900">MiniMax 云端极速识别 (asr-1.0)</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-700">
                云端专属 / 极速识别
              </span>
            </div>
            <p className="text-[11px] text-gray-600">
              2~4 秒极速转写，提供毫秒级字级时间戳，零本地 CPU/GPU 负载与显存压力；本地 Faster-Whisper 已彻底停用。
            </p>
          </div>
        </div>

        {/* 直连 API 连接配置 */}
        <div className="space-y-4 pt-4 border-t border-gray-100">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-1">
                直连 API 配置 (Base URL / API Key)
              </label>
              <p className="text-[11px] text-gray-500">
                填写后字幕纠偏等固定格式任务将直连该端点；配置 MiniMax Key 可同时生效 ASR 与 LLM。
              </p>
            </div>
            <button
              onClick={applyMiniMaxPreset}
              className="self-start sm:self-auto flex items-center space-x-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500/10 to-indigo-500/10 hover:from-blue-500/20 hover:to-indigo-500/20 text-indigo-700 text-xs font-semibold rounded-xl border border-indigo-200/60 transition-all shadow-sm"
              title="一键将 Base URL 设为 MiniMax 生产地址并将模型切换为 MiniMax-Text-01"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>一键载入 MiniMax 预设</span>
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3">
            <input
              type="text"
              value={llmBaseUrl}
              onChange={e => setLlmBaseUrl(e.target.value)}
              placeholder="Base URL，如 https://api.openai.com/v1 或 http://127.0.0.1:15721/v1"
              className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            />
            <input
              type="password"
              value={llmApiKey}
              onChange={e => setLlmApiKey(e.target.value)}
              placeholder={llmApiKeyMasked ? `已配置（${llmApiKeyMasked}），输入新值可更换，留空保持不变` : "API Key（sk-...，留空则继承 codex 本地配置；仅保存在本机 settings.json）"}
              autoComplete="off"
              className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            />
          </div>
        </div>

        {/* 模型参数配置 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-1">
            模型 (Model)
          </label>
          <p className="text-[11px] text-gray-500 mb-2">
            手动填写，或点击「获取模型列表」从 <code className="font-mono bg-gray-100 px-1 py-0.5 rounded">{"{Base URL}"}/models</code> 拉取可用模型后在下拉框中选择。
          </p>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={llmModel}
              onChange={e => setLlmModel(e.target.value)}
              placeholder="如 glm-5.3-flash / deepseek-chat"
              className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            />
            <button
              onClick={handleFetchModels}
              disabled={fetchingModels}
              className="flex items-center space-x-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold text-xs px-3.5 py-2.5 rounded-xl transition-colors disabled:opacity-50 whitespace-nowrap"
              title="调用 {Base URL}/models 获取可用模型列表"
            >
              {fetchingModels ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
              ) : (
                <ListChecks className="w-3.5 h-3.5 text-blue-600" />
              )}
              <span>{fetchingModels ? '获取中...' : '获取模型列表'}</span>
            </button>
          </div>

          {modelOptions.length > 0 && (
            <select
              value={modelOptions.includes(llmModel) ? llmModel : ''}
              onChange={e => setLlmModel(e.target.value)}
              className="mt-2 w-full bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            >
              <option value="" disabled>—— 从 {modelOptions.length} 个可用模型中选择 ——</option>
              {modelOptions.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          )}

          {modelFetchMsg && (
            <div className={`mt-2 text-[11px] flex items-center space-x-1.5 ${modelFetchMsg.ok ? 'text-emerald-700' : 'text-red-600'}`}>
              {modelFetchMsg.ok
                ? <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                : <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />}
              <span className="break-all">{modelFetchMsg.text}</span>
            </div>
          )}
        </div>

        {/* 直连协议配置 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-1">
            直连协议 (LLM Protocol)
          </label>
          <p className="text-[11px] text-gray-500 mb-2">
            当前支持 OpenAI 兼容协议（<code className="font-mono bg-gray-100 px-1 py-0.5 rounded">/chat/completions</code>），GLM 代理、vLLM、oneAPI、DeepSeek、通义兼容模式均可直连；Anthropic / Gemini 原生协议预留中。
          </p>
          <select
            value={llmProtocol}
            onChange={e => setLlmProtocol(e.target.value)}
            className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="openai">openai（OpenAI 兼容 /chat/completions）</option>
            <option value="anthropic" disabled>anthropic（敬请期待）</option>
            <option value="gemini" disabled>gemini（敬请期待）</option>
          </select>
        </div>

        {/* MiniMax 双通道连通性测试卡片 */}
        <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-xl space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-indigo-600" />
              <span className="font-semibold text-xs text-gray-800">MiniMax 双通道健康探测 (ASR + LLM)</span>
            </div>
            <button
              onClick={handleTestMiniMax}
              disabled={testingMiniMax}
              className="self-start sm:self-auto flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs px-3.5 py-2 rounded-xl transition-colors shadow-sm disabled:opacity-50"
            >
              {testingMiniMax ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Zap className="w-3.5 h-3.5 text-amber-300" />
              )}
              <span>{testingMiniMax ? '正在探测双通道...' : '测试 MiniMax 连通性'}</span>
            </button>
          </div>

          {miniMaxTestResult && (
            <div className="p-3 bg-emerald-50/80 border border-emerald-200 rounded-lg text-xs space-y-1.5">
              <div className="flex items-center text-emerald-800 font-semibold space-x-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>{miniMaxTestResult.message || 'MiniMax 双通道健康探测通过！'}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 pt-2 border-t border-emerald-200/60 text-[11px] text-emerald-900">
                <div className="bg-white/70 p-2.5 rounded-lg border border-emerald-200/40">
                  <div className="font-semibold text-gray-700 mb-0.5">大模型通道 (LLM): <span className="text-emerald-700 font-medium">就绪 (HTTP 200)</span></div>
                  <div className="text-[10px] text-gray-500">模型: {miniMaxTestResult.data.model_used} | 延迟: {miniMaxTestResult.data.llm_latency_ms} ms</div>
                </div>
                <div className="bg-white/70 p-2.5 rounded-lg border border-emerald-200/40">
                  <div className="font-semibold text-gray-700 mb-0.5">极速语音识别 (ASR): <span className="text-emerald-700 font-medium">就绪 (HTTP 200)</span></div>
                  <div className="text-[10px] text-gray-500">模型: asr-1.0 | 延迟: {miniMaxTestResult.data.asr_latency_ms} ms</div>
                </div>
              </div>
            </div>
          )}

          {miniMaxTestError && (
            <div className="p-3 bg-red-50/80 border border-red-200 rounded-lg text-xs flex items-start space-x-2 text-red-900">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold">MiniMax 连通性探测失败</div>
                <div className="text-[11px] mt-0.5 text-red-700 break-all">{miniMaxTestError}</div>
              </div>
            </div>
          )}
        </div>

        {/* 连通性测试反馈卡片 */}
        {testResult && (
          <div
            className={`p-4 rounded-xl border text-xs flex items-start space-x-3 transition-all ${
              testResult.success
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                : 'bg-red-50/70 border-red-200 text-red-900'
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <div className="font-semibold flex items-center justify-between">
                <span>{testResult.success ? '连通性测试通过' : '连通性测试未通过'}</span>
                {testResult.latency_ms > 0 && (
                <span className="font-mono text-[11px] bg-white/80 px-2 py-0.5 rounded border border-gray-200/50" title="TTFT：从发起到模型吐出第一个 token 的时间，只含网络与提示词处理，不含完整生成">
                  首 Token 延迟: {testResult.latency_ms} ms
                </span>
                )}
              </div>
              <p className="mt-1 text-[11px] opacity-90">{testResult.message}</p>
              {testResult.active_model && (
                <p className="mt-1 text-[11px] font-mono text-gray-600">
                  当前生效模型: <span className="font-semibold text-gray-800">{testResult.active_model}</span>
                </p>
              )}
            </div>
          </div>
        )}

        {/* 操作按钮区 */}
        <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
          <button
            onClick={handleTestConnection}
            disabled={testing}
            className="flex items-center space-x-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold text-xs px-4 py-2.5 rounded-xl transition-colors disabled:opacity-50"
          >
            {testing ? (
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
            ) : (
              <Zap className="w-4 h-4 text-amber-500" />
            )}
            <span>{testing ? '正在探测 CLI...' : '测试连通性 (Ping)'}</span>
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition-colors shadow-sm disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? '保存中...' : '保存配置'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
