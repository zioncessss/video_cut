import React, { useState } from 'react';
import { Tag, PlayCircle, MapPin, Activity, Award, X, Plus, Sparkles, BookOpen, ChevronDown, RotateCcw } from 'lucide-react';
import { HighlightWord } from '../services/api';

export interface SubtitleItem {
  id: string;
  start_time: number;
  end_time: number;
  raw_text: string;
  corrected_text: string;
  matched_category?: 'venue' | 'medical' | 'experience' | 'lesson' | null;
  matched_keywords?: string[];
  highlight_words?: HighlightWord[];
  scene_decision?: {
    part: 'hook' | 'body' | 'cta';
    broll_category: 'venue' | 'experience' | 'lesson' | null;
    broll_duration: number;
    transition_seconds: number;
    material_id: string | null;
    reason: string;
  } | null;
  broll_material_id?: string | null;
  is_manual_edited?: boolean;
  is_pruned?: boolean;
  prune_reason?: string | null;
  prune_span_id?: string | null;
}

export type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';

interface SubtitleListProps {
  subtitles: SubtitleItem[];
  compactSubtitles?: SubtitleItem[];
  isCompactMode?: boolean;
  currentTime: number;
  saveStatus?: SaveStatus;
  lastSavedAt?: number | null;
  onSelectTime: (time: number) => void;
  onTextChange: (index: number, newText: string) => void;
  onTextBlur?: (index: number) => void;
  onHighlightWordsChange: (index: number, words: HighlightWord[]) => void;
  onRetrySave?: () => void;
  onTogglePrune?: (index: number, sub: SubtitleItem) => void;
}

const SOURCE_META: Record<string, { label: string; cls: string }> = {
  glossary: { label: '词库', cls: 'bg-gray-100 text-gray-700 border-gray-300' },
  ai: { label: 'AI', cls: 'bg-purple-50 text-purple-700 border-purple-200' },
  manual: { label: '手动', cls: 'bg-blue-50 text-blue-700 border-blue-200' }
};

