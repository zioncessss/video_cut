import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE, fetchHardwareMetrics } from '../services/api';
import { Cpu, HardDrive, Layers, Play, CheckCircle2, Clock } from 'lucide-react';

export const BatchCut: React.FC = () => {
  const [hardware, setHardware] = useState<any>(null);
  const [totalCount, setTotalCount] = useState<number>(5);
  const [concurrency, setConcurrency] = useState<number>(2);
  const [jobs, setJobs] = useState<any[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const loadJobs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/batch/jobs`);
      setJobs(res.data);
    } catch (e) {}
  };

  useEffect(() => {
    fetchHardwareMetrics().then(data => {
      setHardware(data);
      if (data && data.recommended_concurrency) {
        setConcurrency(data.recommended_concurrency);
      }
    }).catch(() => {});
    loadJobs();
    const interval = setInterval(loadJobs, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleStartBatch = async () => {
    setSubmitting(true);
    try {
      await axios.post(`${API_BASE}/batch/jobs`, {
        total_count: totalCount,
        concurrency_limit: concurrency
      });
      await loadJobs();
      alert('批量混剪作业已成功加入队列！');
    } catch (err) {
      alert('提交批量任务失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">批量混剪与资源调度 (Batch Production)</h1>
        <p className="text-sm text-gray-500 mt-1">
          根据当前系统 CPU、内存与硬件加速通道自动测算最佳并发槽位，实现高吞吐量无人值守批量生产，杜绝死机与 OOM 崩溃。
        </p>
      </div>

      {/* 硬件感知状态面板 */}
      {hardware && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center space-x-3">
            <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-400 font-medium">CPU 核心 / 负载</span>
              <p className="text-lg font-bold text-gray-800">{hardware.cpu_cores} 核 · {hardware.cpu_percent}%</p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center space-x-3">
            <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
              <HardDrive className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-400 font-medium">可用内存</span>
              <p className="text-lg font-bold text-gray-800">{hardware.memory_available_gb} GB / {hardware.memory_total_gb} GB</p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center space-x-3">
            <div className="p-3 bg-amber-50 text-amber-600 rounded-xl">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-400 font-medium">GPU 硬件加速</span>
              <p className="text-lg font-bold text-gray-800 uppercase">{hardware.gpu_accelerator_detected || 'CPU 软解压'}</p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm flex items-center space-x-3">
            <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
              <Play className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xs text-gray-400 font-medium">推荐安全并发</span>
              <p className="text-lg font-bold text-indigo-600">{hardware.recommended_concurrency} 个并发进程</p>
            </div>
          </div>
        </div>
      )}

      {/* 批量任务配置卡片 */}
      <div className="bg-white border border-gray-200/80 rounded-2xl p-6 shadow-sm mb-8">
        <h2 className="text-base font-bold text-gray-800 mb-4">创建批量生产作业</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-2">生成混剪视频数量</label>
            <input
              type="number"
              min="1"
              max="50"
              value={totalCount}
              onChange={e => setTotalCount(parseInt(e.target.value) || 1)}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-1 focus:ring-blue-500"
            />
            <span className="text-[11px] text-gray-400 mt-1 block">每次混剪将自动随机组合不同的空镜头切片</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-2">并发渲染线程限制</label>
            <input
              type="number"
              min="1"
              max="16"
              value={concurrency}
              onChange={e => setConcurrency(parseInt(e.target.value) || 1)}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-1 focus:ring-blue-500"
            />
            <span className="text-[11px] text-gray-400 mt-1 block">建议不要超过推荐并发数，以保持电脑流畅不卡顿</span>
          </div>
        </div>

        <button
          onClick={handleStartBatch}
          disabled={submitting}
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm px-6 py-3 rounded-xl transition-colors shadow-sm disabled:opacity-50"
        >
          {submitting ? '提交中...' : '启动批量混剪作业'}
        </button>
      </div>

      {/* 任务运行列表 */}
      <div>
        <h2 className="text-base font-bold text-gray-800 mb-4">作业监控队列</h2>
        {jobs.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-xs border border-gray-100 rounded-2xl bg-white">
            暂无批量作业记录
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map(j => {
              const pct = Math.round((j.completed_count / j.total_count) * 100);
              return (
                <div key={j.id} className="bg-white border border-gray-200/80 rounded-xl p-4 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold text-gray-700">作业 ID: {j.id.substring(0, 8)}...</span>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                        j.status === 'finished' ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'
                      }`}>
                        {j.status === 'finished' ? '已完成' : '运行中'}
                      </span>
                    </div>
                    <span className="text-xs font-mono text-gray-500">
                      {j.completed_count} / {j.total_count} ({pct}%)
                    </span>
                  </div>

                  <div className="w-full bg-gray-100 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-blue-600 h-full transition-all duration-300 rounded-full"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
