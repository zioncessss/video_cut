import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX } from 'lucide-react';
import { EditingStrategy, BrollReplacement, Material, getMediaUrl } from '../services/api';

interface VideoPlayerProps {
  videoUrl?: string;
  brolls?: BrollReplacement[];
  materialsMap?: Record<string, Material>;
  subtitles?: Array<{
    start_time: number;
    end_time: number;
    corrected_text: string;
    matched_keywords?: string[];
  }>;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  aspectRatio?: '9:16' | '16:9' | string;
  onAspectRatioChange?: (ratio: '9:16' | '16:9') => void;
  strategy?: EditingStrategy;
  onStrategyChange?: (newStrategy: EditingStrategy) => void;
  onStrategyCommit?: (strategy: EditingStrategy) => void;
  isRendered?: boolean;
}

type DragTarget = 'subtitle' | 'banner' | 'watermark' | null;
type DragMode = 'move' | 'resize-w' | 'resize-e' | 'resize-n' | 'resize-s' | 'resize-corner' | null;

interface ResizeHandlesProps {
  onStartResize: (e: React.MouseEvent, mode: DragMode) => void;
  color?: 'blue' | 'purple' | 'emerald';
  allowHorizontal?: boolean;
  allowVertical?: boolean;
}

const ResizeHandles: React.FC<ResizeHandlesProps> = ({
  onStartResize,
  color = 'blue',
  allowHorizontal = true,
  allowVertical = true,
}) => {
  const colorMap = {
    blue: {
      border: 'border-blue-400',
      bg: 'bg-blue-500',
      ring: 'ring-blue-400',
    },
    purple: {
      border: 'border-purple-400',
      bg: 'bg-purple-500',
      ring: 'ring-purple-400',
    },
    emerald: {
      border: 'border-emerald-400',
      bg: 'bg-emerald-500',
      ring: 'ring-emerald-400',
    },
  }[color];

  return (
    <div className={`absolute -inset-1 border border-dashed ${colorMap.border} rounded-xl pointer-events-none z-30 animate-in fade-in duration-100`}>
      {/* 左右宽度调节手柄 */}
      {allowHorizontal && (
        <>
          <div
            onMouseDown={(e) => onStartResize(e, 'resize-w')}
            className={`pointer-events-auto absolute -left-1.5 top-1/2 -translate-y-1/2 w-2.5 h-6 bg-white border-2 ${colorMap.border} rounded-full cursor-ew-resize hover:scale-125 transition-transform shadow-md flex items-center justify-center`}
            title="向左/向右拖拽调整框体宽度"
          >
            <div className={`w-0.5 h-2.5 ${colorMap.bg}/80 rounded-full`} />
          </div>
          <div
            onMouseDown={(e) => onStartResize(e, 'resize-e')}
            className={`pointer-events-auto absolute -right-1.5 top-1/2 -translate-y-1/2 w-2.5 h-6 bg-white border-2 ${colorMap.border} rounded-full cursor-ew-resize hover:scale-125 transition-transform shadow-md flex items-center justify-center`}
            title="向左/向右拖拽调整框体宽度"
          >
            <div className={`w-0.5 h-2.5 ${colorMap.bg}/80 rounded-full`} />
          </div>
        </>
      )}

      {/* 上下高度与字号调节手柄 */}
      {allowVertical && (
        <>
          <div
            onMouseDown={(e) => onStartResize(e, 'resize-n')}
            className={`pointer-events-auto absolute -top-1.5 left-1/2 -translate-x-1/2 w-6 h-2.5 bg-white border-2 ${colorMap.border} rounded-full cursor-ns-resize hover:scale-125 transition-transform shadow-md flex items-center justify-center`}
            title="向上/向下拖拽调整文字字号与高度"
          >
            <div className={`h-0.5 w-2.5 ${colorMap.bg}/80 rounded-full`} />
          </div>
          <div
            onMouseDown={(e) => onStartResize(e, 'resize-s')}
            className={`pointer-events-auto absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-6 h-2.5 bg-white border-2 ${colorMap.border} rounded-full cursor-ns-resize hover:scale-125 transition-transform shadow-md flex items-center justify-center`}
            title="向上/向下拖拽调整文字字号与高度"
          >
            <div className={`h-0.5 w-2.5 ${colorMap.bg}/80 rounded-full`} />
          </div>
        </>
      )}

      {/* 对角综合缩放手柄 */}
      <div
        onMouseDown={(e) => onStartResize(e, 'resize-corner')}
        className={`pointer-events-auto absolute -right-1.5 -bottom-1.5 w-3.5 h-3.5 bg-white border-2 ${colorMap.border} rounded-full cursor-nwse-resize hover:scale-125 transition-transform shadow-md`}
        title="按住对角拖拽同时调整宽度与字号"
      />
    </div>
  );
};

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  brolls = [],
  materialsMap = {},
  subtitles = [],
  currentTime,
  onTimeUpdate,
  aspectRatio = '9:16',
  onAspectRatioChange,
  strategy,
  onStrategyChange,
  onStrategyCommit,
  isRendered = false
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const brollVideoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(0);

  // 实时分镜探测：判断当前播放时间点是否落在某段 B-roll 空镜窗口内
  const activeBroll = (!isRendered && brolls && brolls.length > 0)
    ? brolls.find(b => currentTime >= b.start_time && currentTime < b.end_time)
    : null;
  const activeBrollMaterial = (activeBroll && materialsMap) ? materialsMap[activeBroll.material_id] : null;
  const activeBrollUrl = activeBrollMaterial ? getMediaUrl(activeBrollMaterial.filepath) : null;

  // 保持空镜视频与口播原声/主时间戳毫秒级同步
  useEffect(() => {
    if (!brollVideoRef.current || !activeBroll) return;
    const brollEl = brollVideoRef.current;
    const offset = Math.max(0, currentTime - activeBroll.start_time);
    const bDur = brollEl.duration || activeBrollMaterial?.duration || 10;
    const target = bDur > 0 ? (offset % bDur) : offset;

    if (Math.abs(brollEl.currentTime - target) > 0.35) {
      brollEl.currentTime = target;
    }
    if (isPlaying) {
      brollEl.play().catch(() => {});
    } else {
      brollEl.pause();
    }
  }, [activeBroll, currentTime, isPlaying, activeBrollMaterial]);
  
  const [dragTarget, setDragTarget] = useState<DragTarget>(null);
  const [dragMode, setDragMode] = useState<DragMode>(null);
  const [dragStartX, setDragStartX] = useState<number>(0);
  const [dragStartY, setDragStartY] = useState<number>(0);
  const [dragStartPosX, setDragStartPosX] = useState<number>(50);
  const [dragStartPosY, setDragStartPosY] = useState<number>(82);
  const [dragStartWidthPercent, setDragStartWidthPercent] = useState<number>(90);
  const [dragStartFontSize, setDragStartFontSize] = useState<number>(72);
  const [hoveredOverlay, setHoveredOverlay] = useState<DragTarget>(null);

  // 动态视窗像素宽度监听 (用于响应式等比映射 1080P 画布尺寸，杜绝预览折行与成片单行撕裂)
  const [containerWidth, setContainerWidth] = useState<number>(360);
  useEffect(() => {
    if (!containerRef.current) return;
    const updateSize = () => {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth;
        if (w > 50) setContainerWidth(w);
      }
    };
    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // 进度条平滑拖拽 Seeking 独立状态，防范播放时 timeupdate 引起滑块回弹抖动
  const [isSeeking, setIsSeeking] = useState<boolean>(false);
  const [seekTime, setSeekTime] = useState<number>(0);
  const [videoAspect, setVideoAspect] = useState<string>('9/16');

  const is169 = aspectRatio === '16:9';

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
    if (videoRef.current && !isSeeking) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  useEffect(() => {
    if (!isSeeking && videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.35) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime, isSeeking]);

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const d = videoRef.current.duration;
      setDuration(isNaN(d) ? 0 : d);
      if (videoRef.current.videoWidth && videoRef.current.videoHeight) {
        const vw = videoRef.current.videoWidth;
        const vh = videoRef.current.videoHeight;
        setVideoAspect(`${vw} / ${vh}`);
        const isLandscape = vw > vh;
        if (isLandscape && aspectRatio !== '16:9' && onAspectRatioChange) {
          onAspectRatioChange('16:9');
        } else if (!isLandscape && aspectRatio !== '9:16' && onAspectRatioChange) {
          onAspectRatioChange('9:16');
        }
      }
    }
  };

  // 进度条拖拽开始
  const handleSeekPointerDown = (e: React.SyntheticEvent<HTMLInputElement>) => {
    setIsSeeking(true);
    const target = parseFloat((e.target as HTMLInputElement).value);
    setSeekTime(target);
  };

  // 进度条拖拽中：即时洗刷视频画面
  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const target = parseFloat(e.target.value);
    setSeekTime(target);
    if (videoRef.current) {
      videoRef.current.currentTime = target;
    }
  };

  // 进度条拖拽释放提交
  const handleSeekPointerUp = () => {
    if (videoRef.current) {
      videoRef.current.currentTime = seekTime;
    }
    onTimeUpdate(seekTime);
    setIsSeeking(false);
  };

  // 全局指针释放监听：确保鼠标拖出进度条外松开时正常提交时间戳
  useEffect(() => {
    if (!isSeeking) return;
    const handleGlobalPointerUp = () => {
      if (videoRef.current) {
        videoRef.current.currentTime = seekTime;
      }
      onTimeUpdate(seekTime);
      setIsSeeking(false);
    };
    window.addEventListener('pointerup', handleGlobalPointerUp);
    window.addEventListener('mouseup', handleGlobalPointerUp);
    return () => {
      window.removeEventListener('pointerup', handleGlobalPointerUp);
      window.removeEventListener('mouseup', handleGlobalPointerUp);
    };
  }, [isSeeking, seekTime]);

  // 快进 / 快退步进
  const stepTime = (deltaSeconds: number) => {
    if (!videoRef.current) return;
    const nextTime = Math.max(0, Math.min(duration || 100, (videoRef.current.currentTime || 0) + deltaSeconds));
    videoRef.current.currentTime = nextTime;
    onTimeUpdate(nextTime);
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) secs = 0;
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

  // 保持 strategy 与 onStrategyChange 的实时引用，避免 window 拖拽监听闭包陈旧
  const strategyRef = useRef(strategy);
  strategyRef.current = strategy;
  const onStrategyChangeRef = useRef(onStrategyChange);
  onStrategyChangeRef.current = onStrategyChange;

  // 拖拽与缩放手柄启动
  const handleStartMove = (
    e: React.MouseEvent,
    target: DragTarget,
    currentPosX: number,
    currentPosY: number
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setDragTarget(target);
    setDragMode('move');
    setDragStartX(e.clientX);
    setDragStartY(e.clientY);
    setDragStartPosX(currentPosX);
    setDragStartPosY(currentPosY);
  };

  const handleStartResize = (
    e: React.MouseEvent,
    target: DragTarget,
    mode: DragMode,
    currentWidthPercent: number,
    currentFontSize: number
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setDragTarget(target);
    setDragMode(mode);
    setDragStartX(e.clientX);
    setDragStartY(e.clientY);
    setDragStartWidthPercent(currentWidthPercent);
    setDragStartFontSize(currentFontSize);
  };

  // 全局 Window 拖拽监听：鼠标移出视频框仍能顺畅吸附拖动与伸缩拉伸，杜绝边界丢失
  useEffect(() => {
    if (!dragTarget || !dragMode) return;

    const handleWindowMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const deltaX = e.clientX - dragStartX;
      const deltaY = e.clientY - dragStartY;
      const deltaPercentX = (deltaX / rect.width) * 100;
      const deltaPercentY = (deltaY / rect.height) * 100;

      const currentStrat = strategyRef.current;
      const changeFn = onStrategyChangeRef.current;
      if (!currentStrat || !changeFn) return;

      if (dragMode === 'move') {
        if (dragTarget === 'subtitle') {
          const newX = Math.max(5, Math.min(95, Math.round(dragStartPosX + deltaPercentX)));
          const newY = Math.max(5, Math.min(95, Math.round(dragStartPosY + deltaPercentY)));
          if (newX !== currentStrat.subtitle_position_x || newY !== currentStrat.subtitle_position_y) {
            changeFn({ ...currentStrat, subtitle_position_x: newX, subtitle_position_y: newY });
          }
        } else if (dragTarget === 'banner') {
          const newX = Math.max(5, Math.min(95, Math.round(dragStartPosX + deltaPercentX)));
          const newY = Math.max(2, Math.min(92, Math.round(dragStartPosY + deltaPercentY)));
          if (newX !== currentStrat.banner_position_x || newY !== currentStrat.banner_position_y) {
            changeFn({ ...currentStrat, banner_position_x: newX, banner_position_y: newY });
          }
        } else if (dragTarget === 'watermark') {
          const newX = Math.max(2, Math.min(98, Math.round(dragStartPosX + deltaPercentX)));
          const newY = Math.max(2, Math.min(98, Math.round(dragStartPosY + deltaPercentY)));
          if (newX !== currentStrat.watermark_position_x || newY !== currentStrat.watermark_position_y) {
            changeFn({ ...currentStrat, watermark_position_x: newX, watermark_position_y: newY });
          }
        }
      } else if (dragMode === 'resize-e' || dragMode === 'resize-w') {
        const factor = dragMode === 'resize-e' ? 1 : -1;
        const deltaW = factor * (deltaX / rect.width) * 200;
        const newWidth = Math.max(20, Math.min(96, Math.round(dragStartWidthPercent + deltaW)));
        if (dragTarget === 'banner') {
          if (newWidth !== currentStrat.banner_width_percent) {
            changeFn({ ...currentStrat, banner_width_percent: newWidth });
          }
        } else if (dragTarget === 'subtitle') {
          if (newWidth !== currentStrat.subtitle_width_percent) {
            changeFn({ ...currentStrat, subtitle_width_percent: newWidth });
          }
        }
      } else if (dragMode === 'resize-s' || dragMode === 'resize-n') {
        const factor = dragMode === 'resize-s' ? 1 : -1;
        const deltaFont = factor * Math.round(deltaY * 0.5);
        if (dragTarget === 'banner') {
          const newFont = Math.max(20, Math.min(96, Math.round(dragStartFontSize + deltaFont)));
          if (newFont !== currentStrat.banner_font_size) {
            changeFn({ ...currentStrat, banner_font_size: newFont });
          }
        } else if (dragTarget === 'subtitle') {
          const newFont = Math.max(36, Math.min(120, Math.round(dragStartFontSize + deltaFont)));
          if (newFont !== currentStrat.subtitle_font_size) {
            changeFn({ ...currentStrat, subtitle_font_size: newFont });
          }
        } else if (dragTarget === 'watermark') {
          const newFont = Math.max(16, Math.min(64, Math.round(dragStartFontSize + deltaFont)));
          if (newFont !== currentStrat.watermark_font_size) {
            changeFn({ ...currentStrat, watermark_font_size: newFont });
          }
        }
      } else if (dragMode === 'resize-corner') {
        const deltaW = (deltaX / rect.width) * 200;
        const deltaFont = Math.round(deltaY * 0.5);
        if (dragTarget === 'banner') {
          const newWidth = Math.max(20, Math.min(96, Math.round(dragStartWidthPercent + deltaW)));
          const newFont = Math.max(20, Math.min(96, Math.round(dragStartFontSize + deltaFont)));
          changeFn({ ...currentStrat, banner_width_percent: newWidth, banner_font_size: newFont });
        } else if (dragTarget === 'subtitle') {
          const newWidth = Math.max(30, Math.min(96, Math.round(dragStartWidthPercent + deltaW)));
          const newFont = Math.max(36, Math.min(120, Math.round(dragStartFontSize + deltaFont)));
          changeFn({ ...currentStrat, subtitle_width_percent: newWidth, subtitle_font_size: newFont });
        } else if (dragTarget === 'watermark') {
          const newFont = Math.max(16, Math.min(64, Math.round(dragStartFontSize + deltaFont)));
          changeFn({ ...currentStrat, watermark_font_size: newFont });
        }
      }
    };

    const handleWindowMouseUp = () => {
      if (dragTarget) {
        if (onStrategyCommit && strategyRef.current) {
          onStrategyCommit(strategyRef.current);
        }
        setDragTarget(null);
        setDragMode(null);
      }
    };

    window.addEventListener('mousemove', handleWindowMouseMove);
    window.addEventListener('mouseup', handleWindowMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleWindowMouseMove);
      window.removeEventListener('mouseup', handleWindowMouseUp);
    };
  }, [dragTarget, dragMode, dragStartX, dragStartY, dragStartPosX, dragStartPosY, dragStartWidthPercent, dragStartFontSize, onStrategyCommit]);

  // 1080P 画布视觉等比映射因子 (彻底消除预览窗口折行与压制 ASS 单行视觉撕裂)
  const scaleFactor = containerWidth > 0 ? containerWidth / 1080 : 0.26;

  // 1. 横幅：字号与尺寸动态计算
  const bannerFontSizeBase = strategy?.banner_font_size || (
    strategy?.banner_size === 'small' ? 36 : strategy?.banner_size === 'large' ? 60 : 48
  );
  const bannerTitlePx = Math.max(10, Math.round(bannerFontSizeBase * scaleFactor));
  const bannerSubPx = Math.max(8, Math.round(bannerTitlePx * 0.65));
  const bannerPaddingY = Math.max(3, Math.round(bannerTitlePx * 0.42));
  const bannerPaddingX = Math.max(8, Math.round(bannerTitlePx * 1.0));
  const bannerPosX = strategy?.banner_position_x ?? 50;
  const bannerPosY = strategy?.banner_position_y ?? (
    hasWatermark && (strategy?.watermark_position ?? 'top_right') === 'top_right' ? 10 : 6
  );

  // 2. 水印：字号与 2D 坐标计算 (默认右上 96%, 3%，与后端 ffmpeg 严丝合缝)
  const wmPos = strategy?.watermark_position || 'top_right';
  const defaultWmPosX = wmPos.endsWith('left') ? 4 : 96;
  const defaultWmPosY = wmPos.startsWith('bottom') ? 96 : 3;
  const wmPosX = strategy?.watermark_position_x ?? defaultWmPosX;
  const wmPosY = strategy?.watermark_position_y ?? defaultWmPosY;
  const wmFontSizeBase = strategy?.watermark_font_size || (
    strategy?.watermark_size === 'small' ? 22 : strategy?.watermark_size === 'large' ? 44 : 32
  );
  const wmPx = Math.max(8, Math.round(wmFontSizeBase * scaleFactor));

  // 3. 字幕：2D 坐标与连续字号计算
  const currentPosX = strategy?.subtitle_position_x ?? 50;
  const currentPosY = strategy?.subtitle_position_y ?? 82;
  const isSubtitleVisible = strategy?.show_subtitles !== false;
  const subtitleFontSizeBase = strategy?.subtitle_font_size || (
    strategy?.font_size === 'small' ? 56 : strategy?.font_size === 'large' ? 86 : strategy?.font_size === 'xlarge' ? 98 : 72
  );
  const subtitlePx = Math.max(11, Math.round(subtitleFontSizeBase * scaleFactor));

  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-0 select-none overflow-hidden p-1">
      {/* 视窗容器：100% 紧贴原视频原生比例，杜绝强行上下填充多余黑边，确保字幕和角标直接贴合在视频画面上 */}
      <div
        ref={containerRef}
        style={{
          aspectRatio: is169 ? '16 / 9' : (videoAspect || '9 / 16'),
        }}
        className={`relative flex items-center justify-center bg-black rounded-2xl overflow-hidden shadow-2xl border border-gray-800/80 select-none transition-all duration-150 ${
          is169
            ? 'w-full max-w-[540px] max-h-[calc(100%-46px)]'
            : 'h-full max-h-[calc(100%-46px)] max-w-full'
        }`}
      >
        {videoUrl ? (
          <div className="relative w-full h-full flex items-center justify-center">
            <video
              ref={videoRef}
              key={videoUrl}
              src={videoUrl}
              preload="auto"
              playsInline
              onClick={togglePlay}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              className="w-full h-full object-contain cursor-pointer bg-black"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              muted={isMuted}
            />

            {/* 实时分镜空镜平替层：当非压制成片播放模式时，按分镜时间窗覆盖呈现空镜素材，音频持续保持口播主音轨 */}
            {activeBrollUrl && (
              <video
                ref={brollVideoRef}
                key={activeBrollUrl}
                src={activeBrollUrl}
                preload="auto"
                playsInline
                muted
                onClick={togglePlay}
                className="absolute inset-0 w-full h-full object-contain cursor-pointer bg-black z-10 animate-in fade-in duration-150"
              />
            )}
          </div>
        ) : (
          <div className="text-gray-400 text-xs px-4 text-center">
            暂无渲染预览，请先分析或上传视频
          </div>
        )}

        {/* 实时分镜切入状态徽标 */}
        {activeBroll && !isRendered && (
          <div className="absolute top-3 left-3 z-30 flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold shadow-lg backdrop-blur-md bg-black/85 text-white border border-white/20 animate-in fade-in duration-150 select-none pointer-events-none">
            <span className={`w-2 h-2 rounded-full animate-pulse ${
              activeBroll.material_category === 'venue' ? 'bg-blue-400' :
              activeBroll.material_category === 'lesson' ? 'bg-emerald-400' : 'bg-purple-400'
            }`} />
            <span>
              {activeBroll.material_category === 'venue' ? '场地实景空镜' :
               activeBroll.material_category === 'lesson' ? '教学练车空镜' : '学员体验空镜'}
            </span>
            <span className="text-gray-300 font-mono text-[11px]">
              {activeBroll.start_time.toFixed(1)}s - {activeBroll.end_time.toFixed(1)}s
            </span>
          </div>
        )}

        {/* 当播放渲染导出的 MP4 成片时，由于滤镜与 ASS 已物理压制进视频流，跳过 DOM 虚拟层避免双重叠加 */}
        {!isRendered && (
          <>
            {/* 1. 顶部挂顶 Title 横幅 (支持 2D 拖拽、边界手柄拉伸与字号缩放) */}
            {hasBanner && (
              <div
                style={{
                  left: `${bannerPosX}%`,
                  top: `${bannerPosY}%`,
                  transform: 'translate(-50%, 0)',
                  width: strategy?.banner_width_percent ? `${strategy.banner_width_percent}%` : undefined,
                  maxWidth: '96%',
                }}
                onMouseEnter={() => setHoveredOverlay('banner')}
                onMouseLeave={() => !dragTarget && setHoveredOverlay(null)}
                onMouseDown={(e) => handleStartMove(e, 'banner', bannerPosX, bannerPosY)}
                title="按住中心可拖拽位置，拖拽边框手柄可拉宽拉高"
                className={`absolute text-center z-20 select-none ${
                  dragTarget === 'banner'
                    ? 'ring-2 ring-purple-400/80 rounded-full opacity-95 transition-none cursor-grabbing'
                    : 'cursor-grab'
                }`}
              >
                <div
                  style={{
                    padding: `${bannerPaddingY}px ${bannerPaddingX}px`,
                  }}
                  className={`inline-block ${strategy?.banner_width_percent ? 'w-full' : ''} bg-black/85 backdrop-blur-md rounded-full border border-white/20 shadow-xl pointer-events-auto`}
                >
                  <div
                    style={{ fontSize: `${bannerTitlePx}px` }}
                    className="font-black text-white flex items-center justify-center space-x-1 tracking-wide leading-tight"
                  >
                    <span>🔥</span>
                    <span className="truncate">{strategy?.banner_main_title}</span>
                  </div>
                  {strategy?.banner_sub_title && (
                    <div
                      style={{ fontSize: `${bannerSubPx}px` }}
                      className="font-semibold text-yellow-400 truncate mt-0.5 leading-tight"
                    >
                      {strategy.banner_sub_title}
                    </div>
                  )}
                </div>

                {/* 边界标识与拉伸缩放手柄 */}
                {(hoveredOverlay === 'banner' || dragTarget === 'banner') && (
                  <ResizeHandles
                    onStartResize={(e, mode) =>
                      handleStartResize(
                        e,
                        'banner',
                        mode,
                        strategy?.banner_width_percent || 90,
                        bannerFontSizeBase
                      )
                    }
                    color="purple"
                  />
                )}
              </div>
            )}

            {/* 2. 品牌防搬运水印角标 (单行锁定杜绝折行，全方位 2D 自由拖拽与边框手柄缩放) */}
            {hasWatermark && (
              <div
                style={{
                  opacity: strategy?.watermark_opacity ?? 0.4,
                  left: `${wmPosX}%`,
                  top: `${wmPosY}%`,
                  transform: `translate(-${wmPosX}%, -${wmPosY}%)`,
                  fontSize: `${wmPx}px`,
                }}
                onMouseEnter={() => setHoveredOverlay('watermark')}
                onMouseLeave={() => !dragTarget && setHoveredOverlay(null)}
                onMouseDown={(e) => handleStartMove(e, 'watermark', wmPosX, wmPosY)}
                title="按住中心可拖拽位置，拖拽边框手柄可缩放字号"
                className={`absolute z-20 text-white rounded-md whitespace-nowrap w-max max-w-none backdrop-blur-xs tracking-tight select-none shadow-sm px-2.5 py-1 font-medium ${
                  dragTarget === 'watermark'
                    ? 'ring-2 ring-emerald-400/90 opacity-95 transition-none cursor-grabbing'
                    : 'cursor-grab'
                }`}
              >
                {strategy?.watermark_text}

                {/* 边界标识与缩放手柄 */}
                {(hoveredOverlay === 'watermark' || dragTarget === 'watermark') && (
                  <ResizeHandles
                    onStartResize={(e, mode) =>
                      handleStartResize(
                        e,
                        'watermark',
                        mode,
                        50,
                        wmFontSizeBase
                      )
                    }
                    color="emerald"
                    allowHorizontal={false}
                  />
                )}
              </div>
            )}

            {/* 3. 动态口播字幕层 (支持精准单词高亮、2D 上下左右拖拽、边界手柄拉宽与字号缩放) */}
            {activeSubtitle && isSubtitleVisible && (
              <div
                style={{
                  left: `${currentPosX}%`,
                  top: `${currentPosY}%`,
                  transform: 'translate(-50%, -50%)',
                  width: strategy?.subtitle_width_percent ? `${strategy.subtitle_width_percent}%` : undefined,
                  maxWidth: '96%',
                  fontSize: `${subtitlePx}px`,
                }}
                onMouseEnter={() => setHoveredOverlay('subtitle')}
                onMouseLeave={() => !dragTarget && setHoveredOverlay(null)}
                onMouseDown={(e) => handleStartMove(e, 'subtitle', currentPosX, currentPosY)}
                title="按住中心可自由拖动位置，拖拽边框手柄可拉宽拉高"
                className={`absolute text-center z-20 select-none ${
                  dragTarget === 'subtitle'
                    ? 'ring-2 ring-blue-400/80 rounded-2xl opacity-95 transition-none cursor-grabbing'
                    : 'cursor-grab'
                }`}
              >
                <div
                  className={`inline-block ${
                    strategy?.subtitle_width_percent ? 'w-full' : ''
                  } px-3 py-1.5 rounded-xl transition-all ${getThemeClass()} leading-relaxed`}
                >
                  {renderSubtitleText()}
                </div>

                {/* 边界标识与拉伸缩放手柄 */}
                {(hoveredOverlay === 'subtitle' || dragTarget === 'subtitle') && (
                  <ResizeHandles
                    onStartResize={(e, mode) =>
                      handleStartResize(
                        e,
                        'subtitle',
                        mode,
                        strategy?.subtitle_width_percent || 90,
                        subtitleFontSizeBase
                      )
                    }
                    color="blue"
                  />
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* 现代化全宽控制栏：带平滑拖拽进度条、±5秒快进退与音量 */}
      <div className="w-full max-w-[480px] mt-2 flex-shrink-0 flex items-center space-x-2 text-xs text-gray-700 bg-white border border-gray-200/80 px-3 py-1.5 rounded-xl shadow-xs">
        <button
          type="button"
          onClick={togglePlay}
          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-800 transition-colors cursor-pointer"
          title={isPlaying ? '暂停' : '播放'}
        >
          {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
        </button>

        <button
          type="button"
          onClick={() => stepTime(-5)}
          className="px-1.5 py-0.5 rounded text-[11px] text-gray-500 hover:text-gray-800 hover:bg-gray-100 transition-colors font-mono cursor-pointer"
          title="后退 5 秒"
        >
          -5s
        </button>
        <button
          type="button"
          onClick={() => stepTime(5)}
          className="px-1.5 py-0.5 rounded text-[11px] text-gray-500 hover:text-gray-800 hover:bg-gray-100 transition-colors font-mono cursor-pointer"
          title="快进 5 秒"
        >
          +5s
        </button>

        <span className="font-mono text-gray-600 text-[11px] min-w-[34px] text-right select-none">
          {formatTime(isSeeking ? seekTime : currentTime)}
        </span>

        {/* 进度拖拽条：带 pointerDown/Up 与即时 scrub 保护，杜绝播放中被重置 */}
        <div className="flex-1 flex items-center px-1">
          <input
            type="range"
            min="0"
            max={duration || 100}
            step="0.05"
            value={isSeeking ? seekTime : currentTime}
            onPointerDown={handleSeekPointerDown}
            onMouseDown={handleSeekPointerDown}
            onTouchStart={handleSeekPointerDown}
            onChange={handleSeekChange}
            onPointerUp={handleSeekPointerUp}
            onMouseUp={handleSeekPointerUp}
            onTouchEnd={handleSeekPointerUp}
            className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 focus:outline-none"
          />
        </div>

        <span className="font-mono text-gray-400 text-[11px] min-w-[34px] select-none">
          {formatTime(duration)}
        </span>

        <button
          type="button"
          onClick={() => setIsMuted(!isMuted)}
          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors cursor-pointer"
          title={isMuted ? '取消静音' : '静音'}
        >
          {isMuted ? <VolumeX className="w-4 h-4 text-red-500" /> : <Volume2 className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};