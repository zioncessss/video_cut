import React, { useState, useEffect, useMemo } from 'react';
import {
  fetchBannedWords,
  saveBannedWord,
  deleteBannedWord,
  resetBannedWords,
  previewBannedWords,
  BannedWordsPreviewResponse
} from '../services/api';
import { useDialog } from '../components/common/CustomDialog';
import {
  ShieldAlert,
  ShieldCheck,
  Plus,
  RotateCcw,
  Search,
  Pencil,
  Trash2,
  Sparkles,
  ArrowRight,
  RefreshCw,
  Copy,
  Check,
  HelpCircle,
  X,
  FileCheck2,
  Layers
} from 'lucide-react';

const COMMON_SUGGESTIONS = [
  { orig: '包过', repl: '包合格', tip: '承诺保过' },
  { orig: '秒过', repl: '稳步通过', tip: '夸大速度' },
  { orig: '买驾照', repl: '考取贺照', tip: '买卖证件' },
  { orig: '免考', repl: '免预约', tip: '违规宣传' },
  { orig: '加微信', repl: '加菉泡泡', tip: '导流第三方' },
  { orig: '全网第一', repl: '优质口碑', tip: '顶级极限词' },
  { orig: '电话', repl: '电讠舌', tip: '联系方式' },
  { orig: '免费', repl: '免弗', tip: '敏感价格' }
];

