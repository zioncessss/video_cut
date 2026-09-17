import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE, testHarness, listModels, TestHarnessResult } from '../services/api';
import { Settings as SettingsIcon, CheckCircle2, AlertCircle, Save, Zap, Loader2, ListChecks } from 'lucide-react';

export const Settings: React.FC = () => {
  const [activeHarness, setActiveHarness] = useState<string>('api');
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

  useEffect(() => {
    axios.get(`${API_BASE}/settings`).then(res => {
      setActiveHarness(res.data.active_harness);
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
      const res = await testHarness(activeHarness, llmModel);
      setTestResult(res);
    } catch (e: any) {
      setTestResult({
        success: false,
        engine: activeHarness,
        latency_ms: 0,
        active_model: '',
        message: e?.response?.data?.message || '测试请求超时或连接失败'
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        active_harness: activeHarness,
        llm_model: llmModel,
        llm_base_url: llmBaseUrl,
        llm_protocol: llmProtocol
      };
      // 凭据红线：仅在用户输入了新 key 时才提交；留空 = 保持后端已存储的 key
      if (llmApiKey.trim()) {
        payload.llm_api_key = llmApiKey.trim();
      }
      await axios.post(`${API_BASE}/settings`, payload);
      alert('设置已成功保存并持久化！');
    } catch (e) {
      alert('保存设置失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
          <SettingsIcon className="w-6 h-6 text-gray-700" />
          <span>系统与 Harness 引擎设置 (Settings)</span>
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          字幕纠偏等固定格式任务由「直连大模型 API」高效驱动；开放式剪辑指令与聊天自动路由 Codex / ZCode CLI 智能体。
        </p>
      </div>

      <div className="bg-white border border-gray-200/80 rounded-2xl p-6 shadow-sm space-y-6">
        {/* Harness 运行时选择 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-3">
            字幕纠偏引擎 (Tier A - 固定格式任务)
          </label>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {[
              { id: 'api', label: '直连大模型 API', desc: 'OpenAI 兼容 /chat/completions，最快最稳（推荐）' },
              { id: 'embedded', label: 'Embedded Agent', desc: '内置词库确定性纠偏（离线可用）' },
              { id: 'codex', label: 'Codex Harness', desc: '外部 Codex CLI 智能体进程' },
              { id: 'zcode', label: 'ZCode Harness', desc: '外部 ZCode Harness 执行器' },
            ].map(engine => {
              const isSelected = activeHarness === engine.id;
              const isAvailable = engine.id === 'embedded' ? true : detected[engine.id];
              return (
                <button
                  key={engine.id}
                  onClick={() => setActiveHarness(engine.id)}
                  className={`p-4 rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/30 ring-2 ring-blue-600/10'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-xs text-gray-900">{engine.label}</span>
                    {isAvailable ? (
                      <span className="text-[10px] text-emerald-600 flex items-center">
                        <CheckCircle2 className="w-3 h-3 mr-0.5" /> 已就绪
                      </span>
                    ) : (
                      <span className="text-[10px] text-gray-400 flex items-center">
                        <AlertCircle className="w-3 h-3 mr-0.5" /> {engine.id === 'api' ? '未配置' : '未检测到CLI'}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500">{engine.desc}</p>
                </button>
              );
            })}
          </div>

          {/* 检测详情提示 */}
          {zcodePath && (
            <div className="mt-3 p-3 bg-emerald-50/60 border border-emerald-200/60 rounded-xl text-xs text-emerald-800 flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span>检测到本地 ZCode 智能引擎核心已就绪：<code className="font-mono text-[11px] bg-emerald-100/70 px-1.5 py-0.5 rounded">{zcodePath}</code></span>
            </div>
          )}
        </div>

        {/* ===== 以下配置区随引擎切换：api=直连配置；codex/zcode=本地配置说明 ===== */}
        {activeHarness === 'api' && (
        <>
        {/* 直连 API 连接配置 */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-1">
              直连 API 配置 (Base URL / API Key)
            </label>
            <p className="text-[11px] text-gray-500 mb-2">
              填写后字幕纠偏等固定格式任务将直连该端点；两者均留空则继承本地 <code className="font-mono bg-gray-100 px-1 py-0.5 rounded">~/.codex/config.toml</code> 的代理配置。
            </p>
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
        </>
        )}

        {activeHarness === 'codex' && (
        <div className="space-y-4">
          <div className="p-4 bg-blue-50/60 border border-blue-200/60 rounded-xl text-xs text-blue-900 space-y-1">
            <p className="font-semibold">Codex 引擎使用本地配置，不使用上方直连 API 设置</p>
            <p>调用路径：优先连接本地代理 <code className="font-mono bg-white/70 px-1 py-0.5 rounded">{engineConfig?.codex?.base_url || '（未检测到，将回退 CLI 进程）'}</code>，代理不可用时自动启动 <code className="font-mono bg-white/70 px-1 py-0.5 rounded">codex exec</code> 子进程。</p>
            <p>供应商 / 模型 / token 全部继承本地 <code className="font-mono bg-white/70 px-1 py-0.5 rounded">~/.codex/config.toml</code>{engineConfig?.codex?.model ? `，当前本地模型：${engineConfig.codex.model}` : ''}{engineConfig?.codex?.has_token ? '，token 已就绪' : ''}。</p>
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-1">模型覆盖 (可选 -m)</label>
            <p className="text-[11px] text-gray-500 mb-2">留空完全继承本地 codex 配置；仅在需要临时指定其它模型时填写。</p>
            <input
              type="text"
              value={llmModel}
              onChange={e => setLlmModel(e.target.value)}
              placeholder="留空继承 ~/.codex/config.toml 的模型"
              className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            />
          </div>
        </div>
        )}

        {activeHarness === 'zcode' && (
        <div className="p-4 bg-emerald-50/60 border border-emerald-200/60 rounded-xl text-xs text-emerald-900 space-y-1">
          <p className="font-semibold">ZCode 引擎直接启动本地 CLI 进程，无需任何 API 配置</p>
          <p>调用路径：node 启动 <code className="font-mono bg-white/70 px-1 py-0.5 rounded">{engineConfig?.zcode?.cli_path || zcodePath || 'zcode.cjs'}</code>，模型与鉴权使用 ZCode 自身登录态（当前引擎内置 GLM 系列），与上方直连 API 设置互不影响。</p>
        </div>
        )}

        {activeHarness === 'embedded' && (
        <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-700">
          <p className="font-semibold mb-1">Embedded 引擎为纯本地词库纠偏</p>
          <p>仅按 <code className="font-mono bg-white px-1 py-0.5 rounded">storage/glossary.json</code> 做确定性错词替换与关键词高亮，无网络与模型依赖；开放式指令/聊天在该引擎下不可用（会明确报错）。</p>
        </div>
        )}

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
