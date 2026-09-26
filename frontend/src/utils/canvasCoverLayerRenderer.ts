/**
 * 015 爆款封面 Canvas 分层排版与无缝连体贴纸渲染器
 * 提供彩虹拱形自适应排列、多阶段描边字芯分层渲染、闭合消除字间缝隙等核心工具算法。
 */

export interface ArcCharLayout {
  ch: string;
  xCenter: number;
  yCenter: number;
  angleDeg: number;
}

/**
 * 计算顶部彩虹拱形微弯排版坐标
 * @param chars 字符数组
 * @param charWidths 字符宽度
 * @param canvasW 画布宽度（默认 360）
 * @param peakY 拱顶 Y 坐标
 * @param microGap 字符间距（负值代表紧凑连体）
 * @param maxDeg 两端最大倾斜角（默认 8.0 度）
 */
export function computeArcLayout(
  chars: string[],
  charWidths: number[],
  canvasW: number = 360,
  peakY: number = 70,
  microGap: number = -2.5,
  maxDeg: number = 7.0
): ArcCharLayout[] {
  const n = chars.length;
  if (n === 0) return [];

  const angles = n > 1
    ? chars.map((_, i) => -maxDeg + (2 * maxDeg * i) / (n - 1))
    : [0];

  const totalW = charWidths.reduce((acc, w) => acc + w, 0) + microGap * (n - 1);
  let curX = (canvasW - totalW) / 2;
  const curveA = 0.00030 * (640 / 1920) * (1080 / canvasW);

  return chars.map((ch, idx) => {
    const cw = charWidths[idx];
    const ang = angles[idx];
    const xCenter = curX + cw / 2;
    const dx = xCenter - canvasW / 2;
    const yCenter = peakY + curveA * (dx * dx);
    curX += cw + microGap;
    return { ch, xCenter, yCenter, angleDeg: ang };
  });
}

/**
 * 计算倾斜平排整行文字坐标（用于胸前引导标与底部价格转化大字）
 */
export function computeTiltedRowLayout(
  chars: string[],
  charWidths: number[],
  startX: number,
  baseY: number,
  angleDeg: number = -3.2,
  gap: number = -2.0
): { ch: string; xCenter: number; curY: number }[] {
  const rad = (angleDeg * Math.PI) / 180;
  let curX = startX;

  return chars.map((ch, idx) => {
    const cw = charWidths[idx];
    const curY = baseY + idx * (cw + gap) * Math.tan(rad);
    const xCenter = curX + cw / 2;
    curX += cw + gap;
    return { ch, xCenter, curY };
  });
}