export const ComplianceWords: React.FC = () => {
  const { showAlert, showConfirm, showToast } = useDialog();

  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterLength, setFilterLength] = useState<'all' | '2' | '3' | '4+'>('all');

  // 实时测试沙盒
  const [testText, setTestText] = useState<string>(
    '在杭州考一个驾驶证要多少钱，我们的出证速度是最快的，最低价格，点个红心加关注，私信评论区找我聊'
  );
  const [testResult, setTestResult] = useState<BannedWordsPreviewResponse | null>(null);
  const [testing, setTesting] = useState<boolean>(false);

  // 添加/编辑模态框
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [editingWord, setEditingWord] = useState<string | null>(null);
  const [inputOriginal, setInputOriginal] = useState<string>('');
  const [inputReplacement, setInputReplacement] = useState<string>('');
  const [saving, setSaving] = useState<boolean>(false);

  // 复制反馈
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

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

  // 实时脱敏测试
  const handleRunTest = async (textToTest?: string) => {
    const text = textToTest !== undefined ? textToTest : testText;
    if (!text.trim()) {
      setTestResult(null);
      return;
    }
    setTesting(true);
    try {
      const res = await previewBannedWords(text);
      setTestResult(res);
    } catch (err: any) {
      showToast('测试脱敏失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      handleRunTest();
    }, 300);
    return () => clearTimeout(timer);
  }, [testText, mappings]);

  // 过滤与排序（长词优先，与底层清洗引擎规则严格对齐）
  const filteredWords = useMemo(() => {
    let entries = Object.entries(mappings);

    // 搜索过滤
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      entries = entries.filter(([k, v]) => k.toLowerCase().includes(q) || v.toLowerCase().includes(q));
    }

    // 长度过滤
    if (filterLength === '2') {
      entries = entries.filter(([k]) => k.length === 2);
    } else if (filterLength === '3') {
      entries = entries.filter(([k]) => k.length === 3);
    } else if (filterLength === '4+') {
      entries = entries.filter(([k]) => k.length >= 4);
    }

    // 严格按原词长度降序，长度相同时按字符字典排序
    return entries.sort((a, b) => b[0].length - a[0].length || a[0].localeCompare(b[0]));
  }, [mappings, searchQuery, filterLength]);

  const handleOpenAddModal = (initialOrig: string = '', initialRepl: string = '') => {
    setEditingWord(null);
    setInputOriginal(initialOrig);
    setInputReplacement(initialRepl);
    setModalOpen(true);
  };

  const handleOpenEditModal = (orig: string, repl: string) => {
    setEditingWord(orig);
    setInputOriginal(orig);
    setInputReplacement(repl);
    setModalOpen(true);
  };

  const handleSaveWord = async (e: React.FormEvent) => {
    e.preventDefault();
    const orig = inputOriginal.trim();
    const repl = inputReplacement.trim();
    if (!orig) {
      showAlert({ title: '输入有误', message: '原始违禁词不能为空', type: 'warning' });
      return;
    }
    if (!repl) {
      showAlert({ title: '输入有误', message: '脱敏替换词不能为空', type: 'warning' });
      return;
    }

    setSaving(true);
    try {
      // 若是重命名已有词，先删旧再存新
      if (editingWord && editingWord !== orig) {
        await deleteBannedWord(editingWord);
      }
      const data = await saveBannedWord(orig, repl);
      setMappings(data.mappings || {});
      setModalOpen(false);
      showToast(editingWord ? '已更新脱敏规则' : '已成功添加脱敏规则', 'success');
    } catch (err: any) {
      showAlert({ title: '保存失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteWord = async (orig: string) => {
    const confirmed = await showConfirm({
      title: '确认删除违禁词规则',
      message: `确定要删除规则 "${orig}" 吗？删除后视频压制与脱敏清洗将不再对此词进行替换。`,
      isDestructive: true,
      confirmText: '确认删除'
    });
    if (!confirmed) return;

    try {
      const data = await deleteBannedWord(orig);
      setMappings(data.mappings || {});
      showToast(`已删除规则: ${orig}`, 'success');
    } catch (err: any) {
      showAlert({ title: '删除失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  const handleResetDefault = async () => {
    const confirmed = await showConfirm({
      title: '确认恢复默认合规词库',
      message: '此操作将重置所有自定义添加与修改，还原为内置的标准抖音短视频脱敏词库。确定要恢复吗？',
      isDestructive: true,
      confirmText: '恢复默认'
    });
    if (!confirmed) return;

    try {
      const data = await resetBannedWords();
      setMappings(data.mappings || {});
      showToast('已成功恢复系统默认合规词库', 'success');
    } catch (err: any) {
      showAlert({ title: '恢复失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    }
  };

  const handleCopyReplacement = (word: string, key: string) => {
    navigator.clipboard.writeText(word);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <div className="h-full flex flex-col bg-[#F8FAFC] overflow-y-auto">
      {/* 顶部现代化页头 */}
      <div className="bg-white border-b border-gray-200/80 px-8 py-5 flex items-center justify-between sticky top-0 z-20 shadow-xs">
        <div className="flex items-center space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 shadow-xs">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-gray-900 tracking-tight">违禁词合规库</h1>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200/60 font-mono">
                {Object.keys(mappings).length} 条规则
              </span>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60 flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>长词优先脱敏已就绪</span>
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              短视频平台合规脱敏清洗系统。在视频导出或批量混剪时开启脱敏，系统将自动对字幕执行长词优先形似字替换，有效防御平台限流与违规判定。
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-colors cursor-pointer border border-gray-200/80 bg-white"
            title="刷新数据"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            type="button"
            onClick={handleResetDefault}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 border border-gray-200/80 bg-white transition-all cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5 text-gray-500" />
            <span>恢复默认词库</span>
          </button>

          <button
            type="button"
            onClick={() => handleOpenAddModal()}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 active:bg-rose-800 transition-all shadow-xs cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>添加违禁词</span>
          </button>
        </div>
      </div>

      <div className="p-8 max-w-7xl mx-auto w-full space-y-6">
        {/* 1. 实时脱敏测试沙盒 (Interactive Test Sandbox) */}
        <div className="bg-white rounded-2xl border border-gray-200/80 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">实时脱敏测试沙盒</h2>
              <span className="text-[11px] text-gray-400">输入任意字幕文案，即时验证词库替换命中与视觉呈现</span>
            </div>
            {testResult && testResult.total_matches > 0 && (
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                命中 {testResult.total_matches} 处违禁词
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 输入区 */}
            <div>
              <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1">
                <span>原始文案输入</span>
                <button
                  type="button"
                  onClick={() => setTestText('想在湖州考驾驶证的朋友看过来！咱们学校学费最低、拿证最快、特惠价只要2000，赶快私信关注我，评论区直接报名')}
                  className="text-rose-600 hover:text-rose-700 hover:underline cursor-pointer"
                >
                  填入示例口播
                </button>
              </div>
              <textarea
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
                placeholder="在此输入包含违禁词的口播文本..."
                rows={4}
                className="w-full text-xs p-3 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 bg-gray-50/50 resize-none font-sans"
              />
            </div>

            {/* 脱敏效果展示区 */}
            <div>
              <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1">
                <span>成片字幕脱敏预览 (替换完成)</span>
                {testResult && testResult.total_matches > 0 && (
                  <span className="text-emerald-600 flex items-center space-x-1">
                    <FileCheck2 className="w-3 h-3" />
                    <span>已完成合规清洗</span>
                  </span>
                )}
              </div>
              <div className="h-[94px] p-3 rounded-xl border border-gray-200/80 bg-gray-50 overflow-y-auto text-xs text-gray-800 leading-relaxed font-sans">
                {testResult?.sanitized_text || <span className="text-gray-400">暂无脱敏输出</span>}
              </div>
            </div>
          </div>

          {/* 命中的明细标签 */}
          {testResult && testResult.matches && testResult.matches.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-gray-400 font-medium">命中脱敏标签:</span>
              {testResult.matches.map((m, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs font-mono"
                >
                  <span className="line-through text-gray-400">{m.original_word}</span>
                  <ArrowRight className="w-3 h-3 text-rose-400" />
                  <span className="font-bold text-rose-700">{m.replacement_word}</span>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 2. 违禁词管理与列表 */}
        <div className="bg-white rounded-2xl border border-gray-200/80 p-5 shadow-xs space-y-4">
          {/* 筛选与搜索工具条 */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:w-72">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索原始词或替换词..."
                className="w-full pl-8 pr-7 py-1.5 text-xs bg-gray-50 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* 长度筛选标签组 */}
            <div className="inline-flex p-0.5 bg-gray-100 rounded-lg border border-gray-200/80 text-xs">
              <button
                type="button"
                onClick={() => setFilterLength('all')}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  filterLength === 'all' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                全部 ({Object.keys(mappings).length})
              </button>
              <button
                type="button"
                onClick={() => setFilterLength('2')}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  filterLength === '2' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                2字词
              </button>
              <button
                type="button"
                onClick={() => setFilterLength('3')}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  filterLength === '3' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                3字词
              </button>
              <button
                type="button"
                onClick={() => setFilterLength('4+')}
                className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  filterLength === '4+' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                4字及以上
              </button>
            </div>
          </div>

          {/* 规则卡片网格 */}
          {filteredWords.length === 0 ? (
            <div className="py-12 text-center text-gray-400 space-y-2">
              <ShieldAlert className="w-8 h-8 mx-auto text-gray-300" />
              <p className="text-xs">未找到匹配的脱敏规则</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {filteredWords.map(([orig, repl]) => (
                <div
                  key={orig}
                  className="group relative bg-gray-50/70 hover:bg-white rounded-xl p-3 border border-gray-200/80 hover:border-rose-200 hover:shadow-xs transition-all flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-gray-200/70 text-gray-600 font-medium">
                      {orig.length} 字词
                    </span>
                    <div className="opacity-0 group-hover:opacity-100 flex items-center space-x-1 transition-opacity">
                      <button
                        type="button"
                        onClick={() => handleOpenEditModal(orig, repl)}
                        className="p-1 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors cursor-pointer"
                        title="编辑规则"
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteWord(orig)}
                        className="p-1 text-gray-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                        title="删除规则"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 my-1">
                    <span className="text-xs font-semibold text-gray-700 bg-white px-2 py-1 rounded-md border border-gray-200/60 truncate flex-1 text-center">
                      {orig}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                    <span className="text-xs font-bold text-rose-600 bg-rose-50/80 px-2 py-1 rounded-md border border-rose-200/60 truncate flex-1 text-center">
                      {repl}
                    </span>
                  </div>

                  <div className="mt-2 pt-2 border-t border-gray-200/40 flex items-center justify-between text-[10px] text-gray-400">
                    <span>长词优先调度</span>
                    <button
                      type="button"
                      onClick={() => handleCopyReplacement(repl, orig)}
                      className="hover:text-gray-600 flex items-center space-x-0.5 cursor-pointer"
                    >
                      {copiedKey === orig ? (
                        <>
                          <Check className="w-2.5 h-2.5 text-emerald-500" />
                          <span className="text-emerald-500">已复制</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-2.5 h-2.5" />
                          <span>复制替换词</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 3. 常见敏感词快速添加建议 (Quick Recommendation Panel) */}
        <div className="bg-indigo-50/40 rounded-2xl border border-indigo-100/80 p-5 space-y-3">
          <div className="flex items-center space-x-2 text-indigo-900">
            <HelpCircle className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-bold uppercase tracking-wider">常用驾考短视频高频违禁词库参考</h3>
          </div>
          <p className="text-xs text-gray-600">
            平台重点巡检绝对承诺、引流导流及敏感价格词汇。点击下方快捷卡片可一键导入规则：
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {COMMON_SUGGESTIONS.map((s, idx) => {
              const alreadyExists = mappings[s.orig] !== undefined;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleOpenAddModal(s.orig, s.repl)}
                  className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
                    alreadyExists
                      ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                      : 'bg-white text-gray-800 border-indigo-100 hover:border-indigo-300 hover:shadow-xs'
                  }`}
                  disabled={alreadyExists}
                >
                  <span className="font-semibold text-gray-900">{s.orig}</span>
                  <span className="text-gray-400">→</span>
                  <span className="text-indigo-600 font-bold">{s.repl}</span>
                  <span className="text-[10px] text-gray-400">({s.tip})</span>
                  {alreadyExists && <span className="text-[10px] text-emerald-600 ml-1">✓已配置</span>}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 4. 添加/编辑模态框 */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl overflow-hidden max-w-md w-full border border-gray-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-rose-600" />
                <h3 className="text-sm font-bold text-gray-900">
                  {editingWord ? `编辑脱敏规则: ${editingWord}` : '添加违禁词脱敏规则'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveWord} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  原始违禁词 / 敏感词 <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={inputOriginal}
                  onChange={(e) => setInputOriginal(e.target.value)}
                  placeholder="例如：新政策、驾驶证、最快、包过..."
                  autoFocus
                  required
                  className="w-full text-xs p-2.5 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 bg-gray-50/50"
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  视频字幕中出现此词汇时将被命中清洗（支持任意汉字或词组）。
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  脱敏替换词 <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={inputReplacement}
                  onChange={(e) => setInputReplacement(e.target.value)}
                  placeholder="例如：新正攵朿、加驶正、蕞快、包合格..."
                  required
                  className="w-full text-xs p-2.5 rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 bg-gray-50/50"
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  通常建议使用形似字、拆字或同音字，保持观众视听自然连贯，同时避免算法封禁。
                </p>
              </div>

              {/* 快捷形似字示例提示 */}
              <div className="bg-gray-50 rounded-xl p-3 border border-gray-100 text-[11px] text-gray-600 space-y-1">
                <span className="font-semibold text-gray-800">常见形似字拆解技巧：</span>
                <p>• 拆字：政 → 正攵，策 → 朿，快 → 忄夬，骗 → 马扁</p>
                <p>• 同音/近义：证 → 正，最 → 蕞，费 → 弗，信 → 俬信</p>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-gray-600 hover:bg-gray-100 font-medium transition-colors cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center space-x-1.5 px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white text-xs font-semibold shadow-xs disabled:opacity-50 transition-colors cursor-pointer"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>{saving ? '保存中...' : '保存规则'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
