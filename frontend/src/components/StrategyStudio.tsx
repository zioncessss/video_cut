import React from 'react';
import { EditingStrategy } from '../services/api';
import { Palette, Type, Shield, Film, Check, Flame, Cpu, Sun, Layers, ShieldCheck, Gauge } from 'lucide-react';

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
  const fontOptions = [
    {
      id: 'notoserif',
      name: '思源 / 华文中宋',
      sub: 'STZhongsong / Noto Serif',
      tag: '电影质感 · 横细竖粗',
      desc: '当代院线与纪录片首选，现代几何美感，小屏超高辨识度',
      sample: '沉着入库，一气呵成',
      fontFamily: '"STZhongsong", "华文中宋", "Source Han Serif SC", "Noto Serif SC", "思源宋体", serif',
    },
    {
      id: 'fangsong',
      name: '清雅仿宋',
      sub: 'FangSong',
      tag: '文艺挺秀 · 信札风骨',
      desc: '笔画秀拔匀称，兼具传统书法风骨与文学剧本文艺感',
      sample: '沉着入库，一气呵成',
      fontFamily: '"FangSong", "FangSong_GB2312", "STFangsong", serif',
    },
    {
      id: 'songti',
      name: '经典宋体',
      sub: 'SimSun',
      tag: '典雅书卷 · 传统印刷',
      desc: '中易宋体正风，端庄规整，古典书籍与传统排版沉淀感',
      sample: '沉着入库，一气呵成',
      fontFamily: '"STSong", "SimSun", "Songti SC", serif',
    },
    {
      id: 'kaiti',
      name: '书法楷体',
      sub: 'KaiTi',
      tag: '原图同款 · 温润叙事',
      desc: '毛笔手写质感，真诚温和，短视频爆款叙事口播原汁原味',
      sample: '沉着入库，一气呵成',
      fontFamily: '"KaiTi", "STKaiti", "华文楷体", serif',
    },
    {
      id: 'yahei',
      name: '现代黑体',
      sub: 'Microsoft YaHei',
      tag: '干脆清晰 · 无衬线',
      desc: '无衬线纯净现代，信息传递干脆利落，适合快节奏干货',
      sample: '沉着入库，一气呵成',
      fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif',
    },
  ];

  const update = (partial: Partial<EditingStrategy>) => {
    onChange({ ...strategy, ...partial });
  };

  return (
    <div className="space-y-4 pb-4">
      {/* 1. 字幕视觉风格：只保留「电影立体白」与字体质感对比 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200/80 shadow-xs">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-1.5">
            <Film className="w-4 h-4 text-indigo-600" />
            <h3 className="font-semibold text-xs text-gray-800">字幕视觉风格</h3>
          </div>
          <span className="text-[10px] text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full font-medium border border-indigo-100/80">
            电影立体白 · 独家定制
          </span>
        </div>

        {/* 电影立体白专属展示卡片 */}
        <div className="rounded-xl p-3 border border-indigo-500/40 bg-indigo-50/20 relative overflow-hidden">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center space-x-1.5">
              <Type className="w-3.5 h-3.5 text-indigo-600" />
              <span className="font-bold text-xs text-gray-900">电影立体白</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-indigo-100 text-indigo-700 font-semibold">
                电影质感
              </span>
            </div>
            <span className="text-[10px] text-gray-400">紧凑微阴影 · 无黑底遮挡</span>
          </div>

          <p className="text-[10px] text-gray-500 leading-relaxed mb-2.5">
            纯白字身辅以紧凑柔和微阴影（Shadow 1.8），在明暗复杂画面中均通透清晰，完美融入视频。
          </p>

          {/* 实时模拟当前字体与高亮效果的电影字幕预览条 */}
          <div className="bg-gradient-to-r from-zinc-950 via-slate-900 to-zinc-950 rounded-lg py-3 px-3 text-center border border-zinc-800/80 shadow-inner">
            <div
              style={{
                fontFamily:
                  (strategy.subtitle_font_family === 'kaiti')
                    ? '"KaiTi", "STKaiti", serif'
                    : (strategy.subtitle_font_family === 'fangsong')
                    ? '"FangSong", "FangSong_GB2312", "STFangsong", serif'
                    : (strategy.subtitle_font_family === 'songti')
                    ? '"STSong", "SimSun", serif'
                    : (strategy.subtitle_font_family === 'yahei')
                    ? '"Microsoft YaHei", sans-serif'
                    : '"STZhongsong", "华文中宋", "Source Han Serif SC", "Noto Serif SC", "思源宋体", serif',
                textShadow: '0 1.5px 3px rgba(0,0,0,0.85), 0 0.5px 1px rgba(0,0,0,0.6)',
              }}
              className="text-[13px] font-bold text-white tracking-wider inline-block select-none"
            >
              科目二 <span style={{ color: strategy.highlight_color || '#FBBF24' }} className="font-extrabold mx-0.5">一把过</span> 秘籍
            </div>
          </div>
        </div>

        {/* 字幕字体风格对比与选择 (思源宋体 / 清雅仿宋 / 经典宋体 / 书法楷体 / 现代黑体) */}
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-800 font-semibold text-xs">字体质感对比与选择</span>
            <span className="text-[10px] text-indigo-600 font-medium bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
              {(() => {
                switch (strategy.subtitle_font_family) {
                  case 'fangsong': return '📜 清雅仿宋 · 文艺清秀';
                  case 'songti': return '📖 经典宋体 · 书卷沉稳';
                  case 'yahei': return '🔤 现代黑体 · 清晰利落';
                  case 'kaiti': return '🖋️ 书法楷体 · 原图同款';
                  case 'notoserif':
                  default: return '🎬 华文中宋 / 思源 · 电影质感';
                }
              })()}
            </span>
          </div>

          <div className="space-y-1.5">
            {fontOptions.map(f => {
              const active = (strategy.subtitle_font_family || 'notoserif') === f.id;
              return (
                <div
                  key={f.id}
                  onClick={() => update({ subtitle_font_family: f.id as any })}
                  className={`cursor-pointer rounded-lg p-2 border transition-all flex items-center justify-between ${
                    active
                      ? 'border-indigo-600 bg-indigo-50/60 ring-1 ring-indigo-500/30 shadow-xs'
                      : 'border-gray-200/90 hover:border-gray-300 hover:bg-gray-50/70'
                  }`}
                >
                  <div className="flex-1 min-w-0 mr-2">
                    <div className="flex items-center space-x-1.5 mb-0.5">
                      <span className={`text-[11px] font-bold ${active ? 'text-indigo-900' : 'text-gray-800'}`}>
                        {f.name}
                      </span>
                      <span className="text-[9px] px-1 py-0.2 rounded bg-gray-100 text-gray-600 font-medium">
                        {f.tag}
                      </span>
                    </div>
                    <div className="text-[10px] text-gray-500 truncate">{f.desc}</div>
                  </div>
                  <div
                    style={{ fontFamily: f.fontFamily }}
                    className={`text-xs px-2 py-1 rounded tracking-wider border select-none flex-shrink-0 ${
                      active
                        ? 'bg-indigo-600 text-white border-indigo-600 font-bold'
                        : 'bg-white text-gray-700 border-gray-200'
                    }`}
                  >
                    {f.sample}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. 字幕布局、大小与显示控制 (宽度锁定 100%，仅垂直微调与字号) */}
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
            {/* 字号选择：预设档位 + 连续滑块 */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-gray-600 font-medium text-[11px]">字幕字号大小</span>
                <span className="text-[10px] font-mono text-blue-600 font-semibold">
                  {strategy.subtitle_font_size || (strategy.font_size === 'small' ? 56 : strategy.font_size === 'large' ? 86 : strategy.font_size === 'xlarge' ? 98 : 72)}px
                </span>
              </div>
              <div className="grid grid-cols-4 gap-1.5 mb-2">
                {[
                  { id: 'small', px: 56, label: '小号 (56px)' },
                  { id: 'medium', px: 72, label: '标准 (72px)' },
                  { id: 'large', px: 86, label: '大号 (86px)' },
                  { id: 'xlarge', px: 98, label: '特大 (98px)' },
                ].map(size => (
                  <button
                    key={size.id}
                    type="button"
                    onClick={() => update({ font_size: size.id as any, subtitle_font_size: size.px })}
                    className={`py-1 rounded-lg border text-center text-[10px] transition-all cursor-pointer ${
                      (strategy.subtitle_font_size === size.px || (!strategy.subtitle_font_size && (strategy.font_size || 'medium') === size.id))
                        ? 'border-blue-600 bg-blue-50 text-blue-700 font-bold'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {size.label}
                  </button>
                ))}
              </div>
              <input
                type="range"
                min="36"
                max="110"
                step="1"
                value={strategy.subtitle_font_size || (strategy.font_size === 'small' ? 56 : strategy.font_size === 'large' ? 86 : strategy.font_size === 'xlarge' ? 98 : 72)}
                onChange={e => update({ subtitle_font_size: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
            </div>

            {/* 垂直位置 (Y轴微调，宽度一律锁定 100%) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-700 font-medium text-[11px]">垂直高度 (Y轴微调)</span>
                <span className="text-[10px] font-mono text-indigo-600 font-bold">
                  {strategy.subtitle_position_y ?? 74}%
                </span>
              </div>
              <input
                type="range"
                min="50"
                max="90"
                step="1"
                value={strategy.subtitle_position_y ?? 74}
                onChange={e => update({ subtitle_position_y: parseInt(e.target.value, 10), subtitle_position_x: 50, subtitle_width_percent: 100 })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
              <div className="flex items-center justify-between mt-1.5 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ subtitle_position_y: 65, subtitle_position_x: 50, subtitle_width_percent: 100 })}
                  className="hover:text-indigo-600 cursor-pointer"
                >
                  视线中位 (65%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ subtitle_position_y: 74, subtitle_position_x: 50, subtitle_width_percent: 100 })}
                  className="text-indigo-600 font-bold bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200/80 hover:bg-indigo-100 cursor-pointer"
                  title="原图同款推荐位：既避开人物面部与下巴，又安全悬停在底部进度条与文案安全区上方"
                >
                  ★ 黄金推荐位 (74%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ subtitle_position_y: 82, subtitle_position_x: 50, subtitle_width_percent: 100 })}
                  className="hover:text-indigo-600 cursor-pointer"
                >
                  下沉贴底 (82%)
                </button>
              </div>
              <div className="mt-1.5 text-[10px] text-gray-500 bg-gray-50 rounded p-1.5 flex items-center justify-between">
                <span>🔒 字幕宽度已锁定 100% 全宽居中</span>
                <span className="text-gray-400">避开人脸与底部控制栏</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 2. 顶部 Title 挂顶横幅 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-2">
            <Type className="w-4 h-4 text-purple-600" />
            <h3 className="font-semibold text-xs text-gray-800">顶部 Title 挂顶横幅</h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
              strategy.enable_top_banner ? 'bg-purple-50 text-purple-600' : 'bg-gray-100 text-gray-400'
            }`}>
              {strategy.enable_top_banner ? '已开启' : '未开启'}
            </span>
          </div>
          {/* 圆点 Toggle 开关：点击开启，并出现圆点可再次点击取消 */}
          <button
            type="button"
            role="switch"
            aria-checked={strategy.enable_top_banner}
            onClick={() => update({ enable_top_banner: !strategy.enable_top_banner })}
            className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
              strategy.enable_top_banner ? 'bg-purple-600' : 'bg-gray-300'
            }`}
            title={strategy.enable_top_banner ? '点击取消 Title 横幅' : '点击开启 Title 横幅'}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                strategy.enable_top_banner ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        {strategy.enable_top_banner && (
          <div className="space-y-2.5 pt-1 border-t border-gray-100 text-xs">
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

            {/* 横幅大小调节：预设档位 + 连续灵活滑块 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">横幅字号大小</span>
                <span className="text-[10px] font-mono text-purple-600 font-semibold">
                  {strategy.banner_font_size || (strategy.banner_size === 'small' ? 36 : strategy.banner_size === 'large' ? 60 : 48)}px
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 mb-2">
                {[
                  { id: 'small', px: 36, label: '小号 (36px)' },
                  { id: 'medium', px: 48, label: '标准 (48px)' },
                  { id: 'large', px: 60, label: '大号 (60px)' },
                ].map(size => (
                  <button
                    key={size.id}
                    type="button"
                    onClick={() => update({ banner_size: size.id as any, banner_font_size: size.px })}
                    className={`py-1 rounded-lg border text-center text-[10px] transition-all ${
                      (strategy.banner_font_size === size.px || (!strategy.banner_font_size && (strategy.banner_size || 'medium') === size.id))
                        ? 'border-purple-600 bg-purple-50 text-purple-700 font-bold'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {size.label}
                  </button>
                ))}
              </div>
              <input
                type="range"
                min="20"
                max="72"
                step="1"
                value={strategy.banner_font_size || (strategy.banner_size === 'small' ? 36 : strategy.banner_size === 'large' ? 60 : 48)}
                onChange={e => update({ banner_font_size: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
              />
            </div>

            {/* 横幅宽度 (横向空间伸缩) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">横幅宽度 (边框拉伸 / 自适应)</span>
                <span className="text-[10px] font-mono text-purple-600 font-semibold">
                  {strategy.banner_width_percent ? `${strategy.banner_width_percent}%` : '紧凑胶囊自适应'}
                </span>
              </div>
              <input
                type="range"
                min="25"
                max="95"
                step="1"
                value={strategy.banner_width_percent || 90}
                onChange={e => update({ banner_width_percent: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
              />
              <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ banner_width_percent: undefined })}
                  className="hover:text-purple-600"
                >
                  紧凑胶囊 (默认)
                </button>
                <button
                  type="button"
                  onClick={() => update({ banner_width_percent: 60 })}
                  className="hover:text-purple-600"
                >
                  中等半宽 (60%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ banner_width_percent: 90 })}
                  className="hover:text-purple-600"
                >
                  全宽贯穿 (90%)
                </button>
              </div>
            </div>

            {/* 横幅水平位置 (X轴左右移动) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">水平位置 (X轴左右移动)</span>
                <span className="text-[10px] font-mono text-purple-600 font-semibold">
                  {strategy.banner_position_x ?? 50}%
                </span>
              </div>
              <input
                type="range"
                min="10"
                max="90"
                step="1"
                value={strategy.banner_position_x ?? 50}
                onChange={e => update({ banner_position_x: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
              />
              <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ banner_position_x: 30 })}
                  className="hover:text-purple-600"
                >
                  偏左 (30%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ banner_position_x: 50 })}
                  className="hover:text-purple-600"
                >
                  居中 (50%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ banner_position_x: 70 })}
                  className="hover:text-purple-600"
                >
                  偏右 (70%)
                </button>
              </div>
            </div>

            {/* 横幅垂直位置 (Y轴上下移动) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">垂直位置 (Y轴上下高度)</span>
                <span className="text-[10px] font-mono text-purple-600 font-semibold">
                  {strategy.banner_position_y ?? 10}%
                </span>
              </div>
              <input
                type="range"
                min="2"
                max="85"
                step="1"
                value={strategy.banner_position_y ?? 10}
                onChange={e => update({ banner_position_y: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
              />
              <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ banner_position_y: 6 })}
                  className="hover:text-purple-600"
                >
                  顶部 (6%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ banner_position_y: 18 })}
                  className="hover:text-purple-600"
                >
                  中上 (18%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ banner_position_y: 48 })}
                  className="hover:text-purple-600"
                >
                  居中 (48%)
                </button>
              </div>
              <div className="mt-1.5 bg-purple-50/60 rounded p-1.5 text-[10px] text-purple-700 flex items-center space-x-1">
                <span>💡</span>
                <span>也可直接在左侧视频画面中鼠标按住横幅上下左右自由拖动！</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4. 品牌防搬运水印角标 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200 shadow-sm">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-emerald-600" />
            <h3 className="font-semibold text-xs text-gray-800">品牌水印角标</h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
              strategy.enable_watermark ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'
            }`}>
              {strategy.enable_watermark ? '已开启' : '未开启'}
            </span>
          </div>
          {/* 圆点 Toggle 开关：点击开启，并出现圆点可再次点击取消 */}
          <button
            type="button"
            role="switch"
            aria-checked={strategy.enable_watermark}
            onClick={() => update({ enable_watermark: !strategy.enable_watermark })}
            className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
              strategy.enable_watermark ? 'bg-emerald-600' : 'bg-gray-300'
            }`}
            title={strategy.enable_watermark ? '点击取消水印' : '点击开启水印'}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                strategy.enable_watermark ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        {strategy.enable_watermark && (
          <div className="space-y-2.5 pt-1 border-t border-gray-100 text-xs">
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

            {/* 水印尺寸调节：预设档位 + 连续灵活滑块 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">水印字号大小</span>
                <span className="text-[10px] font-mono text-emerald-600 font-semibold">
                  {strategy.watermark_font_size || (strategy.watermark_size === 'small' ? 22 : strategy.watermark_size === 'large' ? 44 : 32)}px
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 mb-2">
                {[
                  { id: 'small', px: 22, label: '小号 (22px)' },
                  { id: 'medium', px: 32, label: '标准 (32px)' },
                  { id: 'large', px: 44, label: '大号 (44px)' },
                ].map(size => (
                  <button
                    key={size.id}
                    type="button"
                    onClick={() => update({ watermark_size: size.id as any, watermark_font_size: size.px })}
                    className={`py-1 rounded-lg border text-center text-[10px] transition-all ${
                      (strategy.watermark_font_size === size.px || (!strategy.watermark_font_size && (strategy.watermark_size || 'medium') === size.id))
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-700 font-bold'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {size.label}
                  </button>
                ))}
              </div>
              <input
                type="range"
                min="14"
                max="60"
                step="1"
                value={strategy.watermark_font_size || (strategy.watermark_size === 'small' ? 22 : strategy.watermark_size === 'large' ? 44 : 32)}
                onChange={e => update({ watermark_font_size: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
            </div>

            {/* 水印 4 角预设位置 */}
            <div>
              <span className="text-gray-600 block mb-1 font-medium text-[11px]">角标方位预设</span>
              <div className="grid grid-cols-4 gap-1.5">
                {[
                  { id: 'top_left', label: '左上', x: 4, y: 3 },
                  { id: 'top_right', label: '右上', x: 96, y: 3 },
                  { id: 'bottom_left', label: '左下', x: 4, y: 96 },
                  { id: 'bottom_right', label: '右下', x: 96, y: 96 },
                ].map(pos => (
                  <button
                    key={pos.id}
                    type="button"
                    onClick={() => update({
                      watermark_position: pos.id as any,
                      watermark_position_x: pos.x,
                      watermark_position_y: pos.y
                    })}
                    className={`py-1 rounded-lg border text-center text-[11px] transition-all ${
                      (strategy.watermark_position_x === pos.x && strategy.watermark_position_y === pos.y) ||
                      (strategy.watermark_position_x === undefined && (strategy.watermark_position || 'top_right') === pos.id)
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-700 font-bold'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {pos.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 水印水平微调 (X 轴左右移动) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">水平微调 (X轴左右移动)</span>
                <span className="text-[10px] font-mono text-emerald-600 font-semibold">
                  {strategy.watermark_position_x !== undefined ? `${strategy.watermark_position_x}%` : ((strategy.watermark_position || 'top_right').endsWith('left') ? '4% (靠左)' : '96% (靠右)')}
                </span>
              </div>
              <input
                type="range"
                min="2"
                max="98"
                step="1"
                value={strategy.watermark_position_x ?? ((strategy.watermark_position || 'top_right').endsWith('left') ? 4 : 96)}
                onChange={e => update({ watermark_position_x: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
              <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ watermark_position_x: 4 })}
                  className="hover:text-emerald-600"
                >
                  靠左 (4%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ watermark_position_x: 50 })}
                  className="hover:text-emerald-600"
                >
                  居中 (50%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ watermark_position_x: 96 })}
                  className="hover:text-emerald-600"
                >
                  靠右 (96%)
                </button>
              </div>
            </div>

            {/* 水印垂直微调 (Y 轴上下移动) */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-600 font-medium text-[11px]">垂直微调 (Y轴上下移动)</span>
                <div className="flex items-center space-x-1.5">
                  <span className="text-[10px] font-mono text-emerald-600 font-semibold">
                    {strategy.watermark_position_y !== undefined ? `${strategy.watermark_position_y}%` : ((strategy.watermark_position || 'top_right').startsWith('bottom') ? '96% (靠底)' : '3% (靠顶)')}
                  </span>
                  {(strategy.watermark_position_x !== undefined || strategy.watermark_position_y !== undefined) && (
                    <button
                      type="button"
                      onClick={() => update({ watermark_position_x: undefined, watermark_position_y: undefined })}
                      className="text-[9px] text-gray-400 hover:text-emerald-600 underline"
                    >
                      重置回角标
                    </button>
                  )}
                </div>
              </div>
              <input
                type="range"
                min="2"
                max="98"
                step="1"
                value={strategy.watermark_position_y ?? ((strategy.watermark_position || 'top_right').startsWith('bottom') ? 96 : 3)}
                onChange={e => update({ watermark_position_y: parseInt(e.target.value, 10) })}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
              />
              <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400">
                <button
                  type="button"
                  onClick={() => update({ watermark_position_y: 3 })}
                  className="hover:text-emerald-600"
                >
                  靠顶 (3%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ watermark_position_y: 50 })}
                  className="hover:text-emerald-600"
                >
                  居中 (50%)
                </button>
                <button
                  type="button"
                  onClick={() => update({ watermark_position_y: 96 })}
                  className="hover:text-emerald-600"
                >
                  靠底 (96%)
                </button>
              </div>
              <div className="mt-1.5 bg-emerald-50/60 rounded p-1.5 text-[10px] text-emerald-700 flex items-center space-x-1">
                <span>💡</span>
                <span>也可直接在左侧视频画面中鼠标按住水印上下左右自由拖动！</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
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

      {/* 5. 语速与节奏 */}
      <div className="bg-white rounded-xl p-3.5 border border-gray-200/80 shadow-xs">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center space-x-1.5">
            <Gauge className="w-4 h-4 text-indigo-600" />
            <h3 className="font-semibold text-xs text-gray-800">导出倍速与语速</h3>
          </div>
          <div className="flex items-center space-x-1 bg-indigo-50/80 border border-indigo-200/80 rounded-lg px-2 py-0.5 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500/20">
            <input
              type="number"
              step="0.01"
              min="0.5"
              max="2.5"
              value={strategy.video_speed ?? 1.0}
              onChange={e => {
                const val = parseFloat(e.target.value);
                update({ video_speed: isNaN(val) ? 1.0 : Math.max(0.5, Math.min(2.5, Math.round(val * 100) / 100)) });
              }}
              className="w-12 text-center text-xs font-mono font-bold text-indigo-700 bg-transparent outline-none"
              title="自由输入任意导出倍速（如 1.08, 1.12, 1.15, 1.33 等）"
            />
            <span className="text-[11px] font-mono text-indigo-500 font-bold">x</span>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-1.5 mb-2.5">
          {[
            { speed: 1.0, label: '1.0x', tag: '原速' },
            { speed: 1.1, label: '1.1x', tag: '紧凑' },
            { speed: 1.15, label: '1.15x', tag: '轻快' },
            { speed: 1.2, label: '1.2x', tag: '干脆' },
            { speed: 1.25, label: '1.25x', tag: '快嘴' },
          ].map(item => {
            const currentSpeed = Number(strategy.video_speed || 1.0);
            const active = Math.abs(currentSpeed - item.speed) < 0.005;
            return (
              <button
                key={item.speed}
                type="button"
                onClick={() => update({ video_speed: item.speed })}
                className={`py-1.5 px-1 rounded-lg border text-center transition-all cursor-pointer ${
                  active
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 font-bold shadow-xs ring-1 ring-indigo-500/30'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                <div className="text-xs font-mono">{item.label}</div>
                <div className="text-[9px] text-gray-400 mt-0.5">{item.tag}</div>
              </button>
            );
          })}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-gray-500 text-[11px]">连续精准微调 (步长 0.01)</span>
            <span className="text-[10px] font-mono text-gray-400">0.50x ~ 2.00x</span>
          </div>
          <input
            type="range"
            min="0.50"
            max="2.00"
            step="0.01"
            value={strategy.video_speed || 1.0}
            onChange={e => update({ video_speed: Math.round(parseFloat(e.target.value) * 100) / 100 })}
            className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
          />
          <div className="flex items-center justify-between mt-1 text-[9px] text-gray-400 font-mono">
            <span>0.50x 慢速</span>
            <span>1.00x 原速</span>
            <span>1.50x 快速</span>
            <span>2.00x 极速</span>
          </div>
        </div>
      </div>



      {/* 保存方案按钮 */}
      {onSave && (
        <div className="pt-1">
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="w-full flex items-center justify-center space-x-1.5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors disabled:opacity-50"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{saving ? '正在保存...' : '保存剪辑方案'}</span>
          </button>
        </div>
      )}
    </div>
  );
};