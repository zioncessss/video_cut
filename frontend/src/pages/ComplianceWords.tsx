import React, { useState, useEffect, useMemo } from 'react';
import {
  fetchBannedWords,
  saveBannedWord,
  deleteBannedWord,
  resetBannedWords,
  fetchGlossary,
  saveGlossaryCorrection,
  deleteGlossaryCorrection,
  resetGlossary
} from '../services/api';
import { useDialog } from '../components/common/CustomDialog';
import {
  ShieldCheck,
  Sparkles,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  ArrowRight,
  RefreshCw,
  X,
  Edit2,
  Check
} from 'lucide-react';

export const ComplianceWords: React.FC = () => {
  const { showAlert, showConfirm, showToast } = useDialog();

  const [activeTab, setActiveTab] = useState<'glossary' | 'banned'>('glossary');

  // 字幕纠偏映射与违禁词映射
  const [glossaryMappings, setGlossaryMappings] = useState<Record<string, string>>({});
  const [bannedMappings, setBannedMappings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // 新增输入状态
  const [inputOrig, setInputOrig] = useState<string>('');
  const [inputRepl, setInputRepl] = useState<string>('');
  const [saving, setSaving] = useState<boolean>(false);

  // 行内编辑状态
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editReplValue, setEditReplValue] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [glossaryRes, bannedRes] = await Promise.all([
        fetchGlossary().catch(() => ({ corrections: {} as Record<string, string>, total: 0 })),
        fetchBannedWords().catch(() => ({ mappings: {} as Record<string, string>, total: 0 }))
      ]);
      setGlossaryMappings(glossaryRes.corrections || {});
      setBannedMappings(bannedRes.mappings || {});
    } catch (err: any) {
      showToast('获取词库数据失败: ' + (err?.message || '网络异常'), 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const currentMappings = activeTab === 'glossary' ? glossaryMappings : bannedMappings;

  // 排序与筛选（长词优先展示，对齐后端规则）
  const displayList = useMemo(() => {
    let entries = Object.entries(currentMappings);
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      entries = entries.filter(([k, v]) => k.toLowerCase().includes(q) || v.toLowerCase().includes(q));
    }
    return entries.sort((a, b) => b[0].length - a[0].length || a[0].localeCompare(b[0]));
  }, [currentMappings, searchQuery]);

  const handleAddWord = async (e: React.FormEvent) => {
    e.preventDefault();
    const orig = inputOrig.trim();
    const repl = inputRepl.trim();
    if (!orig) {
      showAlert({ title: '提示', message: activeTab === 'glossary' ? '请输入识别错词' : '请输入原始敏感词', type: 'warning' });
      return;
    }
    if (!repl) {
      showAlert({ title: '提示', message: activeTab === 'glossary' ? '请输入纠偏后的正确词' : '请输入处理后的脱敏词', type: 'warning' });
      return;
    }

    setSaving(true);
    try {
      if (activeTab === 'glossary') {
        const res = await saveGlossaryCorrection(orig, repl);
        setGlossaryMappings(res.corrections || {});
      } else {
        const res = await saveBannedWord(orig, repl);
        setBannedMappings(res.mappings || {});
      }
      setInputOrig('');
      setInputRepl('');
      showToast(`已添加规则: ${orig} → ${repl}`, 'success');
    } catch (err: any) {
      showAlert({ title: '添加失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleStartEdit = (orig: string, repl: string) => {
    setEditingKey(orig);
    setEditReplValue(repl);
  };

  const handleSaveEdit = async (orig: string) => {
    const repl = editReplValue.trim();
    if (!repl) {
      showAlert({ title: '提示', message: '处理后的词不能为空', type: 'warning' });
      return;
    }
    try {
      if (activeTab === 'glossary') {
        const res = await saveGlossaryCorrection(orig, repl);
        setGlossaryMappings(res.corrections || {});
      } else {
        const res = await saveBannedWord(orig, repl);
        setBannedMappings(res.mappings || {});
      }
      setEditingKey(null);
      showToast(`已更新: ${orig} → ${repl}`, 'success');
    } catch (err: any) {
      showAlert({ title: '保存失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  const handleDelete = async (orig: string) => {
    const confirmed = await showConfirm({
      title: '确认删除',
      message: `确定要删除规则 "${orig}" 吗？`,
      isDestructive: true,
      confirmText: '删除'
    });
    if (!confirmed) return;

    try {
      if (activeTab === 'glossary') {
        const res = await deleteGlossaryCorrection(orig);
        setGlossaryMappings(res.corrections || {});
      } else {
        const res = await deleteBannedWord(orig);
        setBannedMappings(res.mappings || {});
      }
      showToast(`已删除: ${orig}`, 'success');
    } catch (err: any) {
      showAlert({ title: '删除失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  const handleReset = async () => {
    const isGlossary = activeTab === 'glossary';
    const confirmed = await showConfirm({
      title: '确认恢复默认',
      message: isGlossary
        ? '确定要将字幕纠偏词库恢复为系统默认配置吗？'
        : '确定要将违禁词脱敏词库恢复为系统默认配置吗？',
      isDestructive: true,
      confirmText: '恢复默认'
    });
    if (!confirmed) return;

    try {
      if (isGlossary) {
        const res = await resetGlossary();
        setGlossaryMappings(res.corrections || {});
        showToast('已恢复默认字幕纠偏词库', 'success');
      } else {
        const res = await resetBannedWords();
        setBannedMappings(res.mappings || {});
        showToast('已恢复默认违禁词词库', 'success');
      }
    } catch (err: any) {
      showAlert({ title: '恢复失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#F8FAFC] overflow-y-auto">
      {/* 顶部标题栏与标签切换 */}
      <div className="bg-white border-b border-gray-200/80 px-8 py-3.5 flex items-center justify-between sticky top-0 z-20 shadow-xs">
        <div className="flex items-center space-x-6">
          {/* 选项卡切换 */}
          <div className="flex items-center space-x-1.5 bg-gray-100 p-1 rounded-xl border border-gray-200/80">
            <button
              type="button"
              onClick={() => {
                setActiveTab('glossary');
                setEditingKey(null);
                setSearchQuery('');
              }}
              className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'glossary'
                  ? 'bg-white text-blue-600 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-white/60'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>字幕纠偏映射</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-50 text-blue-700 font-mono font-bold">
                {Object.keys(glossaryMappings).length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveTab('banned');
                setEditingKey(null);
                setSearchQuery('');
              }}
              className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'banned'
                  ? 'bg-white text-rose-600 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-white/60'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>违禁词脱敏</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-rose-50 text-rose-700 font-mono font-bold">
                {Object.keys(bannedMappings).length}
              </span>
            </button>
          </div>

          <p className="text-xs text-gray-500 hidden md:block">
            {activeTab === 'glossary'
              ? '左边是录音识别错词，右边是纠偏后的正确词。转写与初剪时自动替换。'
              : '左边是敏感词，右边是处理后的。批量混剪与视频导出时自动替换脱敏。'}
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-colors border border-gray-200 bg-white cursor-pointer"
            title="刷新"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 border border-gray-200 bg-white transition-all cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5 text-gray-500" />
            <span>恢复默认</span>
          </button>
        </div>
      </div>

      <div className="p-8 max-w-5xl mx-auto w-full space-y-4">
        {/* 添加新词栏与搜索栏 */}
        <div className="bg-white rounded-2xl border border-gray-200/80 p-4 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
          {/* 添加新词表单 */}
          <form onSubmit={handleAddWord} className="flex items-center space-x-2 w-full md:w-auto flex-1">
            <input
              type="text"
              value={inputOrig}
              onChange={(e) => setInputOrig(e.target.value)}
              placeholder={activeTab === 'glossary' ? '识别错词 (如: 链车)' : '原词 (如: 包过)'}
              className="px-3 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 flex-1 md:w-44"
            />
            <ArrowRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <input
              type="text"
              value={inputRepl}
              onChange={(e) => setInputRepl(e.target.value)}
              placeholder={activeTab === 'glossary' ? '正确词 (如: 练车)' : '处理后 (如: 包合格)'}
              className="px-3 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 flex-1 md:w-44"
            />
            <button
              type="submit"
              disabled={saving}
              className={`flex items-center space-x-1 px-4 py-1.5 rounded-xl text-xs font-semibold text-white transition-all shadow-xs cursor-pointer flex-shrink-0 disabled:opacity-50 ${
                activeTab === 'glossary'
                  ? 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
                  : 'bg-rose-600 hover:bg-rose-700 active:bg-rose-800'
              }`}
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{saving ? '添加中...' : '添加'}</span>
            </button>
          </form>

          {/* 搜索框 */}
          <div className="relative w-full md:w-64 flex-shrink-0">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索词条..."
              className="w-full pl-8 pr-7 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-0.5 cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* 词库表格卡片 */}
        <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden">
          <div className="grid grid-cols-12 px-6 py-3 bg-gray-50/80 border-b border-gray-200 text-xs font-semibold text-gray-600">
            <div className="col-span-5">
              {activeTab === 'glossary' ? '错词（左边）' : '原词（左边）'}
            </div>
            <div className="col-span-1 text-center"></div>
            <div className="col-span-5">
              {activeTab === 'glossary' ? '纠偏正确词（右边）' : '处理后（右边）'}
            </div>
            <div className="col-span-1 text-right">操作</div>
          </div>

          {displayList.length === 0 ? (
            <div className="py-12 text-center text-gray-400 text-xs">
              暂无匹配的规则
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {displayList.map(([orig, repl]) => (
                <div
                  key={orig}
                  className="grid grid-cols-12 px-6 py-3 items-center hover:bg-gray-50/60 transition-colors text-xs"
                >
                  {/* 左边：原词 / 错词 */}
                  <div className="col-span-5 font-semibold text-gray-900 truncate">
                    {orig}
                  </div>

                  {/* 箭头 */}
                  <div className="col-span-1 flex justify-center text-gray-300">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>

                  {/* 右边：处理后 / 正确词 */}
                  <div className={`col-span-5 font-medium ${activeTab === 'glossary' ? 'text-blue-600' : 'text-rose-600'}`}>
                    {editingKey === orig ? (
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={editReplValue}
                          onChange={(e) => setEditReplValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveEdit(orig);
                            if (e.key === 'Escape') setEditingKey(null);
                          }}
                          autoFocus
                          className={`px-2 py-1 text-xs bg-white rounded-lg border focus:outline-hidden focus:ring-2 w-48 font-semibold ${
                            activeTab === 'glossary'
                              ? 'border-blue-300 focus:ring-blue-500/20 text-blue-600'
                              : 'border-rose-300 focus:ring-rose-500/20 text-rose-600'
                          }`}
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveEdit(orig)}
                          className="p-1 text-emerald-600 hover:bg-emerald-50 rounded cursor-pointer"
                          title="确认保存"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingKey(null)}
                          className="p-1 text-gray-400 hover:bg-gray-100 rounded cursor-pointer"
                          title="取消"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div
                        onClick={() => handleStartEdit(orig, repl)}
                        className="inline-block cursor-pointer hover:underline"
                        title="点击直接修改"
                      >
                        {repl}
                      </div>
                    )}
                  </div>

                  {/* 操作 */}
                  <div className="col-span-1 flex items-center justify-end space-x-1">
                    {editingKey !== orig && (
                      <button
                        type="button"
                        onClick={() => handleStartEdit(orig, repl)}
                        className="p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors cursor-pointer"
                        title="编辑"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(orig)}
                      className="p-1 text-gray-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer"
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
