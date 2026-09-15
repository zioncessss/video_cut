import React, { useState, useEffect } from 'react';
import { fetchMaterials, uploadMaterial, deleteMaterial, Material } from '../services/api';
import { Upload, Film, MapPin, Activity, Award, Trash2, Clock, CheckCircle } from 'lucide-react';

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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        await uploadMaterial(activeTab, files[i]);
      }
      await loadData(activeTab);
    } catch (err) {
      alert('上传失败，请检查后端服务是否启动');
    } finally {
      setUploading(false);
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

      {/* 上传拖拽区域 */}
      <div className="mb-8 p-8 border-2 border-dashed border-gray-200 rounded-2xl bg-white text-center hover:border-blue-400 transition-colors">
        <input
          type="file"
          id="material-upload"
          className="hidden"
          multiple
          accept="video/*"
          onChange={handleFileUpload}
          disabled={uploading}
        />
        <label htmlFor="material-upload" className="cursor-pointer flex flex-col items-center">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mb-3">
            <Upload className="w-6 h-6" />
          </div>
          <span className="text-sm font-medium text-gray-900">
            {uploading ? '正在上传与提取元数据...' : '点击或拖拽视频至此处上传'}
          </span>
          <span className="text-xs text-gray-400 mt-1">支持 MP4, MOV, MKV 等常见格式，将自动提取时长与规格</span>
        </label>
      </div>

      {/* 素材列表展示 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-800">
            已就绪素材清单 ({materials.length})
          </h2>
        </div>

        {loading ? (
          <div className="py-12 text-center text-gray-400 text-sm">加载中...</div>
        ) : materials.length === 0 ? (
          <div className="py-16 text-center text-gray-400 border border-gray-100 rounded-2xl bg-white">
            该分类下暂无视频素材，请先上传
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
