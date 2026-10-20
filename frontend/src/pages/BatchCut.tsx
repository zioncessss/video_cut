import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  API_BASE,
  getMediaUrl,
  fetchHardwareMetrics,
  fetchAllProjects,
  uploadAndBatchCut,
  importAndBatchCut,
  openFolder,
  deleteProject,
  batchDeleteProjects,
  renderProject,
  cancelBatchJob,
  retryFailedBatchJob,
  ProjectSummary
} from '../services/api';
import { formatRegionBadge } from '../constants/regions';
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
  Zap,
  AlertTriangle,
  RotateCcw,
  MapPin,
  ChevronRight,
  ChevronsUpDown,
  ShieldAlert,
  ShieldCheck
} from 'lucide-react';

interface BatchCutProps {
  onNavigateToEditor?: (projectId: string, materialId?: string) => void;
}

const ITEM_STATUS_META: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'bg-gray-100 text-gray-500' },
  running: { label: '剪辑中', cls: 'bg-indigo-50 text-indigo-600 animate-pulse' },
  completed: { label: '已完成', cls: 'bg-emerald-50 text-emerald-600' },
  failed: { label: '失败', cls: 'bg-red-50 text-red-600' },
  canceled: { label: '已取消', cls: 'bg-gray-100 text-gray-400' },
  interrupted: { label: '已中断', cls: 'bg-amber-50 text-amber-600' },
};

interface BatchFileInputItem {
  name: string;
  size: number;
  path?: string;
  rawFile?: File;
}

