import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize } from 'lucide-react';

interface VideoPlayerProps {
  videoUrl?: string;
  subtitles?: Array<{ start_time: number; end_time: number; corrected_text: string }>;
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  aspectRatio?: string;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  subtitles = [],
  currentTime,
  onTimeUpdate,
  aspectRatio = '9:16'
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

  return (
    <div className="flex flex-col items-center bg-gray-100/70 p-6 rounded-2xl border border-gray-200/80 shadow-sm">
      {/* 9:16 竖屏播放视窗 */}
      <div className="relative w-72 aspect-[9/16] bg-gray-900 rounded-xl overflow-hidden shadow-md flex items-center justify-center">
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

        {/* 动态字幕层 */}
        {activeSubtitle && (
          <div className="absolute bottom-10 left-3 right-3 text-center pointer-events-none">
            <span className="inline-block bg-black/75 backdrop-blur-sm text-white font-medium text-xs px-3 py-1.5 rounded-lg shadow-lg border border-white/10">
              {activeSubtitle.corrected_text}
            </span>
          </div>
        )}

        <div className="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-md font-mono">
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
