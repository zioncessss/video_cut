import React from 'react';
import { EditingStrategy } from '../services/api';
import { Palette, Sparkles, Type, Shield, Film, Check, Flame, Cpu, Sun, Layers, ShieldCheck } from 'lucide-react';

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
      id: 'glow_gold',
      name: '纯净发光金 (融入视频)',
      desc: '无黑底边框，文字纯白立体投影，关键词发光变金黄，自然融入视频画面',
      bgClass: 'bg-transparent text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] border-amber-400/40',
      badge: '✨ 无黑底·强烈推荐',
      icon: Sun
    },
    {
      id: 'glass_clean',
      name: '超透微磨砂 (融入视频)',
      desc: '极弱超透背景（不遮挡画面），字体通透清晰，科技感高级感并存',
      bgClass: 'bg-white/10 text-white backdrop-blur-[2px] border-white/30',
      badge: '🧊 纯净微透',
      icon: Layers
    },
    {
      id: 'cinema_shadow',
      name: '电影级立体白 (融入视频)',
      desc: '无任何底框，多层柔和深色外阴影，无论视频明暗均极度清晰易读',
      bgClass: 'bg-transparent text-white drop-shadow-[0_4px_6px_rgba(0,0,0,1)] border-gray-400/30',
      badge: '🎬 电影感',
      icon: Type
    },
    {
      id: 'viral_gold',
      name: '爆款胶囊金 (微黑底)',
      desc: '经典微黑半透胶囊 + 发光明黄，短视频传统高饱和吸睛样式',
      bgClass: 'bg-black/80 text-amber-400 border-amber-500/30',
      badge: '🔥 传统胶囊',
      icon: Flame
    },
    {
      id: 'tech_emerald',
      name: '科技青翠 (微黑底)',
      desc: '极客深黑 + 科技荧光青翠，适合理论法规与硬核步骤拆解',
      bgClass: 'bg-slate-900/80 text-emerald-400 border-emerald-500/30',
      badge: '💡 科技感',
      icon: Cpu
    },
    {
      id: 'marker_pen',
      name: '教学记号笔 (明亮底)',
      desc: '荧光黄底衬 + 纯黑大粗体，用于强调重点段落',
      bgClass: 'bg-amber-300 text-gray-950 border-amber-400',
      badge: '✏️ 记号划线',
      icon: Sparkles
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
    <div className="space-y-4 pb-4">
      {/* 1. 字幕视觉预设主题 (升级提供3套无黑底、融入视频的效果) */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Palette className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-xs text-gray-800">字幕呈现方案 (含融入画面·无黑底效果)</h3>
          </div>
          <span className="text-[10px] text-gray-400">支持像爱拍自由挑选</span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {themes.map(t => {
            const isSelected = strategy.subtitle_theme === t.id;
            const IconComponent = t.icon;
            return (
              <div
                key={t.id}
                onClick={() => update({ subtitle_theme: t.id as any })}
                className={`cursor-pointer rounded-xl p-2.5 border transition-all relative overflow-hidden ${
                  isSelected
                    ? 'border-blue-500 ring-2 ring-blue-500/20 shadow-md bg-blue-50/20'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1">
                    <IconComponent className={`w-3.5 h-3.5 ${isSelected ? 'text-blue-600' : 'text-gray-500'}`} />
                    <span className="font-semibold text-[11px] text-gray-800">{t.name}</span>
                  </div>
                </div>
                <span className="inline-block text-[9px] px-1.5 py-0.2 rounded bg-gray-100 text-gray-600 font-medium mb-1.5">
                  {t.badge}
                </span>
                <p className="text-[10px] text-gray-500 line-clamp-2 leading-tight mb-2">
                  {t.desc}
                </p>

                {/* 模拟视频背景上的字幕效果 */}
                <div className="bg-gradient-to-r from-emerald-800 to-slate-800 rounded p-1.5 text-center">
                  <div className={`text-[10px] font-bold px-1 py-0.5 rounded text-center inline-block ${t.bgClass}`}>
                    科目二 <span className="text-yellow-400 font-black">一把过</span>
                  </div>
                </div>

                {isSelected && (
                  <div className="absolute top-1 right-1">
                    <span className="flex h-3 w-3 relative">
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

      {/* 2. 字幕布局、大小与显示控制 (支持隐藏、字号、垂直位置微调与拖动提示) */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Type className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-xs text-gray-800">字幕控制与排版布局</h3>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-[10px] text-gray-500 font-medium">
              {strategy.show_subtitles !== false ? '显示字幕' : '已隐藏字幕'}
            </span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={strategy.show_subtitles !== false}
                onChange={e => update({ show_subtitles: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-8 h-4.5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>

        {strategy.show_subtitles !== false && (
          <div className="space-y-3 pt-1 border-t border-gray-100 text-xs">
            {/* 字号选择 */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-gray-600 font-medium text-[11px]">字幕字号大小</span>
                <span className="text-[10px] text-gray-400">
                  {strategy.font_size === 'small' && '小 (42px)'}
                  {(!strategy.font_size || strategy.font_size === 'medium') && '标准 (52px)'}
                  {strategy.font_size === 'large' && '大号 (64px)'}
                  {strategy.font_size === 'xlarge' && '超大 (76px)'}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                {[
                  { id: 'small', label: '小号' },
                  { id: 'medium', label: '标准' },
                  { id: 'large', label: '大号' },
                  { id: 'xlarge', label: '特大' },
                ].map(size => (
                  <button
                    key={size.id}
                    type="button"
                    onClick={() => update({ font_size: size.id as any })}
                    className={`py-1 rounded-lg border text-center text-[11px] transition-all ${
                      (strategy.font_size || 'medium') === size.id
                        ? 'border-blue-600 bg-blue-50 text-blue-700 font-bold'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {size.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 垂直位置调节 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">垂直位置 (Y轴高度)</span>
                <span className="text-[10px] font-mono text-gray-500">
                  {strategy.subtitle_position_y ?? 82}%
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="range"
                  min="20"
                  max="92"
                  step="1"
                  value={strategy.subtitle_position_y ?? 82}
                  onChange={e => update({ subtitle_position_y: parseInt(e.target.value, 10) })}
                  className="flex-1 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
              </div>
              <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ subtitle_position_y: 50 })}
                  className="hover:text-blue-600"
                >
                  居中 (50%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ subtitle_position_y: 72 })}
                  className="hover:text-blue-600"
                >
                  中下 (72%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ subtitle_position_y: 82 })}
                  className="hover:text-blue-600"
                >
                  贴底 (82%)
                </button>
              </div>
              <div className="mt-1.5 bg-blue-50/60 rounded p-1.5 text-[10px] text-blue-700 flex items-center space-x-1">
                <span>💡</span>
                <span>也可直接在左侧播放器中按住字幕自由拖动调整位置！</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 3. 关键词精准高亮控制 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <h3 className="font-semibold text-xs text-gray-800">单句内关键词精准高亮 (单词强调)</h3>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={strategy.enable_highlight}
              onChange={e => update({ enable_highlight: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-8 h-4.5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-amber-500"></div>
          </label>
        </div>

        {strategy.enable_highlight && (
          <div className="space-y-2.5 pt-1 border-t border-gray-100 text-xs">
            <div>
              <span className="text-gray-600 block mb-1 font-medium text-[11px]">高亮强调色彩</span>
              <div className="flex items-center space-x-2">
                {highlightColors.map(c => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => update({ highlight_color: c.value })}
                    className={`w-5 h-5 rounded-full flex items-center justify-center transition-transform ${c.bg} ${
                      strategy.highlight_color === c.value
                        ? 'ring-2 ring-offset-1 ring-gray-600 scale-110'
                        : 'opacity-80 hover:opacity-100'
                    }`}
                    title={c.name}
                  >
                    {strategy.highlight_color === c.value && (
                      <Check className="w-2.5 h-2.5 text-white stroke-[3]" />
                    )}
                  </button>
                ))}
                <input
                  type="color"
                  value={strategy.highlight_color}
                  onChange={e => update({ highlight_color: e.target.value })}
                  className="w-5 h-5 rounded border border-gray-300 cursor-pointer p-0 bg-transparent ml-2"
                  title="自定义色值"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-0.5">
              <span className="text-gray-600 font-medium text-[11px]">高亮词微放大 (1.1x 动态强调)</span>
              <input
                type="checkbox"
                checked={strategy.highlight_scale}
                onChange={e => update({ highlight_scale: e.target.checked })}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5"
              />
            </div>

            <div>
              <span className="text-gray-600 block mb-1 font-medium text-[11px]">
                专有高亮词库 (AI 会智能检测这些词并精准高亮句子里的这几个字)
              </span>
              <input
                type="text"
                value={strategy.custom_highlight_words?.join('，') || ''}
                onChange={e => {
                  const words = e.target.value.split(/[,，\s]+/).filter(Boolean);
                  update({ custom_highlight_words: words });
                }}
                placeholder="例如: 科目二，一把过，金牌教练，十分钟，快速搞定"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* 3. 顶部 Title 挂顶横幅 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Type className="w-4 h-4 text-purple-600" />
            <h3 className="font-semibold text-xs text-gray-800">顶部 Title 挂顶横幅 (防重叠设计)</h3>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={strategy.enable_top_banner}
              onChange={e => update({ enable_top_banner: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-8 h-4.5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-purple-600"></div>
          </label>
        </div>

        {strategy.enable_top_banner && (
          <div className="space-y-2 pt-1 border-t border-gray-100 text-xs">
            <div>
              <span className="text-gray-600 block mb-1 font-medium text-[11px]">主标题 (大字吸睛)</span>
              <input
                type="text"
                value={strategy.banner_main_title || ''}
                onChange={e => update({ banner_main_title: e.target.value })}
                placeholder="例如: 科目二一把过秘籍"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-purple-500 font-medium"
              />
            </div>
            <div>
              <span className="text-gray-600 block mb-1 font-medium text-[11px]">副标语 (可选金色辅助)</span>
              <input
                type="text"
                value={strategy.banner_sub_title || ''}
                onChange={e => update({ banner_sub_title: e.target.value })}
                placeholder="例如: 教练手把手教学"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* 4. 品牌防搬运水印角标 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Shield className="w-4 h-4 text-emerald-600" />
            <h3 className="font-semibold text-xs text-gray-800">品牌水印角标 (右上角)</h3>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={strategy.enable_watermark}
              onChange={e => update({ enable_watermark: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-8 h-4.5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-600"></div>
          </label>
        </div>

        {strategy.enable_watermark && (
          <div className="space-y-2 pt-1 border-t border-gray-100 text-xs">
            <div>
              <span className="text-gray-600 block mb-1 font-medium text-[11px]">水印文字</span>
              <input
                type="text"
                value={strategy.watermark_text || ''}
                onChange={e => update({ watermark_text: e.target.value })}
                placeholder="例如: @顺达驾校官方教学"
                className="w-full text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-600 font-medium text-[11px]">透明度 ({Math.round((strategy.watermark_opacity || 0.4) * 100)}%)</span>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={strategy.watermark_opacity || 0.4}
                onChange={e => update({ watermark_opacity: parseFloat(e.target.value) })}
                className="w-28 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
            </div>
          </div>
        )}
      </div>

      {/* 5. 空镜穿插节奏 (Pacing) */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-1.5">
            <Film className="w-4 h-4 text-indigo-600" />
            <h3 className="font-semibold text-xs text-gray-800">空镜穿插节奏 (B-roll Pacing)</h3>
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
              className={`p-2 rounded-lg border text-center transition-all ${
                strategy.broll_pacing === p.id
                  ? 'border-indigo-600 bg-indigo-50/40 text-indigo-700 font-semibold ring-1 ring-indigo-500'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              <div className="text-xs">{p.label}</div>
              <div className="text-[9px] text-gray-400 mt-0.5">{p.sub}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 保存并同步策略按钮 */}
      {onSave && (
        <div className="pt-1">
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="w-full flex items-center justify-center space-x-1.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors disabled:opacity-50"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{saving ? '正在保存策略...' : '保存并同步当前剪辑方案'}</span>
          </button>
        </div>
      )}
    </div>
  );
};