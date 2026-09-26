import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Sparkles,
  Image as ImageIcon,
  FolderOpen,
  Layers,
  Shield,
  Check,
  Flame,
  RefreshCw,
  Crop,
  Maximize2,
  MapPin,
  Palette,
  AlertCircle,
  Heading1,
  Tag,
  Type,
  MoveVertical,
  Move,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  Upload
} from 'lucide-react';
import {
  CoverDesignConfig,
  CoverTextZoneStyle,
  CoverZoneKey,
  SuggestedCoverTitle,
  CoverCandidateFrame,
  CoverTemplateItem,
  CoverPalette,
  CoverSafeZoneRect,
  getCoverCandidates,
  getCoverTemplates,
  uploadProjectCoverFile,
  getMediaUrl
} from '../services/api';

export interface CoverPreviewSelectorProps {
  projectId: string;
  initialConfig?: Partial<CoverDesignConfig>;
  suggestedTitles?: SuggestedCoverTitle[];
  currentVideoTime?: number;
  onConfigChange: (config: CoverDesignConfig, customFile?: File) => void;
  embedCoverAsFirstFrame: boolean;
  onToggleEmbedFirstFrame: (embed: boolean) => void;
}

// 6 大实战模板静态兜底目录（与后端 COVER_TEMPLATES_CATALOG 对齐，API 失败时保底可用）
const FALLBACK_TEMPLATES: CoverTemplateItem[] = [
  { id: 'text_behind_person', name: '同城爆款三段贴纸大字', category: 'local_burst', badge: '🔥 顶流同款', sample_preview: '兔牙教练同款', description: '顶部拱形微弧大字 + 胸前引导小标 + 底部亮黄转化大字，单字独立黄金微隙，原汁原味真实画面', supported_themes: ['classic_blue', 'authority_red', 'sunset_orange'] },
  { id: 'sticker_double_stroke', name: '双层描边贴纸大字', category: 'local_hook', badge: '👑 经典贴纸', sample_preview: '武义学车款', description: '顶部超大双层描边地域大字，底部胶囊引导', supported_themes: ['neon_cyber', 'authority_red', 'hot_pink_gold'] },
  { id: 'split_contrast_bar', name: '上下通栏权威撞色条', category: 'authority_banner', badge: '🏛️ 权威正规', sample_preview: '杭州学车款', description: '红底通栏白字 + 白底通栏深红痛点', supported_themes: ['authority_red', 'frost_burgundy'] },
  { id: 'rainbow_arc_header', name: '拱形包头彩虹字', category: 'curved_impact', badge: '⚡ 同城爆款', sample_preview: '金华金东款', description: '向上拱形字环抱发顶不挡脸', supported_themes: ['hot_pink_gold', 'neon_cyber'] },
  { id: 'bottom_fog_vignette', name: '胸前羽化白光沉浸字', category: 'vignette_focus', badge: '✨ 高级清透', sample_preview: '婺城学车款', description: '底部白光雾化弱化杂乱背景', supported_themes: ['frost_burgundy', 'authority_red'] },
  { id: 'angled_impact_stamp', name: '倾角冲击引流标', category: 'angled_stamp', badge: '💥 强烈冲击', sample_preview: '绍兴学车款', description: '-10° 动感倾斜贴纸 + 金句', supported_themes: ['authority_red', 'hot_pink_gold'] },
  { id: 'clean_editorial', name: '极简轻奢杂志风', category: 'editorial', badge: '📖 知性轻奢', sample_preview: '小红书爆款', description: '英文章节标 + 纯白大字高级留白', supported_themes: ['frost_burgundy'] },
  { id: 'neon_3d_sticker', name: '荧光绿 3D 贴纸大字', category: 'local_burst', badge: '⚡ 顶流爆款', sample_preview: '女生学车款', description: '顶部拱形微弧荧光黄绿大字 + 实体3D深绿挤压厚度 + 纯白副标与转化大字 + 纯白手绘高光涂鸦', supported_themes: ['neon_lime', 'classic_blue', 'authority_red'] }
];

// 工业级高转化调色盘（色值与后端 COVER_PALETTES 严格一致：经典宝蓝、国潮警示红、曜石黑金、暖阳橙、极光青、雪白酒红、荧光黄绿）
const FALLBACK_PALETTES: CoverPalette[] = [
  { id: 'classic_blue', name: '经典深宝蓝', main: '#124CD6', sub: '#FFFFFF', accent: '#FFDD00' },
  { id: 'authority_red', name: '国潮警示红', main: '#DC2626', sub: '#FFFFFF', accent: '#FEF08A' },
  { id: 'obsidian_gold', name: '曜石黑金', main: '#0F172A', sub: '#F59E0B', accent: '#FFD200' },
  { id: 'sunset_orange', name: '暖阳橙金', main: '#EA580C', sub: '#FFFFFF', accent: '#FEF08A' },
  { id: 'aurora_emerald', name: '极光青翠', main: '#0F766E', sub: '#FFFFFF', accent: '#FEF08A' },
  { id: 'frost_burgundy', name: '雪白酒红', main: '#991B1B', sub: '#FFFFFF', accent: '#FDE047' },
  { id: 'neon_lime', name: '荧光绿 3D', main: '#DBFA11', sub: '#2A5101', accent: '#FFFFFF' }
];


// 工业级精选全案设计模板（3区联动视觉方案，首推截图同款蓝黄撞色）
export interface MasterDesignTemplate {
  id: string;
  name: string;
  subtitle: string;
  badge: string;
  palette_id: string;
  template_id?: CoverDesignConfig['template_id'];
  zones: {
    location: { text_color: string; stroke_color: string };
    sub: { text_color: string; stroke_color: string };
    main: { text_color: string; stroke_color: string };
  };
}

export const MASTER_DESIGN_TEMPLATES: MasterDesignTemplate[] = [
  {
    id: 'blue_yellow_burst',
    name: '顶流爆款',
    subtitle: '蓝黄撞色',
    badge: '👑 推荐',
    palette_id: 'classic_blue',
    template_id: 'text_behind_person',
    zones: {
      location: { text_color: '#FFFFFF', stroke_color: '#124CD6' },
      sub: { text_color: '#FFFFFF', stroke_color: '#124CD6' },
      main: { text_color: '#FFDD00', stroke_color: '#124CD6' }
    }
  },
  {
    id: 'neon_lime_3d',
    name: '荧光绿 3D',
    subtitle: '实体立体',
    badge: '⚡ 爆款',
    palette_id: 'neon_lime',
    template_id: 'neon_3d_sticker',
    zones: {
      location: { text_color: '#DBFA11', stroke_color: '#2A5101' },
      sub: { text_color: '#FFFFFF', stroke_color: '#2A5101' },
      main: { text_color: '#FFFFFF', stroke_color: '#2A5101' }
    }
  },
  {
    id: 'authority_red_gold',
    name: '国潮正规',
    subtitle: '红黄警示',
    badge: '🏛️ 权威',
    palette_id: 'authority_red',
    template_id: 'text_behind_person',
    zones: {
      location: { text_color: '#FFFFFF', stroke_color: '#DC2626' },
      sub: { text_color: '#FFFFFF', stroke_color: '#DC2626' },
      main: { text_color: '#FFDD00', stroke_color: '#DC2626' }
    }
  },
  {
    id: 'obsidian_black_gold',
    name: '曜石质感',
    subtitle: '黑金尊享',
    badge: '💎 高端',
    palette_id: 'obsidian_gold',
    template_id: 'text_behind_person',
    zones: {
      location: { text_color: '#FFFFFF', stroke_color: '#0F172A' },
      sub: { text_color: '#FFFFFF', stroke_color: '#0F172A' },
      main: { text_color: '#FFD200', stroke_color: '#0F172A' }
    }
  },
  {
    id: 'sunset_warm_orange',
    name: '暖阳活力',
    subtitle: '橙白醒目',
    badge: '🍊 亲和',
    palette_id: 'sunset_orange',
    template_id: 'text_behind_person',
    zones: {
      location: { text_color: '#FFFFFF', stroke_color: '#EA580C' },
      sub: { text_color: '#FFFFFF', stroke_color: '#EA580C' },
      main: { text_color: '#FFDD00', stroke_color: '#EA580C' }
    }
  },
  {
    id: 'aurora_fresh_emerald',
    name: '极光青翠',
    subtitle: '清爽通透',
    badge: '🌿 清新',
    palette_id: 'aurora_emerald',
    template_id: 'text_behind_person',
    zones: {
      location: { text_color: '#FFFFFF', stroke_color: '#059669' },
      sub: { text_color: '#FFFFFF', stroke_color: '#059669' },
      main: { text_color: '#FFDD00', stroke_color: '#059669' }
    }
  },
  {
    id: 'frost_burgundy_wine',
    name: '雪白酒红',
    subtitle: '典雅深邃',
    badge: '🍷 质感',
    palette_id: 'frost_burgundy',
    template_id: 'text_behind_person',
    zones: {
      location: { text_color: '#FFFFFF', stroke_color: '#991B1B' },
      sub: { text_color: '#FFFFFF', stroke_color: '#991B1B' },
      main: { text_color: '#FDE047', stroke_color: '#991B1B' }
    }
  }
];

// 候选帧全局内存缓存，避免在同一个工程中重复网络请求与重复 FFmpeg 抽帧
const candidatesMemoryCache: Record<string, CoverCandidateFrame[]> = {};


// 学车特点库兜底（正常消费 /cover-templates 返回的 cover_hooks，storage/glossary.json 唯一事实源）
const FALLBACK_COVER_HOOKS: string[] = [
  '费用全透明', '明码标价', '先试后报名', '避坑课', '教练全程带教',
  '就近安排练车', '每天都能来练车', '手把手教学', '两三个月拿证', '练车不排队'
];

// 安全区兜底定义（正常情况下消费 /cover-templates 接口返回，不再前端硬编码）
const FALLBACK_SAFE_ZONES: Record<string, CoverSafeZoneRect> = {
  douyin: { top: 0.05, bottom: 0.18, left: 0.05, right: 0.15 },
  xiaohongshu: { aspect: '3:4', top: 0.125, bottom: 0.125, left: 0.0, right: 0.0 }
};

const FONT_OPTIONS: { id: string; label: string; css: string }[] = [
  { id: 'heavy_gothic', label: '超重黑体', css: '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif' },
  { id: 'brush_kai', label: '书法行楷', css: '"KaiTi", "STKaiti", "Kaiti SC", serif' },
  { id: 'handwriting_tilt', label: '倾斜手写', css: '"STXingkai", "Xingkai SC", "KaiTi", "Kaiti SC", cursive' },
  { id: 'editorial_serif', label: '质感标宋', css: '"SimSun", "Songti SC", "Noto Serif SC", serif' }
];

const fontCss = (family: string, weight: number, size: number) => {
  const stack = FONT_OPTIONS.find((f) => f.id === family)?.css || FONT_OPTIONS[0].css;
  return `${weight} ${size}px ${stack}`;
};

/** 与后端 _wrap_text_to_lines 同规则：优先标点切分，否则对半折行 */
const wrapTextLines = (text: string, maxChars: number): string[] => {
  const t = text.trim();
  if (!t) return [];
  if (t.length <= maxChars) return [t];
  for (const sep of ['！', '!', '？', '?', '，', ',', ' ']) {
    if (t.includes(sep)) {
      const parts = t.split(sep).map((p) => p.trim()).filter(Boolean);
      if (parts.length >= 2) return parts.slice(0, 2);
    }
  }
  const mid = Math.ceil(t.length / 2);
  return [t.slice(0, mid), t.slice(mid)];
};

/** 字数超限等比缩小字号（与后端 _fit_font_size 同规则） */
const fitFontSize = (text: string, baseSize: number, maxChars: number): number => {
  if (text.length <= maxChars) return baseSize;
  return Math.max(16, Math.floor((baseSize * maxChars) / text.length));
};

// ===== R3 分区样式（与后端 _resolve_zone_styles / _clamp_element_y 严格同规则） =====
const ZONE_KEYS: CoverZoneKey[] = ['location', 'main', 'sub'];
const clampScale = (v: number) => Math.min(1.4, Math.max(0.6, v));
const clampOffsetXRatio = (v: number) => Math.min(0.20, Math.max(-0.20, v));
const clampOffsetRatio = (v: number) => Math.min(0.12, Math.max(-0.12, v));
const isHexColor = (v?: string | null): v is string => !!v && /^#[0-9A-Fa-f]{6}$/.test(v);

interface ResolvedZoneStyle {
  scale: number;
  offX: number;
  offY: number;
  text: string | null;
  stroke: string | null;
}

const resolveZoneStyle = (
  styles: Partial<Record<CoverZoneKey, CoverTextZoneStyle>> | undefined,
  zone: CoverZoneKey,
  canvasH: number,
  canvasW: number = 360
): ResolvedZoneStyle => {
  const zs = styles?.[zone];
  if (!zs) return { scale: 1, offX: 0, offY: 0, text: null, stroke: null };
  return {
    scale: clampScale(zs.scale ?? 1),
    offX: Math.round(canvasW * clampOffsetXRatio(zs.offset_x ?? 0)),
    offY: Math.round(canvasH * clampOffsetRatio(zs.offset_y ?? 0)),
    text: isHexColor(zs.text_color) ? zs.text_color : null,
    stroke: isHexColor(zs.stroke_color) ? zs.stroke_color : null
  };
};

/** 纵向偏移后的位置钳制：元素锚点永不越出画布（margin 3% 画布高，与后端一致） */
const clampElementY = (y: number, canvasH: number, marginRatio = 0.03): number =>
  Math.min(Math.max(y, canvasH * marginRatio), canvasH * (1 - marginRatio));

/** 色带内文字的纵向钳制：整行文字永不滑出色带与同色底融合（与后端 _clamp_y_in_band 同规则） */
const clampYInBand = (y: number, bandTop: number, bandBottom: number, textH: number, pad: number): number => {
  const top = bandTop + pad;
  const bottom = bandBottom - textH - pad;
  if (bottom < top) return (bandTop + bandBottom) / 2 - textH / 2;
  return Math.min(Math.max(y, top), bottom);
};

