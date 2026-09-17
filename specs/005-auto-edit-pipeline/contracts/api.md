# API Contracts: 005-auto-edit-pipeline

**基座**: FastAPI `/api`（现有前缀），全部 JSON。变更遵循「增量兼容」：旧字段保留一版过渡期。

## C1. POST /api/editor/analyze-and-cut（增强，响应结构扩展）

Request（新增字段）:
```json
{ "talking_head_id": "...", "aspect_ratio": "9:16", "auto_broll": true,
  "force_retranscribe": false, "enable_scene_decision": true }
```

Response（CutProject，新增/变更片段）:
```json
{
  "subtitles": [{
    "id": "s1", "start_time": 0.0, "end_time": 2.1,
    "raw_text": "...", "corrected_text": "...",
    "matched_category": "experience",
    "highlight_words": [{"word": "九月份", "source": "ai"}, {"word": "一把过", "source": "glossary"}],
    "matched_keywords": ["一把过"],
    "scene_decision": {"part": "body", "broll_category": "venue", "broll_duration": 1.8,
                       "transition_seconds": 0.4, "material_id": "...", "reason": "明确提及训练场规模卖点"},
    "broll_material_id": "...", "is_manual_edited": false
  }],
  "last_engine_used": "api",
  "pipeline_notes": {"scene_decision_engine": "api", "scene_decision_degraded": false}
}
```

错误：404（素材不存在）；500（真实失败详情透传，禁止 200+伪成功）。

## C2. PUT /api/editor/{project_id}/subtitles（增强）

请求字幕项新增 `highlight_words` / `scene_decision`（结构与 C1 一致）；人工在前端增删高亮词、改分类/换素材/调时长均走本端点（现状已支持 subtitles+broll_replacements 整体保存）。

## C3. POST /api/editor/{project_id}/scene-decision（新增）

对既有工程单独重跑 AI 分镜决策（不重转写）:
```json
Request:  {}                         // 全部句子；后续可扩展 {"subtitle_ids": []}
Response: {"code":0, "data": {"subtitles": [ /* 仅含 id + scene_decision + highlight_words */ ],
           "engine_used": "api", "latency_ms": 42310.5, "degraded": false }}
```
- AI 失败时 `degraded=true` 并回填关键词规则结果；HTTP 仍 200（决策是增强不是事务），`pipeline_notes` 如实标注。
- 超时上限 120s（research.md R2）。

## C4. POST /api/batch/submit · GET /api/batch/{job_id}（新增）

```json
POST /api/batch/submit
Request:  {"material_ids": ["id1","id2","id3"], "aspect_ratio": "9:16"}
Response: {"code":0, "data": {"job_id": "...", "queued": 3, "concurrency": 2}}

GET /api/batch/{job_id}
Response: {"code":0, "data": {
  "job_id": "...", "status": "running", "concurrency": 2,
  "items": [{"material_id":"id1","project_id":"p1","status":"completed","progress":100,"error":null},
            {"material_id":"id2","status":"running","progress":45,"error":null},
            {"material_id":"id3","status":"failed","progress":0,"error":"ASR 失败: ...真实详情"}]}}
```
- 并发 = `HardwareMetrics.recommended_concurrency`；任务持久化于 `batch_jobs` 表，重启后可查询最终态（不恢复执行，标注 interrupted）。

## C5. POST /api/editor/{project_id}/cover（新增，Story 8）

```json
// 方式一：成片截帧
Request:  {"source": "frame", "timestamp": 12.5}
Response: {"code":0, "data": {"cover_image_path": "storage/covers/<project_id>_t12.jpg", "cover_source": "frame"}}

// 方式二：本地上传（multipart 或 base64 二选一，实现取简）
// AI 生成（预留）：
Request:  {"source": "ai"} → 501 {"code":40901, "message": "AI 封面生成规划中，敬请期待"}
```

## C6. 契约保持不变（显式声明）

- `GET /api/settings`：继续只返回 `has_token/has_key` 布尔态（凭据红线）。
- `POST /api/editor/correct`：保留兼容（前端已移除入口），行为不变。
- `GET /api/editor/{project_id}/progress`：批量与单视频共用，阶段枚举扩展 `SCENE_DECIDING`（85% 档），旧枚举值不动。

## LLM 调用契约（后端内部，职责分离的两段式）

1. **纠偏+高亮**（既有，不变）: `prompting.build_correction_prompt()` → `{subtitles:[{id,corrected_text,highlight_keywords}], corrections:[...]}`。高亮词职责完全在此调用。
2. **分镜决策**（新增 `prompting.build_scene_decision_prompt()`，词库驱动背景 + research.md R8 风格规则）:
```json
{"decisions": [{"id":"s1","part":"hook|body|cta","broll":"venue|experience|lesson|null",
                "broll_duration":1.8,"transition":0.4,"reason":"一句话"}]}
```
   后端确定性校验裁剪（不信任 AI 单方输出）：
   - `broll ∈ 枚举 ∪ null`；`broll_duration ≤ 句时长`；`transition ∈ [0, 0.5]`；
   - **part=hook/cta 强制 broll=null**；**价格手势句（「这个数/这个价/这么多」正则族）强制 broll=null**；
   - **不相邻连续切**：相邻句均为切时裁掉后句；**全片空镜占比 ≤40%**：超限按单处时长从大到小依次裁；
   - 词库高亮兜底不在此调用（纠偏调用已合并）。
