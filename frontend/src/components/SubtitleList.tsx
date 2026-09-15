import React from 'react';
import { Tag, PlayCircle, MapPin, Activity, Award } from 'lucide-react';

export interface SubtitleItem {
  id: string;
  start_time: number;
  end_time: number;
  raw_text: string;
  corrected_text: string;
  matched_category?: 'venue' | 'medical' | 'lesson' | null;
  matched_keywords?: string[];
  broll_material_id?: string | null;
}

interface SubtitleListProps {
  subtitles: SubtitleItem[];
  currentTime: number;
  onSelectTime: (time: number) => void;
  onTextChange: (index: number, newText: string) => void;
}

export const SubtitleList: React.FC<SubtitleListProps> = ({
  subtitles,
  currentTime,
  onSelectTime,
  onTextChange
}) => {
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
    if (cat === 'medical') {
      return (
        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
          <Activity className="w-3 h-3" />
          <span>体检空镜</span>
        </span>
      );
    }
    if (cat === 'lesson') {
      return (
        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
          <Award className="w-3 h-3" />
          <span>练车空镜</span>
        </span>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-gray-200/80 shadow-sm p-4 overflow-hidden">
      <div className="flex items-center justify-between pb-3 border-b border-gray-100 mb-3">
        <h2 className="text-sm font-bold text-gray-800">字幕时间轴与语义空镜分配</h2>
        <span className="text-xs text-gray-400 font-mono">共 {subtitles.length} 条</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {subtitles.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-xs">
            暂无字幕片段，请先点击【AI 智能识别与初剪】
          </div>
        ) : (
          subtitles.map((sub, idx) => {
            const isActive = currentTime >= sub.start_time && currentTime <= sub.end_time;
            return (
              <div
                key={sub.id || idx}
                className={`p-3 rounded-xl border transition-all duration-150 ${
                  isActive
                    ? 'border-blue-500 bg-blue-50/40 ring-1 ring-blue-500/20'
                    : 'border-gray-200 bg-gray-50/50 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <button
                    onClick={() => onSelectTime(sub.start_time)}
                    className="flex items-center space-x-1 text-xs font-mono font-semibold text-gray-700 hover:text-blue-600 transition-colors"
                  >
                    <PlayCircle className="w-3.5 h-3.5 text-blue-600" />
                    <span>{formatTime(sub.start_time)} - {formatTime(sub.end_time)}</span>
                  </button>
                  {getCategoryBadge(sub.matched_category)}
                </div>

                <textarea
                  value={sub.corrected_text}
                  onChange={e => onTextChange(idx, e.target.value)}
                  className="w-full text-xs text-gray-800 bg-white border border-gray-200 rounded-lg p-2 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none"
                  rows={2}
                />

                {sub.matched_keywords && sub.matched_keywords.length > 0 && (
                  <div className="flex items-center space-x-1.5 mt-1.5">
                    <Tag className="w-3 h-3 text-gray-400" />
                    <span className="text-[10px] text-gray-400">
                      命中词: {sub.matched_keywords.join(', ')}
                    </span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