// 三分区编辑卡定义：自上而下严格对齐三大区域（区域 1 顶部微弧大字、区域 2 胸前引导小标、区域 3 底部转化大字）
const ZONE_DEFS: { key: CoverZoneKey; label: string; hint: string }[] = [
  { key: 'location', label: '区域 1：顶部微弧大字', hint: '如：杭州学车（饱满拱形大字）' },
  { key: 'sub', label: '区域 2：胸前引导小标', hint: '如：欢迎试学（左胸引导小标）' },
  { key: 'main', label: '区域 3：底部转化大字', hint: '如：2980全公开（高转化价格大标）' }
];

// 副标题区兜底候选（与后端 generate_fallback_cover_titles 风格一致，非 AI 产出时使用）
const FALLBACK_SUB_CHIPS: string[] = ['欢迎试学', '避坑课', '明码标价', '手把手带教', '练车不排队'];

export type CoverDragTarget =
  | { kind: 'zone'; key: CoverZoneKey }
  | { kind: 'zone_resize'; key: CoverZoneKey }
  | { kind: 'doodle'; key: string };

export interface CoverZoneHitBox {
  key: CoverZoneKey;
  label: string;
  centerX: number;
  centerY: number;
  width: number;
  height: number;
  scale: number;
  offsetX: number;
  offsetY: number;
}