export const BatchCut: React.FC<BatchCutProps> = ({ onNavigateToEditor }) => {
  const { showAlert, showToast: showGlobalToast } = useDialog();
  const [hardware, setHardware] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [jobDetails, setJobDetails] = useState<Record<string, any>>({});
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeTab, setActiveTab] = useState<'gallery' | 'queue'>('gallery');

  // 批量参数与上传
  const [selectedFiles, setSelectedFiles] = useState<BatchFileInputItem[]>([]);
  const [batchAspectRatio, setBatchAspectRatio] = useState<'9:16' | '16:9'>('9:16');
  const [batchFilterBannedWords, setBatchFilterBannedWords] = useState<boolean>(() => {
    try {
      return localStorage.getItem('videocut_batch_filter_banned') === 'true';
    } catch {
      return false;
    }
  });

  const toggleBatchFilterBannedWords = (val?: boolean) => {
    setBatchFilterBannedWords(prev => {
      const next = val !== undefined ? val : !prev;
      try {
        localStorage.setItem('videocut_batch_filter_banned', String(next));
      } catch {}
      return next;
    });
  };
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [uploadingState, setUploadingState] = useState<{
    totalFiles: number;
    totalBytes: number;
    loadedBytes: number;
    percent: number;
    filenames: string[];
  } | null>(null);

  // 弹窗成片预览播放
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [previewVideoTitle, setPreviewVideoTitle] = useState<string>('');

  // 封面容错与卡片独立渲染态
  const [imageErrors, setImageErrors] = useState<Record<string, boolean>>({});
  const [imageLoaded, setImageLoaded] = useState<Record<string, boolean>>({});
  const [imageRetryCounts, setImageRetryCounts] = useState<Record<string, number>>({});
  const [imageRetryTimestamps, setImageRetryTimestamps] = useState<Record<string, number>>({});
  const [renderingProjectIds, setRenderingProjectIds] = useState<Record<string, boolean>>({});
  // 批次卡片折叠/展开状态字典 (job_id -> boolean)
  const [expandedJobs, setExpandedJobs] = useState<Record<string, boolean>>({});

  const toggleJobExpanded = (jobId: string, defaultExpanded: boolean = true) => {
    setExpandedJobs(prev => {
      const current = prev[jobId] !== undefined ? prev[jobId] : defaultExpanded;
      const nextVal = !current;
      if (nextVal && !jobDetailsCacheRef.current[jobId]) {
        axios.get(`${API_BASE}/batch/jobs/${jobId}`).then(d => {
          if (d.data?.data && isMountedRef.current) {
            jobDetailsCacheRef.current[jobId] = d.data.data;
            setJobDetails(prevD => ({ ...prevD, [jobId]: d.data.data }));
          }
        }).catch(err => {
          console.warn('[BatchCut] 按需拉取批次详情失败:', err?.message);
        });
      }
      return { ...prev, [jobId]: nextVal };
    });
  };

  const fileInputRef = useRef<HTMLInputElement>(null);
  const jobDetailsCacheRef = useRef<Record<string, any>>({});
  const pollingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef<boolean>(true);

  const handleImageError = (projId: string) => {
    const currentRetries = imageRetryCounts[projId] || 0;
    if (currentRetries < 3) {
      setTimeout(() => {
        if (!isMountedRef.current) return;
        setImageRetryCounts(prev => ({ ...prev, [projId]: currentRetries + 1 }));
        setImageRetryTimestamps(prev => ({ ...prev, [projId]: Date.now() }));
      }, 1500);
    } else {
      setImageErrors(prev => ({ ...prev, [projId]: true }));
    }
  };

  const handleRenderProject = async (projId: string) => {
    setRenderingProjectIds(prev => ({ ...prev, [projId]: true }));
    try {
      await renderProject(projId, undefined, batchFilterBannedWords);
      showGlobalToast('成片压制完成！', 'success');
      await loadData();
    } catch (err: any) {
      showAlert({ title: '成片合成失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setRenderingProjectIds(prev => ({ ...prev, [projId]: false }));
    }
  };

  const loadData = async (forceRefreshDetails = false) => {
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    if (forceRefreshDetails) {
      setImageErrors({});
      setImageRetryCounts({});
      setImageRetryTimestamps({});
    }

    try {
      const [resJobs, projs] = await Promise.all([
        axios.get(`${API_BASE}/batch/jobs`).catch((err) => {
          console.warn('[BatchCut] 拉取混剪批次失败 (可能正在密集编码):', err?.message);
          return null;
        }),
        fetchAllProjects().catch((err) => {
          console.warn('[BatchCut] 拉取工程画廊失败 (可能正在密集编码):', err?.message);
          return null;
        })
      ]);

      if (!isMountedRef.current) return;

      if (resJobs?.data?.data && Array.isArray(resJobs.data.data)) {
        setJobs(resJobs.data.data);
      }
      if (projs && Array.isArray(projs)) {
        setProjects(projs);
      }

      const list = (resJobs?.data?.data && Array.isArray(resJobs.data.data))
        ? resJobs.data.data
        : (jobs || []);

      // 仅拉取未完成或尚未缓存最终详情的批次（全量检测活跃批次，修复 slice(0, 10) 截断缺陷）
      const terminalStatuses = ['finished', 'canceled', 'interrupted'];
      const needFetch = list.filter((j: any) => {
        const cached = jobDetailsCacheRef.current[j.job_id];
        const isTerminal = terminalStatuses.includes(j.status);
        return !cached || !isTerminal || !terminalStatuses.includes(cached.status);
      });

      if (needFetch.length > 0) {
        await Promise.all(
          needFetch.map(async (j: any) => {
            try {
              const d = await axios.get(`${API_BASE}/batch/jobs/${j.job_id}`);
              if (d.data?.data) {
                jobDetailsCacheRef.current[j.job_id] = d.data.data;
              }
            } catch (e) {}
          })
        );
      }

      if (!isMountedRef.current) return;
      setJobDetails({ ...jobDetailsCacheRef.current });

      // 动态自适应轮询间隔：存在进行中任务时 3s 高频刷新，空闲无任务时拉长至 10s
      const hasRunning = list.some((j: any) => !terminalStatuses.includes(j.status));
      const nextInterval = hasRunning ? 3000 : 10000;
      pollingTimerRef.current = setTimeout(() => {
        loadData();
      }, nextInterval);
    } catch (e) {
      console.error('[BatchCut] 加载数据失败:', e);
      if (isMountedRef.current) {
        pollingTimerRef.current = setTimeout(() => {
          loadData();
        }, 10000);
      }
    }
  };

  useEffect(() => {
    isMountedRef.current = true;
    fetchHardwareMetrics().then(setHardware).catch(() => {});
    loadData();
    return () => {
      isMountedRef.current = false;
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
      }
    };
  }, []);

  const handleCloseUploadModal = () => {
    setShowUploadModal(false);
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files: BatchFileInputItem[] = Array.from(e.target.files).map(f => ({
        name: f.name,
        size: f.size,
        path: (f as any).path,
        rawFile: f
      }));
      setSelectedFiles(prev => [...prev, ...files]);
      setShowUploadModal(true);
    }
    // 关键修复：重置 input.value 确保二次选择同一视频文件时 onChange 必能触发
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files).filter(f =>
        f.type.startsWith('video/') || /\.(mp4|mov|mkv|avi|webm)$/i.test(f.name)
      );
      if (files.length > 0) {
        const items: BatchFileInputItem[] = files.map(f => ({
          name: f.name,
          size: f.size,
          path: (f as any).path,
          rawFile: f
        }));
        setSelectedFiles(prev => [...prev, ...items]);
        setShowUploadModal(true);
      }
    }
  };

  const handleAddVideosClick = async () => {
    if ((window as any).electronAPI?.showOpenDialog) {
      try {
        const res = await (window as any).electronAPI.showOpenDialog({
          title: '选择要批量混剪的口播视频',
          filters: [
            { name: '视频文件', extensions: ['mp4', 'mov', 'mkv', 'avi', 'webm'] }
          ],
          properties: ['openFile', 'multiSelections']
        });
        if (!res.canceled && res.filePaths && res.filePaths.length > 0) {
          const items: BatchFileInputItem[] = res.filePaths.map((fp: string) => {
            const filename = fp.replace(/^.*[\\/]/, '');
            return {
              name: filename,
              size: 0,
              path: fp
            };
          });
          setSelectedFiles(prev => [...prev, ...items]);
          setShowUploadModal(true);
          return;
        }
      } catch (err) {
        console.warn('[BatchCut] Electron showOpenDialog 异常，回退文件选择框:', err);
      }
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const removeSelectedFile = (idx: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleStartBatchCut = async () => {
    if (selectedFiles.length === 0) return;
    const itemsToCut = [...selectedFiles];
    const totalBytes = itemsToCut.reduce((sum, f) => sum + (f.size || 0), 0);

    // 1. 0 毫秒即时转场：立即关闭确认弹窗并无缝切到混剪队列，彻底消除假死卡顿
    handleCloseUploadModal();
    setActiveTab('queue');

    setSubmitting(true);
    try {
      const nativePaths = itemsToCut
        .map(f => f.path)
        .filter((p): p is string => typeof p === 'string' && p.length > 0);

      const isAllNative = nativePaths.length === itemsToCut.length && !!(window as any).electronAPI;

      if (isAllNative) {
        setUploadingState({
          totalFiles: itemsToCut.length,
          totalBytes: 0,
          loadedBytes: 0,
          percent: 100,
          filenames: itemsToCut.map(f => f.name)
        });
        const res = await importAndBatchCut(
          nativePaths,
          batchAspectRatio,
          undefined,
          1.0,
          batchFilterBannedWords
        );
        if (res?.job_id) {
          setExpandedJobs(prev => ({ ...prev, [res.job_id]: true }));
        }
        setUploadingState(null);
        await loadData(false);
      } else {
        const rawFiles = itemsToCut
          .map(f => f.rawFile)
          .filter((f): f is File => f instanceof File);

        if (rawFiles.length === 0) {
          throw new Error('未获取到有效的视频文件对象');
        }

        setUploadingState({
          totalFiles: rawFiles.length,
          totalBytes,
          loadedBytes: 0,
          percent: 0,
          filenames: rawFiles.map(f => f.name)
        });

        const res = await uploadAndBatchCut(
          rawFiles,
          batchAspectRatio,
          undefined,
          1.0,
          (pe: any) => {
            const loaded = pe.loaded || 0;
            const total = pe.total || totalBytes || 1;
            const pct = Math.min(99, Math.round((loaded / total) * 100));
            setUploadingState(prev => prev ? {
              ...prev,
              loadedBytes: loaded,
              percent: pct
            } : null);
          },
          batchFilterBannedWords
        );
        if (res?.job_id) {
          setExpandedJobs(prev => ({ ...prev, [res.job_id]: true }));
        }
        setUploadingState(null);
        await loadData(false);
      }
    } catch (err: any) {
      setUploadingState(null);
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

  const [cancelingJobIds, setCancelingJobIds] = useState<Record<string, boolean>>({});
  const [retryingJobIds, setRetryingJobIds] = useState<Record<string, boolean>>({});

  const handleCancelJob = async (jobId: string) => {
    setCancelingJobIds(prev => ({ ...prev, [jobId]: true }));
    delete jobDetailsCacheRef.current[jobId];
    try {
      await cancelBatchJob(jobId);
      showGlobalToast('已取消批量剪辑任务', 'info');
      await loadData(true);
    } catch (err: any) {
      showAlert({ title: '取消批次失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setCancelingJobIds(prev => ({ ...prev, [jobId]: false }));
    }
  };

  const handleRetryFailed = async (jobId: string) => {
    setRetryingJobIds(prev => ({ ...prev, [jobId]: true }));
    delete jobDetailsCacheRef.current[jobId];
    try {
      const res = await retryFailedBatchJob(jobId);
      showGlobalToast(`已将 ${res.retrying_count || '部分'} 个失败条目重新提交混剪`, 'success');
      await loadData(true);
    } catch (err: any) {
      showAlert({ title: '重试失败项失败', message: err?.response?.data?.detail || err.message, type: 'error' });
    } finally {
      setRetryingJobIds(prev => ({ ...prev, [jobId]: false }));
    }
  };

  const runningJobs = jobs.filter(j => j.status === 'running' || j.status === 'queued');

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

        {/* 中间：快速策略控制 (画幅比例 + 违禁词脱敏) */}
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

          {/* 统一违禁词脱敏处理开关 */}
          <button
            type="button"
            onClick={() => toggleBatchFilterBannedWords()}
            title="开启后，批量剪辑成片压制时将统一对字幕执行违禁词合规脱敏替换（如：驾驶证→加驶正，最快→蕞快）"
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-all cursor-pointer ${
              batchFilterBannedWords
                ? 'bg-rose-50 border-rose-200/80 text-rose-700 shadow-xs'
                : 'bg-gray-100 border-gray-200/80 text-gray-500 hover:text-gray-800'
            }`}
          >
            <ShieldAlert className={`w-3.5 h-3.5 ${batchFilterBannedWords ? 'text-rose-600' : 'text-gray-400'}`} />
            <span>违禁词脱敏: {batchFilterBannedWords ? '已开启' : '已关闭'}</span>
          </button>
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
            onClick={() => loadData(true)}
            className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
            title="刷新数据"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={handleAddVideosClick}
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
                const isVertical = proj.aspect_ratio !== '16:9';
                const aspectClass = isVertical ? 'aspect-[3/4]' : 'aspect-video';
                const retryTs = imageRetryTimestamps[proj.id];
                const fullCoverUrl = coverUrl ? (retryTs ? `${coverUrl}?t=${retryTs}` : coverUrl) : '';
                const isLoaded = !!imageLoaded[proj.id];
                const isErrored = !!imageErrors[proj.id];

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
                    <div
                      onClick={hasOutput && !batchMode ? () => {
                        setPreviewVideoUrl(videoUrl);
                        setPreviewVideoTitle(proj.title);
                      } : undefined}
                      className={`relative ${aspectClass} bg-slate-900 flex items-center justify-center overflow-hidden ${hasOutput && !batchMode ? 'cursor-pointer' : ''}`}
                    >
                      {fullCoverUrl && !isErrored ? (
                        <>
                          <img
                            src={fullCoverUrl}
                            alt={proj.title}
                            className={`w-full h-full object-cover group-hover:scale-105 transition-all duration-300 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}
                            onLoad={() => setImageLoaded(prev => ({ ...prev, [proj.id]: true }))}
                            onError={() => handleImageError(proj.id)}
                          />
                          {!isLoaded && (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 text-slate-400 select-none">
                              <div className="w-7 h-7 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mb-2" />
                              <span className="text-[11px] font-medium text-slate-400">载入封面中...</span>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950/60 to-slate-900 text-slate-300 p-3 text-center select-none">
                          <div className="w-9 h-9 rounded-xl bg-white/10 border border-white/15 flex items-center justify-center mb-1.5 shadow-md">
                            <Film className="w-4 h-4 text-indigo-400" />
                          </div>
                          <span className="text-[11px] font-semibold text-white line-clamp-1 max-w-[90%]">{proj.title}</span>
                          <span className="text-[10px] text-indigo-300 font-mono mt-0.5">
                            {isCompleted ? '成片已完成 · 点击直接播放' : proj.status === 'processing' ? '正在智能合成中...' : '初剪草稿'}
                          </span>
                        </div>
                      )}

                      {/* 批量多选 Checkbox / 状态徽章 */}
                      <div className="absolute top-2 left-2 flex items-center space-x-1.5 z-10 pointer-events-none">
                        {batchMode && (
                          <div
                            className={`w-5 h-5 rounded flex items-center justify-center transition-all pointer-events-auto ${
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
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium shadow-2xs flex items-center space-x-1 ${
                          isCompleted
                            ? 'bg-emerald-600 text-white'
                            : proj.status === 'processing'
                            ? 'bg-indigo-600 text-white animate-pulse'
                            : proj.status === 'failed'
                            ? 'bg-red-600 text-white'
                            : 'bg-gray-800/80 text-gray-200'
                        }`}>
                          {isCompleted ? (
                            <>
                              <Check className="w-2.5 h-2.5 inline mr-0.5" />
                              <span>已完成</span>
                            </>
                          ) : proj.status === 'processing' ? (
                            <>
                              <Zap className="w-2.5 h-2.5 inline mr-0.5 animate-bounce" />
                              <span>压制中</span>
                            </>
                          ) : proj.status === 'failed' ? (
                            <>
                              <AlertTriangle className="w-2.5 h-2.5 inline mr-0.5" />
                              <span>失败</span>
                            </>
                          ) : (
                            <span>草稿</span>
                          )}
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
                        <div className="absolute bottom-2 right-2 text-[10px] px-1.5 py-0.5 rounded bg-black/70 text-white font-mono pointer-events-none">
                          {proj.output_file_size_mb} MB
                        </div>
                      ) : null}

                      {/* 悬停播放遮罩 */}
                      {hasOutput && !batchMode && (
                        <div
                          className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white"
                          title="点击预览播放"
                        >
                          <div className="w-11 h-11 rounded-full bg-white/25 backdrop-blur-md border border-white/30 flex items-center justify-center text-white shadow-xl hover:scale-110 transition-transform">
                            <Play className="w-5 h-5 fill-current ml-0.5 text-white" />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* 卡片信息与操作按钮 */}
                    <div className="p-3 flex-1 flex flex-col justify-between space-y-2">
                      <div>
                        <h3 className="text-xs font-bold text-gray-900 truncate" title={proj.title}>
                          {proj.title}
                        </h3>
                        <div className="flex items-center flex-wrap gap-1.5 text-[10px] text-gray-400 mt-1 font-mono">
                          <div className="flex items-center space-x-1">
                            <Clock className="w-3 h-3 text-gray-400" />
                            <span>{formatDate(proj.updated_at || proj.created_at)}</span>
                          </div>
                          {proj.subtitles && (
                            <span>· {proj.subtitles.length}句</span>
                          )}
                          {proj.target_region && (
                            <span className="inline-flex items-center space-x-0.5 px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-sans font-medium">
                              <MapPin className="w-2.5 h-2.5 text-emerald-600" />
                              <span>{formatRegionBadge(proj.target_region)}</span>
                            </span>
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
          {/* 0. 素材极速上传中进度卡片 (秒级即时转场保障) */}
          {uploadingState && (
            <div className="bg-white border border-indigo-200/80 rounded-2xl p-4 shadow-xs space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
                  <span className="font-bold text-gray-800">正在上传素材并压入混剪队列...</span>
                  <span className="font-mono text-indigo-600 font-semibold">({uploadingState.totalFiles} 个视频)</span>
                </div>
                <div className="flex items-center space-x-2 font-mono text-xs">
                  <span className="text-gray-500">
                    {(uploadingState.loadedBytes / (1024 * 1024)).toFixed(1)} MB / {(uploadingState.totalBytes / (1024 * 1024)).toFixed(1)} MB
                  </span>
                  <span className="font-bold text-indigo-600">{uploadingState.percent}%</span>
                </div>
              </div>
              <div className="w-full bg-gray-100 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-600 h-full transition-all duration-200 rounded-full"
                  style={{ width: `${uploadingState.percent}%` }}
                />
              </div>
              <div className="text-[11px] text-gray-400 truncate">
                {uploadingState.filenames.join(' · ')}
              </div>
            </div>
          )}

          {/* 运行中任务 */}
          {runningJobs.length > 0 && (
            <div className="bg-white border border-indigo-100 rounded-2xl p-4 shadow-xs space-y-3">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
                <h3 className="text-xs font-bold text-gray-800">正在执行的批量任务</h3>
              </div>

              {runningJobs.map(j => {
                const finished = j.completed_count + (j.failed_count || 0);
                const pct = j.total_count > 0 ? Math.round((finished / j.total_count) * 100) : 0;
                const detail = jobDetails[j.job_id];
                const isExpanded = expandedJobs[j.job_id] !== undefined ? expandedJobs[j.job_id] : true;
                return (
                  <div key={j.job_id} className="bg-indigo-50/40 rounded-xl p-3 border border-indigo-100/60 transition-all">
                    <div
                      onClick={() => toggleJobExpanded(j.job_id, true)}
                      className="flex items-center justify-between text-xs mb-1.5 cursor-pointer select-none group/hdr hover:opacity-90 transition-opacity"
                    >
                      <div className="flex items-center space-x-1.5">
                        <ChevronRight className={`w-3.5 h-3.5 text-indigo-500 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                        <span className="font-mono text-gray-700 font-medium">批次: {j.job_id.substring(0, 8)}...</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-indigo-600">
                          {finished} / {j.total_count} ({pct}%)
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCancelJob(j.job_id);
                          }}
                          disabled={cancelingJobIds[j.job_id]}
                          className="flex items-center space-x-1 px-2 py-0.5 text-[11px] font-medium text-red-600 hover:text-red-700 bg-white hover:bg-red-50 border border-red-200 rounded-md transition-colors cursor-pointer disabled:opacity-50 shadow-2xs"
                          title="取消此批次后续排队与正在进行的任务"
                        >
                          <X className="w-3 h-3" />
                          <span>{cancelingJobIds[j.job_id] ? '取消中...' : '取消批次'}</span>
                        </button>
                        <span className="text-[10px] text-indigo-500 font-mono ml-1">
                          {isExpanded ? '收起' : `展开 (${j.total_count}项)`}
                        </span>
                      </div>
                    </div>
                    <div className="w-full bg-gray-200/80 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-600 h-full transition-all duration-300 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    {isExpanded && detail?.items && (
                      <div className="mt-2.5 space-y-1.5">
                        {detail.items.map((it: any, idx: number) => {
                          const meta = ITEM_STATUS_META[it.status] || ITEM_STATUS_META.queued;
                          return (
                            <div key={idx} className="bg-white p-2 rounded-lg border border-gray-100 shadow-2xs space-y-1">
                              <div className="flex items-center justify-between text-[11px]">
                                <div className="flex items-center space-x-2 truncate">
                                  <span className="font-mono text-gray-400">#{idx + 1}</span>
                                  <span className="text-gray-700 font-medium truncate">
                                    {it.project_title || it.material_filename || it.material_id}
                                  </span>
                                  <span className={`px-1.5 py-0.2 rounded text-[10px] ${meta.cls}`}>{meta.label}</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                  {it.status === 'running' && it.stage_message && (
                                    <span className="text-[10px] text-indigo-600 font-medium animate-pulse">
                                      {it.stage_message}
                                    </span>
                                  )}
                                  <span className="text-gray-400 font-mono text-[10px]">{it.progress || 0}%</span>
                                </div>
                              </div>
                              {/* 动态进度条 */}
                              {it.status === 'running' && (
                                <div className="w-full bg-gray-100 h-1 rounded-full overflow-hidden">
                                  <div
                                    className="bg-indigo-500 h-full transition-all duration-300 rounded-full"
                                    style={{ width: `${Math.max(5, it.progress || 0)}%` }}
                                  />
                                </div>
                              )}
                              {/* 失败真实原因透出 */}
                              {it.status === 'failed' && it.error && (
                                <div className="text-[10px] text-red-600 bg-red-50/90 px-2 py-0.5 rounded border border-red-100 flex items-center space-x-1" title={it.error}>
                                  <AlertTriangle className="w-3 h-3 flex-shrink-0 text-red-500" />
                                  <span className="truncate">{it.error}</span>
                                </div>
                              )}
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

          {/* 历史任务记录（过滤进行中任务，彻底杜绝上下重复混乱） */}
          {(() => {
            const historicalJobs = jobs.filter(j => j.status !== 'running' && j.status !== 'queued');
            return (
              <div className="bg-white border border-gray-200/80 rounded-2xl p-4 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-gray-800">
                    历史混剪批次 ({historicalJobs.length} 批)
                  </h3>
                  {historicalJobs.length > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        const anyExpanded = historicalJobs.some(j => !!expandedJobs[j.job_id]);
                        const nextVal = !anyExpanded;
                        setExpandedJobs(prev => {
                          const next = { ...prev };
                          historicalJobs.forEach(j => {
                            next[j.job_id] = nextVal;
                          });
                          return next;
                        });
                      }}
                      className="flex items-center space-x-1 px-2.5 py-1 text-[11px] text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50/80 rounded-lg transition-colors cursor-pointer font-medium"
                      title="一键展开或折叠所有历史批次"
                    >
                      <ChevronsUpDown className="w-3.5 h-3.5" />
                      <span>
                        {historicalJobs.some(j => !!expandedJobs[j.job_id])
                          ? '全部收起'
                          : '全部展开'}
                      </span>
                    </button>
                  )}
                </div>

                {historicalJobs.length === 0 ? (
                  <div className="py-10 text-center text-xs text-gray-400">暂无已结束的混剪任务记录</div>
                ) : (
                  <div className="space-y-2.5">
                    {historicalJobs.map((j) => {
                  const detail = jobDetails[j.job_id];
                  const isDone = j.status === 'finished';
                  const failedCount = j.failed_count || 0;
                  const doneCount = j.completed_count;
                  const incompleteCount = Math.max(0, j.total_count - doneCount);
                  const isExpanded = !!expandedJobs[j.job_id];
                  return (
                    <div key={j.job_id} className="bg-gray-50/60 rounded-xl p-3 border border-gray-200/60 space-y-2 transition-all">
                      <div
                        onClick={() => toggleJobExpanded(j.job_id, false)}
                        className="flex items-center justify-between text-xs cursor-pointer select-none group/header hover:bg-gray-100/70 -m-1.5 p-1.5 rounded-lg transition-colors"
                      >
                        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                          <div className={`transition-colors flex items-center ${isExpanded ? 'text-indigo-600' : 'text-gray-400 group-hover/header:text-indigo-600'}`}>
                            <ChevronRight className={`w-3.5 h-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                          </div>
                          <span className="font-mono font-medium text-gray-700">批次: {j.job_id.substring(0, 8)}...</span>
                          {/* 默认缩起状态下只显批次与基本状态，展开时才显示数量与并发详情 */}
                          {isExpanded ? (
                            <>
                              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                                isDone ? (
                                  doneCount === 0 && j.total_count > 0
                                    ? 'bg-rose-50 text-rose-600 border border-rose-200/60'
                                    : failedCount > 0
                                      ? 'bg-amber-50 text-amber-700 border border-amber-200/60'
                                      : 'bg-emerald-50 text-emerald-600 border border-emerald-200/60'
                                ) :
                                j.status === 'canceled' ? 'bg-gray-100 text-gray-600 border border-gray-200' :
                                j.status === 'interrupted' ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                                'bg-indigo-50 text-indigo-600'
                              }`}>
                                {isDone ? (
                                  doneCount === 0 && j.total_count > 0
                                    ? `全部失败 0/${j.total_count}`
                                    : failedCount > 0
                                      ? `部分完成 ${doneCount}/${j.total_count}`
                                      : `已完成 ${doneCount}/${j.total_count}`
                                ) :
                                 j.status === 'canceled' ? `已取消 ${doneCount}/${j.total_count}` :
                                 j.status === 'interrupted' ? `已中断 ${doneCount}/${j.total_count}` :
                                 `处理中 ${doneCount}/${j.total_count}`}
                              </span>
                              {failedCount > 0 ? (
                                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-red-50 text-red-600 border border-red-200/60">
                                  失败 {failedCount}
                                </span>
                              ) : incompleteCount > 0 && isDone ? (
                                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-50 text-amber-600 border border-amber-200/60">
                                  未完成 {incompleteCount}
                                </span>
                              ) : null}
                              {incompleteCount > 0 && j.status !== 'running' && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRetryFailed(j.job_id);
                                  }}
                                  disabled={retryingJobIds[j.job_id]}
                                  className="flex items-center space-x-1 text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 transition-colors cursor-pointer disabled:opacity-50"
                                  title="重新将该批次中未完成或失败的视频条目加入剪辑队列"
                                >
                                  <RotateCcw className={`w-2.5 h-2.5 ${retryingJobIds[j.job_id] ? 'animate-spin' : ''}`} />
                                  <span>{retryingJobIds[j.job_id] ? '提交中...' : '重试未完成项'}</span>
                                </button>
                              )}
                              <span className="text-[10px] text-gray-400 font-mono">并发: {j.concurrency}</span>
                            </>
                          ) : (
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                              isDone ? (
                                doneCount === 0 && j.total_count > 0
                                  ? 'bg-rose-50 text-rose-600 border border-rose-200/60'
                                  : failedCount > 0
                                    ? 'bg-amber-50 text-amber-700 border border-amber-200/60'
                                    : 'bg-emerald-50 text-emerald-600 border border-emerald-200/60'
                              ) :
                              j.status === 'canceled' ? 'bg-gray-100 text-gray-600 border border-gray-200' :
                              j.status === 'interrupted' ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                              'bg-indigo-50 text-indigo-600'
                            }`}>
                              {isDone ? (
                                doneCount === 0 && j.total_count > 0
                                  ? '全部失败'
                                  : failedCount > 0
                                    ? '部分完成'
                                    : '已完成'
                              ) :
                               j.status === 'canceled' ? '已取消' :
                               j.status === 'interrupted' ? '已中断' :
                               '处理中'}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center space-x-2 text-gray-400 font-mono text-[11px] flex-shrink-0">
                          {j.created_at && (
                            <span>{formatDate(j.created_at)}</span>
                          )}
                          <span className={`text-[10px] font-sans transition-colors ml-1 ${isExpanded ? 'text-indigo-600 font-medium' : 'text-gray-400 group-hover/header:text-indigo-600'}`}>
                            {isExpanded ? '收起' : '展开'}
                          </span>
                        </div>
                      </div>

                      {isExpanded && detail?.items && (
                        <div className="space-y-1.5 pt-1.5 border-t border-gray-100">
                          {detail.items.map((it: any, idx: number) => {
                            const meta = ITEM_STATUS_META[it.status] || ITEM_STATUS_META.queued;
                            return (
                              <div key={idx} className="bg-white p-2.5 rounded-lg border border-gray-100 shadow-2xs space-y-1">
                                <div className="flex items-center justify-between text-[11px]">
                                  <div className="flex items-center space-x-2 truncate">
                                    <span className="font-mono text-gray-400">#{idx + 1}</span>
                                    <span className="text-gray-700 font-medium truncate max-w-xs sm:max-w-md">
                                      {it.project_title || it.material_filename || it.material_id}
                                    </span>
                                    <span className={`px-1.5 py-0.2 rounded text-[10px] ${meta.cls}`}>{meta.label}</span>
                                  </div>
                                  <div className="flex items-center space-x-3 text-gray-400 font-mono flex-shrink-0">
                                    {it.status === 'running' && (
                                      <span className="text-indigo-600 font-medium text-[10px]">{it.progress || 0}%</span>
                                    )}
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
                                {/* 进度条 */}
                                {it.status === 'running' && (
                                  <div className="w-full bg-gray-100 h-1 rounded-full overflow-hidden">
                                    <div
                                      className="bg-indigo-500 h-full transition-all duration-300 rounded-full"
                                      style={{ width: `${Math.max(5, it.progress || 0)}%` }}
                                    />
                                  </div>
                                )}
                                {/* 失败详情透出 */}
                                {it.status === 'failed' && it.error && (
                                  <div className="text-[10px] text-red-600 bg-red-50/90 px-2 py-0.5 rounded border border-red-100 flex items-center space-x-1" title={it.error}>
                                    <AlertTriangle className="w-3 h-3 flex-shrink-0 text-red-500" />
                                    <span className="truncate">{it.error}</span>
                                  </div>
                                )}
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
            );
          })()}
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
                onClick={handleCloseUploadModal}
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
                    {file.size > 0 && (
                      <span className="text-[10px] text-gray-400 font-mono flex-shrink-0">
                        ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                      </span>
                    )}
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
            <div className="bg-gray-50 rounded-xl p-3 text-xs space-y-2.5 border border-gray-100">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">画幅比例</span>
                <span className="font-semibold text-gray-800">{batchAspectRatio === '9:16' ? '9:16 竖屏' : '16:9 横屏'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">并发调度</span>
                <span className="font-mono text-indigo-700 font-semibold">⚡ {hardware?.recommended_concurrency || 2} 任务自适应并行 (智能调度)</span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-gray-200/50">
                <div className="flex items-start space-x-2 mr-3">
                  <ShieldAlert className={`w-4 h-4 mt-0.5 flex-shrink-0 ${batchFilterBannedWords ? 'text-rose-600' : 'text-gray-400'}`} />
                  <div>
                    <div className="font-medium text-gray-800">违禁词合规脱敏清洗</div>
                    <div className="text-[10px] text-gray-500 leading-tight">成片字幕自动将违禁词替换为形似字（如：驾驶证→加驶正，最快→蕞快），避免发布限流</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => toggleBatchFilterBannedWords()}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden ${
                    batchFilterBannedWords ? 'bg-rose-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs ring-0 transition duration-200 ease-in-out ${
                      batchFilterBannedWords ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={handleCloseUploadModal}
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
