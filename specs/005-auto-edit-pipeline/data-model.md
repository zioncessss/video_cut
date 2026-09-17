# Data Model & Changes: 005-auto-edit-pipeline

**原则**: SQLite（storage/videocut.db）为权威存储；变更全部走平滑迁移（幂等、可重跑），旧数据自动映射。

## 1. MaterialCategory 枚举迁移（medical → experience）

```
变更前: talking_head | venue | medical | lesson
变更后: talking_head | venue | experience | lesson
```

- `materials.category`：SQLite CHECK 约束重建（SQLite 不支持 ALTER CHECK）：
  1. `PRAGMA foreign_keys=off` → 按新 CHECK 建 `materials_new`；
  2. `INSERT INTO materials_new SELECT ... , CASE category WHEN 'medical' THEN 'experience' ELSE category END ...`；
  3. drop/rename、重建索引、`foreign_keys=on`；整体放事务，失败回滚，重复执行自动跳过（探测新 CHECK 是否已生效）。
- 代码同步：`entities.MaterialCategory`、`keyword_matcher`、`editor.py` cat_map、`config.CATEGORIES/CATEGORY_DIRS`（磁盘目录 `storage/materials/medical/` → `experience/` 同步改名，旧目录自动搬迁）。
- glossary.json：`keywords.medical` → `keywords.experience`（迁移脚本自动备份原文件到 storage/legacy/）。
- 前端：AssetLibrary 分类卡、SubtitleList 徽标映射（`体检空镜 → 体验空镜`）。

## 2. SubtitleSegment（实体变更）

| 字段 | 类型 | 说明 |
|---|---|---|
| `highlight_words` | `List[HighlightWord]` | **新增**，替代对 `matched_keywords` 的一维依赖（渲染端读取此字段；`matched_keywords` 保留兼容一版后废弃） |
| `matched_category` | `Optional[MaterialCategory]` | 枚举值随迁移（experience） |
| `broll_material_id` | `Optional[str]` | 不变（人工修正入口） |
| `scene_decision` | `Optional[SceneDecision]` | **新增**，AI 分镜决策结果（含理由），随工程持久化 |

```python
class HighlightWord(BaseModel):
    word: str
    source: Literal["glossary", "ai", "manual"] = "glossary"

class SceneDecision(BaseModel):
    broll_category: Optional[MaterialCategory]  # None=不切
    broll_duration: float = 0.0                 # ≤ 句时长，越界裁剪
    transition_seconds: float = 0.0             # 0=硬切; 0.3~0.5 叠化
    material_id: Optional[str] = None           # 随机选取落定后回填
    reason: str = ""                            # 一句话决策理由
```

## 3. BrollReplacement（不变 + 语义扩展）

现有 `start_time/end_time/material_id/material_category/playback_mode` 已够用；`end-start` 即播放时长，转场信息落在 `SubtitleSegment.scene_decision.transition_seconds`，合成管线汇总消费。

## 4. EditingStrategy（默认值变更）

| 字段 | 变更 |
|---|---|
| `enable_top_banner` | 默认 `True → False`（仅新工程；不回写存量工程） |
| `enable_watermark` | 默认 `True → False`（同上） |
| `transition_style` | **新增** `"cut" \| "fade"`，默认 `"cut"`；fade 时按 scene_decision.transition_seconds 应用 xfade |

## 5. CutProject（封面预留）

| 字段 | 类型 | 说明 |
|---|---|---|
| `cover_image_path` | `Optional[str]` | **新增**，相对 storage 的封面图路径（截帧或上传） |
| `cover_source` | `Optional[Literal["frame","upload","ai"]]` | **新增**，来源；`ai` 仅占位（UI 提示规划中） |

## 6. BatchJob（批量剪辑）

```python
class BatchJobItem(BaseModel):
    material_id: str
    project_id: Optional[str]
    status: Literal["queued","running","completed","failed"]
    error: Optional[str] = None        # 真实错误详情
    progress: int = 0                  # 0~100

class BatchJob(BaseModel):             # 持久化到 SQLite 新表 batch_jobs（JSON items 列）
    id / total_count / completed_count / concurrency / status / created_at   # 复用现有
    items: List[BatchJobItem] = []
```

- `batch_jobs` 新表：`id TEXT PK, payload_json TEXT, status TEXT, created_at REAL`；并发数由现有 HardwareMetrics.recommended_concurrency 决定。
- 失败项必须落真实错误（真实执行铁律），不重试掩盖。

## 7. 存量数据迁移清单（幂等脚本 scripts/migrate_005.py）

1. DB：materials CHECK 重建 + medical→experience 映射；
2. projects 表内 JSON 字段：`matched_keywords` → `highlight_words[{word,source:"glossary"}]`（保守来源标记）；`scene_decision` 缺省不补；
3. 磁盘目录：`storage/materials/medical/` → `experience/`（存在才迁）；
4. glossary.json：`keywords.medical` → `keywords.experience`（备份至 storage/legacy/）；
5. 全程默认试运行打印 diff，`--apply` 才写回（对齐 apply_glossary.py 惯例）；后端运行中拒绝执行。
