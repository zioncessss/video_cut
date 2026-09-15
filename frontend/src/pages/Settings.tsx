import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE, testHarness, TestHarnessResult } from '../services/api';
import { Settings as SettingsIcon, Terminal, CheckCircle2, AlertCircle, Save, Zap, Loader2 } from 'lucide-react';

export const Settings: React.FC = () => {
  const [activeHarness, setActiveHarness] = useState<string>('codex');
  const [llmModel, setLlmModel] = useState<string>('GLM-5.3-Flash');
  const [llmApiKey, setLlmApiKey] = useState<string>('');
  const [llmBaseUrl, setLlmBaseUrl] = useState<string>('');
  const [zcodePath, setZcodePath] = useState<string | null>(null);
  const [detected, setDetected] = useState<{ [key: string]: boolean }>({});
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<TestHarnessResult | null>(null);

  useEffect(() => {
    axios.get(`${API_BASE}/settings`).then(res => {
      setActiveHarness(res.data.active_harness);
      setLlmModel(res.data.llm_model || '');
      setLlmApiKey(res.data.llm_api_key || '');
      setLlmBaseUrl(res.data.llm_base_url || '');
      setZcodePath(res.data.zcode_path || null);
      setDetected(res.data.detected_engines || {});
    }).catch(() => {});
  }, []);

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
      await axios.post(`${API_BASE}/settings`, {
        active_harness: activeHarness,
        llm_model: llmModel,
        llm_api_key: llmApiKey,
        llm_base_url: llmBaseUrl
      });
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
          自由切换高阶操作的驱动基座：内置轻量 Agent、Codex CLI 或 ZCode Harness。
        </p>
      </div>

      <div className="bg-white border border-gray-200/80 rounded-2xl p-6 shadow-sm space-y-6">
        {/* Harness 运行时选择 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-3">
            活跃 Harness 智能体引擎 (Active Harness)
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { id: 'embedded', label: 'Embedded Agent', desc: '内置轻量智能体（开箱即用）' },
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
                        <AlertCircle className="w-3 h-3 mr-0.5" /> 未检测到CLI
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

        {/* 模型参数配置 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-1">
            Codex / LLM 模型参数覆盖 (可选 -m)
          </label>
          <p className="text-[11px] text-gray-500 mb-2">
            留空将完全继承本地 <code className="font-mono bg-gray-100 px-1 py-0.5 rounded">~/.codex/config.toml</code> 配置；亦可在此显式指定模型名称（如 <code className="font-mono bg-gray-100 px-1 py-0.5 rounded">glm-5.3-flash</code> 或 <code className="font-mono bg-gray-100 px-1 py-0.5 rounded">deepseek-chat</code>）。
          </p>
          <input
            type="text"
            value={llmModel}
            onChange={e => setLlmModel(e.target.value)}
            placeholder="留空默认使用 Codex 本地配置 (或输入 glm-5.3-flash)"
            className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500 font-mono"
          />
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
                  <span className="font-mono text-[11px] bg-white/80 px-2 py-0.5 rounded border border-gray-200/50">
                    响应延迟: {testResult.latency_ms} ms
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
