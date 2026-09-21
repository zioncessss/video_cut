import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize2, Minimize2, X } from 'lucide-react';
import { EditingStrategy, BrollReplacement, Material, HighlightWord, PruneSpan, getMediaUrl } from '../services/api';

interface VideoPlayerProps {
  videoUrl?: string;
  brolls?: BrollReplacement[];
  materialsMap?: Record<string, Material>;
  subtitles?: Array<{
    start_time: number;
    end_time: number;
    corrected_text: string;
    matched_keywords?: string[];
    highlight_words?: HighlightWord[];
  }>;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  aspectRatio?: '9:16' | '16:9' | string;
  onAspectRatioChange?: (ratio: '9:16' | '16:9') => void;
  strategy?: EditingStrategy;
  onStrategyChange?: (newStrategy: EditingStrategy) => void;
  onStrategyCommit?: (strategy: EditingStrategy) => void;
  isRendered?: boolean;
  isActive?: boolean;
  pruneSpans?: PruneSpan[];
  isEnlarged?: boolean;
  onToggleEnlarge?: () => void;
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
  isRendered = false,
  isActive = true,
  pruneSpans = [],
  isEnlarged: propsIsEnlarged,
  onToggleEnlarge,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const brollVideoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(0);
  const [playbackRate, setPlaybackRate] = useState<number>(1.0);

