import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../services/api';
import { Settings as SettingsIcon, Terminal, CheckCircle2, AlertCircle, Save } from 'lucide-react';

export const Settings: React.FC = () => {
  const [activeHarness, setActiveHarness] = useState<string>('embedded');
  const [llmModel, setLlmModel] = useState<string>('gpt-4o-mini');
  const [detected, setDetected] = useState<{ [key: string]: boolean }>({});
  const [saving, setSaving] = useState<boolean>(false);

  useEffect(() => {
    axios.get(`${API_BASE}/settings`).then(res => {
      setActiveHarness(res.data.active_harness);
      setLlmModel(res.data.llm_model);
      setDetected(res.data.detected_engines || {});
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.post(`${API_BASE}/settings`, {
        active_harness: activeHarness,
        llm_model: llmModel
      });
      alert('设置已成功保存！');
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
        </div>

        {/* 模型选择 */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-2">
            LLM 纠错与意图解析模型
          </label>
          <select
            value={llmModel}
            onChange={e => setLlmModel(e.target.value)}
            className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-xs text-gray-800 outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="gpt-4o-mini">gpt-4o-mini (极速、推荐)</option>
            <option value="deepseek-chat">deepseek-chat (语义理解优异)</option>
            <option value="qwen-plus">qwen-plus (通义千问)</option>
            <option value="local-ollama">local-ollama (本地私有化)</option>
          </select>
        </div>

        {/* 保存按钮 */}
        <div className="pt-4 border-t border-gray-100 flex justify-end">
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
