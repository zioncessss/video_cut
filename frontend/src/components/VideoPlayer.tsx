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
  onStrategyChange?: (newStrategy: EditingStrategy) => void;
  isRendered?: boolean;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  subtitles = [],
  currentTime,
  onTimeUpdate,
  aspectRatio = '9:16',
  strategy,
  onStrategyChange,
  isRendered = false
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStartY, setDragStartY] = useState<number>(0);
  const [dragStartPosY, setDragStartPosY] = useState<number>(82);

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

  // 字号大小类名映射
  const getFontSizeClass = () => {
    const size = strategy?.font_size || 'medium';
    switch (size) {
      case 'small':
        return 'text-[10px] leading-tight';
      case 'medium':
        return 'text-xs leading-relaxed';
      case 'large':
        return 'text-sm font-black leading-snug';
      case 'xlarge':
        return 'text-base font-black tracking-wide leading-normal';
      default:
        return 'text-xs leading-relaxed';
    }
  };

  // 拖拽移动字幕位置事件处理
  const handleSubtitleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    setDragStartY(e.clientY);
    setDragStartPosY(strategy?.subtitle_position_y ?? 82);
  };

  const handleContainerMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const deltaY = e.clientY - dragStartY;
    const deltaPercent = (deltaY / rect.height) * 100;
    const newY = Math.max(20, Math.min(92, Math.round(dragStartPosY + deltaPercent)));
    if (strategy && onStrategyChange && newY !== strategy.subtitle_position_y) {
      onStrategyChange({ ...strategy, subtitle_position_y: newY });
    }
  };

  const handleContainerMouseUp = () => {
    if (isDragging) {
      setIsDragging(false);
    }
  };

  const currentPosY = strategy?.subtitle_position_y ?? 82;
  const isSubtitleVisible = strategy?.show_subtitles !== false;

  return (
    <div className="flex flex-col items-center justify-center h-full max-h-full select-none">
      {/* 9:16 竖屏播放视窗：采用 max-h-[68vh] 自适应父容器高度，彻底避免垂直溢出 */}
      <div
        ref={containerRef}
        onMouseMove={handleContainerMouseMove}
        onMouseUp={handleContainerMouseUp}
        onMouseLeave={handleContainerMouseUp}
        className="relative h-[66vh] aspect-[9/16] max-w-full bg-gray-950 rounded-2xl overflow-hidden shadow-2xl flex items-center justify-center border-2 border-gray-800 select-none"
      >
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            crossOrigin="anonymous"
            playsInline
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

        {/* 当播放渲染导出的 MP4 成片时，由于滤镜与 ASS 已物理压制进视频流，跳过 DOM 虚拟层避免双重叠加 */}
        {!isRendered && (
          <>
            {/* 1. 顶部挂顶 Title 横幅 (当同时开启右上角水印时，横幅下移至 top-14，预留顶部净空，彻底避开右上角水印) */}
            {hasBanner && (
              <div className={`absolute left-3 right-3 text-center pointer-events-none z-10 transition-all ${
                hasWatermark ? 'top-14' : 'top-3'
              }`}>
                <div className="inline-block max-w-[92%] bg-black/85 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/20 shadow-xl">
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

            {/* 2. 品牌防搬运水印角标 (固定置于右上角顶角 top-2.5 right-2.5，纯正角标位) */}
            {hasWatermark && (
              <div
                className="absolute top-2.5 right-2.5 pointer-events-none z-20 text-[10px] font-medium text-white px-2 py-0.5 rounded backdrop-blur-xs tracking-tight select-none shadow-sm transition-all"
                style={{ opacity: strategy?.watermark_opacity ?? 0.4 }}
              >
                {strategy?.watermark_text}
              </div>
            )}

            {/* 3. 动态口播字幕层 (支持精准单词高亮、可自由按住鼠标上下拖拽移动、支持一键隐藏) */}
            {activeSubtitle && isSubtitleVisible && (
              <div
                style={{ top: `${currentPosY}%`, transform: 'translateY(-50%)' }}
                onMouseDown={handleSubtitleMouseDown}
                title="按住鼠标可上下自由拖动字幕位置"
                className={`absolute left-2 right-2 text-center z-20 transition-all cursor-move select-none ${
                  isDragging ? 'ring-2 ring-blue-400/80 rounded-2xl opacity-90' : 'hover:outline-dashed hover:outline-1 hover:outline-blue-400/50'
                }`}
              >
                <div className={`inline-block px-3 py-1.5 rounded-xl max-w-[95%] transition-all ${getThemeClass()} ${getFontSizeClass()}`}>
                  {renderSubtitleText()}
                </div>
              </div>
            )}
          </>
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