  const [internalEnlarged, setInternalEnlarged] = useState<boolean>(false);
  const isEnlarged = propsIsEnlarged !== undefined ? propsIsEnlarged : internalEnlarged;
  const toggleEnlarge = useCallback(() => {
    if (onToggleEnlarge) {
      onToggleEnlarge();
    } else {
      setInternalEnlarged(prev => !prev);
    }
  }, [onToggleEnlarge]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isEnlarged) {
        toggleEnlarge();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isEnlarged, toggleEnlarge]);

  // 容器切至后台隐藏时自动暂停主口播与分镜空镜视频播放
  useEffect(() => {
    if (isActive === false && isPlaying) {
      if (videoRef.current) videoRef.current.pause();
      if (brollVideoRef.current) brollVideoRef.current.pause();
      setIsPlaying(false);
    }
  }, [isActive, isPlaying]);

  const changePlaybackRate = (rate: number) => {
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
    if (brollVideoRef.current) {
      brollVideoRef.current.playbackRate = rate;
    }
  };

  // 智能字幕时序平滑计算（带 70ms 听觉前置量与微停顿无缝接力）
  const findActiveSubtitle = useCallback((time: number) => {
    if (!subtitles || subtitles.length === 0) return null;
    for (let i = 0; i < subtitles.length; i++) {
      const s = subtitles[i];
      const prevEnd = i > 0 ? subtitles[i - 1].end_time : 0;
      const effectiveStart = Math.max(prevEnd, s.start_time - 0.07);

      let effectiveEnd: number;
      if (i + 1 < subtitles.length) {
        const nextStart = subtitles[i + 1].start_time;
        const gap = nextStart - s.end_time;
        if (gap > 0 && gap <= 0.60) {
          effectiveEnd = Math.max(s.end_time, nextStart - 0.07);
        } else {
          effectiveEnd = Math.min(nextStart, s.end_time + 0.25);
        }
      } else {
        effectiveEnd = s.end_time + 0.30;
      }

      if (time >= effectiveStart && time < effectiveEnd) {
        return s;
      }
    }
    return null;
  }, [subtitles]);

  // 将播放器原生时间转换为紧凑时间轴时间（用于未渲染跳播模式下对齐紧凑分镜）
  const getCompactTime = useCallback((rawTime: number) => {
    if (!pruneSpans || pruneSpans.length === 0) return rawTime;
    let prunedBefore = 0;
    for (const span of pruneSpans) {
      if (!span.is_active) continue;
      if (rawTime >= span.end_time) {
        prunedBefore += (span.end_time - span.start_time);
      } else if (rawTime > span.start_time) {
        prunedBefore += (rawTime - span.start_time);
      }
    }
    return Math.max(0, rawTime - prunedBefore);
  }, [pruneSpans]);

  // 实时分镜探测：判断当前播放时间点是否落在某段 B-roll 空镜窗口内
  const findActiveBroll = useCallback((time: number) => {
    if (isRendered || !brolls || brolls.length === 0) return null;
    const checkTime = getCompactTime(time);
    return brolls.find(b => checkTime >= b.start_time && checkTime < b.end_time) || null;
  }, [isRendered, brolls, getCompactTime]);

  // 高精 60fps 逐帧监听机制 (基于 requestAnimationFrame)
  // 彻底打破 Chromium 原生 timeupdate 250ms 一次的迟钝更新，将显示延迟降低至 0~16ms
  const [activeSubtitle, setActiveSubtitle] = useState<any>(() => findActiveSubtitle(currentTime));
  const [activeBroll, setActiveBroll] = useState<any>(() => findActiveBroll(currentTime));
  const activeSubKeyRef = useRef<string | null>(null);
  const activeBrollKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isPlaying) {
      const sub = findActiveSubtitle(currentTime);
      const subKey = sub ? `${sub.start_time}_${sub.end_time}_${sub.corrected_text}` : null;
      if (subKey !== activeSubKeyRef.current) {
        activeSubKeyRef.current = subKey;
        setActiveSubtitle(sub);
      }
      const b = findActiveBroll(currentTime);
      const bKey = b ? `${b.material_id}_${b.start_time}_${b.end_time}` : null;
      if (bKey !== activeBrollKeyRef.current) {
        activeBrollKeyRef.current = bKey;
        setActiveBroll(b);
      }
      return;
    }

    let rafId: number;
    const tick = () => {
      if (videoRef.current && !videoRef.current.paused) {
        const cur = videoRef.current.currentTime;
        const sub = findActiveSubtitle(cur);
        const subKey = sub ? `${sub.start_time}_${sub.end_time}_${sub.corrected_text}` : null;
        if (subKey !== activeSubKeyRef.current) {
          activeSubKeyRef.current = subKey;
          setActiveSubtitle(sub);
        }

        const b = findActiveBroll(cur);
        const bKey = b ? `${b.material_id}_${b.start_time}_${b.end_time}` : null;
        if (bKey !== activeBrollKeyRef.current) {
          activeBrollKeyRef.current = bKey;
          setActiveBroll(b);
        }
      }
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [isPlaying, currentTime, findActiveSubtitle, findActiveBroll]);

  const activeBrollMaterial = (activeBroll && materialsMap) ? materialsMap[activeBroll.material_id] : null;
  const activeBrollUrl = activeBrollMaterial ? getMediaUrl(activeBrollMaterial.filepath) : null;

  // 保持空镜视频与口播原声/主时间戳毫秒级同步
  useEffect(() => {
    if (!brollVideoRef.current || !activeBroll) return;
    const brollEl = brollVideoRef.current;
    const checkTime = isRendered ? currentTime : getCompactTime(currentTime);
    const offset = Math.max(0, checkTime - activeBroll.start_time);
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

  const is169 = aspectRatio === '16:9';

  // 动态物理有效视口 (Active Video Viewport) 测量：排除 Letterbox/Pillarbox 黑边，精准 1:1 映射 1080P 画布
  const [viewport, setViewport] = useState({
    containerWidth: 360,
    containerHeight: 640,
    videoWidth: 360,
    videoHeight: 640,
    offsetX: 0,
    offsetY: 0,
    scaleFactor: 640 / 1920,
  });
  const viewportRef = useRef(viewport);
  viewportRef.current = viewport;

  const updateViewport = useCallback(() => {
    if (!containerRef.current) return;
    const cw = containerRef.current.clientWidth;
    const ch = containerRef.current.clientHeight;
    if (cw < 30 || ch < 30) return;

    const targetAspect = is169 ? 16 / 9 : 9 / 16;
    const containerAspect = cw / ch;

    let vW = cw;
    let vH = ch;
    let offX = 0;
    let offY = 0;

    if (containerAspect > targetAspect) {
      // 容器偏宽：高度撑满，左右黑边 (Pillarbox)
      vH = ch;
      vW = ch * targetAspect;
      offX = (cw - vW) / 2;
      offY = 0;
    } else {
      // 容器偏高：宽度撑满，上下黑边 (Letterbox)
      vW = cw;
      vH = cw / targetAspect;
      offX = 0;
      offY = (ch - vH) / 2;
    }

    const sFactor = is169 ? vW / 1920 : vH / 1920;
    setViewport({
      containerWidth: cw,
      containerHeight: ch,
      videoWidth: vW,
      videoHeight: vH,
      offsetX: offX,
      offsetY: offY,
      scaleFactor: sFactor,
    });
  }, [is169]);

  useEffect(() => {
    updateViewport();
    if (!containerRef.current) return;
    const ro = new ResizeObserver(() => {
      updateViewport();
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [updateViewport]);

  // 进度条平滑拖拽 Seeking 独立状态，防范播放时 timeupdate 引起滑块回弹抖动
  const [isSeeking, setIsSeeking] = useState<boolean>(false);
  const [seekTime, setSeekTime] = useState<number>(0);
  const [videoAspect, setVideoAspect] = useState<string>('9/16');


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

  // 记录待恢复时间点，防范重新合成换 URL 时 `<video>` 初始 00:00 覆盖父级播放进度
  const pendingSeekTimeRef = useRef<number | null>(currentTime > 0 ? currentTime : null);
  const prevVideoUrlRef = useRef<string | undefined>(videoUrl);

  const handleTimeUpdate = () => {
    if (videoRef.current && !isSeeking) {
      if (pendingSeekTimeRef.current !== null) {
        return;
      }
      const cur = videoRef.current.currentTime;
      // 009: 智能粗剪虚拟跳播 (Virtual Skip)
      // 若当前播放位置落入活跃的剔除区间，秒级跳过废动作/口误
      if (!isRendered && pruneSpans && pruneSpans.length > 0) {
        const activeSpan = pruneSpans.find(
          s => s.is_active && cur >= s.start_time - 0.05 && cur < s.end_time - 0.05
        );
        if (activeSpan) {
          videoRef.current.currentTime = activeSpan.end_time;
          onTimeUpdate(activeSpan.end_time);
          return;
        }
      }
      onTimeUpdate(cur);
    }
  };

  useEffect(() => {
    if (!isSeeking && videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.35) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime, isSeeking]);

  // 当 videoUrl 发生变更（如生成成片后携带新时间戳），主动调用 load() 破除浏览器视频解码缓存并维护待恢复时间
  useEffect(() => {
    if (videoUrl !== prevVideoUrlRef.current) {
      prevVideoUrlRef.current = videoUrl;
      if (currentTime > 0) {
        pendingSeekTimeRef.current = currentTime;
      }
      if (videoRef.current && videoUrl) {
        videoRef.current.load();
      }
    }
  }, [videoUrl, currentTime]);

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const d = videoRef.current.duration;
      setDuration(isNaN(d) ? 0 : d);
      if (pendingSeekTimeRef.current !== null && pendingSeekTimeRef.current > 0) {
        videoRef.current.currentTime = pendingSeekTimeRef.current;
        pendingSeekTimeRef.current = null;
      } else if (currentTime > 0) {
        videoRef.current.currentTime = currentTime;
      }
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

  // 竖屏与 1080P 画布 1:1 语义智能折行函数（与后端 subtitle_styler.py 100% 算法同构）
  const wrapSubtitleText = (text: string, maxLineLen: number = 15, protectedWords: string[] = []): string => {
    if (!text || text.length <= maxLineLen || text.includes('\n') || text.includes('\\N')) {
      return text;
    }

    const protectedRanges: Array<[number, number]> = [];
    for (const w of protectedWords) {
      if (w && text.includes(w)) {
        let idx = 0;
        while (true) {
          const p = text.indexOf(w, idx);
          if (p === -1) break;
          protectedRanges.push([p, p + w.length]);
          idx = p + 1;
        }
      }
    }

    const isProtected = (pos: number) => {
      return protectedRanges.some(([start, end]) => pos > start && pos < end);
    };

    // 优先在自然标点、语气助词或连词前断句折行，避开高亮保护词且严禁弱连词挂尾
    const regex = /[，,。？！?!；;]|(?<=[呢吧啊吗呀啦哒哦哈])|(?=(?:还|并且|但是|而且|然后|或者|包括|我们|你们|他们|其实|大家|全部|手把手))/g;
    const danglingChars = ['和', '与', '跟', '及', '同', '在', '从', '到', '向', '由', '把', '让'];
    const candidates: number[] = [];
    let match: RegExpExecArray | null;
    while ((match = regex.exec(text)) !== null) {
      const prefix = text.slice(0, match.index).replace(/[，, ]+$/, '');
      const isDangling = danglingChars.some(d => prefix.endsWith(d));
      if (!isDangling && match.index >= 3 && match.index <= text.length - 3 && !isProtected(match.index)) {
        candidates.push(match.index);
      }
    }

    if (candidates.length > 0) {
      const mid = text.length / 2;
      const best = candidates.reduce((prev, curr) =>
        Math.abs(curr - mid) < Math.abs(prev - mid) ? curr : prev
      );
      return text.slice(0, best).replace(/[，, ]+$/, '') + '\n' + text.slice(best).replace(/^[，, ]+/, '');
    }

    // 若无明显连词/标点，在几何中点折行（若中点落在保护词内，则平移至保护词边缘）
    let midIdx = Math.floor(text.length / 2);
    for (const [start, end] of protectedRanges) {
      if (start < midIdx && midIdx < end) {
        midIdx = (midIdx - start) <= (end - midIdx) ? start : end;
        break;
      }
    }
    return text.slice(0, midIdx) + '\n' + text.slice(midIdx);
  };

  // 根据当前字幕与策略切分普通文本与高亮文本（精准单词高亮）
  const renderSubtitleText = () => {
    if (!activeSubtitle) return null;
    const rawText = activeSubtitle.corrected_text || '';
    const strat = strategy || {
      subtitle_theme: 'glow_gold',
      enable_highlight: true,
      highlight_color: '#FACC15',
      highlight_scale: true,
      custom_highlight_words: []
    };

    if (!strat.enable_highlight) {
      const wrapped = wrapSubtitleText(rawText, 15, []);
      const lines = wrapped.split(/\r?\n|\\N/);
      if (lines.length > 1) {
        return (
          <span className="inline-flex flex-col items-center">
            {lines.map((l, idx) => (
              <span key={idx} className="inline-block whitespace-nowrap">
                {l}
              </span>
            ))}
          </span>
        );
      }
      return <span>{rawText}</span>;
    }

    // 优先构建词汇与专属颜色映射表
    const hlColorMap = new Map<string, string>();
    if (activeSubtitle.highlight_words && activeSubtitle.highlight_words.length > 0) {
      activeSubtitle.highlight_words.forEach(hw => {
        if (hw.word && hw.word.trim()) {
          hlColorMap.set(hw.word.trim(), hw.color || strat.highlight_color || '#FACC15');
        }
      });
    }

    // 合并自定义词
    (strat.custom_highlight_words || []).forEach(cw => {
      const c = (cw || '').trim();
      if (c && !hlColorMap.has(c)) {
        hlColorMap.set(c, strat.highlight_color || '#FACC15');
      }
    });

    // 降级兼容旧 matched_keywords
    (activeSubtitle.matched_keywords || []).forEach(kw => {
      const k = (kw || '').trim();
      if (k && !hlColorMap.has(k)) {
        hlColorMap.set(k, strat.highlight_color || '#FACC15');
      }
    });

    const keywords = Array.from(hlColorMap.keys());
    const text = wrapSubtitleText(rawText, 15, keywords);

    if (keywords.length === 0) {
      const lines = text.split(/\r?\n|\\N/);
      if (lines.length > 1) {
        return (
          <span className="inline-flex flex-col items-center">
            {lines.map((l, idx) => (
              <span key={idx} className="inline-block whitespace-nowrap">
                {l}
              </span>
            ))}
          </span>
        );
      }
      return <span>{text}</span>;
    }

    // 依词长降序正则切分
    keywords.sort((a, b) => b.length - a.length);
    const escaped = keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = new RegExp(`(${escaped})`, 'g');

    const renderLine = (lineText: string, lineKey: number) => {
      const parts = lineText.split(regex);
      return (
        <span key={lineKey} className="inline-block whitespace-nowrap">
          {parts.map((part, i) => {
            if (hlColorMap.has(part)) {
              const wordColor = hlColorMap.get(part) || strat.highlight_color || '#FACC15';
              const upper = wordColor.toUpperCase();
              const isWhite = upper === '#FFFFFF' || upper === '#FFF';
              return (
                <span
                  key={i}
                  style={{
                    color: wordColor,
                    textShadow: isWhite
                      ? '0 0 16px rgba(255,255,255,1), 0 0 6px rgba(255,255,255,0.85), 0 2px 6px rgba(0,0,0,0.95)'
                      : `0 0 12px ${wordColor}95, 0 2px 6px rgba(0,0,0,0.95)`
                  }}
                  className={`font-black inline-block align-baseline transition-all ${
                    isWhite
                      ? 'text-[1.22em] mx-0.5'
                      : strat.highlight_scale !== false
                      ? 'text-[1.15em] mx-0.5'
                      : ''
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

    const lines = (text || '').split(/\r?\n|\\N/);
    if (lines.length > 1) {
      return (
        <span className="inline-flex flex-col items-center">
          {lines.map((l, idx) => renderLine(l, idx))}
        </span>
      );
    }
    return renderLine(text || '', 0);
  };

  // 获取字幕主题样式类名 (支持自然融入视频背景，无黑底)
  const getThemeClass = () => {
    const theme = strategy?.subtitle_theme || 'glow_gold';
    switch (theme) {
      // 1. 发光金黄 (完全融入画面，无黑底框，纯白文字 + 柔和紧凑立体微阴影)
      case 'glow_gold':
        return 'bg-transparent text-white font-bold tracking-wider [text-shadow:_0_1.8px_3px_rgb(0_0_0_/_80%),_0_0_1px_rgb(0_0_0_/_60%)]';
      
      // 2. 超透毛玻璃白 (极微弱纯净透光，不遮挡画面)
      case 'glass_clean':
        return 'bg-black/20 backdrop-blur-[2px] text-white font-bold border border-white/15 shadow-sm [text-shadow:_0_1px_3px_rgb(0_0_0_/_80%)]';
      
      // 3. 电影级自然立体白 (方案 A：纯白字身 + 紧凑微阴影与微羽化边缘，明暗场景均通透清晰)
      case 'cinema_shadow':
        return 'bg-transparent text-white font-bold tracking-wider [text-shadow:_0_1.8px_3px_rgb(0_0_0_/_80%),_0_0_1px_rgb(0_0_0_/_60%)]';
      
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
        return 'bg-transparent text-white font-bold tracking-wider [text-shadow:_0_1.5px_3px_rgb(0_0_0_/_85%),_0_0.5px_1px_rgb(0_0_0_/_60%)]';
    }
  };

  const hasBanner = Boolean(strategy?.enable_top_banner && strategy?.banner_main_title?.trim());
  const hasWatermark = Boolean(
    strategy?.enable_watermark &&
    strategy?.watermark_text?.trim() &&
    strategy.watermark_text.trim() !== '@顺达驾校官方教学'
  );

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
      const activeVW = viewportRef.current.videoWidth || rect.width;
      const activeVH = viewportRef.current.videoHeight || rect.height;

      const deltaX = e.clientX - dragStartX;
      const deltaY = e.clientY - dragStartY;
      const deltaPercentX = (deltaX / activeVW) * 100;
      const deltaPercentY = (deltaY / activeVH) * 100;

      const currentStrat = strategyRef.current;
      const changeFn = onStrategyChangeRef.current;
      if (!currentStrat || !changeFn) return;

      if (dragMode === 'move') {
        if (dragTarget === 'subtitle') {
          // 字幕宽度与X轴固定居中 (100% 宽度，X=50%)，仅允许垂直高度微调
          const newY = Math.max(15, Math.min(92, Math.round(dragStartPosY + deltaPercentY)));
          if (newY !== currentStrat.subtitle_position_y || currentStrat.subtitle_position_x !== 50 || currentStrat.subtitle_width_percent !== 100) {
            changeFn({ ...currentStrat, subtitle_position_x: 50, subtitle_position_y: newY, subtitle_width_percent: 100 });
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
        const deltaW = factor * (deltaX / activeVW) * 200;
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
        const deltaW = (deltaX / activeVW) * 200;
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

  // 1080P 画布视觉等比映射因子 (严格依据物理画面有效像素，彻底消除预览窗口折行与压制 ASS 视觉撕裂)
  const scaleFactor = viewport.scaleFactor;

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
  const currentPosY = strategy?.subtitle_position_y ?? 74;
  const isSubtitleVisible = strategy?.show_subtitles !== false;
  const subtitleFontSizeBase = strategy?.subtitle_font_size || (
    strategy?.font_size === 'small' ? 56 : strategy?.font_size === 'large' ? 86 : strategy?.font_size === 'xlarge' ? 98 : 72
  );
  // ASS 物理渲染 1:1 等比缩放 (保持与 1080P 画布像素级绝对一致)
  const subtitlePx = Math.max(10, Math.round(subtitleFontSizeBase * scaleFactor));

  // 获取字幕字体族 (提供华文中宋/思源宋体、清雅仿宋、经典宋体、书法楷体与现代黑体)
  const getSubtitleFontFamily = () => {
    const family = strategy?.subtitle_font_family || 'notoserif';
    switch (family) {
      case 'notoserif':
        return '"STZhongsong", "华文中宋", "Source Han Serif SC", "Noto Serif SC", "思源宋体", "STSong", "华文宋体", serif';
      case 'fangsong':
        return '"FangSong", "FangSong_GB2312", "STFangsong", "华文仿宋", "仿宋", serif';
      case 'songti':
        return '"STSong", "SimSun", "Songti SC", "华文宋体", "宋体", serif';
      case 'kaiti':
        return '"KaiTi", "STKaiti", "华文楷体", "楷体", "SimKai", "DFKai-SB", serif';
      case 'yahei':
        return '"Microsoft YaHei", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif';
      default:
        return '"STZhongsong", "华文中宋", "Source Han Serif SC", "Noto Serif SC", "思源宋体", "STSong", "华文宋体", serif';
    }
  };

  return (
    <div
      className={
        isEnlarged
          ? 'fixed inset-0 z-50 bg-black/92 backdrop-blur-md flex flex-col items-center justify-center p-4 sm:p-6 animate-in fade-in duration-150 select-none overflow-hidden'
          : 'flex flex-col items-center justify-center w-full h-full min-h-0 select-none overflow-hidden p-1'
      }
    >
      {/* 放大观看模式顶部状态与关闭条 */}
      {isEnlarged && (
        <div className="w-full max-w-4xl flex items-center justify-between pb-3 text-white/90">
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-1 rounded-lg bg-white/10 text-xs font-semibold backdrop-blur-xs">
              {is169 ? '16:9 横屏' : '9:16 竖屏'}
            </span>
            <span className="text-xs font-medium text-white/70">
              {isRendered ? '成片预览' : '实时编辑'}
            </span>
          </div>
          <button
            type="button"
            onClick={toggleEnlarge}
            className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors cursor-pointer flex items-center space-x-1.5 text-xs font-medium"
            title="退出放大 (Esc)"
          >
            <Minimize2 className="w-4 h-4" />
            <span>还原窗口 (Esc)</span>
          </button>
        </div>
      )}

      {/* 视窗容器：100% 紧贴原视频原生比例，杜绝强行上下填充多余黑边，确保字幕和角标直接贴合在视频画面上 */}
      <div
        ref={containerRef}
        style={{
          aspectRatio: is169 ? '16 / 9' : (videoAspect || '9 / 16'),
        }}
        className={`relative flex items-center justify-center bg-black rounded-2xl overflow-hidden shadow-2xl border border-gray-800/80 select-none transition-all duration-150 ${
          isEnlarged
            ? (is169 ? 'w-full max-w-5xl max-h-[78vh]' : 'h-full max-h-[82vh] max-w-full')
            : (is169 ? 'w-full max-w-[540px] max-h-[calc(100%-46px)]' : 'h-full max-h-[calc(100%-46px)] max-w-full')
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
          <div
            style={{
              left: `${viewport.offsetX + 12}px`,
              top: `${viewport.offsetY + 12}px`,
            }}
            className="absolute z-30 flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold shadow-lg backdrop-blur-md bg-black/85 text-white border border-white/20 animate-in fade-in duration-150 select-none pointer-events-none"
          >
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
          <div
            style={{
              position: 'absolute',
              left: `${viewport.offsetX}px`,
              top: `${viewport.offsetY}px`,
              width: `${viewport.videoWidth}px`,
              height: `${viewport.videoHeight}px`,
              pointerEvents: 'none',
            }}
            className="select-none overflow-visible z-20"
          >
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
                className={`absolute text-center z-20 select-none pointer-events-auto ${
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
                className={`absolute z-20 text-white rounded-md whitespace-nowrap w-max max-w-none backdrop-blur-xs tracking-tight select-none shadow-sm px-2.5 py-1 font-medium pointer-events-auto ${
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

            {/* 3. 动态口播字幕层 (全宽 100% 锁定，电影立体白，仅允许垂直微调) */}
            {activeSubtitle && isSubtitleVisible && (
              <div
                style={{
                  left: '50%',
                  top: `${currentPosY}%`,
                  transform: 'translate(-50%, -50%)',
                  width: '100%',
                  maxWidth: '100%',
                  paddingLeft: '16px',
                  paddingRight: '16px',
                  fontSize: `${subtitlePx}px`,
                }}
                onMouseEnter={() => setHoveredOverlay('subtitle')}
                onMouseLeave={() => !dragTarget && setHoveredOverlay(null)}
                onMouseDown={(e) => handleStartMove(e, 'subtitle', 50, currentPosY)}
                title="按住可上下微调垂直位置"
                className={`absolute text-center z-20 select-none pointer-events-auto ${
                  dragTarget === 'subtitle'
                    ? 'ring-1 ring-indigo-400/80 rounded-xl opacity-95 transition-none cursor-ns-resize'
                    : 'cursor-grab'
                }`}
              >
                <div
                  style={{
                    fontFamily: getSubtitleFontFamily(),
                  }}
                  className={`inline-block w-full px-2 py-0.5 rounded-lg transition-all ${getThemeClass()} leading-snug tracking-wider text-center break-words`}
                >
                  {renderSubtitleText()}
                </div>

                {/* 垂直方向与字号微调手柄 (宽度已 100% 锁定，不可横向调节) */}
                {(hoveredOverlay === 'subtitle' || dragTarget === 'subtitle') && (
                  <ResizeHandles
                    onStartResize={(e, mode) =>
                      handleStartResize(
                        e,
                        'subtitle',
                        mode,
                        100,
                        subtitleFontSizeBase
                      )
                    }
                    color="blue"
                    allowHorizontal={false}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 现代化全宽控制栏：带平滑拖拽进度条、±5秒快进退、音量与放大/缩小切换 */}
      <div
        className={`w-full flex-shrink-0 flex items-center space-x-2 text-xs transition-all ${
          isEnlarged
            ? 'max-w-2xl mt-3 text-white bg-gray-900/90 border border-white/10 px-4 py-2 rounded-2xl shadow-2xl backdrop-blur-md'
            : 'max-w-[480px] mt-2 text-gray-700 bg-white border border-gray-200/80 px-3 py-1.5 rounded-xl shadow-xs'
        }`}
      >
        <button
          type="button"
          onClick={togglePlay}
          className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
            isEnlarged ? 'hover:bg-white/10 text-white' : 'hover:bg-gray-100 text-gray-800'
          }`}
          title={isPlaying ? '暂停' : '播放'}
        >
          {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
        </button>

        <button
          type="button"
          onClick={() => stepTime(-5)}
          className={`px-1.5 py-0.5 rounded text-[11px] transition-colors font-mono cursor-pointer ${
            isEnlarged ? 'text-white/70 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
          }`}
          title="后退 5 秒"
        >
          -5s
        </button>
        <button
          type="button"
          onClick={() => stepTime(5)}
          className={`px-1.5 py-0.5 rounded text-[11px] transition-colors font-mono cursor-pointer ${
            isEnlarged ? 'text-white/70 hover:text-white hover:bg-white/10' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
          }`}
          title="快进 5 秒"
        >
          +5s
        </button>

        <span className={`font-mono text-[11px] min-w-[34px] text-right select-none ${
          isEnlarged ? 'text-white/80' : 'text-gray-600'
        }`}>
          {formatTime(isSeeking ? seekTime : currentTime)}
        </span>

        {/* 进度拖拽条：带 pointerDown/Up 与即时 scrub 保护，纯净无留红渲染 */}
        <div className="flex-1 flex items-center px-1 relative h-5">
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
            className={`w-full h-1.5 rounded-lg appearance-none cursor-pointer accent-indigo-500 focus:outline-none relative z-10 ${
              isEnlarged ? 'bg-white/20' : 'bg-gray-200/80'
            }`}
          />
        </div>

        <span className={`font-mono text-[11px] min-w-[34px] select-none ${
          isEnlarged ? 'text-white/50' : 'text-gray-400'
        }`}>
          {formatTime(duration)}
        </span>

        <button
          type="button"
          onClick={() => {
            const rates = [1.0, 1.25, 1.5, 2.0, 0.75];
            const nextIdx = (rates.indexOf(playbackRate) + 1) % rates.length;
            changePlaybackRate(rates[nextIdx]);
          }}
          className={`px-1.5 py-0.5 rounded text-[11px] font-mono transition-colors font-medium cursor-pointer ${
            isEnlarged ? 'text-white/80 hover:text-white hover:bg-white/10' : 'text-gray-700 hover:text-indigo-600 hover:bg-gray-100'
          }`}
          title="点击切换播放倍速 (0.75x ~ 2.0x)"
        >
          {playbackRate}x
        </button>

        <button
          type="button"
          onClick={() => setIsMuted(!isMuted)}
          className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
            isEnlarged ? 'hover:bg-white/10 text-white/70 hover:text-white' : 'hover:bg-gray-100 text-gray-600 hover:text-gray-900'
          }`}
          title={isMuted ? '取消静音' : '静音'}
        >
          {isMuted ? <VolumeX className="w-4 h-4 text-red-500" /> : <Volume2 className="w-4 h-4" />}
        </button>

        <button
          type="button"
          onClick={toggleEnlarge}
          className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
            isEnlarged ? 'hover:bg-white/10 text-white/80 hover:text-white' : 'hover:bg-gray-100 text-gray-600 hover:text-indigo-600'
          }`}
          title={isEnlarged ? '还原窗口 (Esc)' : '放大观看 (剧场模式)'}
        >
          {isEnlarged ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};