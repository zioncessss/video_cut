import React from 'react';
import { EditingStrategy } from '../services/api';
import { Palette, Sparkles, Type, Shield, Film, Check, Flame, Cpu, Sliders } from 'lucide-react';

interface StrategyStudioProps {
  strategy: EditingStrategy;
  onChange: (newStrategy: EditingStrategy) => void;
  onSave?: () => void;
  saving?: boolean;
}

export const StrategyStudio: React.FC<StrategyStudioProps> = ({
  strategy,
  onChange,
  onSave,
  saving = false,
}) => {
  const themes = [
    {
      id: 'viral_gold',
      name: '爆款金黄',
      desc: '黑底胶囊 + 发光明黄，抖音/快手短视频最高完播率预设',
      bgClass: 'bg-gradient-to-r from-gray-900 to-black text-amber-400 border-amber-500/30',
      badge: '🔥 热门爆款',
      icon: Flame
    },
    {
      id: 'tech_emerald',
      name: '科技翡翠',
      desc: '极客深黑 + 科技荧光青翠，适合驾考理论/硬核教程讲解',
      bgClass: 'bg-gradient-to-r from-slate-900 to-teal-950 text-emerald-400 border-emerald-500/30',
      badge: '💡 科技感',
      icon: Cpu
    },
    {
      id: 'marker_pen',
      name: '教学记号笔',
      desc: '荧光黄明亮底衬 + 纯黑大粗体，重点分明一目了然',
      bgClass: 'bg-gradient-to-r from-yellow-100 to-amber-200 text-gray-950 border-amber-400/50',
      badge: '✏️ 教学划线',
      icon: Sparkles
    },
    {
      id: 'minimal_white',
      name: '纯净投影白',
      desc: '无边框加粗纯白 + 立体柔和投影，不挡画面背景',
      bgClass: 'bg-gradient-to-r from-zinc-800 to-zinc-900 text-white border-zinc-700',
      badge: '✨ 极简纯粹',
      icon: Type
    },
  ];

  const highlightColors = [
    { name: '金黄色', value: '#FACC15', bg: 'bg-yellow-400' },
    { name: '翡翠绿', value: '#10B981', bg: 'bg-emerald-500' },
    { name: '亮橙红', value: '#F97316', bg: 'bg-orange-500' },
    { name: '电光粉', value: '#EC4899', bg: 'bg-pink-500' },
    { name: '天空蓝', value: '#38BDF8', bg: 'bg-sky-400' },
  ];

  const update = (partial: Partial<EditingStrategy>) => {
    onChange({ ...strategy, ...partial });
  };

  return (
    <div className="space-y-6">
      {/* 1. 字幕视觉预设主题 (4套可自由组合) */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Palette className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-sm text-gray-800">字幕视觉呈现主题</h3>
          </div>
          <span className="text-[11px] text-gray-400">类似爱拍/剪映预设组合</span>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          {themes.map(t => {
            const isSelected = strategy.subtitle_theme === t.id;
            const IconComponent = t.icon;
            return (
              <div
                key={t.id}
                onClick={() => update({ subtitle_theme: t.id as any })}
                className={`cursor-pointer rounded-xl p-3 border transition-all relative overflow-hidden ${
                  isSelected
                    ? 'border-blue-500 ring-2 ring-blue-500/20 shadow-md bg-blue-50/20'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center space-x-1.5">
                    <IconComponent className={`w-3.5 h-3.5 ${isSelected ? 'text-blue-600' : 'text-gray-500'}`} />
                    <span className="font-semibold text-xs text-gray-800">{t.name}</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-medium">
                    {t.badge}
                  </span>
                </div>
                <p className="text-[11px] text-gray-500 line-clamp-2 leading-relaxed mb-2.5">
                  {t.desc}
                </p>

                {/* 主题微缩效果预览胶囊 */}
                <div className={`text-[10px] font-bold px-2 py-1 rounded text-center border shadow-xs ${t.bgClass}`}>
                  科目二 轻松一把过
                </div>

                {isSelected && (
                  <div className="absolute top-1 right-1">
                    <span className="flex h-3 w-3 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-600 items-center justify-center">
                        <Check className="w-2 h-2 text-white stroke-[3]" />
                      </span>
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. 关键词高亮设计 */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <h3 className="font-semibold text-sm text-gray-800">关键词智能高亮 (重点突出)</h3>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={strategy.enable_highlight}
              onChange={e => update({ enable_highlight: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500"></div>
          </label>
        </div>

        {strategy.enable_highlight && (
          <div className="space-y-3 pt-1 border-t border-gray-100 text-xs">
            <div>
              <span className="text-gray-600 block mb-1.5 font-medium">高亮颜色盘</span>
              <div className="flex items-center space-x-2">
                {highlightColors.map(c => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => update({ highlight_color: c.value })}
                    className={`w-6 h-6 rounded-full flex items-center justify-center transition-transform ${c.bg} ${
                      strategy.highlight_color === c.value
                        ? 'ring-2 ring-offset-2 ring-gray-600 scale-110'
                        : 'opacity-80 hover:opacity-100'
                    }`}
                    title={c.name}
                  >
                    {strategy.highlight_color === c.value && (
                      <Check className="w-3 h-3 text-white stroke-[3]" />
                    )}
                  </button>
                ))}
                <input
                  type="color"
                  value={strategy.highlight_color}
                  onChange={e => update({ highlight_color: e.target.value })}
                  className="w-6 h-6 rounded border border-gray-300 cursor-pointer p-0 bg-transparent ml-2"
                  title="自定义色值"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-gray-600 font-medium">重点词微放大 (1.1x 动态强调)</span>
              <input
                type="checkbox"
                checked={strategy.highlight_scale}
                onChange={e => update({ highlight_scale: e.target.checked })}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
              />
            </div>

            <div>
              <span className="text-gray-600 block mb-1 font-medium">补充自定义高亮词 (逗号隔开)</span>
              <input
                type="text"
                value={strategy.custom_highlight_words?.join('，') || ''}
                onChange={e => {
                  const words = e.target.value.split(/[,，\s]+/).filter(Boolean);
                  update({ custom_highlight_words: words });
                }}
                placeholder="例如: 技巧，秘籍，包过，零基础"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* 3. 顶部 Title 挂顶横幅 (口播吸睛大标题) */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Type className="w-4 h-4 text-purple-600" />
            <h3 className="font-semibold text-sm text-gray-800">顶部 Title 挂顶横幅</h3>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={strategy.enable_top_banner}
              onChange={e => update({ enable_top_banner: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
          </label>
        </div>

        {strategy.enable_top_banner && (
          <div className="space-y-2.5 pt-1 border-t border-gray-100 text-xs">
            <div>
              <span className="text-gray-600 block mb-1 font-medium">主标题 (大字吸睛)</span>
              <input
                type="text"
                value={strategy.banner_main_title || ''}
                onChange={e => update({ banner_main_title: e.target.value })}
                placeholder="例如: 科目二一把过秘籍"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-purple-500 font-medium"
              />
            </div>
            <div>
              <span className="text-gray-600 block mb-1 font-medium">副标语 (可选金色辅助)</span>
              <input
                type="text"
                value={strategy.banner_sub_title || ''}
                onChange={e => update({ banner_sub_title: e.target.value })}
                placeholder="例如: 金牌教练现场教学 · 细节拆解"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* 4. 品牌防搬运水印角标 */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-emerald-600" />
            <h3 className="font-semibold text-sm text-gray-800">品牌水印角标 (防搬运)</h3>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={strategy.enable_watermark}
              onChange={e => update({ enable_watermark: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
          </label>
        </div>

        {strategy.enable_watermark && (
          <div className="space-y-2.5 pt-1 border-t border-gray-100 text-xs">
            <div>
              <span className="text-gray-600 block mb-1 font-medium">水印文字</span>
              <input
                type="text"
                value={strategy.watermark_text || ''}
                onChange={e => update({ watermark_text: e.target.value })}
                placeholder="例如: @顺达驾校官方教学"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600 font-medium">透明度 ({Math.round((strategy.watermark_opacity || 0.4) * 100)}%)</span>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={strategy.watermark_opacity || 0.4}
                onChange={e => update({ watermark_opacity: parseFloat(e.target.value) })}
                className="w-32 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
            </div>
          </div>
        )}
      </div>

      {/* 5. 空镜穿插节奏 (Pacing) */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Film className="w-4 h-4 text-indigo-600" />
            <h3 className="font-semibold text-sm text-gray-800">空镜穿插节奏 (B-roll Pacing)</h3>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            { id: 'fast', label: '快节奏混剪', sub: '2.0s 卡点' },
            { id: 'standard', label: '标准教学', sub: '3.5s 讲解' },
            { id: 'talking_only', label: '纯口播', sub: '不切空镜' },
          ].map(p => (
            <button
              key={p.id}
              type="button"
              onClick={() => update({ broll_pacing: p.id as any })}
              className={`p-2.5 rounded-lg border text-center transition-all ${
                strategy.broll_pacing === p.id
                  ? 'border-indigo-600 bg-indigo-50/40 text-indigo-700 font-semibold ring-1 ring-indigo-500'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              <div className="text-xs">{p.label}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">{p.sub}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 保存并同步策略按钮 */}
      {onSave && (
        <div className="pt-2">
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="w-full flex items-center justify-center space-x-2 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl shadow-md transition-colors disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            <span>{saving ? '正在保存策略...' : '保存并同步当前剪辑方案'}</span>
          </button>
        </div>
      )}
    </div>
  );
};