export const SubtitleList: React.FC<SubtitleListProps> = ({
  subtitles,
  compactSubtitles = [],
  isCompactMode = false,
  currentTime,
  saveStatus = 'idle',
  lastSavedAt,
  onSelectTime,
  onTextChange,
  onTextBlur,
  onHighlightWordsChange,
  onRetrySave,
  onTogglePrune,
}) => {
  const [addingFor, setAddingFor] = useState<string | null>(null);
  const [newWord, setNewWord] = useState('');
  const [showPrunedDrawer, setShowPrunedDrawer] = useState(false);

  const prunedSubs = subtitles.filter(s => s.is_pruned);
  const activeSubs = subtitles.filter(s => !s.is_pruned);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = Math.floor(secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const getCategoryBadge = (cat?: string | null) => {
    if (cat === 'venue') {
      return (
        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <MapPin className="w-3 h-3" />
          <span>场地空镜</span>
        </span>
      );
    }
    if (cat === 'medical' || cat === 'experience') {
      return (
        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
          <Activity className="w-3 h-3" />
          <span>体验空镜</span>
        </span>
      );
    }
    if (cat === 'lesson') {
      return (
        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
          <Award className="w-3 h-3" />
          <span>教学学车空镜</span>
        </span>
      );
    }
    return null;
  };

  const removeWord = (idx: number, sub: SubtitleItem, word: string) => {
    const rest = (sub.highlight_words || []).filter(w => w.word !== word);
    onHighlightWordsChange(idx, rest);
  };

  const addWord = (idx: number, sub: SubtitleItem) => {
    const w = newWord.trim();
    if (!w) return;
    const exists = (sub.highlight_words || []).some(x => x.word === w);
    if (exists) {
      setAddingFor(null);
      setNewWord('');
      return;
    }
    onHighlightWordsChange(idx, [...(sub.highlight_words || []), { word: w, source: 'manual', color: '#FACC15' }]);
    setNewWord('');
    setAddingFor(null);
  };

  const getPartBadge = (part?: string) => {
    if (part === 'hook') {
      return <span className="px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-orange-100 text-orange-700 border border-orange-200">开场</span>;
    }
    if (part === 'cta') {
      return <span className="px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-green-100 text-green-700 border border-green-200">召唤</span>;
    }
    return null;
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between pb-2.5 border-b border-gray-100 mb-2.5 flex-shrink-0">
        <div className="flex items-center space-x-2">
          <h2 className="text-sm font-bold text-gray-800">字幕时间轴与语义空镜分配</h2>
          {/* 实时保存状态反馈徽标 */}
          {saveStatus === 'saving' && (
            <span className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping" />
              <span>保存中...</span>
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span>✓ 全部已同步</span>
            </span>
          )}
          {saveStatus === 'dirty' && (
            <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
              <span>● 编辑未保存</span>
            </span>
          )}
          {saveStatus === 'error' && (
            <button
              type="button"
              onClick={onRetrySave}
              className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 cursor-pointer"
              title="点击手动重试保存至本地权威库"
            >
              <span>✕ 保存失败，点击重试</span>
            </button>
          )}
        </div>
        <span className="text-xs text-gray-400 font-mono">成片共 {activeSubs.length} 句{prunedSubs.length > 0 ? ` · 已过滤 ${prunedSubs.length} 处` : ''}</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {/* 已过滤废话与口误的顶部收纳折叠栏 */}
        {prunedSubs.length > 0 && (
          <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 overflow-hidden mb-2 transition-all shadow-2xs">
            <button
              type="button"
              onClick={() => setShowPrunedDrawer(!showPrunedDrawer)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs text-amber-900 hover:bg-amber-100/60 transition-colors font-medium cursor-pointer select-none"
            >
              <div className="flex items-center space-x-2">
                <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-full bg-amber-200/90 text-amber-900 text-[10px] font-bold">
                  {prunedSubs.length}
                </span>
                <span>已智能过滤 {prunedSubs.length} 处口误与废镜头</span>
              </div>
              <div className="flex items-center space-x-1 text-[11px] text-amber-700">
                <span>{showPrunedDrawer ? '收起' : '展开查看 / 恢复'}</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${showPrunedDrawer ? 'rotate-180' : ''}`} />
              </div>
            </button>

            {showPrunedDrawer && (
              <div className="p-2.5 pt-0 space-y-2 border-t border-amber-200/50 bg-amber-50/30 max-h-56 overflow-y-auto">
                {prunedSubs.map(pSub => {
                  const origIdx = subtitles.findIndex(s => s.id === pSub.id);
                  const reasonLabel =
                    pSub.prune_reason === 'retake_discard' ? '口误重说' :
                    pSub.prune_reason === 'head_idle' ? '开机准备' :
                    pSub.prune_reason === 'tail_idle' ? '关机废镜头' :
                    pSub.prune_reason === 'mid_silence' ? '长停顿压缩' : '手动剔除';
                  return (
                    <div
                      key={pSub.id}
                      className="p-2 rounded-lg border border-dashed border-amber-300/80 bg-white/90 flex items-start justify-between gap-2 shadow-2xs"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                            {reasonLabel}
                          </span>
                          <span className="text-[11px] text-gray-400 font-mono">
                            原片 {formatTime(pSub.start_time)} - {formatTime(pSub.end_time)}
                          </span>
                        </div>
                        <div className="text-gray-500 line-through text-xs break-all">
                          {pSub.corrected_text || pSub.raw_text}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onTogglePrune && onTogglePrune(origIdx, pSub)}
                        className="flex-shrink-0 flex items-center space-x-1 px-2 py-1 rounded-md text-[11px] font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition-colors cursor-pointer"
                        title="将此句恢复到成片时间轴"
                      >
                        <RotateCcw className="w-3 h-3 text-indigo-600" />
                        <span>恢复</span>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* 主列表：仅展示有效保留句，展示紧凑成片时间轴 */}
        {activeSubs.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-xs">
            暂无有效字幕片段，请先点击【智能剪辑】
          </div>
        ) : (
          activeSubs.map((sub, activeIdx) => {
            const origIdx = subtitles.findIndex(s => s.id === sub.id);
            const compactSub = compactSubtitles?.find(cs => cs.id === sub.id);
            const dispStart = (isCompactMode && compactSub) ? compactSub.start_time : sub.start_time;
            const dispEnd = (isCompactMode && compactSub) ? compactSub.end_time : sub.end_time;

            const prevSub = activeIdx > 0 ? activeSubs[activeIdx - 1] : null;
            const prevCompact = prevSub && compactSubtitles ? compactSubtitles.find(cs => cs.id === prevSub.id) : null;
            const prevEnd = prevSub ? ((isCompactMode && prevCompact) ? prevCompact.end_time : prevSub.end_time) : 0;
            const effStart = Math.max(prevEnd, dispStart - 0.07);

            const nextSub = activeIdx + 1 < activeSubs.length ? activeSubs[activeIdx + 1] : null;
            const nextCompact = nextSub && compactSubtitles ? compactSubtitles.find(cs => cs.id === nextSub.id) : null;
            const nextStart = nextSub ? ((isCompactMode && nextCompact) ? nextCompact.start_time : nextSub.start_time) : 999;
            const gap = nextSub ? nextStart - dispEnd : 999;
            const effEnd = nextSub && gap > 0 && gap <= 0.60
              ? Math.max(dispEnd, nextStart - 0.07)
              : dispEnd + 0.25;

            const isActive = currentTime >= effStart && currentTime < effEnd;
            const words: HighlightWord[] = sub.highlight_words
              ? sub.highlight_words
              : (sub.matched_keywords || []).map(w => ({ word: w, source: 'glossary' as const }));

            return (
              <div
                key={sub.id || activeIdx}
                className={`p-3 rounded-xl border transition-all duration-150 ${
                  isActive
                    ? 'border-blue-500 bg-blue-50/40 ring-1 ring-blue-500/20 shadow-xs'
                    : 'border-gray-200 bg-gray-50/50 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-1.5">
                    <button
                      onClick={() => onSelectTime(dispStart)}
                      className="flex items-center space-x-1 text-xs font-mono font-semibold text-gray-700 hover:text-blue-600 transition-colors cursor-pointer"
                      title={isCompactMode && compactSub ? `成片 ${formatTime(dispStart)} - ${formatTime(dispEnd)}（原片 ${formatTime(sub.start_time)} - ${formatTime(sub.end_time)}）` : undefined}
                    >
                      <PlayCircle className="w-3.5 h-3.5 text-blue-600" />
                      <span>{formatTime(dispStart)} - {formatTime(dispEnd)}</span>
                    </button>
                    {sub.is_manual_edited && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-medium bg-blue-50 text-blue-600 border border-blue-200" title="已进行人工手动修改">
                        人工修改
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => onTogglePrune && onTogglePrune(origIdx, sub)}
                      className="px-1.5 py-0.5 rounded text-[10px] text-gray-400 hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 transition-colors cursor-pointer"
                      title="点击剔除此片段（移入已过滤收纳折叠栏）"
                    >
                      剔除
                    </button>
                  </div>
                  <div className="flex items-center space-x-1">
                    {getPartBadge(sub.scene_decision?.part)}
                    {getCategoryBadge(sub.matched_category)}
                  </div>
                </div>

                {sub.scene_decision && (
                  <div
                    className={`mb-1.5 text-[10px] rounded-lg px-2 py-1 border ${
                      sub.scene_decision.broll_category
                        ? 'bg-blue-50/70 text-blue-800 border-blue-200'
                        : 'bg-gray-100/70 text-gray-500 border-gray-200'
                    }`}
                    title={sub.scene_decision.reason}
                  >
                    {sub.scene_decision.broll_category
                      ? `AI 分镜：${sub.scene_decision.broll_category === 'venue' ? '场地' : sub.scene_decision.broll_category === 'experience' ? '体验' : '教学'}空镜 ${sub.scene_decision.broll_duration.toFixed(1)}s · 转场 ${sub.scene_decision.transition_seconds.toFixed(1)}s`
                      : 'AI 分镜：保留口播真人画面'}
                    {sub.scene_decision.reason && sub.scene_decision.reason !== '保留口播真人画面' && (
                      <span className="text-gray-400"> · {sub.scene_decision.reason}</span>
                    )}
                  </div>
                )}

                <textarea
                  value={sub.corrected_text}
                  onChange={e => onTextChange(origIdx, e.target.value)}
                  onBlur={() => onTextBlur && onTextBlur(origIdx)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      (e.target as HTMLElement).blur();
                    }
                  }}
                  placeholder="输入字幕文本..."
                  className="w-full text-xs rounded-lg p-2 outline-none resize-none text-gray-800 bg-white border border-gray-200 focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  rows={2}
                />

                {/* 高亮词 chip：来源徽标（词库/AI/手动）+ 删除；输入框添加新词 */}
                <div className="flex items-center flex-wrap gap-1.5 mt-1.5">
                  <Tag className="w-3 h-3 text-gray-400 flex-shrink-0" />
                  {words.length === 0 && (
                    <span className="text-[10px] text-gray-400">暂无高亮词</span>
                  )}
                  {words.map(w => {
                    const meta = SOURCE_META[w.source] || SOURCE_META.glossary;
                    const wordColor = w.color || '#FACC15';
                    return (
                      <span
                        key={w.word}
                        className={`inline-flex items-center space-x-1 pl-1.5 pr-1 py-0.5 rounded-md text-[10px] font-medium border ${meta.cls}`}
                        title={`来源：${meta.label}${w.category ? ` · 类型：${w.category}` : ''} · 颜色：${wordColor}`}
                      >
                        <span
                          className="w-2 h-2 rounded-full inline-block flex-shrink-0 shadow-xs border border-black/20"
                          style={{ backgroundColor: wordColor }}
                        />
                        {w.source === 'ai' ? (
                          <Sparkles className="w-2.5 h-2.5 opacity-70" />
                        ) : w.source === 'manual' ? (
                          <BookOpen className="w-2.5 h-2.5 opacity-70" />
                        ) : (
                          <Tag className="w-2.5 h-2.5 opacity-70" />
                        )}
                        <span>{w.word}</span>
                        <button
                          onClick={() => removeWord(origIdx, sub, w.word)}
                          className="hover:bg-black/10 rounded-sm p-0.5 transition-colors"
                          title={`删除高亮词「${w.word}」`}
                        >
                          <X className="w-2.5 h-2.5" />
                        </button>
                      </span>
                    );
                  })}
                  {addingFor === sub.id ? (
                    <span className="inline-flex items-center space-x-1">
                      <input
                        autoFocus
                        value={newWord}
                        onChange={e => setNewWord(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') addWord(origIdx, sub);
                          if (e.key === 'Escape') { setAddingFor(null); setNewWord(''); }
                        }}
                        placeholder="新词后回车"
                        className="w-24 text-[10px] border border-blue-300 rounded-md px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <button
                        onClick={() => { setAddingFor(null); setNewWord(''); }}
                        className="text-gray-400 hover:text-gray-600"
                        title="取消"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ) : (
                    <button
                      onClick={() => { setAddingFor(sub.id); setNewWord(''); }}
                      className="inline-flex items-center space-x-0.5 px-1.5 py-0.5 rounded-md text-[10px] text-gray-500 border border-dashed border-gray-300 hover:border-blue-400 hover:text-blue-600 transition-colors"
                      title="添加手动高亮词"
                    >
                      <Plus className="w-2.5 h-2.5" />
                      <span>加词</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
