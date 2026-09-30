import React, { useState, useEffect, useMemo } from 'react';
import {
  fetchBannedWords,
  saveBannedWord,
  deleteBannedWord,
  resetBannedWords
} from '../services/api';
import { useDialog } from '../components/common/CustomDialog';
import {
  ShieldCheck,
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

  const [mappings, setMappings] = useState<Record<string, string>>({});
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
      const data = await fetchBannedWords();
      setMappings(data.mappings || {});
    } catch (err: any) {
      showToast('获取违禁词库失败: ' + (err?.message || '网络异常'), 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // 排序与筛选（长词优先展示，对齐后端规则）
  const displayList = useMemo(() => {
    let entries = Object.entries(mappings);
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      entries = entries.filter(([k, v]) => k.toLowerCase().includes(q) || v.toLowerCase().includes(q));
    }
    return entries.sort((a, b) => b[0].length - a[0].length || a[0].localeCompare(b[0]));
  }, [mappings, searchQuery]);

  const handleAddWord = async (e: React.FormEvent) => {
    e.preventDefault();
    const orig = inputOrig.trim();
    const repl = inputRepl.trim();
    if (!orig) {
      showAlert({ title: '提示', message: '请输入原词', type: 'warning' });
      return;
    }
    if (!repl) {
      showAlert({ title: '提示', message: '请输入处理后的词', type: 'warning' });
      return;
    }

    setSaving(true);
    try {
      const data = await saveBannedWord(orig, repl);
      setMappings(data.mappings || {});
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
      const data = await saveBannedWord(orig, repl);
      setMappings(data.mappings || {});
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
      const data = await deleteBannedWord(orig);
      setMappings(data.mappings || {});
      showToast(`已删除: ${orig}`, 'success');
    } catch (err: any) {
      showAlert({ title: '删除失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  const handleReset = async () => {
    const confirmed = await showConfirm({
      title: '确认恢复默认',
      message: '确定要将违禁词库恢复为系统默认配置吗？',
      isDestructive: true,
      confirmText: '恢复'
    });
    if (!confirmed) return;

    try {
      const data = await resetBannedWords();
      setMappings(data.mappings || {});
      showToast('已恢复默认违禁词库', 'success');
    } catch (err: any) {
      showAlert({ title: '恢复失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#F8FAFC] overflow-y-auto">
      {/* 顶部标题栏 */}
      <div className="bg-white border-b border-gray-200/80 px-8 py-4 flex items-center justify-between sticky top-0 z-20 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-gray-900 tracking-tight">违禁词处理</h1>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200/60 font-mono">
                {Object.keys(mappings).length} 条规则
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              左边是原词，右边是处理后的。批量混剪与导出视频时自动执行替换脱敏。
            </p>
          </div>
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
        {/* 添加违禁词栏与搜索栏 */}
        <div className="bg-white rounded-2xl border border-gray-200/80 p-4 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
          {/* 添加新词表单 */}
          <form onSubmit={handleAddWord} className="flex items-center space-x-2 w-full md:w-auto flex-1">
            <input
              type="text"
              value={inputOrig}
              onChange={(e) => setInputOrig(e.target.value)}
              placeholder="原词 (如: 包过)"
              className="px-3 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 flex-1 md:w-44"
            />
            <ArrowRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <input
              type="text"
              value={inputRepl}
              onChange={(e) => setInputRepl(e.target.value)}
              placeholder="处理后 (如: 包合格)"
              className="px-3 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 flex-1 md:w-44"
            />
            <button
              type="submit"
              disabled={saving}
              className="flex items-center space-x-1 px-4 py-1.5 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 active:bg-rose-800 transition-all shadow-xs cursor-pointer flex-shrink-0 disabled:opacity-50"
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
              className="w-full pl-8 pr-7 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
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
            <div className="col-span-5">原词（左边）</div>
            <div className="col-span-1 text-center"></div>
            <div className="col-span-5">处理后（右边）</div>
            <div className="col-span-1 text-right">操作</div>
          </div>

          {displayList.length === 0 ? (
            <div className="py-12 text-center text-gray-400 text-xs">
              暂无匹配的违禁词规则
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {displayList.map(([orig, repl]) => (
                <div
                  key={orig}
                  className="grid grid-cols-12 px-6 py-3 items-center hover:bg-gray-50/60 transition-colors text-xs"
                >
                  {/* 左边：原词 */}
                  <div className="col-span-5 font-semibold text-gray-900 truncate">
                    {orig}
                  </div>

                  {/* 箭头 */}
                  <div className="col-span-1 flex justify-center text-gray-300">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>

                  {/* 右边：处理后 */}
                  <div className="col-span-5 text-rose-600 font-medium">
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
                          className="px-2 py-1 text-xs bg-white rounded-lg border border-rose-300 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 w-48 text-rose-600 font-semibold"
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
                        title="点击直接修改处理后的词"
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
