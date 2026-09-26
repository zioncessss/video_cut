# API & Canvas Contracts: 015-text-behind-person-cover

## 1. 模板目录 API 契约 (`GET /cover-templates`)

后端接口响应中的 `templates` 列表扩充 `text_behind_person` 模板项：

```json
{
  "templates": [
    {
      "id": "text_behind_person",
      "name": "人后拱形字（3D穿插爆款）",
      "category": "layered_impact",
      "badge": "🔥 顶流穿插",
      "sample_preview": "兔牙教练同款",
      "description": "顶部大字穿插在人像脑后，人物带纯白贴纸发光，彩虹拱形弧度",
      "supported_themes": ["classic_blue", "authority_red", "sunset_orange"]
    }
  ]
}
```

---

## 2. 候选帧与人物图层 API 契约 (`GET /projects/{project_id}/cover-candidates`)

响应中的 `candidates` 数组项支持透明人像字段：

```json
{
  "candidates": [
    {
      "timestamp": 1.5,
      "thumb_url": "/media/covers/candidates/cand_1.5.jpg",
      "person_thumb_url": "/media/covers/candidates/cand_1.5_person.png",
      "score": 0.95,
      "has_person": true
    }
  ]
}
```

---

## 3. 截帧抽图接口 (`POST /projects/{project_id}/cover-frame`)

支持从指定时间点抽取视频帧并可选返回抠出的人像透明图层：

```http
POST /projects/{project_id}/cover-frame
Content-Type: application/json

{
  "timestamp": 3.0,
  "extract_person": true
}
```

响应：

```json
{
  "timestamp": 3.0,
  "image_path": "storage/covers/candidates/custom_3.0.jpg",
  "thumb_url": "/media/covers/candidates/custom_3.0.jpg",
  "person_path": "storage/covers/candidates/custom_3.0_person.png",
  "person_thumb_url": "/media/covers/candidates/custom_3.0_person.png",
  "has_person": true
}
```

---

## 4. 前端 Canvas 渲染契约 (Canvas Layer Contract)

在 `CoverPreviewSelector.tsx` 的 Canvas 渲染循环中遵循以下接口契约：

```typescript
export interface RenderLayeredCoverParams {
  ctx: CanvasRenderingContext2D;
  canvasWidth: number;   // 360
  canvasHeight: number;  // 640
  bgImage: HTMLImageElement;
  personImage: HTMLImageElement | null;
  locationTag: string;   // 顶部拱形主词，如 "杭州学车"
  subTitle: string;      // 中部斜角卡片词，如 "避坑课" 或 "欢迎试学"
  mainTitle: string;     // 底部转化大字，如 "2980全公开"
  palette: {
    main: string;        // 默认 #1650CC
    sub: string;         // 默认 #FFFFFF
    accent: string;      // 默认 #FFEE0A
  };
}
```
