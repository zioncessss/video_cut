import React, { useState, useEffect, useRef } from 'react';
import { fetchMaterials, uploadMaterial, importLocalMaterial, updateMaterialRegion, deleteMaterial, cleanupMaterials, Material, getMediaUrl } from '../services/api';
import { ZHEJIANG_REGIONS, DEFAULT_REGION, formatRegionBadge } from '../constants/regions';
import { useDialog } from '../components/common/CustomDialog';
import { Upload, Film, MapPin, Activity, Award, Trash2, Clock, CheckCircle2, AlertCircle, FolderPlus, Play, Pause, Volume2, VolumeX, X, ExternalLink, Sparkles } from 'lucide-react';

const CATEGORIES = [
  { key: 'venue', label: '场地空镜', desc: '训练场、校区、考场等实景画面', icon: MapPin, color: 'text-emerald-600 bg-emerald-50' },
  { key: 'experience', label: '体验空镜', desc: '报名咨询、体检拍照、试学体验、拿证记录', icon: Activity, color: 'text-amber-600 bg-amber-50' },
  { key: 'lesson', label: '教学学车空镜', desc: '倒车入库、侧方停车、科目二/三实操练车', icon: Award, color: 'text-indigo-600 bg-indigo-50' },
];

interface AssetLibraryProps {
  onSelectForEditor?: (materialId: string) => void;
  isActive?: boolean;
}

