import React, { useState, useEffect } from 'react';
import { fetchMaterials, uploadMaterial, deleteMaterial, Material } from '../services/api';
import { Upload, Film, MapPin, Activity, Award, Trash2, Clock, CheckCircle2, AlertCircle } from 'lucide-react';

const CATEGORIES = [
  { key: 'talking_head', label: '口播主视频', desc: '用于声音主轨与人像切出', icon: Film, color: 'text-blue-600 bg-blue-50' },
  { key: 'venue', label: '场地空镜', desc: '训练场、校区、考场等实景', icon: MapPin, color: 'text-emerald-600 bg-emerald-50' },
  { key: 'medical', label: '体检空镜', desc: '体检大厅、视力检测、拍照', icon: Activity, color: 'text-amber-600 bg-amber-50' },
  { key: 'lesson', label: '教学学车空镜', desc: '倒库、侧方、科目二/三练车', icon: Award, color: 'text-indigo-600 bg-indigo-50' },
];

export const AssetLibrary: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('talking_head');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploadProgressText, setUploadProgressText] = useState<string>('');

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

  const loadData = async (cat: string) => {
    setLoading(true);
    try {
      const data = await fetchMaterials(cat);
      setMaterials(data);
    } catch (err) {
      console.error('Failed to load materials:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(activeTab);
  }, [activeTab]);

  const uploadFileList = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setUploadProgressText(`正在上传 (${i + 1}/${files.length}): ${file.name}...`);
        await uploadMaterial(activeTab, file);
      }
      await loadData(activeTab);
    } catch (err) {
      alert('上传失败，请确保后端服务正常运行');
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
    if (!confirm('确认删除该素材？')) return;
    try {
      await deleteMaterial(id);
      setMaterials(materials.filter(m => m.id !== id));
    } catch (err) {
      alert('删除失败');
    }
  };

  const currentCategoryInfo = CATEGORIES.find(c => c.key === activeTab);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* 顶部标题与说明 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">素材库管理 (Asset Library)</h1>
        <p className="text-sm text-gray-500 mt-1">
          将视频素材分类归档至独立物理目录。口播视频为主音视频轨，其余三类将根据关键词智能切入为空镜头。
        </p>
      </div>

      {/* 四大分类切换卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {CATEGORIES.map(c => {
          const Icon = c.icon;
          const isSelected = activeTab === c.key;
          return (
            <button
              key={c.key}
              onClick={() => setActiveTab(c.key)}
              className={`p-5 rounded-2xl border text-left transition-all duration-200 ${
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
        <label htmlFor="material-upload" className="cursor-pointer flex flex-col items-center select-none">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-3 transition-transform duration-200 ${
            isDragging ? 'bg-blue-600 text-white scale-110 shadow-md' : 'bg-blue-50 text-blue-600'
          }`}>
            <Upload className={`w-7 h-7 ${isDragging ? 'animate-bounce' : ''}`} />
          </div>

          <span className="text-sm font-semibold text-gray-900">
            {uploading
              ? (uploadProgressText || '正在上传并提取元数据...')
              : isDragging
              ? `松开鼠标即可上传至【${currentCategoryInfo?.label}】`
              : `点击或直接拖拽视频至此处上传（归入【${currentCategoryInfo?.label}】）`}
          </span>

          <span className="text-xs text-gray-400 mt-1.5">
            支持 MP4, MOV, MKV, AVI, WEBM 格式，自动探测分辨率与时长
          </span>
        </label>
      </div>

      {/* 素材列表展示 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-800">
            【{currentCategoryInfo?.label}】已就绪素材清单 ({materials.length})
          </h2>
        </div>

        {loading ? (
          <div className="py-12 text-center text-gray-400 text-sm">加载中...</div>
        ) : materials.length === 0 ? (
          <div className="py-16 text-center text-gray-400 border border-gray-100 rounded-2xl bg-white">
            该分类下暂无视频素材，请将视频拖入上方区域上传
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {materials.map(m => (
              <div key={m.id} className="bg-white border border-gray-200/80 rounded-xl overflow-hidden shadow-sm hover:shadow transition-shadow">
                <div className="aspect-[9/16] bg-gray-900 relative flex items-center justify-center overflow-hidden">
                  <video
                    src={`http://localhost:18888/${m.filepath}`}
                    className="w-full h-full object-cover"
                    preload="metadata"
                  />
                  <div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-full font-mono flex items-center space-x-1">
                    <Clock className="w-3 h-3 mr-1" />
                    <span>{m.duration.toFixed(1)}s</span>
                  </div>
                  <button
                    onClick={() => handleDelete(m.id)}
                    className="absolute top-2 right-2 p-1.5 bg-black/60 text-gray-300 hover:text-red-400 rounded-full transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="p-3">
                  <p className="text-xs font-medium text-gray-800 truncate" title={m.filename}>
                    {m.filename}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    {m.width}x{m.height} · {m.fps} FPS
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
