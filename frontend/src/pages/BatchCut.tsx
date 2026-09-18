import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  API_BASE,
  getMediaUrl,
  fetchHardwareMetrics,
  fetchAllProjects,
  uploadAndBatchCut,
  openFolder,
  ProjectSummary
} from '../services/api';
import {
  Cpu,
  HardDrive,
  Layers,
  Play,
  Film,
  FolderOpen,
  AlertCircle,
  Upload,
  Plus,
  Clock,
  X,
  ExternalLink,
  RefreshCw,
  Sparkles
} from 'lucide-react';

interface BatchCutProps {
  onNavigateToEditor?: (projectId: string, materialId?: string) => void;
}

const ITEM_STATUS_META: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'bg-gray-100 text-gray-500' },
  running: { label: '剪辑中', cls: 'bg-blue-50 text-blue-600 animate-pulse' },
  completed: { label: '已完成', cls: 'bg-emerald-50 text-emerald-600' },
  failed: { label: '失败', cls: 'bg-red-50 text-red-600' },
};

export const BatchCut: React.FC<BatchCutProps> = ({ onNavigateToEditor }) => {
  const [hardware, setHardware] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [jobDetails, setJobDetails] = useState<Record<string, any>>({});
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [showHistoryJobs, setShowHistoryJobs] = useState<boolean>(true);

  // 上传与批处理状态
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [batchAspectRatio, setBatchAspectRatio] = useState<'9:16' | '16:9'>('9:16');
  const [customConcurrency, setCustomConcurrency] = useState<number | ''>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  // 弹窗成片预览播放
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [previewVideoTitle, setPreviewVideoTitle] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    try {
      const [resJobs, projs] = await Promise.all([
        axios.get(`${API_BASE}/batch/jobs`).catch(() => ({ data: { data: [] } })),
        fetchAllProjects().catch(() => [])
      ]);

      const list = resJobs.data?.data || [];
      setJobs(list);
      setProjects(projs);

      // 拉取每个任务明细
      const details: Record<string, any> = {};
      await Promise.all(
        list.slice(0, 10).map(async (j: any) => {
          try {
            const d = await axios.get(`${API_BASE}/batch/jobs/${j.job_id}`);
            details[j.job_id] = d.data.data;
          } catch (e) {}
        })
      );
      setJobDetails(details);
    } catch (e) {
      console.error('[BatchCut] 加载数据失败:', e);
    }
  };

  useEffect(() => {
    fetchHardwareMetrics().then(setHardware).catch(() => {});
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      setSelectedFiles(prev => [...prev, ...files]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files).filter(f =>
        f.type.startsWith('video/') || /\.(mp4|mov|mkv|avi|webm)$/i.test(f.name)
      );
      setSelectedFiles(prev => [...prev, ...files]);
    }
  };

  const removeSelectedFile = (idx: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleStartBatchCut = async () => {
    if (selectedFiles.length === 0) return;
    setSubmitting(true);
    try {
      const conc = typeof customConcurrency === 'number' ? customConcurrency : undefined;
      await uploadAndBatchCut(selectedFiles, batchAspectRatio, conc);
      setSelectedFiles([]);
      await loadData();
    } catch (err: any) {
      alert(`启动批量混剪失败: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenFolder = async (projectId?: string) => {
    try {
      await openFolder(undefined, projectId);
    } catch (e) {
      alert('打开专属目录失败，请检查系统路径权限');
    }
  };

  const formatDate = (timestamp?: number) => {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <span>批量混剪与生产调度中心</span>
            <span className="text-xs font-normal px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full border border-blue-200">
              口播直剪 · 独立目录 · 成片网格
            </span>
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            口播视频直接上传并分配专属任务目录（日期+时间），全链路自动化流水线无人值守生产，成片网格一览无余。
          </p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center space-x-1 px-3 py-1.5 bg-white border border-gray-200 rounded-xl text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-50 shadow-xs transition-all cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>刷新数据</span>
        </button>
      </div>

      {/* 1. 口播视频批量拖拽上传与任务启动中心 */}
      <div className="bg-white border border-gray-200/80 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Upload className="w-4 h-4 text-blue-600" />
            <h2 className="text-sm font-bold text-gray-800">上传待剪辑口播视频 (自动分配独立工程目录)</h2>
          </div>
          <div className="flex items-center space-x-3 text-xs">
            {/* 比例选择 */}
            <div className="flex items-center space-x-1 bg-gray-100 p-0.5 rounded-lg">
              <button
                type="button"
                onClick={() => setBatchAspectRatio('9:16')}
                className={`px-2 py-1 rounded text-xs font-medium cursor-pointer transition-all ${
                  batchAspectRatio === '9:16' ? 'bg-white text-blue-600 shadow-xs' : 'text-gray-500'
                }`}
              >
                9:16 竖屏
              </button>
              <button
                type="button"
                onClick={() => setBatchAspectRatio('16:9')}
                className={`px-2 py-1 rounded text-xs font-medium cursor-pointer transition-all ${
                  batchAspectRatio === '16:9' ? 'bg-white text-blue-600 shadow-xs' : 'text-gray-500'
                }`}
              >
                16:9 横屏
              </button>
            </div>

            {/* 并发设定 */}
            <div className="flex items-center space-x-1 text-gray-500">
              <span>并发数:</span>
              <input
                type="number"
                min="1"
                max="8"
                placeholder={hardware?.recommended_concurrency ? String(hardware.recommended_concurrency) : '自动'}
                value={customConcurrency}
                onChange={e => setCustomConcurrency(e.target.value ? parseInt(e.target.value) : '')}
                className="w-14 px-2 py-1 text-xs border border-gray-200 rounded-md text-center focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {/* 拖拽上传触发框 */}
        <div
          onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer ${
            isDragOver
              ? 'border-blue-500 bg-blue-50/50'
              : 'border-gray-200 hover:border-blue-400 bg-gray-50/50 hover:bg-white'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="video/*,.mp4,.mov,.mkv,.avi,.webm"
            className="hidden"
            onChange={handleFileSelect}
          />
          <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <Plus className="w-5 h-5" />
          </div>
          <p className="text-xs font-semibold text-gray-700">
            点击或拖拽口播视频文件至此处（支持多选批量上传）
          </p>
          <p className="text-[11px] text-gray-400 mt-1">
            支持 MP4、MOV、MKV、AVI，上传后每个视频自动创建独立目录归档，进入后台流水线执行
          </p>
        </div>

        {/* 待上传视频列表与开剪按钮 */}
        {selectedFiles.length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-700">
                已选中待剪辑视频 ({selectedFiles.length} 个):
              </span>
              <button
                type="button"
                onClick={() => setSelectedFiles([])}
                className="text-[11px] text-gray-400 hover:text-red-500 cursor-pointer"
              >
                清空选择
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-36 overflow-y-auto mb-3">
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between px-2.5 py-1.5 bg-gray-50 rounded-lg text-xs border border-gray-200/60">
                  <div className="flex items-center space-x-2 truncate">
                    <Film className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                    <span className="truncate text-gray-700">{file.name}</span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0">
                      ({(file.size / (1024 * 1024)).toFixed(1)}MB)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeSelectedFile(idx)}
                    className="text-gray-400 hover:text-red-500 cursor-pointer p-0.5"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={handleStartBatchCut}
                disabled={submitting}
                className="flex items-center space-x-2 px-5 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold shadow-sm shadow-blue-500/20 cursor-pointer disabled:opacity-50 transition-all"
              >
                <Sparkles className="w-4 h-4" />
                <span>{submitting ? '正在提交批处理任务...' : `开始批量智能混剪 (${selectedFiles.length} 个)`}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 2. 硬件资源与并发调度监控 */}
      {hardware && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-xs flex items-center space-x-3">
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400 font-medium">CPU 核心 / 负载</span>
              <p className="text-xs font-bold text-gray-800">{hardware.cpu_cores} 核 · {hardware.cpu_percent}%</p>
            </div>
          </div>

          <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-xs flex items-center space-x-3">
            <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-lg">
              <HardDrive className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400 font-medium">可用内存</span>
              <p className="text-xs font-bold text-gray-800">{hardware.memory_available_gb}G / {hardware.memory_total_gb}G</p>
            </div>
          </div>

          <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-xs flex items-center space-x-3">
            <div className="p-2.5 bg-amber-50 text-amber-600 rounded-lg">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400 font-medium">GPU 硬件加速</span>
              <p className="text-xs font-bold text-gray-800 uppercase">{hardware.gpu_accelerator_detected || 'CPU 软解压'}</p>
            </div>
          </div>

          <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-xs flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
              <Play className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400 font-medium">系统安全并发槽位</span>
              <p className="text-xs font-bold text-indigo-600">{hardware.recommended_concurrency} 进程并发</p>
            </div>
          </div>
        </div>
      )}

      {/* 3.1 正在运行的批处理作业进度条与状态看板 */}
      {jobs.length > 0 && jobs.some(j => j.status !== 'finished') && (
        <div className="bg-white border border-blue-100 rounded-2xl p-4 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
              <h3 className="text-xs font-bold text-gray-800">正在处理的批量剪辑作业</h3>
            </div>
          </div>

          {jobs.filter(j => j.status !== 'finished').map(j => {
            const pct = j.total_count > 0 ? Math.round((j.completed_count / j.total_count) * 100) : 0;
            const detail = jobDetails[j.job_id];
            return (
              <div key={j.job_id} className="bg-blue-50/40 rounded-xl p-3 border border-blue-100/60">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-mono text-gray-600">任务批次: {j.job_id.substring(0, 8)}...</span>
                  <span className="font-semibold text-blue-600">
                    进度: {j.completed_count} / {j.total_count} ({pct}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200/80 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-blue-600 h-full transition-all duration-300 rounded-full"
                    style={{ width: `${pct}%` }}
                  />
                </div>

                {detail?.items && (
                  <div className="mt-2.5 space-y-1">
                    {detail.items.map((it: any, idx: number) => {
                      const meta = ITEM_STATUS_META[it.status] || ITEM_STATUS_META.queued;
                      return (
                        <div key={idx} className="flex items-center justify-between text-[11px] bg-white/70 px-2.5 py-1 rounded">
                          <div className="flex items-center space-x-2 truncate">
                            <span className="font-mono text-gray-400">#{idx + 1}</span>
                            <span className="text-gray-700 font-medium truncate">
                              {it.project_title || it.material_filename || it.material_id}
                            </span>
                            <span className={`px-1.5 py-0.2 rounded text-[10px] ${meta.cls}`}>{meta.label}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-gray-400 font-mono">
                            <span>{it.progress || 0}%</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 3.2 历史已剪辑完成的批处理任务记录看板 */}
      {jobs.filter(j => j.status === 'finished').length > 0 && (
        <div className="bg-white border border-gray-200/80 rounded-2xl p-4 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-emerald-600" />
              <h3 className="text-xs font-bold text-gray-800">
                历史已剪辑任务记录 ({jobs.filter(j => j.status === 'finished').length} 个批次)
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setShowHistoryJobs(!showHistoryJobs)}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
            >
              {showHistoryJobs ? '收起历史批次' : '展开查看任务明细'}
            </button>
          </div>

          {showHistoryJobs && (
            <div className="space-y-3 pt-1">
              {jobs.filter(j => j.status === 'finished').map(j => {
                const detail = jobDetails[j.job_id];
                return (
                  <div key={j.job_id} className="bg-gray-50/70 rounded-xl p-3 border border-gray-200/60 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-medium text-gray-700">批次: {j.job_id.substring(0, 8)}...</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium border border-emerald-200/60">
                          已完成 {j.completed_count} / {j.total_count}
                        </span>
                        <span className="text-[10px] text-gray-400 font-mono">并发: {j.concurrency}</span>
                      </div>
                      {j.created_at && (
                        <span className="text-[11px] text-gray-400 font-mono">
                          {formatDate(j.created_at)}
                        </span>
                      )}
                    </div>

                    {detail?.items && (
                      <div className="space-y-1.5 pt-1">
                        {detail.items.map((it: any, idx: number) => {
                          const meta = ITEM_STATUS_META[it.status] || ITEM_STATUS_META.completed;
                          return (
                            <div key={idx} className="flex items-center justify-between text-[11px] bg-white px-3 py-1.5 rounded-lg border border-gray-100 shadow-2xs">
                              <div className="flex items-center space-x-2 truncate">
                                <span className="font-mono text-gray-400">#{idx + 1}</span>
                                <span className="text-gray-700 font-medium truncate max-w-xs sm:max-w-md">
                                  {it.project_title || it.material_filename || it.material_id}
                                </span>
                                <span className={`px-1.5 py-0.2 rounded text-[10px] ${meta.cls}`}>{meta.label}</span>
                              </div>
                              <div className="flex items-center space-x-3 text-gray-400 font-mono flex-shrink-0">
                                {it.project_id && onNavigateToEditor && (
                                  <button
                                    type="button"
                                    onClick={() => onNavigateToEditor(it.project_id, it.material_id)}
                                    className="text-blue-600 hover:text-blue-700 hover:underline flex items-center space-x-1 cursor-pointer"
                                  >
                                    <span>在编辑器中打开</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 4. 成片卡片网格 (Card Grid) - 彻底替代原下拉框 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Film className="w-4 h-4 text-purple-600" />
            <h2 className="text-sm font-bold text-gray-900">剪辑成片与成果库 (一个个排列的视频卡片)</h2>
            <span className="text-xs text-gray-400 font-mono">({projects.length} 个视频工程)</span>
          </div>
          <button
            onClick={() => handleOpenFolder()}
            className="flex items-center space-x-1 text-xs text-gray-600 hover:text-blue-600 cursor-pointer"
          >
            <FolderOpen className="w-3.5 h-3.5" />
            <span>浏览根目录 storage/tasks</span>
          </button>
        </div>

        {projects.length === 0 ? (
          <div className="py-16 text-center text-gray-400 text-xs border border-gray-200/80 rounded-2xl bg-white shadow-xs">
            <Film className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p className="font-medium text-gray-500">暂无剪辑好的视频成片</p>
            <p className="text-[11px] mt-1 text-gray-400">
              在上方拖入待剪口播视频，点击「开始批量智能混剪」即可一键自动生成
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {projects.map(proj => {
              const hasOutput = !!proj.output_video_path;
              const videoUrl = hasOutput ? getMediaUrl(proj.output_video_path!) : '';
              const coverUrl = proj.cover_image_path ? getMediaUrl(proj.cover_image_path) : '';
              const isCompleted = proj.status === 'completed';

              return (
                <div
                  key={proj.id}
                  className="bg-white border border-gray-200/90 rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition-all flex flex-col group"
                >
                  {/* 卡片封面图/预览区 */}
                  <div className="relative aspect-video bg-gray-900 flex items-center justify-center overflow-hidden">
                    {coverUrl ? (
                      <img
                        src={coverUrl}
                        alt={proj.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-800 to-slate-950 text-gray-400">
                        <Film className="w-8 h-8 mb-1 text-gray-500" />
                        <span className="text-[10px] font-mono">
                          {proj.aspect_ratio || '9:16'}
                        </span>
                      </div>
                    )}

                    {/* 状态角标 */}
                    <div className="absolute top-2 left-2 flex items-center space-x-1">
                      <span className={`text-[10px] px-2 py-0.5 rounded-md font-medium shadow-xs ${
                        isCompleted
                          ? 'bg-emerald-600 text-white'
                          : proj.status === 'processing'
                          ? 'bg-blue-600 text-white animate-pulse'
                          : 'bg-gray-700/80 text-gray-200'
                      }`}>
                        {isCompleted ? '剪辑完成' : proj.status === 'processing' ? '剪辑中' : '草稿'}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-black/60 text-white font-mono">
                        {proj.aspect_ratio || '9:16'}
                      </span>
                    </div>

                    {/* 时长与大小 */}
                    {proj.output_file_size_mb ? (
                      <div className="absolute bottom-2 right-2 text-[10px] px-1.5 py-0.5 rounded bg-black/70 text-white font-mono">
                        {proj.output_file_size_mb} MB
                      </div>
                    ) : null}

                    {/* 悬浮播放成片遮罩按钮 */}
                    {hasOutput && (
                      <button
                        onClick={() => {
                          setPreviewVideoUrl(videoUrl);
                          setPreviewVideoTitle(proj.title);
                        }}
                        className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white cursor-pointer"
                        title="点击播放成片"
                      >
                        <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white hover:scale-110 transition-transform">
                          <Play className="w-5 h-5 fill-current ml-0.5" />
                        </div>
                      </button>
                    )}
                  </div>

                  {/* 卡片详情信息 */}
                  <div className="p-3.5 flex-1 flex flex-col justify-between space-y-2.5">
                    <div>
                      <h3 className="text-xs font-bold text-gray-800 truncate" title={proj.title}>
                        {proj.title}
                      </h3>
                      {proj.task_dir && (
                        <p className="text-[10px] text-gray-400 font-mono truncate mt-0.5" title={proj.task_dir}>
                          📁 {proj.task_dir.split('/').pop()}
                        </p>
                      )}
                      <div className="flex items-center space-x-2 text-[10px] text-gray-400 mt-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(proj.updated_at || proj.created_at)}</span>
                        {proj.subtitles && (
                          <span>· {proj.subtitles.length} 句字幕</span>
                        )}
                      </div>
                    </div>

                    {/* 快捷动作按钮组 */}
                    <div className="pt-2 border-t border-gray-100 flex items-center justify-between gap-1.5">
                      {/* 打开专属独立文件夹 */}
                      <button
                        type="button"
                        onClick={() => handleOpenFolder(proj.id)}
                        className="flex-1 flex items-center justify-center space-x-1 py-1 px-2 rounded-lg bg-gray-50 hover:bg-gray-100 text-[11px] text-gray-700 font-medium transition-colors cursor-pointer"
                        title="在系统文件管理器中打开该视频的专属独立文件夹"
                      >
                        <FolderOpen className="w-3 h-3 text-gray-500" />
                        <span>打开目录</span>
                      </button>

                      {/* 播放成片 */}
                      {hasOutput && (
                        <button
                          type="button"
                          onClick={() => {
                            setPreviewVideoUrl(videoUrl);
                            setPreviewVideoTitle(proj.title);
                          }}
                          className="flex items-center justify-center p-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 transition-colors cursor-pointer"
                          title="播放合成好的最终成片"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                        </button>
                      )}

                      {/* 单点进入剪辑工作台 */}
                      <button
                        type="button"
                        onClick={() => {
                          if (onNavigateToEditor) {
                            onNavigateToEditor(proj.id, proj.talking_head_id);
                          }
                        }}
                        className="flex-1 flex items-center justify-center space-x-1 py-1 px-2 rounded-lg bg-blue-50 hover:bg-blue-100 text-[11px] text-blue-700 font-medium transition-colors cursor-pointer"
                        title="跳转进入剪辑工作台进行精细化调整与人工审核"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>进入工作台</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 5. 成片全屏播放模态框 */}
      {previewVideoUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-gray-900 rounded-2xl overflow-hidden max-w-2xl w-full border border-gray-800 shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 text-white">
              <div className="flex items-center space-x-2 truncate">
                <Film className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-semibold truncate">{previewVideoTitle}</span>
              </div>
              <button
                onClick={() => setPreviewVideoUrl(null)}
                className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-gray-800 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="relative aspect-[9/16] max-h-[70vh] bg-black mx-auto">
              <video
                src={previewVideoUrl}
                controls
                autoPlay
                className="w-full h-full object-contain"
              />
            </div>
            <div className="p-3 bg-gray-950 flex items-center justify-between text-xs text-gray-400">
              <span className="font-mono text-[10px] truncate max-w-md">{previewVideoUrl}</span>
              <button
                onClick={() => setPreviewVideoUrl(null)}
                className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 text-white text-xs cursor-pointer"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