export const AssetLibrary: React.FC<AssetLibraryProps> = ({ onSelectForEditor, isActive = true }) => {
  const { showAlert, showConfirm, showToast } = useDialog();
  const [activeTab, setActiveTab] = useState<string>('venue');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [cleaning, setCleaning] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploadProgressText, setUploadProgressText] = useState<string>('');
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<string>(
    () => localStorage.getItem('videocut_upload_region') || DEFAULT_REGION
  );
  const [filterRegion, setFilterRegion] = useState<string>('');

  // 素材预览弹窗专属播放器状态与 Ref
  const modalVideoRef = useRef<HTMLVideoElement | null>(null);
  const [modalPlaying, setModalPlaying] = useState<boolean>(true);
  const [modalCurrentTime, setModalCurrentTime] = useState<number>(0);
  const [modalDuration, setModalDuration] = useState<number>(0);
  const [modalMuted, setModalMuted] = useState<boolean>(false);
  const [modalSeeking, setModalSeeking] = useState<boolean>(false);
  const [modalSeekTime, setModalSeekTime] = useState<number>(0);
  const [modalAspect, setModalAspect] = useState<'auto' | '16:9' | '9:16'>('auto');
  const [loadError, setLoadError] = useState<string>('');

  // 当预览素材变更时重置播放状态
  useEffect(() => {
    if (previewMaterial) {
      setModalPlaying(true);
      setModalCurrentTime(0);
      setModalDuration(previewMaterial.duration || 0);
      setModalSeeking(false);
      setModalSeekTime(0);
      // 根据素材原生分辨率自动选择初始比例
      if (previewMaterial.width && previewMaterial.height) {
        if (previewMaterial.width > previewMaterial.height) {
          setModalAspect('16:9');
        } else {
          setModalAspect('9:16');
        }
      } else {
        setModalAspect('auto');
      }
    }
  }, [previewMaterial]);

  // 切出标签页时，自动暂停弹窗内正在播放的预览视频
  useEffect(() => {
    if (isActive === false && modalVideoRef.current && modalPlaying) {
      modalVideoRef.current.pause();
      setModalPlaying(false);
    }
  }, [isActive, modalPlaying]);

  // 全局松开拖拽监听，确保松手时准确定位并恢复
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (modalSeeking) {
        setModalSeeking(false);
        if (modalVideoRef.current) {
          modalVideoRef.current.currentTime = modalSeekTime;
        }
      }
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    window.addEventListener('pointerup', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
      window.removeEventListener('pointerup', handleGlobalMouseUp);
    };
  }, [modalSeeking, modalSeekTime]);

  const toggleModalPlay = () => {
    if (!modalVideoRef.current) return;
    if (modalVideoRef.current.paused) {
      modalVideoRef.current.play();
      setModalPlaying(true);
    } else {
      modalVideoRef.current.pause();
      setModalPlaying(false);
    }
  };

  const handleModalTimeUpdate = () => {
    if (!modalVideoRef.current || modalSeeking) return;
    setModalCurrentTime(modalVideoRef.current.currentTime);
  };

  const handleModalSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setModalSeekTime(val);
    setModalCurrentTime(val);
    if (modalVideoRef.current) {
      modalVideoRef.current.currentTime = val;
    }
  };

  const handleModalStep = (delta: number) => {
    if (!modalVideoRef.current) return;
    const target = Math.max(0, Math.min(modalDuration, modalVideoRef.current.currentTime + delta));
    modalVideoRef.current.currentTime = target;
    setModalCurrentTime(target);
  };

  const formatSec = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  // 按 Esc 键关闭素材播放预览弹窗
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPreviewMaterial(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 关键：阻止浏览器在拖拽文件进入未绑定区域时的默认打开/下载行为
  useEffect(() => {
    const preventWindowDrop = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('dragover', preventWindowDrop);
    window.addEventListener('drop', preventWindowDrop);
    return () => {
      window.removeEventListener('dragover', preventWindowDrop);
      window.removeEventListener('drop', preventWindowDrop);
    };
  }, []);

  const loadData = async (cat: string, reg?: string) => {
    setLoading(true);
    setLoadError('');
    try {
      const data = await fetchMaterials(cat, reg || undefined);
      setMaterials(data);
    } catch (err: any) {
      // 请求失败必须清空残留列表并明示错误：严禁展示上一分类的数据造成"共用库"假象
      setMaterials([]);
      const detail = err?.response?.data?.detail;
      const hint = Array.isArray(detail)
        ? `后端不认识分类「${cat}」，请重启应用以加载最新版本`
        : (typeof detail === 'string' ? detail : '');
      setLoadError(hint || `【${currentCategoryInfo?.label || cat}】素材列表加载失败，请确认后端服务已更新并重启`);
      console.error('Failed to load materials:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setMaterials([]);
    loadData(activeTab, (activeTab === 'venue' || activeTab === 'lesson') ? filterRegion : undefined);
  }, [activeTab, filterRegion]);

  const handleUpdateRegion = async (materialId: string, newRegion: string) => {
    try {
      await updateMaterialRegion(materialId, newRegion);
      setMaterials(prev => prev.map(m => m.id === materialId ? { ...m, plate_region: newRegion } : m));
      showToast(`已将所属地区修改为「${formatRegionBadge(newRegion)}」`);
    } catch (err) {
      showAlert({ title: '修改失败', message: '修改所属地区失败，请检查后端服务状态。', type: 'error' });
    }
  };

  const handleNativeSelectFiles = async () => {
    if (window.electronAPI?.showOpenDialog) {
      const res = await window.electronAPI.showOpenDialog({
        title: `批量导入${currentCategoryInfo?.label || '素材'}`,
        filters: [
          { name: 'Video Files', extensions: ['mp4', 'mov', 'mkv', 'avi', 'flv', 'webm'] },
          { name: 'All Files', extensions: ['*'] }
        ],
        properties: ['openFile', 'multiSelections']
      });
      if (!res.canceled && res.filePaths.length > 0) {
        setUploading(true);
        const regionToTag = (activeTab === 'venue' || activeTab === 'lesson') ? selectedRegion : undefined;
        try {
          for (let i = 0; i < res.filePaths.length; i++) {
            const p = res.filePaths[i];
            const name = p.split(/[/\\]/).pop() || p;
            setUploadProgressText(`正在导入 (${i + 1}/${res.filePaths.length}): ${name}...`);
            await importLocalMaterial(activeTab, p, regionToTag);
          }
          await loadData(activeTab, filterRegion);
          showToast(`成功导入 ${res.filePaths.length} 个本地素材`);
        } catch (err: any) {
          const detail = err?.response?.data?.detail;
          const msg = typeof detail === 'string'
            ? detail
            : (err?.message ? `本地导入失败: ${err.message}` : '本地导入失败，请检查文件是否存在且有读取权限。');
          showAlert({ title: '本地导入失败', message: msg, type: 'error' });
        } finally {
          setUploading(false);
          setUploadProgressText('');
        }
      }
    } else {
      document.getElementById('material-upload')?.click();
    }
  };

  const uploadFileList = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const regionToTag = (activeTab === 'venue' || activeTab === 'lesson') ? selectedRegion : undefined;
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        // 如果在 Electron 环境中拖拽，优先获取其原生文件绝对路径执行零拷贝快速导入
        const nativePath = (file as any).path;
        if (nativePath && window.electronAPI) {
          setUploadProgressText(`正在极速导入 (${i + 1}/${files.length}): ${file.name}...`);
          await importLocalMaterial(activeTab, nativePath, regionToTag);
        } else {
          setUploadProgressText(`正在上传 (${i + 1}/${files.length}): ${file.name}...`);
          await uploadMaterial(activeTab, file, regionToTag);
        }
      }
      await loadData(activeTab, filterRegion);
      showToast(`成功上传 ${files.length} 个素材`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : (err?.message ? `素材上传失败: ${err.message}` : '素材上传失败，请确保后端服务正常运行。');
      showAlert({ title: '上传失败', message: msg, type: 'error' });
    } finally {
      setUploading(false);
      setUploadProgressText('');
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      await uploadFileList(e.target.files);
    }
    e.target.value = '';
  };

  // 拖拽事件监听
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // 避免在子元素间移动时闪烁
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      await uploadFileList(files);
    }
  };

  const handleDelete = async (id: string) => {
    const targetMat = materials.find(m => m.id === id);
    const confirmed = await showConfirm({
      title: '确认删除素材',
      message: `确定要彻底删除素材「${targetMat?.filename || '该视频'}」吗？删除后不可撤销。`,
      isDestructive: true
    });
    if (!confirmed) return;
    try {
      await deleteMaterial(id);
      setMaterials(prev => prev.filter(m => m.id !== id));
      setPreviewMaterial(curr => (curr?.id === id ? null : curr));
      showToast('素材已成功删除');
    } catch (err) {
      showAlert({ title: '删除失败', message: '删除素材失败，请检查后端服务状态。', type: 'error' });
    }
  };

  const handleCleanup = async () => {
    const confirmed = await showConfirm({
      title: '深度整理素材库',
      message: '系统将基于文件内容指纹（SHA-256）精准扫描并合并重复素材，清理历史残留测试与孤儿文件。已关联工程的素材会自动受到保护并无损映射，是否继续？',
      confirmText: '立即整理',
    });
    if (!confirmed) return;

    setCleaning(true);
    try {
      const res = await cleanupMaterials(false);
      const data = res.data;
      await loadData(activeTab);
      if (data.freed_mb > 0 || data.removed_files_count > 0 || data.merged_materials_count > 0) {
        showAlert({
          title: '素材整理完成',
          message: `共合并去重 ${data.merged_materials_count} 组素材，清理 ${data.removed_files_count} 个冗余文件，释放磁盘空间 ${data.freed_mb} MB！`,
          type: 'success',
        });
      } else {
        showToast('素材库状态优良，未发现重复素材或冗余文件');
      }
    } catch (err: any) {
      showAlert({
        title: '整理失败',
        message: `素材库整理失败: ${err?.response?.data?.detail || err.message}`,
        type: 'error',
      });
    } finally {
      setCleaning(false);
    }
  };

  const currentCategoryInfo = CATEGORIES.find(c => c.key === activeTab);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* 顶部标题与说明 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">素材库管理 (Asset Library)</h1>
        <p className="text-sm text-gray-500 mt-1">
          将空镜素材分类归档至独立物理目录。三大纯空镜素材将根据解说词与 AI 分镜决策智能切入为画面平替。
        </p>
      </div>

      {/* 纯化素材库提示引导横幅 */}
      <div className="mb-6 p-4 rounded-2xl bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 border border-blue-200/70 shadow-xs flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0 shadow-sm">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-gray-800">
              口播主视频已全面升级至【批量混剪】与【剪辑工作台】
            </h3>
            <p className="text-[11px] text-gray-600 mt-0.5">
              待剪辑口播视频上传时系统将自动分配独立任务目录（日期+时间）。素材库已纯化为三大纯空镜素材库（场地、体验、教学），供 AI 剪辑引擎智能平替切入。
            </p>
          </div>
        </div>
      </div>

      {/* 三大空镜分类切换卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {CATEGORIES.map(c => {
          const Icon = c.icon;
          const isSelected = activeTab === c.key;
          return (
            <button
              key={c.key}
              onClick={() => setActiveTab(c.key)}
              className={`p-5 rounded-2xl border text-left transition-all duration-200 cursor-pointer ${
                isSelected
                  ? 'border-blue-600 bg-white shadow-md ring-2 ring-blue-600/10'
                  : 'border-gray-200 bg-white hover:border-gray-300 shadow-sm'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className={`p-2.5 rounded-xl ${c.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 text-sm">{c.label}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">{c.desc}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* 上传拖拽区域（具备完整的 HTML5 拖拽监听） */}
      <div
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`mb-8 p-8 border-2 border-dashed rounded-2xl text-center transition-all duration-200 ${
          isDragging
            ? 'border-blue-600 bg-blue-50/70 scale-[1.01] shadow-lg ring-4 ring-blue-500/10'
            : 'border-gray-200 bg-white hover:border-blue-400 shadow-sm'
        }`}
      >
        <input
          type="file"
          id="material-upload"
          className="hidden"
          multiple
          accept="video/*"
          onChange={handleFileInputChange}
          disabled={uploading}
        />
        <div className="flex flex-col items-center select-none">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-3 transition-transform duration-200 ${
            isDragging ? 'bg-blue-600 text-white scale-110 shadow-md' : 'bg-blue-50 text-blue-600'
          }`}>
            <Upload className={`w-7 h-7 ${isDragging ? 'animate-bounce' : ''}`} />
          </div>

          <span className="text-sm font-semibold text-gray-900 mb-2">
            {uploading
              ? (uploadProgressText || '正在极速导入并提取元数据...')
              : isDragging
              ? `松开鼠标即可导入至【${currentCategoryInfo?.label}】`
              : `拖拽视频至此处，或点击下方按钮选择文件`}
          </span>

          {(activeTab === 'venue' || activeTab === 'lesson') && (
            <div className="flex items-center gap-2 mb-3 bg-blue-50/70 border border-blue-200/80 px-3.5 py-1.5 rounded-xl shadow-xs">
              <span className="text-xs text-blue-900 font-medium whitespace-nowrap">所属车牌/城市:</span>
              <select
                value={selectedRegion}
                onChange={(e) => {
                  setSelectedRegion(e.target.value);
                  localStorage.setItem('videocut_upload_region', e.target.value);
                }}
                className="text-xs font-semibold text-blue-700 bg-white px-2 py-1 rounded-md border border-blue-200 outline-none cursor-pointer hover:border-blue-400"
              >
                {ZHEJIANG_REGIONS.map(r => (
                  <option key={r.code} value={r.code}>{r.label}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center space-x-3 mb-2">
            <button
              type="button"
              onClick={handleNativeSelectFiles}
              disabled={uploading}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium shadow-sm transition-all active:scale-95 cursor-pointer"
            >
              <FolderPlus className="w-4 h-4" />
              <span>选择本地视频文件（极速导入）</span>
            </button>
          </div>

          <span className="text-xs text-gray-400">
            支持 MP4, MOV, MKV, AVI, WEBM 格式，桌面端自动采用零拷贝物理索引
          </span>
        </div>
      </div>

      {/* 素材列表展示 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-800">
            【{currentCategoryInfo?.label}】已就绪素材清单 ({materials.length})
          </h2>
          <button
            type="button"
            onClick={handleCleanup}
            disabled={cleaning || loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50 text-gray-600 hover:text-blue-600 text-xs font-medium transition-all shadow-xs cursor-pointer active:scale-95 disabled:opacity-50"
            title="基于 SHA-256 内容哈希查重去重并清理冗余文件"
          >
            <Sparkles className={`w-3.5 h-3.5 ${cleaning ? 'animate-spin text-blue-600' : 'text-blue-500'}`} />
            <span>{cleaning ? '正在深度整理...' : '查重与整理素材'}</span>
          </button>
        </div>

        {(activeTab === 'venue' || activeTab === 'lesson') && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-4 scrollbar-none">
            <span className="text-xs text-gray-400 whitespace-nowrap mr-1 font-medium">地区筛选:</span>
            <button
              type="button"
              onClick={() => setFilterRegion('')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap ${
                !filterRegion ? 'bg-blue-600 text-white shadow-xs' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              全部地市
            </button>
            {ZHEJIANG_REGIONS.map(r => (
              <button
                key={r.code}
                type="button"
                onClick={() => setFilterRegion(filterRegion === r.code ? '' : r.code)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition cursor-pointer ${
                  filterRegion === r.code ? 'bg-blue-600 text-white shadow-xs' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className="py-12 text-center text-gray-400 text-sm">加载中...</div>
        ) : loadError ? (
          <div className="py-10 text-center border border-red-200 bg-red-50/70 rounded-2xl">
            <AlertCircle className="w-6 h-6 text-red-500 mx-auto mb-2" />
            <p className="text-sm text-red-700 font-medium">{loadError}</p>
          </div>
        ) : materials.length === 0 ? (
          <div className="py-16 text-center text-gray-400 border border-gray-100 rounded-2xl bg-white">
            该分类下暂无视频素材，请将视频拖入上方区域上传
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {materials.map(m => (
              <div
                key={m.id}
                className="group bg-white border border-gray-200/80 rounded-2xl overflow-hidden shadow-xs hover:shadow-md transition-all duration-200 flex flex-col"
              >
                {/* 缩略图与悬停快速预览区 */}
                <div
                  className="aspect-[9/16] bg-gray-950 relative flex items-center justify-center overflow-hidden cursor-pointer select-none"
                  onClick={() => setPreviewMaterial(m)}
                  onMouseEnter={(e) => {
                    const v = e.currentTarget.querySelector('video');
                    if (v) {
                      v.currentTime = 0;
                      v.play().catch(() => {});
                    }
                  }}
                  onMouseLeave={(e) => {
                    const v = e.currentTarget.querySelector('video');
                    if (v) {
                      v.pause();
                      v.currentTime = 0;
                    }
                  }}
                >
                  <video
                    src={getMediaUrl(m.filepath)}
                    className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-300"
                    preload="metadata"
                    muted
                    loop
                    playsInline
                  />

                  {/* 居中大播放按钮遮罩 */}
                  <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-colors flex items-center justify-center">
                    <div className="w-12 h-12 rounded-full bg-black/50 backdrop-blur-md text-white flex items-center justify-center border border-white/20 shadow-xl group-hover:scale-110 group-hover:bg-blue-600 transition-all duration-200">
                      <Play className="w-5 h-5 fill-current ml-0.5" />
                    </div>
                  </div>

                  {/* 左上角时长气泡 */}
                  <div className="absolute top-2.5 left-2.5 bg-black/70 backdrop-blur-sm text-white text-[11px] px-2 py-0.5 rounded-full font-mono flex items-center space-x-1 shadow-sm">
                    <Clock className="w-3 h-3 text-gray-300" />
                    <span>{m.duration.toFixed(1)}s</span>
                  </div>

                  {/* 右上角删除按钮 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(m.id);
                    }}
                    title="删除素材"
                    className="absolute top-2.5 right-2.5 p-1.5 bg-black/70 backdrop-blur-sm text-gray-300 hover:text-red-400 hover:bg-black/90 rounded-full transition-colors cursor-pointer shadow-sm"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>

                  {/* 悬停底部轻提示 */}
                  <div className="absolute bottom-2 inset-x-2 text-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                    <span className="text-[10px] bg-black/75 backdrop-blur-xs text-white/90 px-2.5 py-0.5 rounded-full font-medium shadow-sm">
                      点击全屏播放预览
                    </span>
                  </div>
                </div>

                {/* 底部详情与显式播放入口 */}
                <div className="p-3.5 flex flex-col justify-between flex-1 bg-white">
                  <div className="flex items-center justify-between gap-1.5">
                    <p className="text-xs font-semibold text-gray-800 truncate flex-1" title={m.filename}>
                      {m.filename}
                    </p>
                    {(m.category === 'venue' || m.category === 'lesson' || m.plate_region) && (
                      <div className="relative inline-flex items-center shrink-0" onClick={(e) => e.stopPropagation()}>
                        <select
                          value={m.plate_region || ''}
                          onChange={(e) => handleUpdateRegion(m.id, e.target.value)}
                          className="text-[11px] font-semibold pl-2 pr-4 py-0.5 rounded-md border border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100 cursor-pointer outline-none appearance-none"
                          title="点击切换所属城市"
                        >
                          <option value="" disabled>未标注地区</option>
                          {ZHEJIANG_REGIONS.map(r => (
                            <option key={r.code} value={r.code}>{r.label}</option>
                          ))}
                        </select>
                        <span className="absolute right-1 top-1/2 -translate-y-1/2 text-[8px] text-sky-600 pointer-events-none">▼</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
                    <span className="text-[11px] text-gray-400 font-mono">
                      {m.width}x{m.height} · {m.fps} FPS
                    </span>
                    <button
                      onClick={() => setPreviewMaterial(m)}
                      className="flex items-center space-x-1 text-xs font-medium text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100/80 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
                    >
                      <Play className="w-3 h-3 fill-current" />
                      <span>播放预览</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 素材视频播放预览模态弹窗 */}
      {previewMaterial && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 sm:p-6 animate-in fade-in duration-150"
          onClick={() => setPreviewMaterial(null)}
        >
          <div
            className="bg-gray-900 border border-gray-800 rounded-3xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden text-white animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗顶部栏 */}
            <div className="flex items-center justify-between px-6 py-3.5 border-b border-gray-800 bg-gray-900/90 flex-shrink-0">
              <div className="flex items-center space-x-3 overflow-hidden pr-4">
                <span className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold ${
                  CATEGORIES.find(c => c.key === previewMaterial.category)?.color || 'text-blue-400 bg-blue-950/60'
                }`}>
                  <span>{CATEGORIES.find(c => c.key === previewMaterial.category)?.label || '素材'}</span>
                </span>
                <h3 className="font-semibold text-sm sm:text-base text-gray-100 truncate" title={previewMaterial.filename}>
                  {previewMaterial.filename}
                </h3>
              </div>

              <div className="flex items-center space-x-3">
                {/* 16:9 / 9:16 画幅切换按钮 */}
                <div className="flex items-center bg-gray-800 p-0.5 rounded-lg border border-gray-700/60 text-xs">
                  <button
                    onClick={() => setModalAspect('16:9')}
                    className={`px-2 py-1 rounded font-mono font-medium transition-all ${
                      modalAspect === '16:9'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                    title="强制 16:9 横屏显示"
                  >
                    16:9 横屏
                  </button>
                  <button
                    onClick={() => setModalAspect('9:16')}
                    className={`px-2 py-1 rounded font-mono font-medium transition-all ${
                      modalAspect === '9:16'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                    title="强制 9:16 竖屏显示"
                  >
                    9:16 竖屏
                  </button>
                  <button
                    onClick={() => setModalAspect('auto')}
                    className={`px-2 py-1 rounded font-mono font-medium transition-all ${
                      modalAspect === 'auto'
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                    title="原始分辨率自适应"
                  >
                    自适应
                  </button>
                </div>

                <button
                  onClick={() => setPreviewMaterial(null)}
                  className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                  title="关闭 (Esc)"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* 视频播放主视窗 - 强制无裁切 object-contain */}
            <div className="flex-1 bg-black/95 flex items-center justify-center overflow-hidden min-h-[360px] max-h-[60vh] p-4 relative">
              <div className={`relative flex items-center justify-center max-h-full max-w-full transition-all duration-300 ${
                modalAspect === '16:9' ? 'aspect-video w-full' : modalAspect === '9:16' ? 'aspect-[9/16] h-full' : 'w-full h-full'
              }`}>
                <video
                  ref={modalVideoRef}
                  key={previewMaterial.id}
                  src={getMediaUrl(previewMaterial.filepath)}
                  autoPlay
                  playsInline
                  muted={modalMuted}
                  onTimeUpdate={handleModalTimeUpdate}
                  onLoadedMetadata={(e) => {
                    const dur = e.currentTarget.duration;
                    if (dur && !isNaN(dur)) setModalDuration(dur);
                  }}
                  onPlay={() => setModalPlaying(true)}
                  onPause={() => setModalPlaying(false)}
                  onClick={toggleModalPlay}
                  className="w-full h-full object-contain rounded-lg shadow-2xl cursor-pointer"
                />
              </div>
            </div>

            {/* 显式拖动进度条与播放控制器 - 保证 100% 永久可见、可拖拽 */}
            <div className="px-6 py-3 bg-gray-900 border-t border-gray-800/80 flex flex-col space-y-2">
              <div className="flex items-center space-x-3 w-full">
                <span className="font-mono text-xs text-gray-300 w-16 select-none">
                  {formatSec(modalSeeking ? modalSeekTime : modalCurrentTime)}
                </span>
                
                {/* 醒目的视频拖动进度条 */}
                <input
                  type="range"
                  min="0"
                  max={modalDuration || 100}
                  step="0.05"
                  value={modalSeeking ? modalSeekTime : modalCurrentTime}
                  onPointerDown={() => setModalSeeking(true)}
                  onMouseDown={() => setModalSeeking(true)}
                  onChange={handleModalSeekChange}
                  className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 focus:outline-none transition-all"
                  title="拖动调整播放位置"
                />

                <span className="font-mono text-xs text-gray-400 w-16 text-right select-none">
                  {formatSec(modalDuration)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={toggleModalPlay}
                    className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs shadow transition-colors cursor-pointer"
                  >
                    {modalPlaying ? (
                      <>
                        <Pause className="w-4 h-4 fill-white" />
                        <span>暂停</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 fill-white" />
                        <span>播放</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => handleModalStep(-5)}
                    className="px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white font-mono text-xs transition-colors cursor-pointer"
                    title="快退 5 秒"
                  >
                    -5s
                  </button>
                  <button
                    onClick={() => handleModalStep(5)}
                    className="px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white font-mono text-xs transition-colors cursor-pointer"
                    title="快进 5 秒"
                  >
                    +5s
                  </button>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => {
                      if (modalVideoRef.current) {
                        modalVideoRef.current.muted = !modalMuted;
                        setModalMuted(!modalMuted);
                      }
                    }}
                    className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors cursor-pointer"
                    title={modalMuted ? '取消静音' : '静音'}
                  >
                    {modalMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>

            {/* 弹窗底部信息与操作栏 */}
            <div className="px-6 py-4 bg-gray-950/90 border-t border-gray-800 flex flex-wrap items-center justify-between gap-3 text-xs text-gray-400 flex-shrink-0">
              <div className="flex items-center space-x-4">
                <span className="flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5 text-gray-500" />
                  <span className="font-mono text-gray-200">{previewMaterial.duration.toFixed(1)}s</span>
                </span>
                <span>
                  分辨率: <span className="font-mono text-gray-200">{previewMaterial.width} × {previewMaterial.height}</span>
                </span>
                <span>
                  帧率: <span className="font-mono text-gray-200">{previewMaterial.fps} FPS</span>
                </span>
              </div>

              <div className="flex items-center space-x-2.5">
                {onSelectForEditor && previewMaterial.category === 'talking_head' && (
                  <button
                    onClick={() => {
                      const matId = previewMaterial.id;
                      setPreviewMaterial(null);
                      onSelectForEditor(matId);
                    }}
                    className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors cursor-pointer shadow-sm"
                  >
                    <Film className="w-3.5 h-3.5" />
                    <span>进入工作台剪辑</span>
                  </button>
                )}

                {window.electronAPI?.openPathInExplorer && (
                  <button
                    onClick={() => {
                      window.electronAPI?.openPathInExplorer(previewMaterial.filepath);
                    }}
                    className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium transition-colors cursor-pointer"
                    title="在系统文件管理器中定位该视频文件"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>定位文件</span>
                  </button>
                )}

                <button
                  onClick={() => {
                    const id = previewMaterial.id;
                    handleDelete(id);
                  }}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-red-950/40 hover:bg-red-900/60 text-red-300 border border-red-800/40 font-medium transition-colors cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>删除素材</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
