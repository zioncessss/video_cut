import React, { useState, useEffect, useRef } from 'react';
import { 
  X, 
  Film, 
  Play, 
  Pause, 
  Clock, 
  Check, 
  Trash2, 
  Sparkles, 
  MapPin, 
  Video,
  ShieldAlert,
  Scissors,
  RotateCcw,
  Globe
} from 'lucide-react';
import { Material, BrollReplacement, getMediaUrl } from '../services/api';
import { ZHEJIANG_REGIONS, formatRegionBadge } from '../constants/regions';
import { SubtitleItem } from './SubtitleList';

interface BrollPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  sub: SubtitleItem | null;
  dispStart: number;
  dispEnd: number;
  existingBroll: BrollReplacement | null;
  materialsMap: Record<string, Material>;
  brolls?: BrollReplacement[];
  totalDuration?: number;
  onSave: (broll: BrollReplacement | null, subId: string) => void;
}

export const BrollPickerModal: React.FC<BrollPickerModalProps> = ({
  isOpen,
  onClose,
  sub,
  dispStart,
  dispEnd,
  existingBroll,
  materialsMap,
  brolls = [],
  totalDuration = 0,
  onSave
}) => {
  const [selectedMatId, setSelectedMatId] = useState<string>('');
  const [clipDuration, setClipDuration] = useState<number>(1.0);
  const [sourceInPoint, setSourceInPoint] = useState<number>(0.0);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [regionFilter, setRegionFilter] = useState<string>('all'); // 'all' | 'public' | specific region code
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [previewTime, setPreviewTime] = useState<number>(0.0);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  // 当前分镜在主视频时间轴上的切入起点
  const timelineStart = existingBroll ? existingBroll.start_time : dispStart;
  // 当前字幕原始默认时长
  const defaultSubDuration = Math.max(0.1, Number((dispEnd - dispStart).toFixed(2)));

  // 检测后置分镜以防时间轴重叠冲突
  const otherBrolls = (brolls || []).filter(b => {
    if (existingBroll && b.id === existingBroll.id) return false;
    if (Math.abs(b.start_time - timelineStart) < 0.05) return false;
    return true;
  });

  const subsequentBrolls = otherBrolls
    .filter(b => b.start_time >= timelineStart + 0.05)
    .sort((a, b) => a.start_time - b.start_time);

  const nextBroll = subsequentBrolls.length > 0 ? subsequentBrolls[0] : null;

  // 与后置分镜或视频末尾的防冲突最大时长限制
  const maxConflictDuration: number = nextBroll
    ? Math.max(0.2, Number((nextBroll.start_time - timelineStart).toFixed(2)))
    : (totalDuration && totalDuration > timelineStart)
    ? Math.max(0.2, Number((totalDuration - timelineStart).toFixed(2)))
    : 60.0;

  const selectedMaterial = selectedMatId ? materialsMap[selectedMatId] : null;

  // 当前分镜持续时长最大上限：由后置分镜碰撞与视频总长决定，拖动时独立运行
  const maxAllowedDuration = selectedMaterial
    ? Math.max(0.2, Number(Math.min(maxConflictDuration, selectedMaterial.duration).toFixed(2)))
    : maxConflictDuration;

  // 素材自身总时长：作为 In 点滑块的固定上限，完全独立于持续时长
  const materialTotalDuration = selectedMaterial ? Number(selectedMaterial.duration.toFixed(2)) : 10.0;

  // 初始化已有分镜或推荐状态
  useEffect(() => {
    if (isOpen && sub) {
      const initMatId = existingBroll?.material_id || sub.broll_material_id || '';
      setSelectedMatId(initMatId);

      const mat = initMatId ? materialsMap[initMatId] : null;
      const initialMaxDur = mat
        ? Math.max(0.2, Number(Math.min(maxConflictDuration, mat.duration).toFixed(2)))
        : maxConflictDuration;

      const initialDur = existingBroll
        ? Math.max(0.2, Number((existingBroll.end_time - existingBroll.start_time).toFixed(2)))
        : defaultSubDuration;
      const clampedDur = Math.min(initialMaxDur, initialDur);
      setClipDuration(clampedDur);

      const initInPoint = existingBroll?.source_start_time ?? 0.0;
      setSourceInPoint(Number(initInPoint.toFixed(2)));
      setPreviewTime(Number(initInPoint.toFixed(2)));
      setIsPlaying(false);

      // 若原句有推荐分类且当前无筛选，可默认切换到推荐分类
      const recCat = sub.scene_decision?.broll_category || sub.matched_category;
      if (recCat && (!initMatId || !materialsMap[initMatId])) {
        setCategoryFilter(recCat);
      } else {
        setCategoryFilter('all');
      }
      setRegionFilter('all');
    }
  }, [isOpen, sub, existingBroll, materialsMap]);

  // 切换所选素材卡片时，仅重置素材 In 点和视窗，不影响用户设定的持续时长
  const handleSelectMaterial = (matId: string) => {
    setSelectedMatId(matId);
    setSourceInPoint(0.0);
    setPreviewTime(0.0);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
    }
  };

  // 监听 ESC 键关闭弹窗
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !sub) return null;

  const allBrollMaterials = Object.values(materialsMap).filter(m => m.category !== 'talking_head');

  // 仅场地 (venue) 和教学 (lesson) 参与地区与公共库划分；学员体验为通用素材，不区分地域（与素材库完全一致）
  const regionalMaterials = allBrollMaterials.filter(m => 
    categoryFilter === 'all' ? (m.category === 'venue' || m.category === 'lesson') : m.category === categoryFilter
  );

  // 动态提取素材库中实际存在的地区（仅统计场地与教学）
  const presentRegionsInLibrary = Array.from(
    new Set(
      regionalMaterials
        .map(m => m.plate_region)
        .filter(Boolean) as string[]
    )
  ).sort();

  // 素材复合筛选（分类 + 地区/公共库）
  const filteredMaterials = allBrollMaterials.filter(m => {
    // 1. 分类筛选
    if (categoryFilter !== 'all' && m.category !== categoryFilter) {
      return false;
    }
    // 2. 学员体验为通用素材，完全不区分地域（跟素材库第一个页面一致）
    if (m.category === 'experience') {
      return true;
    }
    // 3. 场地与教学按地区与公共库筛选
    if (regionFilter === 'all') {
      return true;
    }
    if (regionFilter === 'public') {
      return !m.plate_region || m.plate_region === 'public' || m.plate_region === '通用';
    }
    return m.plate_region === regionFilter;
  });

  const handleTogglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      const clipEnd = Math.min(materialTotalDuration, sourceInPoint + clipDuration);
      if (videoRef.current.currentTime < sourceInPoint || videoRef.current.currentTime >= clipEnd) {
        videoRef.current.currentTime = sourceInPoint;
      }
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  // 循环播放截取区间试看
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const cur = videoRef.current.currentTime;
    setPreviewTime(cur);
    const clipEnd = Math.min(materialTotalDuration, sourceInPoint + clipDuration);
    if (cur >= clipEnd || cur < sourceInPoint - 0.05) {
      videoRef.current.currentTime = sourceInPoint;
    }
  };

  // 独立调节持续时长：绝对不联动修改 sourceInPoint
  const handleDurationChange = (val: number) => {
    const clampedDur = Math.max(0.2, Math.min(maxAllowedDuration, Number(val.toFixed(2))));
    setClipDuration(clampedDur);
  };

  // 独立调节素材 In 点：绝对不联动修改 clipDuration
  const handleInPointChange = (val: number) => {
    const clampedIn = Math.max(0, Math.min(materialTotalDuration, Number(val.toFixed(2))));
    setSourceInPoint(clampedIn);
    if (videoRef.current) {
      videoRef.current.currentTime = clampedIn;
    }
    setPreviewTime(clampedIn);
  };

  const handleConfirm = () => {
    if (!selectedMatId || !selectedMaterial) return;
    const sStart = Math.max(0, Math.min(Math.max(0, selectedMaterial.duration - 0.1), sourceInPoint));
    const newBroll: BrollReplacement = {
      id: existingBroll?.id || `broll_${Date.now()}`,
      start_time: Number(timelineStart.toFixed(2)),
      end_time: Number((timelineStart + clipDuration).toFixed(2)),
      material_id: selectedMatId,
      material_category: (selectedMaterial.category === 'lesson' || selectedMaterial.category === 'experience' ? selectedMaterial.category : 'venue'),
      source_start_time: Number(sStart.toFixed(2)),
      playback_mode: 'fit'
    };
    onSave(newBroll, sub.id);
    onClose();
  };

  const handleRemove = () => {
    onSave(null, sub.id);
    onClose();
  };

  const formatExactTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) secs = 0;
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toFixed(2).padStart(5, '0');
    return `${m}:${s}`;
  };

  // 统计各标签数量（仅针对有地区属性的场地/教学）
  const publicCount = regionalMaterials.filter(m => !m.plate_region || m.plate_region === 'public' || m.plate_region === '通用').length;

  return (
    <div 
      className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div 
        className="bg-white w-full max-w-4xl h-[650px] max-h-[90vh] rounded-2xl shadow-xl border border-slate-200/80 flex flex-col overflow-hidden text-slate-800"
        onClick={e => e.stopPropagation()}
      >
        {/* Header 顶部标题栏：克制、明晰、低噪 */}
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-white flex-shrink-0">
          <div className="flex items-center space-x-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center flex-shrink-0">
              <Film className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-semibold text-slate-900">分镜空镜设置</span>
                <span className="text-[11px] font-mono text-slate-600 bg-slate-100 px-2 py-0.5 rounded font-medium">
                  {formatExactTime(timelineStart)} - {formatExactTime(timelineStart + clipDuration)} ({clipDuration.toFixed(2)}s)
                </span>
              </div>
              <p className="text-xs text-slate-500 truncate max-w-xl mt-0.5" title={sub.corrected_text || sub.raw_text}>
                当前字幕：{sub.corrected_text || sub.raw_text}
              </p>
            </div>
          </div>
          <button 
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            title="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 筛选条：分类切换与地区/公共库筛选，统一低饱和度 Slate 色阶，固定高度杜绝跳动 */}
        <div className="px-5 py-2.5 border-b border-slate-100 bg-slate-50/50 space-y-2 flex-shrink-0 min-h-[74px]">
          {/* 第 1 栏：空镜分类 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 overflow-x-auto py-0.5">
              <button
                type="button"
                onClick={() => setCategoryFilter('all')}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer whitespace-nowrap ${
                  categoryFilter === 'all'
                    ? 'bg-slate-900 text-white shadow-2xs'
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                }`}
              >
                全部分类 ({allBrollMaterials.length})
              </button>
              <button
                type="button"
                onClick={() => setCategoryFilter('venue')}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer whitespace-nowrap ${
                  categoryFilter === 'venue'
                    ? 'bg-slate-900 text-white shadow-2xs'
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                }`}
              >
                场地实景 ({allBrollMaterials.filter(m => m.category === 'venue').length})
              </button>
              <button
                type="button"
                onClick={() => setCategoryFilter('lesson')}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer whitespace-nowrap ${
                  categoryFilter === 'lesson'
                    ? 'bg-slate-900 text-white shadow-2xs'
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                }`}
              >
                教学实操 ({allBrollMaterials.filter(m => m.category === 'lesson').length})
              </button>
              <button
                type="button"
                onClick={() => setCategoryFilter('experience')}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer whitespace-nowrap ${
                  categoryFilter === 'experience'
                    ? 'bg-slate-900 text-white shadow-2xs'
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                }`}
              >
                学员体验 ({allBrollMaterials.filter(m => m.category === 'experience' || m.category === 'medical').length})
              </button>
            </div>

            {sub.scene_decision?.broll_category && (
              <span className="text-[11px] text-slate-600 bg-white border border-slate-200 px-2 py-0.5 rounded-md font-medium flex items-center space-x-1 flex-shrink-0 ml-2">
                <Sparkles className="w-3 h-3 text-slate-500" />
                <span>建议：{sub.scene_decision.broll_category === 'venue' ? '场地' : sub.scene_decision.broll_category === 'lesson' ? '教学' : '体验'}空镜</span>
              </span>
            )}
          </div>

          {/* 第 2 栏：地区与公共库筛选（仅场地与教学支持地区划分；学员体验为通用素材不分地区） */}
          {categoryFilter !== 'experience' ? (
            <div className="flex items-center space-x-2 text-xs text-slate-500 pt-0.5">
              <span className="flex items-center space-x-1 text-slate-400 font-medium text-[11px] flex-shrink-0">
                <MapPin className="w-3 h-3" />
                <span>来源筛选:</span>
              </span>

              <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                <button
                  type="button"
                  onClick={() => setRegionFilter('all')}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition cursor-pointer ${
                    regionFilter === 'all'
                      ? 'bg-slate-700 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                  }`}
                >
                  全部地区 ({regionalMaterials.length})
                </button>

                <button
                  type="button"
                  onClick={() => setRegionFilter('public')}
                  className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium transition cursor-pointer ${
                    regionFilter === 'public'
                      ? 'bg-slate-700 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                  }`}
                  title="未绑定特定城市车牌的通用公共素材"
                >
                  <Globe className="w-2.5 h-2.5 text-slate-400" />
                  <span>公共库 ({publicCount})</span>
                </button>

                {/* 已入库地市快捷标签 */}
                {presentRegionsInLibrary.map(reg => {
                  const count = regionalMaterials.filter(m => m.plate_region === reg).length;
                  return (
                    <button
                      key={reg}
                      type="button"
                      onClick={() => setRegionFilter(regionFilter === reg ? 'all' : reg)}
                      className={`px-2 py-0.5 rounded text-[11px] font-medium transition cursor-pointer ${
                        regionFilter === reg
                          ? 'bg-slate-700 text-white'
                          : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
                      }`}
                    >
                      {formatRegionBadge(reg)} ({count})
                    </button>
                  );
                })}

                {/* 更多地市下拉选择 */}
                <select
                  value={presentRegionsInLibrary.includes(regionFilter) ? regionFilter : (regionFilter === 'all' || regionFilter === 'public' ? '' : regionFilter)}
                  onChange={e => setRegionFilter(e.target.value || 'all')}
                  className="text-[11px] bg-white border border-slate-200 rounded px-1.5 py-0.5 text-slate-600 outline-none hover:border-slate-300"
                >
                  <option value="">更多地市...</option>
                  {ZHEJIANG_REGIONS.map(r => (
                    <option key={r.code} value={r.code}>{r.label}</option>
                  ))}
                </select>
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 text-[11px] text-slate-500 pt-0.5">
              <Globe className="w-3 h-3 text-slate-400" />
              <span>学员体验为全通用素材，不区分地域（与素材库完全一致）</span>
            </div>
          )}
        </div>

        {/* 主体双栏区域：左侧素材网格，右侧实时预览与独立双轴精调 */}
        <div className="flex-1 min-h-0 grid grid-cols-12 overflow-hidden bg-slate-50/30">
          {/* 左侧：可视化素材卡片列表 */}
          <div className="col-span-7 border-r border-slate-200/80 overflow-y-auto p-4 space-y-3">
            {filteredMaterials.length === 0 ? (
              <div className="py-20 text-center text-slate-400 text-xs space-y-1">
                <div>暂无符合筛选条件的空镜素材</div>
                <div className="text-[11px] text-slate-400">可切换分类、切换地区，或在素材库中上传</div>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                {filteredMaterials.map(mat => {
                  const isSelected = selectedMatId === mat.id;
                  const isExperience = mat.category === 'experience';
                  const catLabel = mat.category === 'venue' ? '场地' : mat.category === 'lesson' ? '教学' : '学员体验';
                  const badgeLabel = isExperience
                    ? '学员体验'
                    : `${catLabel} · ${mat.plate_region ? mat.plate_region.replace('·', '') : '公共库'}`;

                  return (
                    <div
                      key={mat.id}
                      onClick={() => handleSelectMaterial(mat.id)}
                      className={`group relative rounded-xl overflow-hidden border transition-all cursor-pointer bg-slate-900 flex flex-col ${
                        isSelected
                          ? 'border-slate-900 ring-2 ring-slate-900/30 shadow-sm'
                          : 'border-slate-200/90 hover:border-slate-400 shadow-2xs hover:shadow-xs'
                      }`}
                    >
                      {/* 视频真实画面缩略图，悬停自动播放 */}
                      <div 
                        className="aspect-[9/16] relative flex items-center justify-center overflow-hidden bg-black"
                        onMouseEnter={e => {
                          const v = e.currentTarget.querySelector('video');
                          if (v) {
                            v.currentTime = 0;
                            v.play().catch(() => {});
                          }
                        }}
                        onMouseLeave={e => {
                          const v = e.currentTarget.querySelector('video');
                          if (v) {
                            v.pause();
                            v.currentTime = 0;
                          }
                        }}
                      >
                        <video
                          src={getMediaUrl(mat.filepath)}
                          className="w-full h-full object-contain pointer-events-none"
                          preload="metadata"
                          muted
                          loop
                          playsInline
                        />

                        {/* 分类与地区轻量胶囊 */}
                        <span className="absolute top-1.5 left-1.5 bg-black/65 backdrop-blur-xs text-white/95 text-[10px] font-medium px-1.5 py-0.5 rounded shadow-xs">
                          {badgeLabel}
                        </span>

                        {/* 时长角标 */}
                        <span className="absolute bottom-1.5 right-1.5 bg-black/65 backdrop-blur-xs text-white/90 text-[10px] font-mono px-1.5 py-0.5 rounded shadow-xs">
                          {mat.duration.toFixed(1)}s
                        </span>

                        {/* 选中勾号 */}
                        {isSelected && (
                          <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-slate-900 text-white flex items-center justify-center shadow-md">
                            <Check className="w-3.5 h-3.5" />
                          </div>
                        )}
                      </div>

                      {/* 底部文件名（简化展示） */}
                      <div className="p-1.5 bg-white text-[11px] text-slate-700 font-normal truncate" title={mat.filename}>
                        {mat.filename}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 右侧：所选素材视窗与独立双轴参数精调 */}
          <div className="col-span-5 p-4 flex flex-col justify-between overflow-y-auto bg-white">
            {selectedMaterial ? (
              <div className="flex flex-col h-full space-y-3">
                {/* 视频视窗 */}
                <div className="relative aspect-[9/16] max-h-[210px] mx-auto bg-black rounded-xl overflow-hidden shadow-xs flex items-center justify-center border border-slate-200 flex-shrink-0">
                  <video
                    ref={videoRef}
                    src={getMediaUrl(selectedMaterial.filepath)}
                    className="w-full h-full object-contain"
                    onTimeUpdate={handleTimeUpdate}
                    onEnded={() => setIsPlaying(false)}
                    playsInline
                  />

                  {/* 居中播放/暂停按钮 */}
                  <button
                    type="button"
                    onClick={handleTogglePlay}
                    className="absolute inset-0 flex items-center justify-center bg-black/20 hover:bg-black/30 transition-colors group cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center backdrop-blur-xs group-hover:scale-105 group-hover:bg-slate-900 transition-all shadow-md">
                      {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5 fill-current" />}
                    </div>
                  </button>

                  <div className="absolute bottom-1.5 left-1.5 right-1.5 flex items-center justify-between text-[10px] font-mono text-white/90 bg-black/60 backdrop-blur-xs px-2 py-0.5 rounded">
                    <span>进度: {previewTime.toFixed(2)}s</span>
                    <span>总长: {materialTotalDuration.toFixed(2)}s</span>
                  </div>
                </div>

                {/* 独立双轴控制卡片 */}
                <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-200/80 space-y-3">
                  {/* 1. 画中画持续时长控制轴（与 In 点互不影响） */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-800 flex items-center space-x-1">
                        <Clock className="w-3.5 h-3.5 text-slate-600" />
                        <span>持续时长 (时间轴):</span>
                      </label>
                      <div className="flex items-center space-x-1.5">
                        <button
                          type="button"
                          onClick={() => handleDurationChange(defaultSubDuration)}
                          className="inline-flex items-center space-x-0.5 text-[10px] text-slate-500 hover:text-slate-800 hover:underline cursor-pointer"
                          title={`重置为原句字幕时长 ${defaultSubDuration.toFixed(2)}s`}
                        >
                          <RotateCcw className="w-2.5 h-2.5" />
                          <span>重置原长</span>
                        </button>
                        <div className="flex items-center space-x-0.5">
                          <input
                            type="number"
                            step="0.05"
                            min="0.2"
                            max={maxAllowedDuration}
                            value={clipDuration}
                            onChange={e => {
                              const val = parseFloat(e.target.value) || 0.2;
                              handleDurationChange(val);
                            }}
                            className="w-14 px-1 py-0.5 text-xs font-mono font-semibold text-slate-900 bg-white border border-slate-300 rounded text-center outline-none focus:border-slate-800"
                          />
                          <span className="text-xs text-slate-500 font-mono">s</span>
                        </div>
                      </div>
                    </div>

                    {/* 时长滑动条 */}
                    <div className="space-y-0.5">
                      <input
                        type="range"
                        min="0.2"
                        max={maxAllowedDuration}
                        step="0.05"
                        value={clipDuration}
                        onChange={e => handleDurationChange(parseFloat(e.target.value))}
                        className="w-full accent-slate-800 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                        <span>0.2s</span>
                        <span>最大可用: {maxAllowedDuration.toFixed(2)}s</span>
                      </div>
                    </div>

                    {/* 防冲突限制提示 */}
                    {nextBroll ? (
                      <div className="flex items-start space-x-1.5 text-[11px] text-amber-900 bg-amber-50/80 border border-amber-200/70 px-2 py-1 rounded-md">
                        <ShieldAlert className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
                        <div className="leading-tight">
                          后置分镜将于 <span className="font-mono font-semibold">{formatExactTime(nextBroll.start_time)}</span> 切入，时长已限制在 <span className="font-mono font-semibold">{maxConflictDuration.toFixed(2)}s</span> 内防冲突。
                        </div>
                      </div>
                    ) : (
                      <div className="text-[10px] text-slate-500 bg-slate-100/80 px-2 py-0.5 rounded">
                        ✓ 后续无分镜重叠，可用至素材末尾 ({maxAllowedDuration.toFixed(2)}s)
                      </div>
                    )}
                  </div>

                  <div className="border-t border-slate-200/60" />

                  {/* 2. 素材裁剪起始位置 (In 点) 控制轴（与持续时长互不影响） */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-800 flex items-center space-x-1">
                        <Scissors className="w-3.5 h-3.5 text-slate-600" />
                        <span>素材裁剪起点 (In 点):</span>
                      </label>
                      <div className="flex items-center space-x-0.5">
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          max={materialTotalDuration}
                          value={sourceInPoint}
                          onChange={e => {
                            const val = parseFloat(e.target.value) || 0;
                            handleInPointChange(val);
                          }}
                          className="w-14 px-1 py-0.5 text-xs font-mono font-semibold text-slate-900 bg-white border border-slate-300 rounded text-center outline-none focus:border-slate-800"
                        />
                        <span className="text-xs text-slate-500 font-mono">s</span>
                      </div>
                    </div>

                    {/* In 点滑动条：固定全长 materialTotalDuration，不受持续时长影响 */}
                    <div className="space-y-0.5">
                      <input
                        type="range"
                        min="0"
                        max={materialTotalDuration || 0.1}
                        step="0.05"
                        value={sourceInPoint}
                        onChange={e => handleInPointChange(parseFloat(e.target.value))}
                        className="w-full accent-slate-800 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                        <span>0.0s</span>
                        <span>素材总长: {materialTotalDuration.toFixed(2)}s</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 截取时间区间说明 */}
                <div className="text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200/80 space-y-1 font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">素材截取:</span>
                    <span className="text-slate-800 font-semibold">{sourceInPoint.toFixed(2)}s ~ {Math.min(materialTotalDuration, sourceInPoint + clipDuration).toFixed(2)}s</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">时间轴展现:</span>
                    <span className="text-slate-800 font-semibold">{formatExactTime(timelineStart)} ~ {formatExactTime(timelineStart + clipDuration)} ({clipDuration.toFixed(2)}s)</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400 space-y-2">
                <Video className="w-10 h-10 text-slate-300" />
                <p className="text-xs">请在左侧点击挑选一个心仪的空镜视频</p>
                <p className="text-[11px] text-slate-400">支持按地区或通用公共库精准筛选</p>
              </div>
            )}
          </div>
        </div>

        {/* Footer 底部控制栏 */}
        <div className="px-5 py-3 border-t border-slate-200 bg-white flex items-center justify-between flex-shrink-0">
          <div>
            {existingBroll && (
              <button
                type="button"
                onClick={handleRemove}
                className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 transition-colors cursor-pointer"
                title="移除当前字幕配置的分镜"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>移除分镜</span>
              </button>
            )}
          </div>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={!selectedMatId}
              className="px-5 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-30 transition-colors shadow-2xs cursor-pointer"
            >
              确定使用此分镜 ({clipDuration.toFixed(2)}s)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
