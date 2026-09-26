export interface RegionItem {
  code: string;         // '浙E·湖州'
  platePrefix: string;  // '浙E'
  cityName: string;     // '湖州'
  label: string;        // '浙E · 湖州'
}

export const ZHEJIANG_REGIONS: RegionItem[] = [
  { code: '浙A·杭州', platePrefix: '浙A', cityName: '杭州', label: '浙A · 杭州' },
  { code: '浙B·宁波', platePrefix: '浙B', cityName: '宁波', label: '浙B · 宁波' },
  { code: '浙C·温州', platePrefix: '浙C', cityName: '温州', label: '浙C · 温州' },
  { code: '浙D·绍兴', platePrefix: '浙D', cityName: '绍兴', label: '浙D · 绍兴' },
  { code: '浙E·湖州', platePrefix: '浙E', cityName: '湖州', label: '浙E · 湖州' },
  { code: '浙F·嘉兴', platePrefix: '浙F', cityName: '嘉兴', label: '浙F · 嘉兴' },
  { code: '浙G·金华', platePrefix: '浙G', cityName: '金华', label: '浙G · 金华' },
  { code: '浙H·衢州', platePrefix: '浙H', cityName: '衢州', label: '浙H · 衢州' },
  { code: '浙J·台州', platePrefix: '浙J', cityName: '台州', label: '浙J · 台州' },
  { code: '浙K·丽水', platePrefix: '浙K', cityName: '丽水', label: '浙K · 丽水' },
  { code: '浙L·舟山', platePrefix: '浙L', cityName: '舟山', label: '浙L · 舟山' },
];

export const DEFAULT_REGION = '浙E·湖州';

export const formatRegionBadge = (code?: string | null): string => {
  if (!code) return '未标注地区';
  const found = ZHEJIANG_REGIONS.find(r => r.code === code);
  return found ? found.label : code;
};
