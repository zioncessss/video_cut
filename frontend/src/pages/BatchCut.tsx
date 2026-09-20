import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  API_BASE,
  getMediaUrl,
  fetchHardwareMetrics,
  fetchAllProjects,
  uploadAndBatchCut,
  openFolder,
  deleteProject,
  batchDeleteProjects,
  renderProject,
  ProjectSummary
} from '../services/api';
import { useDialog } from '../components/common/CustomDialog';
import {
  Cpu,
  Play,
  Film,
  FolderOpen,
  Upload,
  Plus,
  Clock,
  X,
  ExternalLink,
  RefreshCw,
  Sparkles,
  ListOrdered,
  LayoutGrid,
  Trash2,
  CheckSquare,
  Square,
  Check,
  Zap
} from 'lucide-react';

interface BatchCutProps {
  onNavigateToEditor?: (projectId: string, materialId?: string) => void;
}

const ITEM_STATUS_META: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'bg-gray-100 text-gray-500' },
  running: { label: '剪辑中', cls: 'bg-indigo-50 text-indigo-600 animate-pulse' },
  completed: { label: '已完成', cls: 'bg-emerald-50 text-emerald-600' },
  failed: { label: '失败', cls: 'bg-red-50 text-red-600' },
};

export const BatchCut: React.FC<BatchCutProps> = ({ onNavigateToEditor }) => {
  const { showAlert, showToast: showGlobalToast } = useDialog();
  const [hardware, setHardware] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [jobDetails, setJobDetails] = useState<Record<string, any>>({});
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeTab, setActiveTab] = useState<'gallery' | 'queue'>('gallery');

  // 批量参数与上传
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [batchAspectRatio, setBatchAspectRatio] = useState<'9:16' | '16:9'>('9:16');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);

  // 弹窗成片预览播放
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [previewVideoTitle, setPreviewVideoTitle] = useState<string>('');

  // 封面容错与卡片独立渲染态
  const [imageErrors, setImageErrors] = useState<Record<string, boolean>>({});
  const [renderingProjectIds, setRenderingProjectIds] = useState<Record<string, boolean>>({});

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleRenderProject = async (projId: string) => {
    setRenderingProjectIds(prev => ({ ...prev, [projId]: true }));
    try {
      await renderProject(projId);
      showGlobalToast('成片压制完成！', 'success');
      await loadData();
    } catch (err: any) {
      showAlert({ title: '成片合成失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setRenderingProjectIds(prev => ({ ...prev, [projId]: false }));
    }
  };

  const loadData = async () => {
    try {
      const [resJobs, projs] = await Promise.all([
        axios.get(`${API_BASE}/batch/jobs`).catch(() => ({ data: { data: [] } })),
        fetchAllProjects().catch(() => [])
      ]);

      const list = resJobs.data?.data || [];
      setJobs(list);
      setProjects(projs);

      // 拉取运行中或最近的批次详情
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
      setShowUploadModal(true);
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
      setShowUploadModal(true);
    }
  };

  const removeSelectedFile = (idx: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleStartBatchCut = async () => {
    if (selectedFiles.length === 0) return;
    setSubmitting(true);
    try {
      await uploadAndBatchCut(selectedFiles, batchAspectRatio, undefined, 1.0);
      setSelectedFiles([]);
      setShowUploadModal(false);
      setActiveTab('queue');
      await loadData();
    } catch (err: any) {
      showAlert({ title: '启动批量剪辑失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenFolder = async (projectId?: string) => {
    try {
      await openFolder(undefined, projectId);
    } catch (e) {
      showGlobalToast('打开专属目录失败，请检查系统权限', 'error');
    }
  };

  // 删除功能相关状态与交互
  const [projectToDelete, setProjectToDelete] = useState<ProjectSummary | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [isBatchDeleting, setIsBatchDeleting] = useState<boolean>(false);
  const [deleteWithFiles, setDeleteWithFiles] = useState<boolean>(true);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [batchMode, setBatchMode] = useState<boolean>(false);
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<any>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  const handleSingleDeleteClick = (proj: ProjectSummary) => {
    setProjectToDelete(proj);
    setIsBatchDeleting(false);
    setDeleteWithFiles(true);
    setShowDeleteConfirm(true);
  };

  const handleBatchDeleteClick = () => {
    if (selectedProjectIds.size === 0) return;
    setProjectToDelete(null);
    setIsBatchDeleting(true);
    setDeleteWithFiles(true);
    setShowDeleteConfirm(true);
  };

  const toggleSelectProject = (id: string) => {
    setSelectedProjectIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedProjectIds.size === projects.length) {
      setSelectedProjectIds(new Set());
    } else {
      setSelectedProjectIds(new Set(projects.map(p => p.id)));
    }
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    try {
      if (isBatchDeleting) {
        const ids = Array.from(selectedProjectIds);
        await batchDeleteProjects(ids, deleteWithFiles);
        setProjects(prev => prev.filter(p => !selectedProjectIds.has(p.id)));
        showToast(`已成功删除 ${ids.length} 个成片工程`);
        setSelectedProjectIds(new Set());
        setBatchMode(false);
      } else if (projectToDelete) {
        await deleteProject(projectToDelete.id, deleteWithFiles);
        setProjects(prev => prev.filter(p => p.id !== projectToDelete.id));
        showToast(`已成功删除「${projectToDelete.title}」`);
        setProjectToDelete(null);
      }
      setShowDeleteConfirm(false);
      await loadData();
    } catch (err: any) {
      showAlert({ title: '删除失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (timestamp?: number) => {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  };

  const runningJobs = jobs.filter(j => j.status !== 'finished');

  return (
    <div
      onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4"
    >
      {/* 隐藏上传 input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="video/*,.mp4,.mov,.mkv,.avi,.webm"
        className="hidden"
        onChange={handleFileSelect}
      />

      {/* 1. 顶部生产驾驶舱 Command Bar */}
      <div className="bg-white border border-gray-200/80 rounded-2xl p-3.5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        {/* 左侧：标题与模态 Tabs */}
        <div className="flex items-center space-x-3">
          <div>
            <h1 className="text-base font-bold text-gray-900 tracking-tight flex items-center space-x-2">
              <span>批量混剪</span>
              {runningJobs.length > 0 && (
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-50 text-indigo-600 border border-indigo-100">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 animate-pulse"></span>
                  <span>{runningJobs.length} 批次进行中</span>
                </span>
              )}
            </h1>
          </div>

          {/* 双模态视图切换: 成片画廊 vs 混剪队列 */}
          <div className="inline-flex p-0.5 bg-gray-100 rounded-lg border border-gray-200/80">
            <button
              type="button"
              onClick={() => setActiveTab('gallery')}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                activeTab === 'gallery'
                  ? 'bg-white text-gray-900 shadow-xs font-semibold'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5 text-indigo-600" />
              <span>成片画廊</span>
              <span className="text-[10px] text-gray-400 font-mono">({projects.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('queue')}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                activeTab === 'queue'
                  ? 'bg-white text-gray-900 shadow-xs font-semibold'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <ListOrdered className="w-3.5 h-3.5 text-indigo-600" />
              <span>混剪队列</span>
              {runningJobs.length > 0 && (
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-600"></span>
              )}
            </button>
          </div>
        </div>

        {/* 中间：快速策略控制 (画幅比例) */}
        <div className="flex items-center space-x-2.5 text-xs">
          {/* 画幅比例 */}
          <div className="inline-flex p-0.5 bg-gray-100 rounded-lg border border-gray-200/80">
            <button
              type="button"
              onClick={() => setBatchAspectRatio('9:16')}
              className={`px-2 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                batchAspectRatio === '9:16' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500'
              }`}
            >
              9:16 竖屏
            </button>
            <button
              type="button"
              onClick={() => setBatchAspectRatio('16:9')}
              className={`px-2 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                batchAspectRatio === '16:9' ? 'bg-white text-gray-900 shadow-xs font-semibold' : 'text-gray-500'
              }`}
            >
              16:9 横屏
            </button>
          </div>
        </div>

        {/* 右侧：智能硬件感知调度状态 + 一键上传动作 */}
        <div className="flex items-center space-x-2">
          {hardware && (
            <div
              className="hidden md:flex items-center space-x-1.5 px-3 py-1 bg-indigo-50/50 border border-indigo-100 rounded-lg text-[11px] font-mono text-gray-700"
              title="系统按视频合成与编码真实物理消耗自适应规划的最优并发数"
            >
              <Cpu className="w-3.5 h-3.5 text-indigo-600" />
              <span className="font-semibold text-indigo-700">⚡ 智能并发: {hardware.recommended_concurrency} 路并行</span>
              <span className="text-gray-300">|</span>
              <span className="text-gray-500">{hardware.cpu_cores}核 · {hardware.memory_available_gb}G可用 · {hardware.gpu_accelerator_detected ? 'GPU加速' : 'CPU'}</span>
            </div>
          )}

          <button
            type="button"
            onClick={loadData}
            className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
            title="刷新数据"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>添加口播混剪</span>
          </button>
        </div>
      </div>

      {/* 拖拽吸附提示条 (当用户拖拽文件到窗口时浮现) */}
      {isDragOver && (
        <div className="p-8 border-2 border-dashed border-indigo-500 bg-indigo-50/70 rounded-2xl text-center text-indigo-700 text-xs font-semibold animate-in fade-in">
          松开鼠标立即批量导入口播视频进行混剪
        </div>
      )}

      {/* 2. 成片画廊视图 (Gallery Mode，默认聚焦交付物) */}
      {activeTab === 'gallery' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-gray-500 px-1">
            <span>成片成果总计 {projects.length} 部</span>
            <div className="flex items-center space-x-2">
              {projects.length > 0 && (
                <>
                  {batchMode ? (
                    <div className="flex items-center space-x-1.5 bg-gray-100/80 rounded-xl px-2 py-1">
                      <span className="text-[11px] text-gray-600 font-mono px-1">
                        已选 {selectedProjectIds.size}/{projects.length}
                      </span>
                      <button
                        type="button"
                        onClick={toggleSelectAll}
                        className="px-2 py-0.5 text-[11px] text-gray-600 hover:text-gray-900 hover:bg-white rounded-lg transition-colors cursor-pointer"
                      >
                        {selectedProjectIds.size === projects.length ? '取消全选' : '全选'}
                      </button>
                      <button
                        type="button"
                        disabled={selectedProjectIds.size === 0}
                        onClick={handleBatchDeleteClick}
                        className="flex items-center space-x-1 px-2.5 py-0.5 text-[11px] bg-red-50 hover:bg-red-100 text-red-600 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>删除 ({selectedProjectIds.size})</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setBatchMode(false);
                          setSelectedProjectIds(new Set());
                        }}
                        className="px-2 py-0.5 text-[11px] text-gray-500 hover:text-gray-800 rounded-lg transition-colors cursor-pointer"
                      >
                        退出
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setBatchMode(true)}
                      className="flex items-center space-x-1 text-gray-600 hover:text-gray-900 hover:bg-gray-100 px-2.5 py-1 rounded-lg transition-colors cursor-pointer text-xs font-medium"
                      title="批量管理与删除成片"
                    >
                      <CheckSquare className="w-3.5 h-3.5 text-gray-400" />
                      <span>批量管理</span>
                    </button>
                  )}
                </>
              )}
              <button
                onClick={() => handleOpenFolder()}
                className="flex items-center space-x-1 text-gray-600 hover:text-indigo-600 px-2 py-1 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>打开任务根目录</span>
              </button>
            </div>
          </div>

          {projects.length === 0 ? (
            <div className="py-20 text-center text-gray-400 text-xs border border-gray-200/80 rounded-2xl bg-white shadow-xs">
              <Film className="w-8 h-8 mx-auto mb-2 text-gray-300" />
              <p className="font-medium text-gray-600">暂无已生成的成片</p>
              <p className="text-[11px] mt-1 text-gray-400">
                点击右上角「添加口播混剪」或直接拖入视频文件，流水线即可自动批量生成
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
              {projects.map(proj => {
                const hasOutput = !!proj.output_video_path;
                const videoUrl = hasOutput ? getMediaUrl(proj.output_video_path!) : '';
                const coverUrl = proj.cover_image_path ? getMediaUrl(proj.cover_image_path) : '';
                const isCompleted = proj.status === 'completed';
                const isSelected = selectedProjectIds.has(proj.id);
                const hasValidCover = Boolean(coverUrl && !imageErrors[proj.id]);

                return (
                  <div
                    key={proj.id}
                    onClick={batchMode ? () => toggleSelectProject(proj.id) : undefined}
                    className={`bg-white border rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition-all flex flex-col group relative ${
                      batchMode && isSelected
                        ? 'border-red-400 ring-2 ring-red-400/20'
                        : 'border-gray-200/80'
                    }`}
                  >
                    {/* 封面与 Hover 播放 */}
                    <div className="relative aspect-video bg-gray-900 flex items-center justify-center overflow-hidden">
                      {hasValidCover ? (
                        <img
                          src={coverUrl}
                          alt={proj.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={() => {
                            setImageErrors(prev => ({ ...prev, [proj.id]: true }));
                          }}
                        />
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-slate-850 to-slate-900 text-slate-400 p-3 text-center select-none">
                          <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center mb-1.5 shadow-inner">
                            <Film className="w-4 h-4 text-indigo-400/80" />
                          </div>
                          <span className="text-[11px] font-medium text-slate-300 line-clamp-1 max-w-[90%]">{proj.title}</span>
                          <span className="text-[10px] text-slate-500 font-mono mt-0.5">
                            {isCompleted ? '已就绪' : '草稿 · 待压制'} · {proj.aspect_ratio || '9:16'}
                          </span>
                        </div>
                      )}

                      {/* 批量多选 Checkbox / 状态徽章 */}
                      <div className="absolute top-2 left-2 flex items-center space-x-1.5 z-10">
                        {batchMode && (
                          <div
                            className={`w-5 h-5 rounded flex items-center justify-center transition-all ${
                              isSelected
                                ? 'bg-red-600 text-white shadow-xs'
                                : 'bg-black/60 text-white/70 hover:bg-black/80'
                            }`}
                          >
                            {isSelected ? (
                              <Check className="w-3.5 h-3.5" />
                            ) : (
                              <Square className="w-3 h-3 opacity-60" />
                            )}
                          </div>
                        )}
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium shadow-2xs ${
                          isCompleted
                            ? 'bg-emerald-600 text-white'
                            : proj.status === 'processing'
                            ? 'bg-indigo-600 text-white animate-pulse'
                            : 'bg-gray-800/80 text-gray-200'
                        }`}>
                          {isCompleted ? '已就绪' : proj.status === 'processing' ? '压制中' : '草稿'}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white font-mono">
                          {proj.aspect_ratio || '9:16'}
                        </span>
                      </div>

                      {/* 悬停快捷删除图标 (非批量模式) */}
                      {!batchMode && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSingleDeleteClick(proj);
                          }}
                          className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/60 hover:bg-red-600 text-white/80 hover:text-white opacity-0 group-hover:opacity-100 transition-all cursor-pointer shadow-xs z-10"
                          title="删除该成片"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}

                      {/* 文件体积 */}
                      {proj.output_file_size_mb ? (
                        <div className="absolute bottom-2 right-2 text-[10px] px-1.5 py-0.5 rounded bg-black/70 text-white font-mono">
                          {proj.output_file_size_mb} MB
                        </div>
                      ) : null}

                      {/* 悬停播放遮罩 */}
                      {hasOutput && !batchMode && (
                        <button
                          onClick={() => {
                            setPreviewVideoUrl(videoUrl);
                            setPreviewVideoTitle(proj.title);
                          }}
                          className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white cursor-pointer"
                          title="点击预览播放"
                        >
                          <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white hover:scale-110 transition-transform">
                            <Play className="w-4 h-4 fill-current ml-0.5" />
                          </div>
                        </button>
                      )}
                    </div>

                    {/* 卡片信息与操作按钮 */}
                    <div className="p-3 flex-1 flex flex-col justify-between space-y-2">
                      <div>
                        <h3 className="text-xs font-bold text-gray-900 truncate" title={proj.title}>
                          {proj.title}
                        </h3>
                        <div className="flex items-center space-x-2 text-[10px] text-gray-400 mt-1 font-mono">
                          <Clock className="w-3 h-3 text-gray-400" />
                          <span>{formatDate(proj.updated_at || proj.created_at)}</span>
                          {proj.subtitles && (
                            <span>· {proj.subtitles.length}句</span>
                          )}
                        </div>
                      </div>

                      {/* 快捷动作 */}
                      <div className="pt-2 border-t border-gray-100 flex items-center justify-between gap-1.5 text-[11px]">
                        {hasOutput ? (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenFolder(proj.id);
                            }}
                            className="flex-1 flex items-center justify-center space-x-1 py-1 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600 font-medium transition-colors cursor-pointer"
                            title="打开专属工程文件夹"
                          >
                            <FolderOpen className="w-3 h-3 text-gray-400" />
                            <span>打开目录</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            disabled={renderingProjectIds[proj.id]}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRenderProject(proj.id);
                            }}
                            className="flex-1 flex items-center justify-center space-x-1 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium transition-colors cursor-pointer disabled:opacity-50"
                            title="立即压制并生成成片"
                          >
                            <Zap className={`w-3 h-3 text-emerald-600 ${renderingProjectIds[proj.id] ? 'animate-bounce' : ''}`} />
                            <span>{renderingProjectIds[proj.id] ? '压制中...' : '生成成片'}</span>
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onNavigateToEditor) {
                              onNavigateToEditor(proj.id, proj.talking_head_id);
                            }
                          }}
                          className="flex-1 flex items-center justify-center space-x-1 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium transition-colors cursor-pointer"
                          title="在剪辑工作台中精修调整"
                        >
                          <ExternalLink className="w-3 h-3 text-indigo-600" />
                          <span>进入工作台</span>
                        </button>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSingleDeleteClick(proj);
                          }}
                          className="p-1 rounded-lg bg-gray-50 hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors cursor-pointer"
                          title="删除工程与成片"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 3. 混剪队列视图 (Queue Mode) */}
      {activeTab === 'queue' && (
        <div className="space-y-4">
          {/* 运行中任务 */}
          {runningJobs.length > 0 && (
            <div className="bg-white border border-indigo-100 rounded-2xl p-4 shadow-xs space-y-3">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
                <h3 className="text-xs font-bold text-gray-800">正在执行的批量任务</h3>
              </div>

              {runningJobs.map(j => {
                const pct = j.total_count > 0 ? Math.round((j.completed_count / j.total_count) * 100) : 0;
                const detail = jobDetails[j.job_id];
                return (
                  <div key={j.job_id} className="bg-indigo-50/40 rounded-xl p-3 border border-indigo-100/60">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-mono text-gray-600">批次: {j.job_id.substring(0, 8)}...</span>
                      <span className="font-semibold text-indigo-600">
                        {j.completed_count} / {j.total_count} ({pct}%)
                      </span>
                    </div>
                    <div className="w-full bg-gray-200/80 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-600 h-full transition-all duration-300 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    {detail?.items && (
                      <div className="mt-2.5 space-y-1">
                        {detail.items.map((it: any, idx: number) => {
                          const meta = ITEM_STATUS_META[it.status] || ITEM_STATUS_META.queued;
                          return (
                            <div key={idx} className="flex items-center justify-between text-[11px] bg-white px-2.5 py-1 rounded border border-gray-100 shadow-2xs">
                              <div className="flex items-center space-x-2 truncate">
                                <span className="font-mono text-gray-400">#{idx + 1}</span>
                                <span className="text-gray-700 font-medium truncate">
                                  {it.project_title || it.material_filename || it.material_id}
                                </span>
                                <span className={`px-1.5 py-0.2 rounded text-[10px] ${meta.cls}`}>{meta.label}</span>
                              </div>
                              <span className="text-gray-400 font-mono text-[10px]">{it.progress || 0}%</span>
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

          {/* 历史任务记录 */}
          <div className="bg-white border border-gray-200/80 rounded-2xl p-4 shadow-xs space-y-3">
            <h3 className="text-xs font-bold text-gray-800">
              历史混剪批次 ({jobs.length} 批)
            </h3>

            {jobs.length === 0 ? (
              <div className="py-10 text-center text-xs text-gray-400">暂无混剪任务记录</div>
            ) : (
              <div className="space-y-2.5">
                {jobs.map(j => {
                  const detail = jobDetails[j.job_id];
                  const isDone = j.status === 'finished';
                  return (
                    <div key={j.job_id} className="bg-gray-50/60 rounded-xl p-3 border border-gray-200/60 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono font-medium text-gray-700">批次: {j.job_id.substring(0, 8)}...</span>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                            isDone ? 'bg-emerald-50 text-emerald-600 border border-emerald-200/60' : 'bg-indigo-50 text-indigo-600'
                          }`}>
                            {isDone ? `已完成 ${j.completed_count}/${j.total_count}` : `处理中 ${j.completed_count}/${j.total_count}`}
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
                        <div className="space-y-1 pt-1">
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
                                      className="text-indigo-600 hover:text-indigo-700 flex items-center space-x-1 cursor-pointer"
                                    >
                                      <span>工作台</span>
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
        </div>
      )}

      {/* 4. 上传与启动批剪弹窗 */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full border border-gray-200 shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center space-x-2">
                <Upload className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-gray-900">批量混剪任务确认</h3>
                <span className="text-xs text-gray-400 font-mono">({selectedFiles.length} 个视频)</span>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 待剪辑列表 */}
            <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between px-3 py-1.5 bg-gray-50 rounded-lg text-xs border border-gray-200/60">
                  <div className="flex items-center space-x-2 truncate">
                    <Film className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                    <span className="truncate text-gray-700 font-medium">{file.name}</span>
                    <span className="text-[10px] text-gray-400 font-mono flex-shrink-0">
                      ({(file.size / (1024 * 1024)).toFixed(1)} MB)
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

            {/* 策略核准 */}
            <div className="bg-gray-50 rounded-xl p-3 text-xs space-y-2 border border-gray-100">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">画幅比例</span>
                <span className="font-semibold text-gray-800">{batchAspectRatio === '9:16' ? '9:16 竖屏' : '16:9 横屏'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">并发调度</span>
                <span className="font-mono text-indigo-700 font-semibold">⚡ {hardware?.recommended_concurrency || 2} 任务自适应并行 (智能调度)</span>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="px-4 py-2 rounded-xl text-xs text-gray-600 hover:bg-gray-100 font-medium transition-colors cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleStartBatchCut}
                disabled={submitting || selectedFiles.length === 0}
                className="flex items-center space-x-1.5 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-semibold shadow-xs disabled:opacity-50 transition-colors cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{submitting ? '提交中...' : `开始剪辑 (${selectedFiles.length} 个视频)`}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. 成片全屏播放模态框 */}
      {previewVideoUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-gray-900 rounded-2xl overflow-hidden max-w-2xl w-full border border-gray-800 shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 text-white">
              <div className="flex items-center space-x-2 truncate">
                <Film className="w-4 h-4 text-indigo-400" />
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

      {/* 6. 删除确认模态框 */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 border border-gray-100 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-start space-x-3">
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center flex-shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-bold text-gray-900">
                  {isBatchDeleting ? `批量删除 ${selectedProjectIds.size} 部成片工程` : '确认删除成片工程'}
                </h3>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                  {isBatchDeleting ? (
                    `确定要彻底删除已选中的 ${selectedProjectIds.size} 个剪辑工程吗？此操作不可撤销。`
                  ) : (
                    <>
                      确定要删除工程「<span className="font-semibold text-gray-800">{projectToDelete?.title}</span>」吗？
                    </>
                  )}
                </p>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-3 border border-gray-100">
              <label className="flex items-center space-x-2 text-xs text-gray-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={deleteWithFiles}
                  onChange={e => setDeleteWithFiles(e.target.checked)}
                  className="rounded text-red-600 focus:ring-red-500"
                />
                <span>同时清理本地磁盘成片文件与专属任务目录（释放磁盘空间）</span>
              </label>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setProjectToDelete(null);
                }}
                className="px-4 py-2 rounded-xl text-xs text-gray-600 hover:bg-gray-100 font-medium transition-colors cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 active:bg-red-800 text-white text-xs font-semibold shadow-xs disabled:opacity-50 transition-colors cursor-pointer"
              >
                {isDeleting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>正在删除...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>确认删除</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. 轻量 Toast 提示 */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-gray-900 text-white text-xs px-4 py-2.5 rounded-xl shadow-lg border border-gray-800 flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-2">
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
};