export const CoverPreviewSelector: React.FC<CoverPreviewSelectorProps> = ({
  projectId,
  initialConfig,
  suggestedTitles = [],
  currentVideoTime = 0,
  onConfigChange,
  embedCoverAsFirstFrame,
  onToggleEmbedFirstFrame,
}) => {
  // ===== 模板目录 / 调色盘 / 特点库 / 安全区（消费后端契约，失败回退静态兜底） =====
  const [templates, setTemplates] = useState<CoverTemplateItem[]>(FALLBACK_TEMPLATES);
  const [palettes, setPalettes] = useState<CoverPalette[]>(FALLBACK_PALETTES);
  const [coverHooks, setCoverHooks] = useState<string[]>(FALLBACK_COVER_HOOKS);
  const [safeZones, setSafeZones] = useState<Record<string, CoverSafeZoneRect>>(FALLBACK_SAFE_ZONES);

  // 核心配置状态：默认优先锁定同城爆款三段贴纸大字，三大区域独立解耦
  const [templateId, setTemplateId] = useState<CoverDesignConfig['template_id']>(
    (initialConfig?.template_id as CoverDesignConfig['template_id']) || 'text_behind_person'
  );
  const [colorTheme, setColorTheme] = useState<string>(initialConfig?.color_theme || 'classic_blue');
  const [fontFamily, setFontFamily] = useState<string>(initialConfig?.font_family || 'heavy_gothic');
  const [locationTag, setLocationTag] = useState<string>(
    initialConfig?.location_tag || suggestedTitles[0]?.location_tag || ''
  );
  const [subTitle, setSubTitle] = useState<string>(
    initialConfig?.sub_title || suggestedTitles[0]?.sub_title || ''
  );
  const [mainTitle, setMainTitle] = useState<string>(
    initialConfig?.main_title || suggestedTitles[0]?.main_title || ''
  );
  const [source, setSource] = useState<'video_frame' | 'custom_upload'>(
    initialConfig?.source === 'custom_upload' ? 'custom_upload' : 'video_frame'
  );
  const [frameTimestamp, setFrameTimestamp] = useState<number>(
    initialConfig?.frame_timestamp ?? Math.max(0.5, currentVideoTime)
  );
  // 默认 center_crop：真实视频帧满屏呈现，杜绝虚化加暗
  const [aspectMode, setAspectMode] = useState<'blur_padding' | 'center_crop'>(
    initialConfig?.aspect_mode || 'center_crop'
  );
  const [showSafeZone, setShowSafeZone] = useState<boolean>(
    initialConfig?.show_safe_zone ?? false
  );
  // 当前选中的全案设计模板 ID（默认首推：蓝黄撞色）
  const [selectedMasterId, setSelectedMasterId] = useState<string>(() => {
    if (initialConfig?.template_id === 'neon_3d_sticker') {
      return 'neon_lime_3d';
    }
    if (initialConfig?.color_theme) {
      const found = MASTER_DESIGN_TEMPLATES.find((m) => m.palette_id === initialConfig.color_theme);
      if (found) return found.id;
    }
    return 'blue_yellow_burst';
  });

  // R3: 三分区文本样式覆盖（开箱即赋予首推“顶流爆款·蓝黄撞色”，保证真实成片视觉质感）
  const [zoneStyles, setZoneStyles] = useState<Partial<Record<CoverZoneKey, CoverTextZoneStyle>>>(() => {
    if (initialConfig?.zone_styles && Object.keys(initialConfig.zone_styles).length > 0) {
      return initialConfig.zone_styles;
    }
    const defMaster = MASTER_DESIGN_TEMPLATES[0];
    return {
      location: { scale: 1.0, offset_y: 0.0, text_color: defMaster.zones.location.text_color, stroke_color: defMaster.zones.location.stroke_color },
      sub: { scale: 1.0, offset_y: 0.0, text_color: defMaster.zones.sub.text_color, stroke_color: defMaster.zones.sub.stroke_color },
      main: { scale: 1.0, offset_y: 0.0, text_color: defMaster.zones.main.text_color, stroke_color: defMaster.zones.main.stroke_color },
    };
  });
  // 015: 人像超清与美颜增强配置（默认开启推荐自然白皙，实时美化底图人物五官与肤色）
  const [enablePortraitEnhancement, setEnablePortraitEnhancement] = useState<boolean>(
    initialConfig?.enable_portrait_enhancement ?? true
  );
  const [beautyMode, setBeautyMode] = useState<'natural' | 'hd_clear' | 'delicate' | 'off'>(
    (initialConfig?.beauty_mode as any) || 'natural'
  );
  const [beautyStrength, setBeautyStrength] = useState<number>(
    initialConfig?.beauty_strength ?? 0.70
  );
  const [clarityStrength, setClarityStrength] = useState<number>(
    initialConfig?.clarity_strength ?? 0.50
  );
  const [showBeautySliders, setShowBeautySliders] = useState<boolean>(false);

  // 当前激活的全案模板对象
  const activeMaster = useMemo(() => {
    return MASTER_DESIGN_TEMPLATES.find((t) => t.id === selectedMasterId) || MASTER_DESIGN_TEMPLATES[0];
  }, [selectedMasterId]);

  // 候选帧列表与上传
  const [candidates, setCandidates] = useState<CoverCandidateFrame[]>([]);
  const [candidateLoading, setCandidateLoading] = useState<boolean>(false);
  const [customImagePreview, setCustomImagePreview] = useState<string | null>(
    initialConfig?.custom_image_path ? getMediaUrl(initialConfig.custom_image_path) : null
  );
  const [customFile, setCustomFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string>('');

  // Canvas 与交互画板引用
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // 贴纸/涂鸦全向拖拽偏移量 (x: 宽占比 [-0.6, 0.6], y: 高占比 [-0.6, 0.6])
  const [doodleOffsets, setDoodleOffsets] = useState<Record<string, { x: number; y: number }>>(() => {
    return (initialConfig?.doodle_offsets as Record<string, { x: number; y: number }>) || {};
  });

  // 画板实时交互拖拽目标（支持文字分区全向拖拽、右下角字号缩放手柄与独立贴纸涂鸦）
  const [hoveredTarget, setHoveredTarget] = useState<CoverDragTarget | null>(null);
  const [draggingTarget, setDraggingTarget] = useState<CoverDragTarget | null>(null);
  const dragTrackerRef = useRef<{
    target: CoverDragTarget;
    startX: number;
    startY: number;
    startScale: number;
    startOffX: number;
    startOffY: number;
  } | null>(null);

  // 地域词快捷标签：AI 提炼的 location_tag 候选（去重），不预置任何虚构地名
  const quickTags = useMemo(() => {
    const tags = new Set<string>();
    if (initialConfig?.location_tag) tags.add(initialConfig.location_tag);
    for (const t of suggestedTitles) {
      if (t.location_tag) tags.add(t.location_tag);
    }
    return Array.from(tags).slice(0, 6);
  }, [suggestedTitles, initialConfig?.location_tag]);

  // R3: 分区候选 chips —— 一组 SuggestedCoverTitle 即三个区域的一组候选，按区展开
  const mainChips = useMemo(() => {
    const chips: string[] = [];
    for (const t of suggestedTitles) {
      if (t.main_title && !chips.includes(t.main_title)) chips.push(t.main_title);
    }
    // AI 未返回时按区兜底：主标题区 = 学车特点库（storage/glossary.json cover_hooks）
    return chips.length ? chips.slice(0, 6) : coverHooks.slice(0, 6);
  }, [suggestedTitles, coverHooks]);

  const subChips = useMemo(() => {
    const chips: string[] = [];
    for (const t of suggestedTitles) {
      if (t.sub_title && !chips.includes(t.sub_title)) chips.push(t.sub_title);
    }
    return chips.length ? chips.slice(0, 6) : FALLBACK_SUB_CHIPS;
  }, [suggestedTitles]);

  // 套用全案设计风格模板（3区联动协同，已深度校准最佳排版与色彩）
  const handleSelectMaster = (tpl: MasterDesignTemplate) => {
    setSelectedMasterId(tpl.id);
    setColorTheme(tpl.palette_id);
    if (tpl.template_id) {
      setTemplateId(tpl.template_id);
    }
    // 切换至荧光绿 3D 爆款时，若当前为初始默认文案，则一键填入爆款同款文本
    if (tpl.template_id === 'neon_3d_sticker') {
      if (!locationTag || locationTag === '杭州学车') {
        setLocationTag('女生学车更难？');
      }
      if (!subTitle || subTitle === '欢迎试学') {
        setSubTitle('男女学员真实表现对比');
      }
      if (!mainTitle || mainTitle === '2980全公开') {
        setMainTitle('别再凭性别下结论');
      }
    }
    setZoneStyles((prev) => ({
      location: {
        scale: 1.0,
        offset_y: prev.location?.offset_y ?? 0.0,
        text_color: tpl.zones.location.text_color,
        stroke_color: tpl.zones.location.stroke_color
      },
      sub: {
        scale: 1.0,
        offset_y: prev.sub?.offset_y ?? 0.0,
        text_color: tpl.zones.sub.text_color,
        stroke_color: tpl.zones.sub.stroke_color
      },
      main: {
        scale: 1.0,
        offset_y: prev.main?.offset_y ?? 0.0,
        text_color: tpl.zones.main.text_color,
        stroke_color: tpl.zones.main.stroke_color
      }
    }));
  };

  // 字号大小调节（0.6x ~ 1.4x 缩放，与后端 _zone_scaled 严格对齐）
  const updateZoneScale = (zone: CoverZoneKey, scale: number) => {
    const clamped = clampScale(scale);
    setZoneStyles((prev) => ({
      ...prev,
      [zone]: {
        ...(prev[zone] || { offset_x: 0, offset_y: 0, text_color: activeMaster.zones[zone].text_color, stroke_color: activeMaster.zones[zone].stroke_color }),
        scale: parseFloat(clamped.toFixed(2))
      }
    }));
  };

  // 全向位置微调（上下左右滑动/画板拖拽实时微调文字位置）
  const updateZoneOffset = (zone: CoverZoneKey, offsetX: number, offsetY: number) => {
    const clampedX = clampOffsetXRatio(offsetX);
    const clampedY = clampOffsetRatio(offsetY);
    setZoneStyles((prev) => ({
      ...prev,
      [zone]: {
        ...(prev[zone] || { scale: 1.0, text_color: activeMaster.zones[zone].text_color, stroke_color: activeMaster.zones[zone].stroke_color }),
        offset_x: parseFloat(clampedX.toFixed(3)),
        offset_y: parseFloat(clampedY.toFixed(3))
      }
    }));
  };

  // 兼容单向纵向微调
  const updateZoneOffsetY = (zone: CoverZoneKey, offsetY: number) => {
    const curX = zoneStyles[zone]?.offset_x ?? 0;
    updateZoneOffset(zone, curX, offsetY);
  };

  // 计算各分区在 360x640 画布坐标下的中心、尺寸包围盒与字号缩放（用于画板拖拽移动、角落缩放手柄与滚轮交互）
  const getZoneHitBoxes = (): Record<CoverZoneKey, CoverZoneHitBox> => {
    const W = 360;
    const H = 640;
    const zLoc = resolveZoneStyle(zoneStyles, 'location', H, W);
    const zSub = resolveZoneStyle(zoneStyles, 'sub', H, W);
    const zMain = resolveZoneStyle(zoneStyles, 'main', H, W);

    if (templateId === 'neon_3d_sticker') {
      const topScale = zLoc.scale;
      const subScale = zSub.scale;
      const botScale = zMain.scale;
      const topW = Math.min(W * 0.94, Math.max(140, (locationTag.length || 6) * 36 * topScale));
      const subW = Math.min(W * 0.90, Math.max(120, (subTitle.length || 8) * 19 * subScale));
      const botW = Math.min(W * 0.94, Math.max(140, (mainTitle.length || 7) * 26 * botScale));

      return {
        location: {
          key: 'location',
          label: '顶部3D大字',
          centerX: W / 2 + zLoc.offX,
          centerY: clampElementY(H * 0.12 + zLoc.offY, H),
          width: topW,
          height: Math.round(56 * topScale),
          scale: topScale,
          offsetX: zoneStyles.location?.offset_x ?? 0,
          offsetY: zoneStyles.location?.offset_y ?? 0
        },
        sub: {
          key: 'sub',
          label: '引导小标',
          centerX: W / 2 + zSub.offX,
          centerY: clampElementY(H * 0.22 + zSub.offY, H),
          width: subW,
          height: Math.round(44 * subScale),
          scale: subScale,
          offsetX: zoneStyles.sub?.offset_x ?? 0,
          offsetY: zoneStyles.sub?.offset_y ?? 0
        },
        main: {
          key: 'main',
          label: '底部3D大字',
          centerX: W / 2 + zMain.offX,
          centerY: clampElementY(H * 0.88 + zMain.offY, H),
          width: botW,
          height: Math.round(58 * botScale),
          scale: botScale,
          offsetX: zoneStyles.main?.offset_x ?? 0,
          offsetY: zoneStyles.main?.offset_y ?? 0
        }
      };
    } else if (templateId === 'text_behind_person') {
      const topScale = zLoc.scale;
      const subScale = zSub.scale;
      const botScale = zMain.scale;
      const topW = Math.min(W * 0.94, Math.max(130, (locationTag.length || 4) * 44 * topScale));
      const subW = Math.min(W * 0.75, Math.max(90, (subTitle.length || 4) * 26 * subScale));
      const botW = Math.min(W * 0.94, Math.max(130, (mainTitle.length || 6) * 36 * botScale));

      return {
        location: {
          key: 'location',
          label: '顶部微弧大字',
          centerX: W / 2 + zLoc.offX,
          centerY: clampElementY(H * 0.105 + zLoc.offY, H),
          width: topW,
          height: Math.round(58 * topScale),
          scale: topScale,
          offsetX: zoneStyles.location?.offset_x ?? 0,
          offsetY: zoneStyles.location?.offset_y ?? 0
        },
        sub: {
          key: 'sub',
          label: '胸前引导小标',
          centerX: W * 0.28 + zSub.offX,
          centerY: clampElementY(H * 0.59 + zSub.offY, H),
          width: subW,
          height: Math.round(44 * subScale),
          scale: subScale,
          offsetX: zoneStyles.sub?.offset_x ?? 0,
          offsetY: zoneStyles.sub?.offset_y ?? 0
        },
        main: {
          key: 'main',
          label: '底部转化大字',
          centerX: W / 2 + zMain.offX,
          centerY: clampElementY(H * 0.675 + zMain.offY, H),
          width: botW,
          height: Math.round(58 * botScale),
          scale: botScale,
          offsetX: zoneStyles.main?.offset_x ?? 0,
          offsetY: zoneStyles.main?.offset_y ?? 0
        }
      };
    } else if (templateId === 'split_contrast_bar') {
      return {
        location: {
          key: 'location',
          label: '顶部通栏',
          centerX: W / 2 + zLoc.offX,
          centerY: clampElementY(H * 0.08 + zLoc.offY, H),
          width: W * 0.88,
          height: Math.round(48 * zLoc.scale),
          scale: zLoc.scale,
          offsetX: zoneStyles.location?.offset_x ?? 0,
          offsetY: zoneStyles.location?.offset_y ?? 0
        },
        main: {
          key: 'main',
          label: '白栏主标',
          centerX: W / 2 + zMain.offX,
          centerY: clampElementY(H * 0.78 + zMain.offY, H),
          width: W * 0.88,
          height: Math.round(56 * zMain.scale),
          scale: zMain.scale,
          offsetX: zoneStyles.main?.offset_x ?? 0,
          offsetY: zoneStyles.main?.offset_y ?? 0
        },
        sub: {
          key: 'sub',
          label: '引导副标',
          centerX: W / 2 + zSub.offX,
          centerY: clampElementY(H * 0.88 + zSub.offY, H),
          width: W * 0.70,
          height: Math.round(38 * zSub.scale),
          scale: zSub.scale,
          offsetX: zoneStyles.sub?.offset_x ?? 0,
          offsetY: zoneStyles.sub?.offset_y ?? 0
        }
      };
    } else {
      return {
        location: {
          key: 'location',
          label: '顶部大字',
          centerX: W / 2 + zLoc.offX,
          centerY: clampElementY(H * 0.10 + zLoc.offY, H),
          width: W * 0.88,
          height: Math.round(52 * zLoc.scale),
          scale: zLoc.scale,
          offsetX: zoneStyles.location?.offset_x ?? 0,
          offsetY: zoneStyles.location?.offset_y ?? 0
        },
        sub: {
          key: 'sub',
          label: '引导副标',
          centerX: W / 2 + zSub.offX,
          centerY: clampElementY(H * 0.58 + zSub.offY, H),
          width: W * 0.75,
          height: Math.round(42 * zSub.scale),
          scale: zSub.scale,
          offsetX: zoneStyles.sub?.offset_x ?? 0,
          offsetY: zoneStyles.sub?.offset_y ?? 0
        },
        main: {
          key: 'main',
          label: '主标题',
          centerX: W / 2 + zMain.offX,
          centerY: clampElementY(H * 0.70 + zMain.offY, H),
          width: W * 0.88,
          height: Math.round(58 * zMain.scale),
          scale: zMain.scale,
          offsetX: zoneStyles.main?.offset_x ?? 0,
          offsetY: zoneStyles.main?.offset_y ?? 0
        }
      };
    }
  };

  // 计算各贴纸涂鸦在 360x640 画布坐标下的中心与包围盒（支持上下左右 2D 全向拖拽）
  const getDoodleHitBoxes = () => {
    if (templateId !== 'neon_3d_sticker') return {};
    const W = 360;
    const H = 640;
    const zLoc = resolveZoneStyle(zoneStyles, 'location', H, W);
    const subY = clampElementY(H * 0.22 + (zoneStyles.sub?.offset_y ?? 0) * H, H);
    const rayRDx = (doodleOffsets.rays_right?.x ?? 0) * W;
    const rayRDy = (doodleOffsets.rays_right?.y ?? 0) * H;
    const rX = W * 0.84 + rayRDx;
    const rY = subY + rayRDy;

    const botY = clampElementY(H * 0.88 + (zoneStyles.main?.offset_y ?? 0) * H, H);
    const rayLDx = (doodleOffsets.rays_left?.x ?? 0) * W;
    const rayLDy = (doodleOffsets.rays_left?.y ?? 0) * H;
    const bX = W * 0.14 + rayLDx;
    const bY = botY + rayLDy;

    return {
      rays_right: {
        id: 'rays_right',
        label: '面颊光束',
        cx: rX + 4,
        cy: rY,
        w: 42,
        h: 52,
        offX: doodleOffsets.rays_right?.x ?? 0,
        offY: doodleOffsets.rays_right?.y ?? 0
      },
      rays_left: {
        id: 'rays_left',
        label: '底部光束',
        cx: bX - 4,
        cy: bY,
        w: 42,
        h: 52,
        offX: doodleOffsets.rays_left?.x ?? 0,
        offY: doodleOffsets.rays_left?.y ?? 0
      }
    };
  };

  // 根据 Canvas (X, Y) 探测鼠标落入哪个贴纸、缩放手柄或文字选框（支持字号缩放手柄、全向文字移动与贴纸移动）
  const findTargetAtCanvasPoint = (
    canvasX: number,
    canvasY: number
  ): CoverDragTarget | null => {
    // 1. 优先探测手绘非文字贴纸涂鸦（双三角 △ △、光束，支持上下左右 2D 全向拖拽）
    const doodles = getDoodleHitBoxes();
    for (const [key, d] of Object.entries(doodles)) {
      const halfW = d.w / 2 + 8;
      const halfH = d.h / 2 + 8;
      if (
        canvasX >= d.cx - halfW &&
        canvasX <= d.cx + halfW &&
        canvasY >= d.cy - halfH &&
        canvasY <= d.cy + halfH
      ) {
        return { kind: 'doodle', key };
      }
    }

    // 2. 探测文字分区的右下角“字号缩放手柄” (zone_resize)
    const boxes = getZoneHitBoxes();
    const zoneKeys: CoverZoneKey[] = ['location', 'sub', 'main'];
    for (const key of zoneKeys) {
      const b = boxes[key];
      const rightX = b.centerX + b.width / 2;
      const bottomY = b.centerY + b.height / 2;
      // 容差 16px 探测右下角缩放圆点
      if (
        canvasX >= rightX - 16 &&
        canvasX <= rightX + 16 &&
        canvasY >= bottomY - 16 &&
        canvasY <= bottomY + 16
      ) {
        return { kind: 'zone_resize', key };
      }
    }

    // 3. 探测文字分区选框内部（支持全向拖动移动位置）
    let bestZone: CoverZoneKey | null = null;
    let minDistance = Infinity;

    for (const key of zoneKeys) {
      const b = boxes[key];
      const halfW = b.width / 2 + 10;
      const halfH = b.height / 2 + 8;
      if (
        canvasX >= b.centerX - halfW &&
        canvasX <= b.centerX + halfW &&
        canvasY >= b.centerY - halfH &&
        canvasY <= b.centerY + halfH
      ) {
        const dist = Math.hypot(canvasX - b.centerX, canvasY - b.centerY);
        if (dist < minDistance) {
          minDistance = dist;
          bestZone = key;
        }
      }
    }
    if (bestZone) {
      return { kind: 'zone', key: bestZone };
    }
    return null;
  };

  // 画板指针交互事件
  const handleCanvasPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const scaleX = 360 / rect.width;
    const scaleY = 640 / rect.height;
    const canvasX = (e.clientX - rect.left) * scaleX;
    const canvasY = (e.clientY - rect.top) * scaleY;

    const hit = findTargetAtCanvasPoint(canvasX, canvasY);
    if (hit) {
      e.preventDefault();
      container.setPointerCapture(e.pointerId);
      if (hit.kind === 'doodle') {
        const curOff = doodleOffsets[hit.key] || { x: 0, y: 0 };
        dragTrackerRef.current = {
          target: hit,
          startX: e.clientX,
          startY: e.clientY,
          startScale: 1.0,
          startOffX: curOff.x,
          startOffY: curOff.y
        };
      } else if (hit.kind === 'zone_resize') {
        const curScale = zoneStyles[hit.key]?.scale ?? 1.0;
        dragTrackerRef.current = {
          target: hit,
          startX: e.clientX,
          startY: e.clientY,
          startScale: curScale,
          startOffX: 0,
          startOffY: 0
        };
      } else {
        const curOffX = zoneStyles[hit.key]?.offset_x ?? 0;
        const curOffY = zoneStyles[hit.key]?.offset_y ?? 0;
        dragTrackerRef.current = {
          target: hit,
          startX: e.clientX,
          startY: e.clientY,
          startScale: zoneStyles[hit.key]?.scale ?? 1.0,
          startOffX: curOffX,
          startOffY: curOffY
        };
      }
      setDraggingTarget(hit);
    }
  };

  const handleCanvasPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();

    if (draggingTarget && dragTrackerRef.current) {
      const tracker = dragTrackerRef.current;
      if (tracker.target.kind === 'doodle') {
        // 非文字标贴：上下左右 2D 全向自由拖拽！
        const deltaX = (e.clientX - tracker.startX) / rect.width;
        const deltaY = (e.clientY - tracker.startY) / rect.height;
        const newX = Math.max(-0.6, Math.min(0.6, tracker.startOffX + deltaX));
        const newY = Math.max(-0.6, Math.min(0.6, tracker.startOffY + deltaY));
        setDoodleOffsets((prev) => ({
          ...prev,
          [tracker.target.key]: {
            x: parseFloat(newX.toFixed(3)),
            y: parseFloat(newY.toFixed(3))
          }
        }));
      } else if (tracker.target.kind === 'zone_resize') {
        // 右下角手柄拖拽缩放字号大小：向右下拖动放大，向左上拖动缩小
        const delta = ((e.clientX - tracker.startX) + (e.clientY - tracker.startY)) / (rect.width * 0.7);
        const newScale = clampScale(tracker.startScale + delta);
        updateZoneScale(tracker.target.key, parseFloat(newScale.toFixed(2)));
      } else {
        // 文字分区：上下左右 2D 全向自由拖动微调
        const deltaX = (e.clientX - tracker.startX) / rect.width;
        const deltaY = (e.clientY - tracker.startY) / rect.height;
        const newOffsetX = clampOffsetXRatio(tracker.startOffX + deltaX);
        const newOffsetY = clampOffsetRatio(tracker.startOffY + deltaY);
        updateZoneOffset(tracker.target.key, parseFloat(newOffsetX.toFixed(3)), parseFloat(newOffsetY.toFixed(3)));
      }
    } else {
      const scaleX = 360 / rect.width;
      const scaleY = 640 / rect.height;
      const canvasX = (e.clientX - rect.left) * scaleX;
      const canvasY = (e.clientY - rect.top) * scaleY;
      const hit = findTargetAtCanvasPoint(canvasX, canvasY);
      setHoveredTarget(hit);
    }
  };

  const handleCanvasPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (draggingTarget) {
      const container = containerRef.current;
      if (container && container.hasPointerCapture(e.pointerId)) {
        try {
          container.releasePointerCapture(e.pointerId);
        } catch {}
      }
      setDraggingTarget(null);
      dragTrackerRef.current = null;
    }
  };

  const handleCanvasPointerLeave = () => {
    if (!draggingTarget) {
      setHoveredTarget(null);
    }
  };

  // 鼠标滚轮缩放字号：鼠标悬浮在文字区域上时直接滚动调整字号大小
  const handleCanvasWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const scaleX = 360 / rect.width;
    const scaleY = 640 / rect.height;
    const canvasX = (e.clientX - rect.left) * scaleX;
    const canvasY = (e.clientY - rect.top) * scaleY;
    const hit = findTargetAtCanvasPoint(canvasX, canvasY);
    if (hit && (hit.kind === 'zone' || hit.kind === 'zone_resize')) {
      e.preventDefault();
      const zoneKey = hit.key;
      const curScale = zoneStyles[zoneKey]?.scale ?? 1.0;
      const step = e.deltaY < 0 ? 0.03 : -0.03;
      const newScale = clampScale(curScale + step);
      updateZoneScale(zoneKey, parseFloat(newScale.toFixed(2)));
    }
  };

  // 兼容调用：旧调色盘映射
  const handleApplyTheme = (themeId: string) => {
    const matched = MASTER_DESIGN_TEMPLATES.find((m) => m.palette_id === themeId);
    if (matched) {
      handleSelectMaster(matched);
    } else {
      setColorTheme(themeId);
    }
  };

  // 1. 拉取模板目录 / 调色盘 / 安全区契约
  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const res = await getCoverTemplates();
        if (!isMounted) return;
        if (res.templates?.length) setTemplates(res.templates);
        if (res.palettes?.length) setPalettes(res.palettes);
        if (res.cover_hooks?.length) setCoverHooks(res.cover_hooks);
        if (res.safe_zones && Object.keys(res.safe_zones).length) setSafeZones(res.safe_zones);
      } catch (err) {
        console.warn('获取封面模板目录失败，使用静态兜底目录:', err);
      }
    })();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. 初始化拉取视频候选帧（优先复用内存与会话缓存，避免重复抽帧与网络等待）
  useEffect(() => {
    let isMounted = true;
    // 1. 尝试从模块全局缓存恢复
    let cached = candidatesMemoryCache[projectId];
    // 2. 尝试从 sessionStorage 恢复
    if (!cached || cached.length === 0) {
      try {
        const raw = sessionStorage.getItem(`cover_cand_${projectId}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed) && parsed.length > 0) {
            cached = parsed;
            candidatesMemoryCache[projectId] = parsed;
          }
        }
      } catch {}
    }

    if (projectId && cached && cached.length > 0) {
      setCandidates(cached);
      if (initialConfig?.frame_timestamp === undefined && cached[0]) {
        setFrameTimestamp(cached[0].timestamp);
      }
    }

    const loadCandidates = async () => {
      if (!projectId) return;
      if (!candidatesMemoryCache[projectId] || candidatesMemoryCache[projectId].length === 0) {
        setCandidateLoading(true);
      }
      try {
        const res = await getCoverCandidates(projectId);
        if (isMounted && res.candidates && res.candidates.length > 0) {
          candidatesMemoryCache[projectId] = res.candidates;
          try {
            sessionStorage.setItem(`cover_cand_${projectId}`, JSON.stringify(res.candidates));
          } catch {}
          setCandidates(res.candidates);
          if (initialConfig?.frame_timestamp === undefined && res.candidates[0]) {
            setFrameTimestamp(res.candidates[0].timestamp);
          }
        }
      } catch (err) {
        console.warn('获取封面候选帧失败 (可能正在生成或无视频源):', err);
      } finally {
        if (isMounted) setCandidateLoading(false);
      }
    };

    loadCandidates();
    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // 3. 当配置改变时向父组件上报
  useEffect(() => {
    const cfg: CoverDesignConfig = {
      source,
      frame_timestamp: frameTimestamp,
      template_id: templateId,
      location_tag: locationTag,
      main_title: mainTitle,
      sub_title: subTitle,
      color_theme: colorTheme,
      font_family: fontFamily,
      aspect_mode: aspectMode,
      show_safe_zone: showSafeZone,
      custom_image_path: initialConfig?.custom_image_path,
      zone_styles: zoneStyles,
      enable_portrait_enhancement: enablePortraitEnhancement,
      beauty_mode: beautyMode,
      beauty_strength: beautyStrength,
      clarity_strength: clarityStrength,
      doodle_offsets: doodleOffsets,
    };
    onConfigChange(cfg, customFile || undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, frameTimestamp, templateId, locationTag, mainTitle, subTitle, colorTheme, fontFamily, aspectMode, showSafeZone, customFile, zoneStyles, enablePortraitEnhancement, beautyMode, beautyStrength, clarityStrength, doodleOffsets]);

  // 4. 核心：Canvas 极速实时排版渲染（算法与后端 Pillow 严格对齐，缩放比 360/1080 = 1/3）
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let isCancelled = false;
    const W = 360;
    const H = 640; // 9:16 比例
    canvas.width = W;
    canvas.height = H;

    ctx.fillStyle = '#111827';
    ctx.fillRect(0, 0, W, H);

    // 寻找当前底图 URL
    let bgImgUrl = '';
    if (source === 'custom_upload' && customImagePreview) {
      bgImgUrl = customImagePreview;
    } else {
      const matchedCand = candidates.find((c) => Math.abs(c.timestamp - frameTimestamp) < 0.1);
      bgImgUrl = getMediaUrl(matchedCand ? matchedCand.thumb_url : candidates[0]?.thumb_url || '');
    }

    const palette = palettes.find((p) => p.id === colorTheme) || FALLBACK_PALETTES[0];

    const drawTextLayout = () => {
      if (isCancelled) return;

      const tag = locationTag.trim();
      const mTitle = mainTitle.trim();
      const sTitle = subTitle.trim();
      // R3: 分区覆盖解析（渲染取色三级优先级：分区覆盖 → 模板默认 → 调色盘）
      const zLoc = resolveZoneStyle(zoneStyles, 'location', H);
      const zMain = resolveZoneStyle(zoneStyles, 'main', H);
      const zSub = resolveZoneStyle(zoneStyles, 'sub', H);
      // 地域词是第一视觉锚点，缺省时由主标题补位，保证画面永不为空
      const anchor = tag || mTitle || '同城学车不踩坑';
      const anchorFont = (size: number) => fontCss(fontFamily, 900, Math.max(12, Math.round(fitFontSize(anchor, size, 6) * zLoc.scale)));

      if (templateId === 'pure_image') {
        // 纯净原图直出模式：不叠加任何文字、贴纸或遮罩，直接呈现纯净背景底图
      } else if (templateId === 'sticker_double_stroke') {
        // ===== 双标题贴纸风（真实爆款同款）：顶部地域大字（彩色字芯+超粗白描边+柔和投影，≤22% 不挡脸）
        // + 下方钩子大字（行楷手写体，胸前 60%~78%，避开平台底部 UI） =====
        const lines = wrapTextLines(anchor, 6);
        let y = clampElementY(H * 0.085 + zLoc.offY, H);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.lineJoin = 'round';
        const tagFontSize = Math.max(12, Math.round(fitFontSize(anchor, 56, 6) * zLoc.scale));
        for (const line of lines) {
          ctx.font = anchorFont(56);
          const cx = W / 2;
          // 柔和投影
          ctx.lineWidth = 6;
          ctx.strokeStyle = 'rgba(0,0,0,0.32)';
          ctx.strokeText(line, cx + 2, y + 3);
          // 超粗纯白描边（分区可覆盖）
          ctx.lineWidth = 6;
          ctx.strokeStyle = zLoc.stroke ?? '#FFFFFF';
          ctx.strokeText(line, cx, y);
          // 彩色字芯（分区可覆盖）
          ctx.fillStyle = zLoc.text ?? palette.main;
          ctx.fillText(line, cx, y);
          y = clampElementY(y + tagFontSize * 1.1, H);
        }

        // 下方钩子大字：行楷手写 + 白字主色描边 + 微倾角
        const hookText = tag && mTitle ? mTitle : (mTitle || sTitle);
        const tailText = tag && mTitle && sTitle ? sTitle : '';
        if (hookText) {
          ctx.save();
          ctx.translate(W / 2, clampElementY(H * 0.655 + zMain.offY, H));
          ctx.rotate((-3 * Math.PI) / 180);
          ctx.textBaseline = 'middle';
          const hookLines = wrapTextLines(hookText, 8);
          const hookFontSize = Math.max(12, Math.round(fitFontSize(hookText, 38, 8) * zMain.scale));
          const hookLineGap = Math.round(44 * zMain.scale);
          ctx.font = `900 ${hookFontSize}px ${FONT_OPTIONS.find((f) => f.id === 'handwriting_tilt')?.css}`;
          hookLines.forEach((line, li) => {
            const dy = (li - (hookLines.length - 1) / 2) * hookLineGap;
            ctx.lineWidth = 4;
            ctx.strokeStyle = zMain.stroke ?? palette.main;
            ctx.strokeText(line, 0, dy);
            ctx.fillStyle = zMain.text ?? '#FFFFFF';
            ctx.fillText(line, 0, dy);
          });
          ctx.restore();
        }

        if (tailText) {
          ctx.save();
          ctx.translate(W / 2, clampElementY(H * 0.775 + zSub.offY, H));
          ctx.rotate((-3 * Math.PI) / 180);
          ctx.textBaseline = 'middle';
          ctx.font = `700 ${Math.max(10, Math.round(fitFontSize(tailText, 17, 10) * zSub.scale))}px ${FONT_OPTIONS.find((f) => f.id === 'handwriting_tilt')?.css}`;
          ctx.lineWidth = 3;
          ctx.strokeStyle = zSub.stroke ?? '#FFFFFF';
          ctx.strokeText(tailText, 0, 0);
          ctx.fillStyle = zSub.text ?? palette.accent;
          ctx.fillText(tailText, 0, 0);
          ctx.restore();
        }
      } else if (templateId === 'split_contrast_bar') {
        // ===== 上下通栏权威撞色条：三段式构图 =====
        const topH = H * 0.16;
        ctx.fillStyle = palette.main;
        ctx.fillRect(0, 0, W, topH);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.font = fontCss(fontFamily, 900, Math.max(12, Math.round(fitFontSize(anchor, 40, 6) * zLoc.scale)));
        ctx.fillStyle = zLoc.text ?? palette.sub;
        ctx.fillText(anchor, W / 2, clampElementY(topH / 2 + zLoc.offY, H));

        const botH = H * 0.17;
        const botY = H * 0.73;
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, botY, W, botH);

        const bodyLines = wrapTextLines(mTitle || anchor, 7);
        const bodyFontSize = Math.max(12, Math.round(fitFontSize(mTitle || anchor, 32, 7) * zMain.scale));
        ctx.font = fontCss(fontFamily, 900, bodyFontSize);
        ctx.fillStyle = zMain.text ?? palette.main;
        const botBottom = botY + botH;
        const bandPad = H * 0.008;
        const gap = H * 0.009;
        // 主文案+副标整块布局：块起点一次性钳入白栏，块内行距固定不互压（与后端同规则）
        const subFontSize = Math.max(9, Math.round(13 * zSub.scale));
        const blockH = bodyLines.length * bodyFontSize * 1.12 + Math.max(0, bodyLines.length - 1) * gap
          + (sTitle ? 8 * (H / 1920) + subFontSize : 0);
        let by = botY + botH * 0.28 + zMain.offY;
        by = Math.min(Math.max(by, botY + bandPad), Math.max(botY + bandPad, botBottom - blockH - bandPad));
        for (const line of bodyLines) {
          if (zMain.stroke) {
            ctx.lineWidth = 1.7;
            ctx.strokeStyle = zMain.stroke;
            ctx.lineJoin = 'round';
            ctx.strokeText(line, W / 2, by);
          }
          ctx.fillText(line, W / 2, by);
          by += bodyFontSize * 1.12 + gap;
        }
        if (sTitle) {
          ctx.font = fontCss(fontFamily, 400, subFontSize);
          let sy = by + 8 * (H / 1920) + zSub.offY;
          sy = Math.min(Math.max(sy, botY + bandPad), botBottom - subFontSize - bandPad);
          if (zSub.stroke) {
            ctx.lineWidth = 0.7;
            ctx.strokeStyle = zSub.stroke;
            ctx.lineJoin = 'round';
            ctx.strokeText(sTitle, W / 2, sy);
          }
          ctx.fillStyle = zSub.text ?? '#6B7280';
          ctx.fillText(sTitle, W / 2, sy);
        }
      } else if (templateId === 'rainbow_arc_header') {
        // ===== 拱形包头彩虹字：弧顶抬升至约 17% 高度环抱头顶，不压 25% 以下的脸部区域 =====
        const arcText = anchor;
        const n = arcText.length;
        const perChar = 12;
        const total = perChar * (n - 1);
        const cx = W / 2;
        const cy = clampElementY(H * 0.43 + zLoc.offY, H);
        const R = W * 0.46;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.font = fontCss(fontFamily, 900, Math.max(12, Math.round(fitFontSize(arcText, 40, 7) * zLoc.scale)));
        ctx.lineJoin = 'round';
        for (let i = 0; i < n; i++) {
          const deg = -total / 2 + perChar * i;
          const rad = (deg * Math.PI) / 180;
          const x = cx + R * Math.sin(rad);
          const y = cy - R * Math.cos(rad);
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(rad);
          ctx.lineWidth = 5;
          ctx.strokeStyle = zLoc.stroke ?? '#000000';
          ctx.strokeText(arcText[i], 0, 0);
          ctx.fillStyle = zLoc.text ?? palette.main;
          ctx.fillText(arcText[i], 0, 0);
          ctx.restore();
        }

        // 顶部右侧斜角胶囊标
        const badgeText = sTitle || '@同城学车';
        ctx.save();
        ctx.translate(W * 0.78, clampElementY(H * 0.115 + zSub.offY, H));
        ctx.rotate((-8 * Math.PI) / 180);
        ctx.font = fontCss(fontFamily, 700, Math.max(9, Math.round(12 * zSub.scale)));
        const bw = ctx.measureText(badgeText).width;
        ctx.fillStyle = palette.main;
        ctx.beginPath();
        ctx.roundRect(-bw / 2 - 9, -11, bw + 18, 22, 8);
        ctx.fill();
        if (zSub.stroke) {
          ctx.lineWidth = 0.7;
          ctx.strokeStyle = zSub.stroke;
          ctx.lineJoin = 'round';
          ctx.strokeText(badgeText, 0, 0);
        }
        ctx.fillStyle = zSub.text ?? '#FFFFFF';
        ctx.fillText(badgeText, 0, 0);
        ctx.restore();

        // 底部手写疑问句（上移至 80%，避开抖音底部标题与互动区）
        const qText = tag ? mTitle : mTitle || sTitle;
        if (qText) {
          ctx.save();
          ctx.translate(W / 2, clampElementY(H * 0.80 + zMain.offY, H));
          ctx.rotate((-6 * Math.PI) / 180);
          ctx.font = fontCss(fontFamily, 900, Math.max(12, Math.round(fitFontSize(qText, 28, 8) * zMain.scale)));
          ctx.lineWidth = 5;
          ctx.strokeStyle = zMain.stroke ?? '#000000';
          ctx.lineJoin = 'round';
          ctx.strokeText(qText, 0, 0);
          ctx.fillStyle = zMain.text ?? '#FFFFFF';
          ctx.fillText(qText, 0, 0);
          ctx.restore();
        }
      } else if (templateId === 'bottom_fog_vignette') {
        // ===== 胸前羽化白光沉浸字：底部白色雾化渐变 + 立体深红白边大字 =====
        // 无地域词时胸前大字即主标题钩子，分区归属随内容切换（与后端一致）
        const fog = ctx.createLinearGradient(0, H, 0, H * 0.42);
        fog.addColorStop(0, 'rgba(255,255,255,0.92)');
        fog.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = fog;
        ctx.fillRect(0, H * 0.42, W, H * 0.58);

        const bigZone = tag ? zLoc : zMain;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.lineJoin = 'round';
        const bigLines = wrapTextLines(anchor, 6);
        const bigFontSize = Math.max(12, Math.round(fitFontSize(anchor, 47, 6) * bigZone.scale));
        let gy = clampElementY(H * 0.60 + bigZone.offY, H);
        for (const line of bigLines) {
          ctx.font = fontCss(fontFamily, 900, bigFontSize);
          // 白色厚发光边（分区可覆盖）
          ctx.lineWidth = 8;
          ctx.strokeStyle = bigZone.stroke ?? '#FFFFFF';
          ctx.strokeText(line, W / 2, gy);
          ctx.fillStyle = bigZone.text ?? palette.main;
          ctx.fillText(line, W / 2, gy);
          gy = clampElementY(gy + bigFontSize * 1.2, H);
        }

        // 有地域词时胸前大字为地域锚点，主标题钩子另起一行（雾化区 80%），保证 main 分区亦有元素
        if (tag && mTitle) {
          ctx.save();
          ctx.translate(W / 2, clampElementY(H * 0.80 + zMain.offY, H));
          ctx.rotate((-4 * Math.PI) / 180);
          ctx.textBaseline = 'middle';
          ctx.font = `900 ${Math.max(12, Math.round(fitFontSize(mTitle, 24, 8) * zMain.scale))}px ${FONT_OPTIONS.find((f) => f.id === 'handwriting_tilt')?.css}`;
          ctx.lineWidth = 3;
          ctx.strokeStyle = zMain.stroke ?? '#000000';
          ctx.strokeText(mTitle, 0, 0);
          ctx.fillStyle = zMain.text ?? '#FFFFFF';
          ctx.fillText(mTitle, 0, 0);
          ctx.restore();
        }

        if (sTitle) {
          ctx.save();
          ctx.translate(W * 0.30, clampElementY(H * 0.13 + zSub.offY, H));
          ctx.rotate((-6 * Math.PI) / 180);
          ctx.font = fontCss(fontFamily, 700, Math.max(9, Math.round(fitFontSize(sTitle, 16, 10) * zSub.scale)));
          ctx.lineWidth = 4;
          ctx.strokeStyle = zSub.stroke ?? '#FFFFFF';
          ctx.lineJoin = 'round';
          ctx.strokeText(sTitle, 0, 0);
          ctx.fillStyle = zSub.text ?? palette.accent;
          ctx.fillText(sTitle, 0, 0);
          ctx.restore();
        }
      } else if (templateId === 'angled_impact_stamp') {
        // ===== 倾角冲击引流标：-10° 地域贴纸 + 右侧双行金句 + 底部警示通栏 =====
        // 顶部倾斜贴纸
        ctx.save();
        ctx.translate(W * 0.40, clampElementY(H * 0.16 + zLoc.offY, H));
        ctx.rotate((10 * Math.PI) / 180);
        ctx.font = fontCss(fontFamily, 900, Math.max(12, Math.round(fitFontSize(anchor, 38, 6) * zLoc.scale)));
        const sw = ctx.measureText(anchor).width;
        ctx.fillStyle = palette.main;
        ctx.beginPath();
        ctx.roundRect(-sw / 2 - 13, -20, sw + 26, 40, 6);
        ctx.fill();
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.lineJoin = 'round';
        ctx.lineWidth = 4;
        ctx.strokeStyle = zLoc.stroke ?? '#000000';
        ctx.strokeText(anchor, 0, 0);
        ctx.fillStyle = zLoc.text ?? '#FFFFFF';
        ctx.fillText(anchor, 0, 0);
        ctx.restore();

        // 右侧紧凑金句（最多两行，每行 4 字）
        const rightText = tag ? mTitle : mTitle || sTitle;
        if (rightText) {
          const rLines = wrapTextLines(rightText, 4).slice(0, 2);
          const rFontSize = Math.max(12, Math.round(25 * zMain.scale));
          ctx.textAlign = 'right';
          ctx.textBaseline = 'top';
          ctx.font = fontCss(fontFamily, 900, rFontSize);
          let ry = clampElementY(H * 0.34 + zMain.offY, H);
          for (const line of rLines) {
            ctx.lineJoin = 'round';
            ctx.lineWidth = 4;
            ctx.strokeStyle = zMain.stroke ?? '#000000';
            ctx.strokeText(line, W * 0.94, ry);
            ctx.fillStyle = zMain.text ?? palette.sub;
            ctx.fillText(line, W * 0.94, ry);
            ry = clampElementY(ry + rFontSize * 1.28, H);
          }
        }

        // 底部警示通栏（上移避开平台底部 UI）
        const banH = H * 0.085;
        const banY = H * 0.745;
        ctx.fillStyle = palette.accent;
        ctx.fillRect(0, banY, W, banH);
        const warn = sTitle || '评论区咨询';
        const warnFontSize = Math.max(9, Math.round(fitFontSize(warn, 15, 12) * zSub.scale));
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.font = fontCss(fontFamily, 700, warnFontSize);
        const warnY = clampYInBand(banY + banH / 2 + zSub.offY, banY, banY + banH, warnFontSize, H * 0.006);
        if (zSub.stroke) {
          ctx.lineWidth = 1;
          ctx.strokeStyle = zSub.stroke;
          ctx.lineJoin = 'round';
          ctx.strokeText(warn, W / 2, warnY);
        }
        ctx.fillStyle = zSub.text ?? '#FFFFFF';
        ctx.fillText(warn, W / 2, warnY);
      } else if (templateId === 'clean_editorial') {
        // ===== 极简轻奢杂志风：英文章节标 + 纯白大字 + 细横线 + 衬线副标 =====
        // 有地域词时大字即主标题钩子（main 区），无地域词时大字承担地域锚点（location 区）
        const bodyText = tag ? mTitle || anchor : anchor;
        const bodyZone = tag ? zMain : zLoc;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = '300 10px "SimSun", "Songti SC", serif';
        // 柔和暗影垫底，防止浅色实景吃掉白色小字
        ctx.fillStyle = 'rgba(15, 23, 42, 0.5)';
        ctx.fillText('F E A T U R E D   S T O R Y', W / 2 + 1, H * 0.10 + 1);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.96)';
        ctx.fillText('F E A T U R E D   S T O R Y', W / 2, H * 0.10);

        // 地域衬线行（location 分区元素，显式描边色时补绘描边层）
        if (tag) {
          const locFontSize = Math.max(9, Math.round(15 * zLoc.scale));
          ctx.font = fontCss('editorial_serif', 700, locFontSize);
          ctx.textBaseline = 'top';
          const ly = clampElementY(H * 0.465 + zLoc.offY, H);
          ctx.fillStyle = 'rgba(15, 23, 42, 0.5)';
          ctx.fillText(tag, W / 2 + 1, ly + 1);
          if (zLoc.stroke) {
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = zLoc.stroke;
            ctx.lineJoin = 'round';
            ctx.strokeText(tag, W / 2, ly);
          }
          ctx.fillStyle = zLoc.text ?? palette.main;
          ctx.fillText(tag, W / 2, ly);
          ctx.textBaseline = 'middle';
        }

        const mLines = wrapTextLines(bodyText, 8);
        const mFontSize = Math.max(12, Math.round(fitFontSize(bodyText, 33, 8) * bodyZone.scale));
        ctx.font = fontCss('editorial_serif', 700, mFontSize);
        let my = clampElementY(H * 0.55 + bodyZone.offY, H);
        for (const line of mLines) {
          ctx.fillStyle = 'rgba(0,0,0,0.55)';
          ctx.fillText(line, W / 2 + 1.5, my + 1.5);
          if (bodyZone.stroke) {
            // 用户显式指定描边色时补绘描边层（默认无描边，保持杂志风留白）
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = bodyZone.stroke;
            ctx.lineJoin = 'round';
            ctx.strokeText(line, W / 2, my);
          }
          ctx.fillStyle = bodyZone.text ?? '#FFFFFF';
          ctx.fillText(line, W / 2, my);
          my = clampElementY(my + mFontSize * 1.2, H);
        }

        ctx.strokeStyle = 'rgba(226,232,240,0.75)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(W / 2 - 54, my + 4);
        ctx.lineTo(W / 2 + 54, my + 4);
        ctx.stroke();

        if (sTitle) {
          ctx.font = fontCss('editorial_serif', 400, Math.max(9, Math.round(14 * zSub.scale)));
          ctx.fillStyle = zSub.text ?? 'rgba(226,232,240,0.92)';
          ctx.fillText(sTitle, W / 2, clampElementY(my + 26 + zSub.offY, H));
        }
      } else if (templateId === 'text_behind_person') {
        // ===== 同城爆款三段贴纸大字（兔牙教练同款）：严格解耦三大区域，禁止跨区域混杂 =====
        // 区域 1：顶部微弧大字（严格对应 locationTag，如：杭州学车）
        // 区域 2：胸前引导小标（严格对应 subTitle，如：欢迎试学）
        // 区域 3：底部转化大字（严格对应 mainTitle，如：2980全公开）
        const topText = (tag || '').trim();
        const subHook = (sTitle || '').trim();
        const botHook = (mTitle || '').trim();
        const strokeBase = palette.main || '#124CD6';

        // 区域 1：顶部微弧拱桥（饱满大字号，对齐目标图）
        const topChars = Array.from(topText);
        const nTop = topChars.length;
        if (nTop > 0) {
          let baseTopSize = 68;
          if (nTop <= 4) baseTopSize = 68;
          else if (nTop === 5) baseTopSize = 60;
          else if (nTop === 6) baseTopSize = 53;
          else if (nTop <= 8) baseTopSize = 47;
          else baseTopSize = Math.max(38, Math.round((68 * 4) / nTop));
          const topFontSize = Math.max(16, Math.round(baseTopSize * zLoc.scale));
          ctx.font = fontCss(fontFamily, 900, topFontSize);
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.lineJoin = 'round';

          const maxDeg = 7.5;
          const angles = nTop > 1
            ? topChars.map((_, i) => -maxDeg + (2 * maxDeg * i) / (nTop - 1))
            : [0];

          // 测量字符宽度与间距（微紧凑排布）
          const charWidths = topChars.map((ch) => ctx.measureText(ch).width);
          const microGap = -3.0; // 紧凑连体
          const totalW = charWidths.reduce((acc, w) => acc + w, 0) + microGap * (nTop - 1);
          let curX = (W - totalW) / 2 + zLoc.offX;
          const peakY = clampElementY(H * 0.105 + zLoc.offY, H);
          const curveA = 0.00032 * (H / 1920) * (1080 / W);

          const topLayout = topChars.map((ch, idx) => {
            const cw = charWidths[idx];
            const ang = angles[idx];
            const xCenter = curX + cw / 2;
            const dx = xCenter - (W / 2 + zLoc.offX);
            const yCenter = peakY + curveA * (dx * dx);
            curX += cw + microGap;
            return { ch, xCenter, yCenter, ang };
          });

          // Phase 1: 底层统一加粗纯正实心描边（硬边无阴影，彻底消除发青/发白脏光晕）
          topLayout.forEach(({ ch, xCenter, yCenter, ang }) => {
            ctx.save();
            ctx.translate(xCenter, yCenter);
            ctx.rotate((ang * Math.PI) / 180);
            ctx.lineWidth = 10;
            ctx.strokeStyle = zLoc.stroke ?? strokeBase;
            ctx.strokeText(ch, 0, 0);
            ctx.restore();
          });

          // Phase 2: 顶层统一填充纯白字芯（笔画清晰坚实）
          topLayout.forEach(({ ch, xCenter, yCenter, ang }) => {
            ctx.save();
            ctx.translate(xCenter, yCenter);
            ctx.rotate((ang * Math.PI) / 180);
            ctx.fillStyle = zLoc.text ?? '#FFFFFF';
            ctx.fillText(ch, 0, 0);
            ctx.restore();
          });
        }

        // 区域 2：胸前引导小标（左胸微倾，无缝一体闭合）
        const subChars = Array.from(subHook);
        const nSub = subChars.length;
        if (nSub > 0) {
          const subFontSize = Math.max(12, Math.round(32 * zSub.scale));
          ctx.font = fontCss(fontFamily, 900, subFontSize);
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.lineJoin = 'round';
          const subAngle = -3.8;
          const rad = (subAngle * Math.PI) / 180;
          const subCharWidths = subChars.map((ch) => ctx.measureText(ch).width);
          const subGap = -1.8;
          let curX = W * 0.10 + zSub.offX;
          const baseY = clampElementY(H * 0.59 + zSub.offY, H);

          const subLayout = subChars.map((ch, idx) => {
            const cw = subCharWidths[idx];
            const curY = baseY + idx * (cw + subGap) * Math.tan(rad);
            const xCenter = curX + cw / 2;
            curX += cw + subGap;
            return { ch, xCenter, curY };
          });

          // Phase 1: 底描边连体闭合（实心硬边）
          subLayout.forEach(({ ch, xCenter, curY }) => {
            ctx.save();
            ctx.translate(xCenter, curY);
            ctx.rotate(rad);
            ctx.lineWidth = 7;
            ctx.strokeStyle = zSub.stroke ?? strokeBase;
            ctx.strokeText(ch, 0, 0);
            ctx.restore();
          });

          // Phase 2: 字芯填充
          subLayout.forEach(({ ch, xCenter, curY }) => {
            ctx.save();
            ctx.translate(xCenter, curY);
            ctx.rotate(rad);
            ctx.fillStyle = zSub.text ?? '#FFFFFF';
            ctx.fillText(ch, 0, 0);
            ctx.restore();
          });
        }

        // 区域 3：底部亮黄转化大字（两阶段一体化贴纸，彻底填实所有字间缝隙）
        const botChars = Array.from(botHook);
        const nBot = botChars.length;
        if (nBot > 0) {
          const botBase = nBot >= 7 ? 46 : nBot === 6 ? 48 : 51;
          const botFontSize = Math.max(14, Math.round(botBase * zMain.scale));
          ctx.font = fontCss(fontFamily, 900, botFontSize);
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.lineJoin = 'round';

          const botAngle = -3.2;
          const rad = (botAngle * Math.PI) / 180;
          const botCharWidths = botChars.map((ch) => ctx.measureText(ch).width);
          const botGap = -2.5; // 紧凑连体
          const totalW = botCharWidths.reduce((acc, w) => acc + w, 0) + botGap * (nBot - 1);
          let curX = (W - totalW) / 2 + zMain.offX;
          const baseY = clampElementY(H * 0.675 + zMain.offY, H);

          const botLayout = botChars.map((ch, idx) => {
            const cw = botCharWidths[idx];
            const curY = baseY + idx * (cw + botGap) * Math.tan(rad);
            const xCenter = curX + cw / 2;
            curX += cw + botGap;
            return { ch, xCenter, curY };
          });

          // Phase 1: 大底托（加粗闭合，彻底消灭一切字间漏光三角空洞，无虚化阴影）
          botLayout.forEach(({ ch, xCenter, curY }) => {
            ctx.save();
            ctx.translate(xCenter, curY);
            ctx.rotate(rad);
            ctx.lineWidth = 9;
            ctx.strokeStyle = zMain.stroke ?? strokeBase;
            ctx.strokeText(ch, 0, 0);
            ctx.restore();
          });

          // Phase 2: 亮黄字芯置顶填充（高饱和荧光柠檬黄，纯净亮眼）
          botLayout.forEach(({ ch, xCenter, curY }) => {
            ctx.save();
            ctx.translate(xCenter, curY);
            ctx.rotate(rad);
            ctx.fillStyle = zMain.text ?? '#FFEE0A';
            ctx.fillText(ch, 0, 0);
            ctx.restore();
          });
        }
      } else if (templateId === 'neon_3d_sticker') {
        // ===== 荧光绿 3D 贴纸大字（同城爆款争议/干货教学款）=====
        // 区域 1：顶部微弧 3D 实体下沉大字（荧光柠檬黄字芯 + 墨绿 3D 实体块面挤压厚度）
        // 区域 2：胸前引导小标（纯白字芯 + 墨绿 3D 实体下沉厚度）
        // 区域 3：底部转化大字（纯白字芯 + 墨绿 3D 实体下沉厚度）
        // 手绘白色贴纸涂鸦（左上 △ △、面颊与底部 \ | / 强调线条）
        const topText = (tag || '').trim() || (mTitle || '女生学车更难？');
        const subHook = (sTitle || '').trim() || '男女学员真实表现对比';
        const botHook = (tag ? mTitle : '').trim() || '别再凭性别下结论';

        const draw3dBlock = (
          text: string,
          centerX: number,
          centerY: number,
          fontSize: number,
          frontColor: string,
          extrudeColor: string,
          depth: number = 8,
          angleDeg: number = 0,
          arcRadius: number = 0,
          strokeColor: string = '#183401'
        ) => {
          const chars = Array.from(text);
          if (!chars.length) return;
          ctx.save();
          ctx.font = fontCss(fontFamily, 900, fontSize);
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          const charWidths = chars.map((ch) => ctx.measureText(ch).width);
          const totalW = charWidths.reduce((a, b) => a + b, 0) + 1 * (chars.length - 1);
          let curX = centerX - totalW / 2;

          const coords = chars.map((ch, idx) => {
            const cw = charWidths[idx];
            const dx = (curX + cw / 2) - centerX;
            const yOff = arcRadius !== 0 ? arcRadius * (dx * dx) : 0;
            const res = { ch, x: curX + cw / 2, y: centerY + yOff };
            curX += cw + 1;
            return res;
          });

          if (angleDeg !== 0) {
            ctx.translate(centerX, centerY);
            ctx.rotate((angleDeg * Math.PI) / 180);
            ctx.translate(-centerX, -centerY);
          }

          // 1. 3D 挤压实体色块 (向下偏右，饱满密实无缝隙)
          for (let step = depth; step > 0; step--) {
            const offY = step;
            const offX = step * 0.18;
            ctx.fillStyle = extrudeColor;
            ctx.strokeStyle = extrudeColor;
            ctx.lineWidth = 2.4;
            ctx.lineJoin = 'round';
            coords.forEach(({ ch, x, y }) => {
              ctx.strokeText(ch, x + offX, y + offY);
              ctx.fillText(ch, x + offX, y + offY);
            });
          }

          // 2. 正面字芯 (极细深绿硬边轮廓 + 饱满色彩字芯)
          ctx.fillStyle = frontColor;
          ctx.strokeStyle = strokeColor;
          ctx.lineWidth = 1.6;
          ctx.lineJoin = 'round';
          coords.forEach(({ ch, x, y }) => {
            ctx.strokeText(ch, x, y);
            ctx.fillText(ch, x, y);
          });

          ctx.restore();
        };

        const neonYellow = zLoc.text ?? palette.main ?? '#DBFA11';
        const darkGreen = zLoc.stroke ?? palette.sub ?? '#2A5101';
        const subFront = zSub.text ?? '#FFFFFF';
        const subExtrude = zSub.stroke ?? darkGreen;
        const botFront = zMain.text ?? '#FFFFFF';
        const botExtrude = zMain.stroke ?? darkGreen;

        // Zone 1: 顶部微弧 3D 实体大字 (-2.0° 动感微倾)
        const topFontSize = Math.max(16, Math.round(fitFontSize(topText, 48, 7) * zLoc.scale));
        const topY = clampElementY(H * 0.12 + zLoc.offY, H);
        draw3dBlock(topText, W / 2 + zLoc.offX, topY, topFontSize, neonYellow, darkGreen, 10, -2.0, 0.00025);

        // Zone 2: 胸前引导小标
        const subFontSize = Math.max(11, Math.round(fitFontSize(subHook, 26, 10) * zSub.scale));
        const subY = clampElementY(H * 0.22 + zSub.offY, H);
        draw3dBlock(subHook, W / 2 + zSub.offX, subY, subFontSize, subFront, subExtrude, 6, -2.0, 0.00015);

        // Zone 3: 底部转化大字
        const botFontSize = Math.max(13, Math.round(fitFontSize(botHook, 36, 9) * zMain.scale));
        const botY = clampElementY(H * 0.88 + zMain.offY, H);
        draw3dBlock(botHook, W / 2 + zMain.offX, botY, botFontSize, botFront, botExtrude, 7, 0.0, 0.0);

        // 手绘白色贴纸涂鸦 (镂空中空 △ △ 与放射射线 \ | /，支持独立上下左右全向拖拽)
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)';
        ctx.lineWidth = 3.2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        // 右侧面颊旁 3 束白光 (随胸前小标联动 + 独立上下左右拖拽)
        const rayRDx = (doodleOffsets.rays_right?.x ?? 0) * W;
        const rayRDy = (doodleOffsets.rays_right?.y ?? 0) * H;
        const rX = W * 0.84 + rayRDx;
        const rY = subY + rayRDy;
        ctx.beginPath();
        ctx.moveTo(rX - 8, rY - 14);
        ctx.lineTo(rX + 16, rY - 22);
        ctx.moveTo(rX - 5, rY);
        ctx.lineTo(rX + 20, rY);
        ctx.moveTo(rX - 8, rY + 14);
        ctx.lineTo(rX + 16, rY + 22);
        ctx.stroke();

        // 3. 底部左侧 3 束白光 (随底部大标联动 + 独立上下左右拖拽)
        const rayLDx = (doodleOffsets.rays_left?.x ?? 0) * W;
        const rayLDy = (doodleOffsets.rays_left?.y ?? 0) * H;
        const bX = W * 0.14 + rayLDx;
        const bY = botY + rayLDy;
        ctx.beginPath();
        ctx.moveTo(bX + 8, bY - 14);
        ctx.lineTo(bX - 16, bY - 22);
        ctx.moveTo(bX + 5, bY);
        ctx.lineTo(bX - 20, bY);
        ctx.moveTo(bX + 8, bY + 14);
        ctx.lineTo(bX - 16, bY + 22);
        ctx.stroke();

        ctx.restore();
      }

      // 安全区辅助线绘制（消费 /cover-templates 契约定义）
      if (showSafeZone) {
        const dz = safeZones.douyin || FALLBACK_SAFE_ZONES.douyin;
        const xhs = safeZones.xiaohongshu || FALLBACK_SAFE_ZONES.xiaohongshu;
        ctx.save();
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.7)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([4, 4]);

        // 抖音顶部避让区
        ctx.strokeRect(8, 8, W - 16, H * (dz.top ?? 0.05));
        // 抖音底部标题与音乐避让区
        const botH = H * (dz.bottom ?? 0.18);
        ctx.strokeRect(8, H - botH - 8, W - 16, botH);
        // 抖音右侧互动按钮区
        const rightW = W * (dz.right ?? 0.15);
        ctx.strokeRect(W - rightW - 8, H * 0.35, rightW, H * 0.4);

        // 小红书 3:4 双列流裁切保护参考线
        const xhsOffset = H * (xhs.top ?? 0.125);
        ctx.strokeStyle = 'rgba(244, 63, 94, 0.4)';
        ctx.beginPath();
        ctx.moveTo(0, xhsOffset);
        ctx.lineTo(W, xhsOffset);
        ctx.moveTo(0, H - xhsOffset);
        ctx.lineTo(W, H - xhsOffset);
        ctx.stroke();

        ctx.restore();
      }
    };

    if (bgImgUrl) {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        if (isCancelled) return;

        const imgRatio = img.width / img.height;
        const targetRatio = W / H; // 9:16

        // 1.5 人像美颜与超清实时滤镜（硬件加速实时调优面部通透度、白皙度与微对比）
        ctx.save();
        if (enablePortraitEnhancement && beautyMode !== 'off') {
          const bFactor = beautyStrength;
          const cFactor = clarityStrength;
          let contrast = 1.05;
          let brightness = 1.05;
          let saturate = 1.03;
          if (beautyMode === 'hd_clear') {
            contrast = 1.08 + cFactor * 0.06;
            brightness = 1.03 + bFactor * 0.03;
            saturate = 1.02;
          } else if (beautyMode === 'delicate') {
            contrast = 1.04;
            brightness = 1.07 + bFactor * 0.05;
            saturate = 1.06;
          } else {
            // natural
            contrast = 1.06 + cFactor * 0.04;
            brightness = 1.05 + bFactor * 0.04;
            saturate = 1.04;
          }
          ctx.filter = `contrast(${contrast.toFixed(2)}) brightness(${brightness.toFixed(2)}) saturate(${saturate.toFixed(2)})`;
        }

        // 默认居中铺满呈现真实画面：100% 原始色彩与清晰度，不模糊、不降低亮度
        if (aspectMode === 'center_crop' || Math.abs(imgRatio - targetRatio) < 0.15) {
          let srcW = img.width;
          let srcH = img.height;
          let srcX = 0;
          let srcY = 0;

          if (imgRatio > targetRatio) {
            srcW = img.height * targetRatio;
            srcX = (img.width - srcW) / 2;
          } else {
            srcH = img.width / targetRatio;
            srcY = (img.height - srcH) / 2;
          }
          ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, W, H);
        } else {
          // 仅在明确选择模糊填充时使用
          ctx.save();
          ctx.filter = 'blur(16px)';
          ctx.drawImage(img, 0, 0, W, H);
          ctx.restore();

          let drawW = W;
          let drawH = W / imgRatio;
          if (drawH > H) {
            drawH = H;
            drawW = H * imgRatio;
          }
          ctx.drawImage(img, (W - drawW) / 2, (H - drawH) / 2, drawW, drawH);
        }
        ctx.restore(); // 恢复滤镜，保证后续 text 纯净无失真

        drawTextLayout();
      };
      img.onerror = () => {
        if (!isCancelled) {
          drawTextLayout();
        }
      };
      img.src = bgImgUrl;
    } else {
      drawTextLayout();
    }

    return () => {
      isCancelled = true;
    };
  }, [templateId, locationTag, mainTitle, subTitle, colorTheme, fontFamily, source, frameTimestamp, aspectMode, showSafeZone, customImagePreview, candidates, palettes, safeZones, zoneStyles, enablePortraitEnhancement, beautyMode, beautyStrength, clarityStrength, doodleOffsets]);

  // 处理本地图片选择（jpg/png/webp 白名单 + 15MB 客户端拦截）
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    const okType = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type);
    if (!okType) {
      setUploadError('仅支持 JPG / PNG / WebP 格式图片');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setUploadError('图片超过 15MB 上限，请压缩后再试');
      return;
    }
    setUploadError('');
    setCustomFile(file);
    const objectUrl = URL.createObjectURL(file);
    setCustomImagePreview(objectUrl);
    setSource('custom_upload');

    // 自动在后台上传自适应
    setIsUploading(true);
    try {
      await uploadProjectCoverFile(projectId, file, aspectMode);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '未知错误';
      setUploadError(`封面上传失败：${detail}`);
      console.warn('上传自定义封面文件失败:', err);
    } finally {
      setIsUploading(false);
    }
  };

  // 切换模板时，若当前调色盘不受支持则自动回退到该模板首选调色盘
  const handleSelectTemplate = (id: string) => {
    setTemplateId(id as CoverDesignConfig['template_id']);
    const tpl = templates.find((t) => t.id === id);
    if (tpl && tpl.supported_themes?.length && !tpl.supported_themes.includes(colorTheme)) {
      handleApplyTheme(tpl.supported_themes[0]);
    }
  };

  // ===== R3: 分区编辑卡绑定（文本值 / 候选 chips / 覆盖样式） =====
  const activePalette = palettes.find((p) => p.id === colorTheme) || FALLBACK_PALETTES[0];
  // 颜色候选色板：当前调色盘 main/sub/accent + 纯白 + 纯黑（契约定义，去重）
  const zoneSwatches = useMemo(() => {
    const seen = new Set<string>();
    const list: string[] = [];
    for (const c of [activePalette.main, activePalette.sub, activePalette.accent, '#FFFFFF', '#000000']) {
      const upper = c.toUpperCase();
      if (!seen.has(upper)) {
        seen.add(upper);
        list.push(c);
      }
    }
    return list;
  }, [activePalette]);

  const zoneTextValue = (z: CoverZoneKey): string =>
    z === 'location' ? locationTag : z === 'main' ? mainTitle : subTitle;
  const setZoneTextValue = (z: CoverZoneKey, v: string) => {
    if (z === 'location') setLocationTag(v);
    else if (z === 'main') setMainTitle(v);
    else setSubTitle(v);
  };
  const zoneChips = (z: CoverZoneKey): string[] => {
    if (templateId === 'neon_3d_sticker') {
      if (z === 'location') return quickTags.length > 0 ? quickTags : ['女生学车更难？', '倒车入库秘籍', '杭州90后女教练', '科二难点全拆解', '杭州学车'];
      if (z === 'sub') return ['男女学员真实表现对比', '新手必看避坑指南', '细节拆解手把手教', '学员实测真实反馈'];
      return ['别再凭性别下结论', '科二科三一次过', '费用全公开无套路', '包教包会零压力'];
    }
    if (z === 'location') return quickTags.length > 0 ? quickTags : ['杭州学车', '武义学车', '金华学车', '绍兴学车', '宁波学车'];
    if (z === 'sub') return ['欢迎试学', '避坑课', '明码标价', '手把手教学', '练车不排队'];
    return ['2980全公开', '费用全透明', '先试后报名', '两三个月拿证', '科二科三一把过'];
  };
  const zonePlaceholder = (z: CoverZoneKey): string => {
    if (templateId === 'neon_3d_sticker') {
      return z === 'location' ? '如：女生学车更难？（顶部大字）' : z === 'sub' ? '如：男女学员真实表现对比（胸前小标）' : '如：别再凭性别下结论（底部大标）';
    }
    return z === 'location' ? '如：杭州学车（顶部大字）' : z === 'sub' ? '如：欢迎试学（胸前小标）' : '如：2980全公开（底部大标）';
  };
  const zoneIcon = (z: CoverZoneKey) =>
    z === 'location' ? <MapPin className="w-3.5 h-3.5 text-rose-600" /> : z === 'sub' ? <Tag className="w-3.5 h-3.5 text-sky-600" /> : <Flame className="w-3.5 h-3.5 text-amber-600" />;
  const zoneCardCls = (z: CoverZoneKey): string =>
    z === 'location'
      ? 'bg-gradient-to-r from-rose-50/70 to-red-50/60 border-rose-200/70'
      : z === 'sub'
        ? 'bg-gradient-to-r from-sky-50/70 to-blue-50/60 border-sky-200/70'
        : 'bg-gradient-to-r from-amber-50/70 to-orange-50/60 border-amber-200/70';

  const renderZoneCard = (def: { key: CoverZoneKey; label: string; hint: string }) => {
    const chips = zoneChips(def.key);
    const offsetX = zoneStyles[def.key]?.offset_x ?? 0;
    const offsetY = zoneStyles[def.key]?.offset_y ?? 0;
    const scale = zoneStyles[def.key]?.scale ?? 1.0;
    const isShifted = Math.abs(offsetX) > 0.001 || Math.abs(offsetY) > 0.001 || Math.abs(scale - 1.0) > 0.01;
    return (
      <div className={`p-3 rounded-xl border space-y-2.5 ${zoneCardCls(def.key)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
            {zoneIcon(def.key)}
            <span>{def.label}</span>
            <span className="text-[10px] font-normal text-slate-400">{def.hint}</span>
          </div>
          {isShifted && (
            <button
              type="button"
              onClick={() => {
                updateZoneOffset(def.key, 0, 0);
                updateZoneScale(def.key, 1.0);
              }}
              className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/90 border border-slate-200 text-slate-600 hover:text-slate-900 transition-all cursor-pointer shadow-2xs"
              title="复位至最佳默认位置与标准字号"
            >
              复位位置与字号
            </button>
          )}
        </div>

        {/* AI 分区候选 chips（地域区=location_tag 候选；主标区=AI 主标题，缺省回退学车特点库；副标区=AI 副标题） */}
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {chips.map((chip) => {
              const isActive = zoneTextValue(def.key) === chip;
              return (
                <button
                  key={chip}
                  type="button"
                  onClick={() => setZoneTextValue(def.key, chip)}
                  className={`text-[11px] px-2 py-0.5 rounded-lg border transition-all cursor-pointer ${
                    isActive
                      ? 'bg-slate-800 border-slate-800 text-white font-semibold shadow-sm'
                      : 'bg-white/90 border-slate-200 text-slate-700 hover:bg-white hover:border-slate-400'
                  }`}
                >
                  {chip}
                </button>
              );
            })}
          </div>
        )}

        {/* 分区文本自由编辑 */}
        <input
          type="text"
          value={zoneTextValue(def.key)}
          onChange={(e) => setZoneTextValue(def.key, e.target.value)}
          placeholder={zonePlaceholder(def.key)}
          maxLength={def.key === 'location' ? 10 : def.key === 'main' ? 24 : 30}
          className="w-full text-xs px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-800 font-medium"
        />

        {/* 字号大小调节（拖拽缩放/滑块微调/快捷步进） */}
        <div className="flex items-center gap-2 pt-1 border-t border-slate-200/50">
          <span className="text-[10px] text-slate-500 w-14 flex-shrink-0 flex items-center gap-1">
            <Type className="w-3 h-3 text-slate-400" />
            <span>字号大小</span>
          </span>
          <button
            type="button"
            onClick={() => updateZoneScale(def.key, Math.max(0.6, scale - 0.05))}
            className="w-4 h-4 flex items-center justify-center rounded bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 text-xs font-bold cursor-pointer"
            title="字号缩小 5%"
          >
            -
          </button>
          <input
            type="range"
            min={0.6}
            max={1.4}
            step={0.02}
            value={scale}
            onChange={(e) => updateZoneScale(def.key, parseFloat(e.target.value))}
            className="flex-1 h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <button
            type="button"
            onClick={() => updateZoneScale(def.key, Math.min(1.4, scale + 0.05))}
            className="w-4 h-4 flex items-center justify-center rounded bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 text-xs font-bold cursor-pointer"
            title="字号放大 5%"
          >
            +
          </button>
          <span className="text-[10px] font-mono text-slate-600 w-8 text-right font-medium">
            {Math.round(scale * 100)}%
          </span>
        </div>

        {/* 上下纵向位置微调 */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 w-14 flex-shrink-0 flex items-center gap-1">
            <MoveVertical className="w-3 h-3 text-slate-400" />
            <span>上下位置</span>
          </span>
          <input
            type="range"
            min={-0.12}
            max={0.12}
            step={0.005}
            value={offsetY}
            onChange={(e) => updateZoneOffset(def.key, offsetX, parseFloat(e.target.value))}
            className="flex-1 h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <span className="text-[10px] font-mono text-slate-500 w-8 text-right">
            {offsetY > 0 ? `+${Math.round(offsetY * 100)}%` : `${Math.round(offsetY * 100)}%`}
          </span>
        </div>

        {/* 左右横向位置微调 */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 w-14 flex-shrink-0 flex items-center gap-1">
            <Move className="w-3 h-3 text-slate-400" />
            <span>左右位置</span>
          </span>
          <input
            type="range"
            min={-0.20}
            max={0.20}
            step={0.005}
            value={offsetX}
            onChange={(e) => updateZoneOffset(def.key, parseFloat(e.target.value), offsetY)}
            className="flex-1 h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <span className="text-[10px] font-mono text-slate-500 w-8 text-right">
            {offsetX > 0 ? `+${Math.round(offsetX * 100)}%` : `${Math.round(offsetX * 100)}%`}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
      {/* 左侧：9:16 高清大图即时预览 (Sticky 吸顶锁定，滚动条只在右侧移动，左侧不动) */}
      <div className="lg:col-span-5 flex flex-col items-center justify-start sticky top-0 self-start z-10">
        <div
          ref={containerRef}
          onPointerDown={handleCanvasPointerDown}
          onPointerMove={handleCanvasPointerMove}
          onPointerUp={handleCanvasPointerUp}
          onPointerLeave={handleCanvasPointerLeave}
          onWheel={handleCanvasWheel}
          style={{
            cursor: draggingTarget
              ? (draggingTarget.kind === 'zone_resize' ? 'nwse-resize' : 'grabbing')
              : hoveredTarget
                ? (hoveredTarget.kind === 'zone_resize' ? 'nwse-resize' : hoveredTarget.kind === 'doodle' ? 'move' : 'grab')
                : 'default'
          }}
          className="relative w-full max-w-[280px] aspect-[9/16] rounded-2xl overflow-hidden shadow-xl border border-slate-200 bg-slate-900 flex items-center justify-center group touch-none select-none"
        >
          <canvas ref={canvasRef} className="w-full h-full object-cover select-none pointer-events-none" />

          {/* 1. 文字分区 2D 拖拽与字号缩放选框 */}
          {Object.entries(getZoneHitBoxes()).map(([key, box]) => {
            const zKey = key as CoverZoneKey;
            const isDraggingThis = draggingTarget?.key === zKey;
            const isHoveredThis = hoveredTarget?.key === zKey;
            if (!isDraggingThis && !isHoveredThis) return null;

            const isResize = (draggingTarget?.kind === 'zone_resize' || hoveredTarget?.kind === 'zone_resize') && (isDraggingThis || isHoveredThis);

            const leftPercent = Math.max(0, Math.min(100, ((box.centerX - box.width / 2) / 360) * 100));
            const topPercent = Math.max(0, Math.min(100, ((box.centerY - box.height / 2) / 640) * 100));
            const widthPercent = (box.width / 360) * 100;
            const heightPercent = (box.height / 640) * 100;
            const scalePercent = Math.round(box.scale * 100);

            return (
              <div
                key={zKey}
                className={`absolute rounded-xl transition-colors pointer-events-none ${
                  isDraggingThis
                    ? isResize
                      ? 'border-2 border-emerald-400 bg-emerald-500/15 shadow-lg shadow-emerald-500/20'
                      : 'border-2 border-blue-400 bg-blue-500/15 shadow-lg shadow-blue-500/20'
                    : 'border-2 border-dashed border-sky-400/80 bg-sky-400/10'
                }`}
                style={{
                  left: `${leftPercent}%`,
                  top: `${topPercent}%`,
                  width: `${widthPercent}%`,
                  height: `${heightPercent}%`
                }}
              >
                {/* 顶部悬浮标签与快速字号调节步进 */}
                <div className="absolute -top-6 left-0 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-slate-900/90 text-white font-medium backdrop-blur-xs shadow-xs text-[10px] whitespace-nowrap pointer-events-auto">
                  <Move className="w-2.5 h-2.5 text-sky-400" />
                  <span>{box.label}</span>
                  <span className="font-mono text-amber-300 font-semibold ml-1">{scalePercent}%</span>
                  <button
                    type="button"
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      updateZoneScale(zKey, Math.max(0.6, box.scale - 0.05));
                    }}
                    className="w-3.5 h-3.5 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold cursor-pointer"
                    title="字号 -5%"
                  >
                    -
                  </button>
                  <button
                    type="button"
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      updateZoneScale(zKey, Math.min(1.4, box.scale + 0.05));
                    }}
                    className="w-3.5 h-3.5 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold cursor-pointer"
                    title="字号 +5%"
                  >
                    +
                  </button>
                </div>

                {/* 右下角字号缩放手柄（按住向右下拖动放大字号，向左上拖动缩小字号） */}
                <div
                  className={`absolute -bottom-2 -right-2 w-4 h-4 rounded-full border-2 border-white shadow-md flex items-center justify-center text-[8px] text-white font-bold select-none cursor-nwse-resize ${
                    isResize ? 'bg-emerald-500 ring-2 ring-emerald-300 scale-125' : 'bg-blue-600 ring-1 ring-blue-300'
                  }`}
                  title="拖动缩放字号大小"
                >
                  ⤡
                </div>
              </div>
            );
          })}

          {/* 2. 手绘图贴/涂鸦 2D 全向自由拖拽选框 (双三角 △ △、光束，支持上下左右自由移动) */}
          {Object.entries(getDoodleHitBoxes()).map(([key, d]) => {
            const isDragging = draggingTarget?.kind === 'doodle' && draggingTarget.key === key;
            const isHovered = hoveredTarget?.kind === 'doodle' && hoveredTarget.key === key;
            if (!isDragging && !isHovered) return null;

            const leftPercent = Math.max(0, Math.min(100, ((d.cx - d.w / 2) / 360) * 100));
            const topPercent = Math.max(0, Math.min(100, ((d.cy - d.h / 2) / 640) * 100));
            const wPercent = (d.w / 360) * 100;
            const hPercent = (d.h / 640) * 100;

            return (
              <div
                key={`doodle-${key}`}
                className={`absolute rounded-xl transition-colors pointer-events-none flex items-start justify-center ${
                  isDragging
                    ? 'border-2 border-amber-400 bg-amber-400/25 shadow-lg shadow-amber-500/30 ring-2 ring-amber-300/40'
                    : 'border-2 border-dashed border-amber-300 bg-amber-300/15'
                }`}
                style={{
                  left: `${leftPercent}%`,
                  top: `${topPercent}%`,
                  width: `${wPercent}%`,
                  height: `${hPercent}%`
                }}
              >
                <span className="text-[9px] px-1.5 py-0.2 rounded-md bg-slate-900/90 text-amber-300 font-medium backdrop-blur-xs flex items-center gap-1 shadow-xs whitespace-nowrap -mt-5">
                  <Move className="w-2.5 h-2.5 text-amber-400" />
                  <span>{d.label}</span>
                  <span className="text-[8px] text-amber-400/80">上下左右拖动</span>
                </span>
              </div>
            );
          })}

          {candidateLoading && (
            <div className="absolute inset-x-0 top-0 h-0.5 bg-blue-100 overflow-hidden pointer-events-none">
              <div className="h-full w-1/3 bg-blue-500 animate-pulse" />
            </div>
          )}

          {isUploading && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex flex-col items-center justify-center text-white text-xs gap-2 pointer-events-none">
              <RefreshCw className="w-5 h-5 animate-spin text-blue-400" />
              <span>正在自适应画幅...</span>
            </div>
          )}
        </div>

        {/* 画面交互拖拽提示卡 */}
        <div className="mt-2 w-full max-w-[280px] px-2.5 py-1.5 rounded-xl bg-blue-50/90 border border-blue-200/80 text-[11px] text-blue-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-1.5 font-medium">
            <Move className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
            <span>拖拽文字全向移动 · 拖动右下角或滚轮缩放字号</span>
          </div>
          {(Object.values(zoneStyles).some(zs => Math.abs(zs?.offset_x ?? 0) > 0.001 || Math.abs(zs?.offset_y ?? 0) > 0.001 || Math.abs((zs?.scale ?? 1) - 1) > 0.01) ||
            Object.values(doodleOffsets).some(v => Math.abs(v.x) > 0.001 || Math.abs(v.y) > 0.001)) && (
            <button
              type="button"
              onClick={() => {
                setZoneStyles((prev) => ({
                  location: { ...prev.location, offset_x: 0, offset_y: 0, scale: 1.0 },
                  sub: { ...prev.sub, offset_x: 0, offset_y: 0, scale: 1.0 },
                  main: { ...prev.main, offset_x: 0, offset_y: 0, scale: 1.0 }
                }));
                setDoodleOffsets({});
              }}
              className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100/90 hover:bg-blue-200 text-blue-800 font-medium transition-colors cursor-pointer"
              title="一键复位所有文字位置、字号与图贴"
            >
              一键复位
            </button>
          )}
        </div>

        {uploadError && (
          <div className="mt-2 w-full max-w-[280px] px-2.5 py-1.5 rounded-lg bg-red-50 border border-red-200 text-[11px] text-red-700 flex items-start gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
            <span>{uploadError}</span>
          </div>
        )}

        {/* 预览下方控制条（无任何画面遮挡） */}
        <div className="mt-2.5 w-full max-w-[280px] flex items-center justify-between text-xs text-slate-500 px-1">
          <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-800 transition-colors">
            <input
              type="checkbox"
              checked={showSafeZone}
              onChange={(e) => setShowSafeZone(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
            />
            <span>短视频安全区辅助线</span>
          </label>

          <span className="text-[11px] text-slate-400 font-mono">9:16 · 1080×1920</span>
        </div>

        {/* 本地自定义封面上传与模式选择 */}
        <div className="mt-3 w-full max-w-[280px] p-2.5 rounded-xl border border-slate-200/90 bg-white shadow-2xs space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-slate-800 flex items-center gap-1.5">
              <Upload className="w-3.5 h-3.5 text-blue-600" />
              <span>{source === 'custom_upload' ? '已选用自定义封面' : '上传自定义封面图片'}</span>
            </span>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/bmp"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
              className="px-2.5 py-1 font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer flex items-center gap-1 shadow-2xs disabled:opacity-50"
            >
              <Upload className="w-3 h-3" />
              <span>{isUploading ? '上传中...' : source === 'custom_upload' ? '更换图片' : '上传本地图片'}</span>
            </button>
          </div>

          {source === 'custom_upload' ? (
            <div className="space-y-1.5 pt-1.5 border-t border-slate-100">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-emerald-700 font-medium flex items-center gap-1">
                  <Check className="w-3 h-3 text-emerald-600" />
                  自定义封面已生效
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSource('video_frame');
                    if (templateId === 'pure_image') {
                      setTemplateId('text_behind_person');
                    }
                  }}
                  className="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
                >
                  切回视频截帧
                </button>
              </div>

              {/* 纯净直出 vs 模板设计快捷切换 */}
              <div className="flex items-center gap-1.5 pt-0.5">
                <button
                  type="button"
                  onClick={() => setTemplateId('pure_image')}
                  className={`flex-1 py-1 px-1.5 rounded-lg border text-center transition-all cursor-pointer text-[11px] ${
                    templateId === 'pure_image'
                      ? 'bg-blue-50 border-blue-500 text-blue-700 font-bold shadow-2xs'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                  title="直接使用上传的原图作为封面，不叠加任何文字"
                >
                  🖼️ 纯图直出 (不叠字)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (templateId === 'pure_image') {
                      setTemplateId('text_behind_person');
                    }
                  }}
                  className={`flex-1 py-1 px-1.5 rounded-lg border text-center transition-all cursor-pointer text-[11px] ${
                    templateId !== 'pure_image'
                      ? 'bg-blue-50 border-blue-500 text-blue-700 font-bold shadow-2xs'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                  title="在上传的底图上继续套用标题与贴纸"
                >
                  🎨 套用文字模板
                </button>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-slate-400 leading-normal">
              支持上传自己设计的封面（JPG/PNG），可一键作为纯净封面直出或继续套用模板
            </p>
          )}
        </div>
      </div>

      {/* 右侧：三大核心区域独立编辑与底图选择 (拥有专属独立滚动条，滚动只移动右边) */}
      <div className="lg:col-span-7 space-y-3.5 max-h-[calc(90vh-140px)] overflow-y-auto pr-1.5 scrollbar-thin">
        <div className="flex items-center justify-between pb-1 border-b border-slate-100">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span className="text-xs font-bold text-slate-800">封面全案设计与区域精修</span>
          </div>
          <span className="text-[11px] text-slate-400">顶部全案模板 · 下方单区精修 · 协同解耦</span>
        </div>

        {/* 精选全案设计风格模板（一键注入3区协同方案，首推截图同款蓝黄撞色） */}
        <div className="p-3 rounded-2xl bg-white border border-slate-200/90 shadow-2xs space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span className="text-xs font-bold text-slate-800">全案设计风格模板</span>
              <span className="text-[10px] text-slate-400">（开箱即用，已深度校准最佳排版与视觉效果）</span>
            </div>

            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200/80 font-medium flex items-center gap-1">
              <Check className="w-2.5 h-2.5 stroke-[3]" />
              <span>最佳视觉校准</span>
            </span>
          </div>

          {/* 7 大全案设计风格模板卡片（极简清爽排版，字样完整无遮挡） */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {MASTER_DESIGN_TEMPLATES.map((m) => {
              const isSelected = selectedMasterId === m.id;
              const mainBg = m.zones.location.stroke_color;
              const accentColor = m.zones.main.text_color;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => handleSelectMaster(m)}
                  className={`p-2.5 rounded-xl border text-left transition-all flex items-center justify-between cursor-pointer group ${
                    isSelected
                      ? 'bg-blue-50/90 border-blue-600 ring-2 ring-blue-500/20 shadow-xs'
                      : 'bg-slate-50/70 border-slate-200/90 hover:bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {/* 双色质感指示圆点 */}
                    <div
                      className="w-5 h-5 rounded-full shrink-0 border border-black/10 shadow-2xs flex items-center justify-center overflow-hidden"
                      style={{ background: `linear-gradient(135deg, ${mainBg} 50%, ${accentColor} 50%)` }}
                      title={`${m.name} · ${m.subtitle}`}
                    />
                    <div className="min-w-0">
                      <div className={`text-xs font-bold leading-tight ${isSelected ? 'text-blue-950 font-black' : 'text-slate-800'}`}>
                        {m.name}
                      </div>
                      <div className="text-[10px] text-slate-500 leading-tight mt-0.5">
                        {m.subtitle}
                      </div>
                    </div>
                  </div>

                  {isSelected && (
                    <div className="w-4 h-4 rounded-full bg-blue-600 text-white shrink-0 flex items-center justify-center shadow-xs ml-1">
                      <Check className="w-2.5 h-2.5 stroke-[3]" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* 人像超清与美颜处理卡片 */}
        <div className="p-3 rounded-xl border border-slate-200/90 bg-white/90 shadow-2xs space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
              <Sparkles className="w-3.5 h-3.5 text-rose-500" />
              <span>人物清晰与美颜处理</span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-rose-50 text-rose-600 border border-rose-200/60">
                ✨ 肤色白皙·五官超清
              </span>
            </div>
            <label className="inline-flex items-center gap-1.5 cursor-pointer select-none text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors">
              <input
                type="checkbox"
                checked={enablePortraitEnhancement}
                onChange={(e) => {
                  const val = e.target.checked;
                  setEnablePortraitEnhancement(val);
                  if (val && beautyMode === 'off') {
                    setBeautyMode('natural');
                  }
                }}
                className="w-3.5 h-3.5 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer"
              />
              <span>{enablePortraitEnhancement ? '已开启' : '未开启'}</span>
            </label>
          </div>

          {enablePortraitEnhancement && (
            <div className="space-y-2 pt-1 border-t border-slate-100">
              {/* 3 套智能预设 */}
              <div className="grid grid-cols-3 gap-1.5">
                {[
                  { id: 'natural', name: '自然白皙', desc: '天然通透·去黄气', badge: '推荐' },
                  { id: 'hd_clear', name: '超清质感', desc: '五官锐利·发丝分明', badge: '高清' },
                  { id: 'delicate', name: '元气红润', desc: '白里透红·车内补光', badge: '元气' }
                ].map((mode) => {
                  const isSelected = beautyMode === mode.id;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => {
                        setBeautyMode(mode.id as any);
                        if (mode.id === 'natural') {
                          setBeautyStrength(0.70);
                          setClarityStrength(0.50);
                        } else if (mode.id === 'hd_clear') {
                          setBeautyStrength(0.50);
                          setClarityStrength(0.85);
                        } else if (mode.id === 'delicate') {
                          setBeautyStrength(0.85);
                          setClarityStrength(0.45);
                        }
                      }}
                      className={`relative px-2 py-2 rounded-lg border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? 'bg-rose-50/60 border-rose-500 ring-2 ring-rose-400/20 shadow-xs'
                          : 'bg-white border-slate-200/80 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`text-[11px] font-bold ${isSelected ? 'text-rose-900' : 'text-slate-700'}`}>
                          {mode.name}
                        </span>
                        <span className={`text-[9px] px-1 py-0.2 rounded font-medium ${
                          isSelected ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-500'
                        }`}>
                          {mode.badge}
                        </span>
                      </div>
                      <span className="text-[9px] text-slate-500 mt-1 leading-tight">
                        {mode.desc}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* 高级精细微调滑杆（折叠） */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowBeautySliders(!showBeautySliders)}
                  className="text-[10px] text-slate-500 hover:text-slate-800 flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <SlidersHorizontal className="w-2.5 h-2.5 text-rose-500" />
                  <span>{showBeautySliders ? '收起精细调节' : '展开精细参数调节'}</span>
                  {showBeautySliders ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
                </button>

                {showBeautySliders && (
                  <div className="mt-1.5 p-2 rounded-lg bg-slate-50 border border-slate-200/80 space-y-2">
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-600 font-medium">肤质磨皮与白皙强度</span>
                        <span className="font-mono text-rose-600 font-bold">{Math.round(beautyStrength * 100)}%</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={beautyStrength}
                        onChange={(e) => setBeautyStrength(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-rose-500"
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-600 font-medium">五官超清与微对比锐化</span>
                        <span className="font-mono text-blue-600 font-bold">{Math.round(clarityStrength * 100)}%</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={clarityStrength}
                        onChange={(e) => setClarityStrength(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 仅保留三大核心区域编辑卡：区域 1 顶部微弧大字、区域 2 胸前引导小标、区域 3 底部转化大字 */}
        {ZONE_DEFS.map((def) => (
          <React.Fragment key={def.key}>{renderZoneCard(def)}</React.Fragment>
        ))}

        {/* 底图来源选择：视频精选截帧 vs 本地图片上传 */}
        <div className="pt-2 border-t border-slate-100 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <ImageIcon className="w-3.5 h-3.5 text-blue-500" />
              <span>封面底图来源</span>
            </span>

            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-2.5 py-1 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors flex items-center gap-1"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>选择本地图片 / 文件夹</span>
              </button>
            </div>
          </div>

          {/* 候选帧缩略图横排 */}
          {source === 'video_frame' ? (
            <div className="space-y-1.5">
              <p className="text-[11px] text-slate-400">视频精选截帧（点击选用）：</p>
              <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                {candidateLoading ? (
                  <div className="py-4 text-xs text-slate-400 flex items-center gap-2">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-500" />
                    <span>正在截取视频候选帧...</span>
                  </div>
                ) : candidates.length > 0 ? (
                  candidates.map((c, idx) => {
                    const isSelected = Math.abs(c.timestamp - frameTimestamp) < 0.1;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setSource('video_frame');
                          setFrameTimestamp(c.timestamp);
                        }}
                        className={`relative flex-shrink-0 w-20 aspect-[9/16] rounded-lg overflow-hidden border transition-all ${
                          isSelected
                            ? 'border-blue-600 ring-2 ring-blue-500 shadow-md'
                            : 'border-slate-200 opacity-70 hover:opacity-100'
                        }`}
                      >
                        <img
                          src={getMediaUrl(c.thumb_url)}
                          alt={c.label}
                          className="w-full h-full object-cover"
                        />
                        <span className="absolute bottom-1 right-1 text-[9px] px-1 py-0.2 rounded bg-black/70 text-white font-mono">
                          {c.label}
                        </span>
                        {isSelected && (
                          <div className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-blue-600 text-white flex items-center justify-center shadow-xs">
                            <Check className="w-2 h-2 stroke-[3]" />
                          </div>
                        )}
                      </button>
                    );
                  })
                ) : (
                  <p className="text-xs text-slate-400 py-2">暂无候选帧，请先导入或合成视频。</p>
                )}
              </div>
            </div>
          ) : (
            // 自定义图片上传状态展示与画幅适配模式
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  已选用自定义本地图片
                </span>
                <button
                  type="button"
                  onClick={() => setSource('video_frame')}
                  className="text-xs text-blue-600 hover:underline"
                >
                  切回视频截帧
                </button>
              </div>

              {/* 比例适配切换 */}
              <div className="pt-1 flex items-center gap-2">
                <span className="text-[11px] text-slate-500">画幅比例适配：</span>
                <button
                  type="button"
                  onClick={() => setAspectMode('blur_padding')}
                  className={`text-xs px-2 py-1 rounded-lg border flex items-center gap-1 ${
                    aspectMode === 'blur_padding'
                      ? 'bg-blue-50 border-blue-400 text-blue-700 font-semibold'
                      : 'bg-white border-slate-200 text-slate-600'
                  }`}
                >
                  <Maximize2 className="w-3 h-3" />
                  <span>高斯模糊背景填充 (不裁切)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setAspectMode('center_crop')}
                  className={`text-xs px-2 py-1 rounded-lg border flex items-center gap-1 ${
                    aspectMode === 'center_crop'
                      ? 'bg-blue-50 border-blue-400 text-blue-700 font-semibold'
                      : 'bg-white border-slate-200 text-slate-600'
                  }`}
                >
                  <Crop className="w-3 h-3" />
                  <span>居中裁切填充 (满屏)</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
