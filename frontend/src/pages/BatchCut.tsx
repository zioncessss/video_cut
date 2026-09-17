import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE, fetchHardwareMetrics } from '../services/api';
import { Cpu, HardDrive, Layers, Play } from 'lucide-react';

export const BatchCut: React.FC = () => {
  const [hardware, setHardware] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);

  const loadJobs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/batch/jobs`);
      setJobs(res.data.data || []);
    } catch (e) {}
  };

  useEffect(() => {
    fetchHardwareMetrics().then(setHardware).catch(() => {});
    loadJobs();
    const interval = setInterval(loadJobs, 3000);
    return () => clearInterval(interval);
  }, []);

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

      {/* 批量任务说明卡片 */}
      <div className="bg-white border border-gray-200/80 rounded-2xl p-6 shadow-sm mb-8">
        <h2 className="text-base font-bold text-gray-800 mb-2">创建批量智能剪辑任务</h2>
        <p className="text-sm text-gray-500">
          批量剪辑入口已整合至「素材库」：在口播分镜页签勾选多个视频，点击「批量智能剪辑」即可按推荐并发逐个执行
          完整流水线（ASR → AI 纠偏 → 高亮词 → AI 分镜决策 → 合成）。每个视频完成后可在此或素材库点入单视频工作台人工修正。
        </p>
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
              const pct = j.total_count > 0 ? Math.round((j.completed_count / j.total_count) * 100) : 0;
              return (
                <div key={j.job_id} className="bg-white border border-gray-200/80 rounded-xl p-4 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold text-gray-700">作业 ID: {String(j.job_id).substring(0, 8)}...</span>
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
