import React, { useState } from 'react';
import { Tag, PlayCircle, MapPin, Activity, Award, X, Plus, Sparkles, BookOpen, ChevronDown, RotateCcw, Clock, Film, Trash2, Check, Scissors, Link, Flag, AlertTriangle, Wand2 } from 'lucide-react';
import { HighlightWord, Material, BrollReplacement } from '../services/api';
import { BrollPickerModal } from './BrollPickerModal';

export interface SubtitleWord {
  word: string;
  start: number;
  end: number;
}

export interface SubtitleItem {
  id: string;
  start_time: number;
  end_time: number;
  raw_text: string;
  corrected_text: string;
  matched_category?: 'venue' | 'medical' | 'experience' | 'lesson' | null;
  matched_keywords?: string[];
  highlight_words?: HighlightWord[];
  words?: SubtitleWord[];
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
  materialsMap?: Record<string, Material>;
  brolls?: BrollReplacement[];
  totalDuration?: number;
  onSelectTime: (time: number) => void;
  onTextChange: (index: number, newText: string) => void;
  onTextBlur?: (index: number) => void;
  onHighlightWordsChange: (index: number, words: HighlightWord[]) => void;
  onRetrySave?: () => void;
  onTogglePrune?: (index: number, sub: SubtitleItem) => void;
  onTimeRangeChange?: (index: number, start: number, end: number) => void;
  onAddSubtitle?: (insertAfterIndex: number) => void;
  onSplitSubtitle?: (index: number, sub: SubtitleItem, splitData?: { part1Text?: string; part2Text?: string; splitTime?: number }) => void;
  onMergeNextSubtitle?: (index: number, sub: SubtitleItem) => void;
  onBrollChange?: (broll: BrollReplacement | null, subId: string) => void;
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
  materialsMap = {},
  brolls = [],
  totalDuration = 0,
  onSelectTime,
  onTextChange,
  onTextBlur,
  onHighlightWordsChange,
  onRetrySave,
  onTogglePrune,
  onTimeRangeChange,
  onAddSubtitle,
  onSplitSubtitle,
  onMergeNextSubtitle,
  onBrollChange,
}) => {
  const [addingFor, setAddingFor] = useState<string | null>(null);
  const [newWord, setNewWord] = useState('');

  // T013: 时间微调状态
  const [editingTimeId, setEditingTimeId] = useState<string | null>(null);
  const [timeStartStr, setTimeStartStr] = useState<string>('');
  const [timeEndStr, setTimeEndStr] = useState<string>('');
  const [timeError, setTimeError] = useState<string | null>(null);

  // 字幕拆分状态
  const [splittingSubId, setSplittingSubId] = useState<string | null>(null);
  const [splitPart1, setSplitPart1] = useState<string>('');
  const [splitPart2, setSplitPart2] = useState<string>('');
  const [splitTimeStr, setSplitTimeStr] = useState<string>('');
  const [splitError, setSplitError] = useState<string | null>(null);

  // 分镜素材挑选与截取弹窗状态
  const [pickingBrollState, setPickingBrollState] = useState<{
    sub: SubtitleItem;
    dispStart: number;
    dispEnd: number;
  } | null>(null);

  const [showPrunedList, setShowPrunedList] = useState<boolean>(false);

  const prunedSubs = subtitles.filter(s => s.is_pruned);
  const activeSubs = subtitles.filter(s => !s.is_pruned);

  // 计算字级声学对齐时间点
  const computeSplitTime = (sub: SubtitleItem, p1Text: string, dispStart: number, dispEnd: number) => {
    const dur = dispEnd - dispStart;
    const textLen = (sub.corrected_text || sub.raw_text || '').trim().length;
    const p1Len = p1Text.trim().length;

    // 若原句具备 ASR 字级声学时间戳，优先根据字级结束时间进行声学对齐
    if (sub.words && sub.words.length > 0 && p1Len > 0) {
      let accum = '';
      let matchIdx = -1;
      for (let i = 0; i < sub.words.length; i++) {
        accum += sub.words[i].word;
        if (accum.length >= p1Len) {
          matchIdx = i;
          break;
        }
      }
      if (matchIdx !== -1) {
        const wEnd = sub.words[matchIdx].end;
        const rawDur = Math.max(0.01, sub.end_time - sub.start_time);
        const ratio = (wEnd - sub.start_time) / rawDur;
        const sTime = dispStart + dur * Math.max(0.05, Math.min(0.95, ratio));
        return Number(sTime.toFixed(2));
      }
    }

    // 次选当前播放器位置（若落在该句有效中间区间）
    if (currentTime > dispStart + 0.1 && currentTime < dispEnd - 0.1) {
      return Number(currentTime.toFixed(2));
    }

    // 默认字数比例线性插值
    const ratio = p1Len / Math.max(1, textLen);
    const sTime = dispStart + dur * Math.max(0.05, Math.min(0.95, ratio));
    return Number(sTime.toFixed(2));
  };

  const handleStartSplit = (sub: SubtitleItem, dispStart: number, dispEnd: number) => {
    if (splittingSubId === sub.id) {
      setSplittingSubId(null);
      return;
    }
    const text = (sub.corrected_text || sub.raw_text || '').trim();
    setSplittingSubId(sub.id);
    setSplitError(null);

    const puncts = ['，', '。', '！', '？', '；', ',', '!', '?', ';', ' '];
    const mid = Math.floor(text.length / 2);
    let bestDist = 999;
    let foundIdx = -1;
    for (let i = 0; i < text.length; i++) {
      if (puncts.includes(text[i]) && i >= 1 && i < text.length - 1) {
        const dist = Math.abs(i - mid);
        if (dist < bestDist) {
          bestDist = dist;
          foundIdx = i;
        }
      }
    }

    let p1 = '';
    let p2 = '';
    if (foundIdx !== -1) {
      p1 = text.slice(0, foundIdx).replace(/[，。！？；,!?; ]+$/, '');
      p2 = text.slice(foundIdx + 1).replace(/^[，。！？；,!?; ]+/, '');
    } else {
      const splitAt = Math.max(1, Math.min(text.length - 1, mid));
      p1 = text.slice(0, splitAt);
      p2 = text.slice(splitAt);
    }
    setSplitPart1(p1);
    setSplitPart2(p2);

    const sTime = computeSplitTime(sub, p1, dispStart, dispEnd);
    setSplitTimeStr(sTime.toFixed(2));
  };

  const formatExactTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) secs = 0;
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toFixed(2).padStart(5, '0');
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
        <div className="flex items-center space-x-2">
          {onAddSubtitle && (
            <button
              type="button"
              onClick={() => onAddSubtitle(-1)}
              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors shadow-2xs cursor-pointer"
              title="在末尾或当前播放位置插入新字幕"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>插入字幕</span>
            </button>
          )}
          <span className="text-xs text-gray-400 font-mono">成片共 {activeSubs.length} 句{prunedSubs.length > 0 ? ` · 已过滤 ${prunedSubs.length} 处` : ''}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">


        {/* 已剔除片段折叠条：剔除片段不占成片时间轴，主轴纯净单调递增 */}
        {prunedSubs.length > 0 && (
          <div className="mb-2 p-2 rounded-xl bg-gray-50 border border-dashed border-gray-300">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-xs text-gray-600">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span className="font-medium">已智能剔除 {prunedSubs.length} 处口误与废镜头（已从时间轴移除）</span>
              </div>
              <button
                type="button"
                onClick={() => setShowPrunedList(prev => !prev)}
                className="text-[11px] font-medium text-blue-600 hover:text-blue-700 flex items-center space-x-1 cursor-pointer"
              >
                <span>{showPrunedList ? '收起' : '查看 / 恢复'}</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showPrunedList ? 'rotate-180' : ''}`} />
              </button>
            </div>
            {showPrunedList && (
              <div className="mt-2 space-y-1.5 border-t border-gray-200/60 pt-2">
                {prunedSubs.map((sub, pIdx) => {
                  const origIdx = subtitles.findIndex(s => s.id === sub.id);
                  const reasonLabel =
                    sub.prune_reason === 'retake_discard' ? '口误重读' :
                    sub.prune_reason === 'head_idle' ? '开机准备' :
                    sub.prune_reason === 'tail_idle' ? '关机废镜头' :
                    sub.prune_reason === 'mid_silence' ? '长停顿' : '已剔除';
                  return (
                    <div
                      key={sub.id || pIdx}
                      className="px-2.5 py-1.5 rounded-lg border border-dashed border-gray-200 bg-white flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex items-center space-x-2 min-w-0">
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-gray-100 text-gray-600">
                          {reasonLabel}
                        </span>
                        <span className="text-[11px] text-gray-400 font-mono flex-shrink-0">
                          原片 {formatExactTime(sub.start_time)} - {formatExactTime(sub.end_time)}
                        </span>
                        <span className="line-through truncate text-gray-400 text-xs max-w-[200px]" title={sub.corrected_text || sub.raw_text}>
                          {sub.corrected_text || sub.raw_text}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => onTogglePrune && onTogglePrune(origIdx, sub)}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 transition-colors shadow-2xs flex-shrink-0 cursor-pointer"
                        title="恢复此片段到成片中"
                      >
                        <RotateCcw className="w-3 h-3 text-blue-600" />
                        <span>恢复</span>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeSubs.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-xs">
            暂无字幕片段，请点击顶部【插入字幕】或选择素材进行智能剪辑
          </div>
        ) : (
          activeSubs.map((sub, activeIdx) => {
            const origIdx = subtitles.findIndex(s => s.id === sub.id);
            const compactSub = compactSubtitles?.find(cs => cs.id === sub.id);
            const dispStart = compactSub ? compactSub.start_time : sub.start_time;
            const dispEnd = compactSub ? compactSub.end_time : sub.end_time;

            const prevSub = activeIdx > 0 ? activeSubs[activeIdx - 1] : null;
            const prevCompact = prevSub && compactSubtitles ? compactSubtitles.find(cs => cs.id === prevSub.id) : null;
            const prevEnd = prevCompact ? prevCompact.end_time : (prevSub ? prevSub.end_time : 0);
            const effStart = Math.max(prevEnd, dispStart - 0.07);

            const nextSub = activeIdx >= 0 && activeIdx + 1 < activeSubs.length ? activeSubs[activeIdx + 1] : null;
            const nextCompact = nextSub && compactSubtitles ? compactSubtitles.find(cs => cs.id === nextSub.id) : null;
            const nextStart = nextCompact ? nextCompact.start_time : (nextSub ? nextSub.start_time : 999);
            const gap = nextSub ? nextStart - dispEnd : 999;
            const effEnd = nextSub && gap > 0 && gap <= 0.60
              ? Math.max(dispEnd, nextStart - 0.07)
              : dispEnd + 0.25;

            const isActive = currentTime >= effStart && currentTime < effEnd;
            const words: HighlightWord[] = sub.highlight_words
              ? sub.highlight_words
              : (sub.matched_keywords || []).map(w => ({ word: w, source: 'glossary' as const }));

            const existingBroll = brolls?.find(b =>
              (sub.broll_material_id && (b.id === sub.broll_material_id || b.material_id === sub.broll_material_id)) ||
              Math.abs(b.start_time - dispStart) < 0.15
            );

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
                  <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                    {/* 播放当前句 */}
                    <button
                      type="button"
                      onClick={() => onSelectTime(dispStart)}
                      className="p-1 rounded-md text-blue-600 hover:bg-blue-100 transition-colors cursor-pointer"
                      title="播放此句"
                    >
                      <PlayCircle className="w-4 h-4 shrink-0" />
                    </button>

                    {/* 精简原地直接编辑的时间胶囊 */}
                    {editingTimeId === sub.id ? (
                      <div className="inline-flex items-center space-x-1 bg-white px-1.5 py-0.5 rounded-lg border border-blue-400 shadow-2xs">
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          value={timeStartStr}
                          onChange={e => { setTimeStartStr(e.target.value); setTimeError(null); }}
                          className="w-14 text-center font-mono text-xs bg-gray-50 border border-gray-200 rounded px-1 py-0.5 outline-none focus:bg-white focus:border-blue-500"
                          placeholder="起"
                        />
                        <span className="text-gray-400 font-mono">-</span>
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          value={timeEndStr}
                          onChange={e => { setTimeEndStr(e.target.value); setTimeError(null); }}
                          className="w-14 text-center font-mono text-xs bg-gray-50 border border-gray-200 rounded px-1 py-0.5 outline-none focus:bg-white focus:border-blue-500"
                          placeholder="止"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const s = parseFloat(timeStartStr);
                            const e = parseFloat(timeEndStr);
                            if (isNaN(s) || isNaN(e) || e <= s + 0.05) {
                              setTimeError('止时间需大于起时间 0.05s');
                              return;
                            }
                            onTimeRangeChange?.(origIdx, Number(s.toFixed(2)), Number(e.toFixed(2)));
                            setEditingTimeId(null);
                          }}
                          className="p-0.5 text-blue-600 hover:text-blue-800 font-bold cursor-pointer"
                          title="保存"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingTimeId(null)}
                          className="p-0.5 text-gray-400 hover:text-gray-600 cursor-pointer"
                          title="取消"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setEditingTimeId(sub.id);
                          setTimeStartStr(dispStart.toFixed(2));
                          setTimeEndStr(dispEnd.toFixed(2));
                          setTimeError(null);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded-lg bg-gray-100 hover:bg-blue-50 text-gray-800 hover:text-blue-700 border border-gray-200/80 hover:border-blue-200 text-xs font-mono font-bold transition-all shadow-2xs cursor-pointer"
                        title="点击直接修改时间"
                      >
                        <span>{formatExactTime(dispStart)} - {formatExactTime(dispEnd)}</span>
                        <span className="text-[10px] text-gray-400 font-normal">({(dispEnd - dispStart).toFixed(2)}s)</span>
                      </button>
                    )}

                    {/* 极短碎片轻量一键修复徽标 */}
                    {(dispEnd - dispStart) < 0.35 && (
                      <button
                        type="button"
                        onClick={() => {
                          const safeEnd = nextSub ? Math.min(dispStart + 1.20, Math.max(dispStart + 0.5, nextStart - 0.05)) : dispStart + 1.20;
                          onTimeRangeChange?.(origIdx, dispStart, Number(safeEnd.toFixed(2)));
                        }}
                        className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-800 hover:bg-amber-200 border border-amber-300 cursor-pointer shadow-2xs"
                        title="该句时长过短可能无声，点击一键延展至安全时长 (1.2s)"
                      >
                        <AlertTriangle className="w-2.5 h-2.5 text-amber-600" />
                        <span>极短，点此延伸</span>
                      </button>
                    )}

                    {timeError && editingTimeId === sub.id && (
                      <span className="text-[10px] text-red-500 font-medium">{timeError}</span>
                    )}
                  </div>

                  {/* 精简后的右侧操作栏 */}
                  <div className="flex items-center space-x-1">
                    {onMergeNextSubtitle && activeIdx < activeSubs.length - 1 && (
                      <button
                        type="button"
                        onClick={() => onMergeNextSubtitle(origIdx, sub)}
                        className="px-1.5 py-0.5 rounded text-[10px] font-medium text-emerald-700 hover:bg-emerald-50 border border-emerald-200 transition-colors cursor-pointer"
                        title="将此句与下一句合并为单句"
                      >
                        合并
                      </button>
                    )}
                    {onSplitSubtitle && (
                      <button
                        type="button"
                        onClick={() => handleStartSplit(sub, dispStart, dispEnd)}
                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium border transition-colors cursor-pointer ${
                          splittingSubId === sub.id
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'text-indigo-600 hover:bg-indigo-50 border-indigo-200'
                        }`}
                        title="拆分字幕"
                      >
                        拆分
                      </button>
                    )}
                    {onBrollChange && (
                      <button
                        type="button"
                        onClick={() => setPickingBrollState({ sub, dispStart, dispEnd })}
                        className={`px-1.5 py-0.5 rounded text-[10px] border transition-colors cursor-pointer ${
                          existingBroll
                            ? 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 font-medium'
                            : 'text-gray-400 hover:text-purple-600 border-transparent hover:border-purple-200'
                        }`}
                        title="可视化配置分镜空镜素材与截取区间"
                      >
                        {existingBroll ? `分镜 ${(existingBroll.end_time - existingBroll.start_time).toFixed(1)}s` : '分镜'}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onTogglePrune && onTogglePrune(origIdx, sub)}
                      className="px-1.5 py-0.5 rounded text-[10px] text-gray-400 hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 transition-colors cursor-pointer"
                      title="剔除此句（原视频物理剪裁）"
                    >
                      剔除
                    </button>
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

                {/* 字幕拆分配置面板 */}
                {splittingSubId === sub.id && (
                  <div className="mt-2 p-3 rounded-lg bg-indigo-50/90 border border-indigo-200 text-xs space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-indigo-900 text-[11px] flex items-center space-x-1.5">
                        <Scissors className="w-3.5 h-3.5 text-indigo-600" />
                        <span>智能拆分为 2 段字幕</span>
                      </span>
                      {sub.words && sub.words.length > 0 ? (
                        <span className="text-[10px] text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded-full font-medium flex items-center space-x-1">
                          <Sparkles className="w-2.5 h-2.5 text-emerald-600" />
                          <span>已开启 ASR 声学字级毫秒对齐</span>
                        </span>
                      ) : (
                        <span className="text-[10px] text-gray-500 bg-white/70 px-2 py-0.5 rounded-full font-medium">
                          按字比/标点智能估算
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => setSplittingSubId(null)}
                        className="text-gray-400 hover:text-gray-600 p-0.5 rounded cursor-pointer"
                        title="关闭"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* 交互式单字流点击切分：点击任一字直接断句 */}
                    <div className="p-2 bg-white rounded-lg border border-indigo-100 space-y-1">
                      <div className="text-[10px] text-indigo-800 font-medium flex items-center justify-between">
                        <span>👉 点击下方文字，直接在此字后精准切断（自动吸附发音毫秒）：</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {Array.from((sub.corrected_text || sub.raw_text || '').trim()).map((ch, chIdx, arr) => {
                          const isCut = chIdx + 1 === splitPart1.length;
                          return (
                            <React.Fragment key={chIdx}>
                              <button
                                type="button"
                                onClick={() => {
                                  const p1 = arr.slice(0, chIdx + 1).join('').trim();
                                  const p2 = arr.slice(chIdx + 1).join('').trim();
                                  setSplitPart1(p1);
                                  setSplitPart2(p2);
                                  const sTime = computeSplitTime(sub, p1, dispStart, dispEnd);
                                  setSplitTimeStr(sTime.toFixed(2));
                                  setSplitError(null);
                                }}
                                className={`px-1.5 py-0.5 rounded text-xs font-medium transition-all cursor-pointer ${
                                  chIdx < splitPart1.length
                                    ? 'bg-indigo-100/80 text-indigo-900 border border-indigo-300'
                                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200'
                                }`}
                                title={`在此字「${ch}」后切分`}
                              >
                                {ch}
                              </button>
                              {isCut && chIdx < arr.length - 1 && (
                                <span className="w-1 h-5 bg-indigo-600 rounded-full mx-0.5 animate-pulse" title="当前切分点" />
                              )}
                            </React.Fragment>
                          );
                        })}
                      </div>
                    </div>

                    {/* 文本切分预览与微调 */}
                    <div className="space-y-1.5">
                      <div className="flex items-center space-x-2">
                        <span className="w-12 text-[11px] font-medium text-indigo-700 flex-shrink-0">前半句:</span>
                        <input
                          type="text"
                          value={splitPart1}
                          onChange={e => {
                            setSplitPart1(e.target.value);
                            setSplitError(null);
                            const sTime = computeSplitTime(sub, e.target.value, dispStart, dispEnd);
                            setSplitTimeStr(sTime.toFixed(2));
                          }}
                          className="flex-1 px-2 py-1 text-xs bg-white border border-indigo-200 rounded outline-none focus:border-indigo-500 font-sans"
                          placeholder="前半句文本"
                        />
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="w-12 text-[11px] font-medium text-indigo-700 flex-shrink-0">后半句:</span>
                        <input
                          type="text"
                          value={splitPart2}
                          onChange={e => {
                            setSplitPart2(e.target.value);
                            setSplitError(null);
                          }}
                          className="flex-1 px-2 py-1 text-xs bg-white border border-indigo-200 rounded outline-none focus:border-indigo-500 font-sans"
                          placeholder="后半句文本"
                        />
                      </div>
                    </div>

                    {/* 时间切分点与预览 */}
                    <div className="flex items-center justify-between pt-1 border-t border-indigo-100 flex-wrap gap-2 text-[11px]">
                      <div className="flex items-center space-x-1.5">
                        <span className="text-gray-600">切分秒数:</span>
                        <input
                          type="number"
                          step="0.05"
                          min={(dispStart + 0.05).toFixed(2)}
                          max={(dispEnd - 0.05).toFixed(2)}
                          value={splitTimeStr}
                          onChange={e => {
                            setSplitTimeStr(e.target.value);
                            setSplitError(null);
                          }}
                          className="w-16 px-1.5 py-0.5 text-xs font-mono bg-white border border-indigo-200 rounded outline-none focus:border-indigo-500"
                        />
                        <span className="text-gray-400 font-mono">s</span>

                        {currentTime > dispStart + 0.05 && currentTime < dispEnd - 0.05 && (
                          <button
                            type="button"
                            onClick={() => setSplitTimeStr(currentTime.toFixed(2))}
                            className="px-1.5 py-0.5 text-[10px] bg-white text-indigo-600 border border-indigo-200 rounded hover:bg-indigo-50 transition-colors cursor-pointer"
                            title={`使用当前播放器时间 (${currentTime.toFixed(2)}s)`}
                          >
                            用播放时间 {currentTime.toFixed(2)}s
                          </button>
                        )}
                      </div>

                      <div className="flex items-center space-x-2">
                        <span className="text-gray-500 font-mono text-[10px]">
                          前: {(parseFloat(splitTimeStr) - dispStart > 0 ? (parseFloat(splitTimeStr) - dispStart) : 0).toFixed(2)}s · 后: {(dispEnd - parseFloat(splitTimeStr) > 0 ? (dispEnd - parseFloat(splitTimeStr)) : 0).toFixed(2)}s
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            const sTime = parseFloat(splitTimeStr);
                            if (!splitPart1.trim() || !splitPart2.trim()) {
                              setSplitError('前半句与后半句文本均不能为空');
                              return;
                            }
                            if (isNaN(sTime) || sTime <= dispStart + 0.04 || sTime >= dispEnd - 0.04) {
                              setSplitError(`切分时间必须在 ${dispStart.toFixed(2)}s 至 ${dispEnd.toFixed(2)}s 之间`);
                              return;
                            }
                            onSplitSubtitle?.(origIdx, sub, {
                              part1Text: splitPart1.trim(),
                              part2Text: splitPart2.trim(),
                              splitTime: Number(sTime.toFixed(2))
                            });
                            setSplittingSubId(null);
                          }}
                          className="px-2.5 py-1 rounded bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition-colors cursor-pointer text-[11px] shadow-2xs"
                        >
                          确认拆分
                        </button>
                      </div>
                    </div>

                    {splitError && (
                      <div className="text-[10px] text-red-500 font-medium">{splitError}</div>
                    )}
                  </div>
                )}

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

      {/* 分镜素材挑选与截取弹窗 */}
      <BrollPickerModal
        isOpen={!!pickingBrollState}
        onClose={() => setPickingBrollState(null)}
        sub={pickingBrollState?.sub || null}
        dispStart={pickingBrollState?.dispStart || 0}
        dispEnd={pickingBrollState?.dispEnd || 0}
        existingBroll={
          pickingBrollState
            ? brolls?.find(b =>
                (pickingBrollState.sub.broll_material_id && (b.id === pickingBrollState.sub.broll_material_id || b.material_id === pickingBrollState.sub.broll_material_id)) ||
                Math.abs(b.start_time - pickingBrollState.dispStart) < 0.15
              ) || null
            : null
        }
        materialsMap={materialsMap}
        brolls={brolls}
        totalDuration={totalDuration}
        onSave={(broll, subId) => onBrollChange?.(broll, subId)}
      />
    </div>
  );
};
