import React, { useRef, useState } from 'react';
import { Play, Pause, Volume2, VolumeX, Sparkles } from 'lucide-react';
import { EditingStrategy } from '../services/api';

interface VideoPlayerProps {
  videoUrl?: string;
  subtitles?: Array<{
    start_time: number;
    end_time: number;
    corrected_text: string;
    matched_keywords?: string[];
  }>;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  aspectRatio?: string;
  strategy?: EditingStrategy;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  subtitles = [],
  currentTime,
  onTimeUpdate,
  aspectRatio = '9:16',
  strategy
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(0);

  const activeSubtitle = subtitles.find(
    s => currentTime >= s.start_time && currentTime <= s.end_time
  );

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const target = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = target;
      onTimeUpdate(target);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = Math.floor(secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // 根据当前字幕与策略切分普通文本与高亮文本
  const renderSubtitleText = () => {
    if (!activeSubtitle) return null;
    const text = activeSubtitle.corrected_text;
    const strat = strategy || {
      subtitle_theme: 'viral_gold',
      enable_highlight: true,
      highlight_color: '#FACC15',
      highlight_scale: true,
      custom_highlight_words: []
    };

    if (!strat.enable_highlight) {
      return <span>{text}</span>;
    }

    const keywords = [
      ...(activeSubtitle.matched_keywords || []),
      ...(strat.custom_highlight_words || [])
    ].filter(Boolean);

    if (keywords.length === 0) {
      return <span>{text}</span>;
    }

    // 依词长降序正则切分
    keywords.sort((a, b) => b.length - a.length);
    const escaped = keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = new RegExp(`(${escaped})`, 'g');
    const parts = text.split(regex);

    return (
      <span>
        {parts.map((part, i) => {
          const isKeyword = keywords.includes(part);
          if (isKeyword) {
            return (
              <span
                key={i}
                style={{ color: strat.highlight_color }}
                className={`font-black drop-shadow-md mx-0.5 inline-block transition-all ${
                  strat.highlight_scale ? 'scale-110 tracking-wide' : ''
                }`}
              >
                {part}
              </span>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </span>
    );
  };

  // 获取字幕主题样式类名
  const getThemeClass = () => {
    const theme = strategy?.subtitle_theme || 'viral_gold';
    switch (theme) {
      case 'tech_emerald':
        return 'bg-slate-950/80 backdrop-blur-md text-white border border-emerald-500/40 shadow-emerald-950/50';
      case 'marker_pen':
        return 'bg-amber-300 text-gray-950 font-black border-2 border-white shadow-xl';
      case 'minimal_white':
        return 'bg-transparent text-white font-extrabold drop-shadow-[0_4px_6px_rgba(0,0,0,0.9)] border-none';
      case 'viral_gold':
      default:
        return 'bg-black/85 backdrop-blur-md text-white font-bold border border-yellow-500/30 shadow-2xl';
    }
  };

  return (
    <div className="flex flex-col items-center bg-gray-100/70 p-6 rounded-2xl border border-gray-200/80 shadow-sm">
      {/* 9:16 竖屏播放视窗 */}
      <div className="relative w-72 aspect-[9/16] bg-gray-900 rounded-2xl overflow-hidden shadow-2xl flex items-center justify-center border-4 border-gray-800 select-none">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-cover"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            muted={isMuted}
          />
        ) : (
          <div className="text-gray-400 text-xs px-4 text-center">
            暂无渲染预览，请先分析或上传视频
          </div>
        )}

        {/* 1. 顶部挂顶 Title 横幅 */}
        {strategy?.enable_top_banner && strategy.banner_main_title && (
          <div className="absolute top-4 left-3 right-3 text-center pointer-events-none z-10">
            <div className="inline-block max-w-full bg-black/75 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-white/20 shadow-lg">
              <div className="text-xs font-black text-white tracking-wider flex items-center justify-center space-x-1">
                <span>🔥</span>
                <span className="truncate">{strategy.banner_main_title}</span>
              </div>
              {strategy.banner_sub_title && (
                <div className="text-[10px] font-semibold text-yellow-400 scale-90 truncate">
                  {strategy.banner_sub_title}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 2. 右上角品牌水印角标 */}
        {strategy?.enable_watermark && strategy.watermark_text && (
          <div
            className="absolute top-3 right-3 pointer-events-none z-10 text-[10px] font-medium text-white px-2 py-0.5 rounded backdrop-blur-xs tracking-tight select-none shadow-sm"
            style={{ opacity: strategy.watermark_opacity ?? 0.4 }}
          >
            {strategy.watermark_text}
          </div>
        )}

        {/* 3. 动态口播字幕层 (支持4套主题与关键词高亮) */}
        {activeSubtitle && (
          <div className="absolute bottom-12 left-2 right-2 text-center pointer-events-none z-20 transition-all duration-150">
            <div className={`inline-block px-3 py-1.5 rounded-xl text-xs max-w-[95%] leading-relaxed ${getThemeClass()}`}>
              {renderSubtitleText()}
            </div>
          </div>
        )}

        {/* 比例与预设状态标签 */}
        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-[9px] px-1.5 py-0.5 rounded font-mono">
          {aspectRatio}
        </div>
      </div>

      {/* 控制栏 */}
      <div className="w-full mt-4 flex items-center space-x-3 text-xs text-gray-600">
        <button
          onClick={togglePlay}
          className="p-2 rounded-full hover:bg-white text-gray-700 transition-colors shadow-sm"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>

        <span className="font-mono text-gray-500 min-w-[35px]">{formatTime(currentTime)}</span>
        <input
          type="range"
          min="0"
          max={duration || 100}
          step="0.1"
          value={currentTime}
          onChange={handleSeek}
          className="flex-1 h-1.5 bg-gray-300 rounded-lg appearance-none cursor-pointer accent-blue-600"
        />
        <span className="font-mono text-gray-500 min-w-[35px]">{formatTime(duration)}</span>

        <button
          onClick={() => setIsMuted(!isMuted)}
          className="p-1.5 rounded-lg hover:bg-white text-gray-600"
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};