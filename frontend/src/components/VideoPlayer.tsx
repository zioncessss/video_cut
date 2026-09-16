import React, { useRef, useState } from 'react';
import { Play, Pause, Volume2, VolumeX } from 'lucide-react';
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

  // 根据当前字幕与策略切分普通文本与高亮文本（精准单词高亮）
  const renderSubtitleText = () => {
    if (!activeSubtitle) return null;
    const text = activeSubtitle.corrected_text;
    const strat = strategy || {
      subtitle_theme: 'glow_gold',
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
                style={{
                  color: strat.highlight_color || '#FACC15',
                  textShadow: `0 0 10px ${strat.highlight_color || '#FACC15'}80, 0 2px 4px rgba(0,0,0,0.9)`
                }}
                className={`font-black mx-0.5 inline-block transition-all ${
                  strat.highlight_scale ? 'scale-110 tracking-wide font-extrabold' : ''
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

  // 获取字幕主题样式类名 (支持自然融入视频背景，无黑底)
  const getThemeClass = () => {
    const theme = strategy?.subtitle_theme || 'glow_gold';
    switch (theme) {
      // 1. 发光金黄 (完全融入画面，无黑底框，纯白文字 + 金光强调)
      case 'glow_gold':
        return 'bg-transparent text-white font-extrabold drop-shadow-[0_2px_5px_rgba(0,0,0,0.95)] [text-shadow:_0_2px_4px_rgb(0_0_0_/_90%)]';
      
      // 2. 超透毛玻璃白 (极微弱纯净透光，不遮挡画面)
      case 'glass_clean':
        return 'bg-black/20 backdrop-blur-[2px] text-white font-bold border border-white/15 shadow-sm [text-shadow:_0_1px_3px_rgb(0_0_0_/_80%)]';
      
      // 3. 电影级自然立体白 (多层柔和深色外阴影，完美融入任何明暗视频)
      case 'cinema_shadow':
        return 'bg-transparent text-white font-black tracking-wide drop-shadow-[0_4px_8px_rgba(0,0,0,1)] [text-shadow:_0_3px_6px_rgb(0_0_0_/_95%),_0_1px_2px_rgb(0_0_0_/_90%)]';
      
      // 4. 科技翡翠
      case 'tech_emerald':
        return 'bg-slate-950/60 backdrop-blur-sm text-white font-bold border border-emerald-500/30 shadow-md';

      // 5. 教学记号笔
      case 'marker_pen':
        return 'bg-amber-300 text-gray-950 font-black border border-amber-400 shadow-md';

      // 6. 爆款黑底胶囊金
      case 'viral_gold':
        return 'bg-black/80 backdrop-blur-md text-white font-bold border border-yellow-500/30 shadow-xl';

      default:
        return 'bg-transparent text-white font-extrabold drop-shadow-[0_2px_5px_rgba(0,0,0,0.95)]';
    }
  };

  const hasBanner = Boolean(strategy?.enable_top_banner && strategy?.banner_main_title);
  const hasWatermark = Boolean(strategy?.enable_watermark && strategy?.watermark_text);

  return (
    <div className="flex flex-col items-center justify-center h-full max-h-full">
      {/* 9:16 竖屏播放视窗：采用 max-h-[68vh] 自适应父容器高度，彻底避免垂直溢出 */}
      <div className="relative h-[66vh] aspect-[9/16] max-w-full bg-gray-950 rounded-2xl overflow-hidden shadow-2xl flex items-center justify-center border-2 border-gray-800 select-none">
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

        {/* 1. 顶部挂顶 Title 横幅 (居中顶部，严谨控制高度与内边距) */}
        {hasBanner && (
          <div className="absolute top-3 left-3 right-3 text-center pointer-events-none z-10">
            <div className="inline-block max-w-[92%] bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/20 shadow-xl">
              <div className="text-[11px] font-black text-white tracking-wider flex items-center justify-center space-x-1">
                <span>🔥</span>
                <span className="truncate">{strategy?.banner_main_title}</span>
              </div>
              {strategy?.banner_sub_title && (
                <div className="text-[9px] font-semibold text-yellow-400 truncate mt-0.5">
                  {strategy.banner_sub_title}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 2. 品牌防搬运水印角标 (错开顶部横幅位置，避免产生遮挡碰撞) */}
        {hasWatermark && (
          <div
            className={`absolute right-3 pointer-events-none z-10 text-[9px] font-medium text-white px-2 py-0.5 rounded backdrop-blur-xs tracking-tight select-none shadow-sm transition-all ${
              hasBanner ? 'top-16' : 'top-3'
            }`}
            style={{ opacity: strategy?.watermark_opacity ?? 0.4 }}
          >
            {strategy?.watermark_text}
          </div>
        )}

        {/* 3. 动态口播字幕层 (精准单词高亮，融入画面无黑底) */}
        {activeSubtitle && (
          <div className="absolute bottom-10 left-2 right-2 text-center pointer-events-none z-20 transition-all duration-150">
            <div className={`inline-block px-3 py-1 rounded-xl text-xs max-w-[95%] leading-relaxed ${getThemeClass()}`}>
              {renderSubtitleText()}
            </div>
          </div>
        )}

        {/* 比例标签 */}
        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-[8px] px-1.5 py-0.5 rounded font-mono">
          {aspectRatio}
        </div>
      </div>

      {/* 紧凑控制栏 */}
      <div className="w-full max-w-[280px] mt-3 flex items-center space-x-2 text-xs text-gray-600 px-2">
        <button
          onClick={togglePlay}
          className="p-1.5 rounded-full hover:bg-white text-gray-700 transition-colors shadow-xs"
        >
          {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
        </button>

        <span className="font-mono text-gray-500 text-[10px] min-w-[30px]">{formatTime(currentTime)}</span>
        <input
          type="range"
          min="0"
          max={duration || 100}
          step="0.1"
          value={currentTime}
          onChange={handleSeek}
          className="flex-1 h-1 bg-gray-300 rounded-lg appearance-none cursor-pointer accent-blue-600"
        />
        <span className="font-mono text-gray-500 text-[10px] min-w-[30px]">{formatTime(duration)}</span>

        <button
          onClick={() => setIsMuted(!isMuted)}
          className="p-1 rounded hover:bg-white text-gray-600"
        >
          {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  );
};