# Implementation Plan: 视频封面设计与实战爆款模板升级 (012-video-cover-design)

**Branch**: `012-video-cover-design` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

---

## 1. 业务目标与实拍样本深度重构

结合创作者实际业务中高转化的 5 张实拍短视频爆款封面样片（武义学车、杭州学车、金华金东学车、婺城学车、绍兴学车），对封面设计系统进行体系化升级：
1. **强突出同城地域钩子（在哪里学车 - Location Hook）**：
   - 将“地域地名大字”（如“武义学车”、“杭州学车”、“金东学车”、“婺城学车”、“绍兴学车”）作为封面第一视觉冲击点；
   - 支持从 AI 语义提取或工程配置中自动锁定地名词，也可在界面独立编辑。
2. **模板多元化（6 大实操高转化模板库）**：
   - 包含双层描边贴纸大字报、上下通栏权威撞色条、拱形包头彩虹字、胸前羽化白光沉浸字、倾角冲击引流标、极简轻奢杂志风；
3. **字体与颜色配置美学体系**：
   - 引入 4 大字系支持（超重黑体、书法行楷、倾斜手写、质感标宋）；
   - 严选 4 套高转化调色盘（国潮权威红、电光冷紫绿、荧光粉金爆款、雪白羽化酒红）；
4. **导出时直观呈现与零转码开销**：
   - 导出弹窗直接呈现 9:16 高清预览与 6 大模板自由选择，导出时同步输出独立 1080x1920 `cover.jpg`，并可选支持首帧 0.08s 压入。

---

## 2. 技术架构与设计决策 (Architecture Layout)

```text
                                [ 创作者在导出弹窗中交互 ]
                                           │
       ┌───────────────────────────────────┴───────────────────────────────────┐
       ▼                                                                       ▼
【前端 Canvas 实时排版渲染】                                         【后端 Pillow 印刷级高清渲染】
- 双层描边 (Outer White + Inner Black)                               - `adapt_image_aspect_ratio`
- 上下通栏全宽条 (Split Banners)                                     - `render_cover_image` (1080x1920)
- 向上拱形包头字 (Rainbow Arc)                                        - 6 大模板矩阵与色彩映射
- 底部羽化雾化遮罩 (Fog Vignette)                                     - 导出成片就地保存 `cover.jpg`
- 倾角动感字 (-10° Rotation)                                          - 可选 0.08s 首帧无缝拼接
       │                                                                       │
       └───────────────────────────────┬───────────────────────────────────────┘
                                       ▼
                       【SQLite 数据库 & 任务目录】
                        - `storage/videocut.db`
                        - `storage/tasks/<task_dir>/cover.jpg`
                        - `storage/tasks/<task_dir>/output.mp4`
```

---

## 3. 模板与视觉规格设计 (Template Specifications)

### 3.1 6 大实战模板清单
1. **`sticker_double_stroke`（双层描边贴纸大字）**：
   - 结构：顶部超大双层描边地域字（贴纸感）+ 底部指示胶囊与荧光大字；
   - 配色：电光冷紫 / 亮金黄 + 纯黑内描边 + 纯白外厚描边。
2. **`split_contrast_bar`（上下通栏权威撞色条）**：
   - 结构：顶部红色全宽通栏（书法白字）+ 中间人物实景 + 底部白色全宽通栏（深红大字痛点）；
   - 配色：国潮中国红（`#B91C1C`）+ 纯白（`#FFFFFF`）+ 墨黑。
3. **`rainbow_arc_header`（拱形包头彩虹字）**：
   - 结构：向上彩虹拱形包头大字（避开人脸，环绕头顶）+ 底部斜向疑问手写字 + 小红书账号标；
   - 配色：荧光热辣粉（`#F43F5E`）+ 黑色粗阴影。
4. **`bottom_fog_vignette`（胸前羽化白光沉浸字）**：
   - 结构：画面下方大面积白色羽化渐变遮罩 + 人物胸前立体深红大字 + 顶部倾斜副标；
   - 配色：暗酒红（`#991B1B`）+ 纯白发光厚边 + 柔和白雾。
5. **`angled_impact_stamp`（倾角冲击引流标）**：
   - 结构：顶部 -10° 动态倾斜暗红大字贴纸 + 右侧紧凑金色双行金句 + 底部通栏警示横幅；
   - 配色：砖红（`#881337`）+ 亮金黄（`#FACC15`）+ 纯白粗描边。
6. **`clean_editorial`（极简轻奢杂志风）**：
   - 结构：顶部英文分类标 + 优雅居中纯白大字 + 细横线 + 衬线知性副标；
   - 配色：极简纯白 + 浅灰（`#E2E8F0`）+ 暗角背景。

---

## 4. 实施阶段规划 (Phases)

### Phase 1: 数据模型与排版核心扩展
- 在 `CoverDesignConfig` 扩展 `location_tag`、`template_id`（支持 6 大模板）、`color_theme`（4 组调色盘）；
- 升级 `backend/app/core/cover_generator.py`：实现双层描边、拱形文字坐标计算、通栏横幅渲染与羽化渐变蒙版；
- 完善纯函数单测 `tests/test_cover_generator.py`。

### Phase 2: 前端 Canvas 极速排版与视觉控件升级
- 升级 `frontend/src/components/CoverPreviewSelector.tsx`：
  - 支持 6 款模板卡片网格切换；
  - Canvas 算法对齐后端：实现双层描边、向上拱形弧排、上下通栏色块、底部羽化雾气；
  - 增加“地域关键词”快捷标签栏（自动提炼武义、金华、杭州、绍兴等）；
  - 增加 4 款调色盘快速切换。

### Phase 3: 导出弹窗集成与端到端闭环
- 在 `ExportConfirmModal.tsx` 中直接展现 6 大模板选择器与调色盘；
- 运行 `tests/test_cover_pipeline_e2e.py` 端到端全量回归；
- 构建前端并进行用户交付。

---

## 5. 验证与测试保障 (Verification Plan)
- **单元测试**：6 款模板纯函数 Pillow 出图单测（断言 1080x1920 尺寸、RGBA 通道与色块像素）；
- **接口测试**：`GET /api/v1/editor/cover-templates` 返回 6 款模板与配色定义；
- **真实场景端到端**：模拟带地域词的视频封面配置，验证 `cover.jpg` 正确落盘且 `embed_cover_as_first_frame` 正常拼接。

---

## 6. R3 迭代：分区文本样式编辑与 AI 分区推荐 (2026-09-21 用户实测反馈)

### 6.1 用户反馈（实机截图）
1. AI 没有按区域返回推荐文字（地域词区只有手动输入框，无 AI 候选）；
2. 不是每个区域的文字都可编辑；
3. 颜色选择不到位：区域内"文字颜色"与"文字边框颜色"应可在调色盘中选择；
4. 文字大小、位置需要可调。

### 6.2 产品设计决策（专业剪辑师 + PM 视角）
- **分区模型（Zone）**：封面文案固定为三个文字区——`location` 地域区（顶部大字）、`main` 主标题钩子区（中部大字）、`sub` 副标题区（小字/胶囊）。每区 = 可编辑文本 + AI 推荐候选 chips + 可覆盖样式。
- **AI 分区推荐**：每组 `SuggestedCoverTitle` 的三个字段即三个区域的候选；2~3 组文案展开为每区 2~3 个候选 chips，点击即套用该区文本。AI 未返回时按区兜底：地域区用词库地名高亮、主标题区用学车特点库（cover_hooks）、副标题区用特点库尾词条目。
- **分区样式覆盖（剪辑软件通用范式）**：每区可覆盖 4 项——`text_color` 文字填充色、`stroke_color` 文字描边色、`scale` 字号缩放（0.6~1.4）、`offset_y` 纵向位置偏移（±0.12 画布高占比）。颜色候选 = 当前调色盘 main/sub/accent 三色 + 纯白 + 纯黑（剪辑最稳组合），不做自由取色器；位置用滑杆而非画布拖拽——守住宪章 V 极简，且渲染端 clamp 保证文字永不越出安全区/人脸区。
- **默认值语义**：所有覆盖项默认 None/中性值 = 完全跟随模板与调色盘默认（一键"恢复默认"即清空覆盖）。
- **双端同规**：前端 Canvas 与后端 Pillow 按同一 zone→文字元素映射与同一 clamp 规则应用覆盖，预览即所得。

### 6.3 实施阶段
- **Phase A 数据与渲染**：`CoverTextZoneStyle` + `CoverDesignConfig.zone_styles`；Pillow 六大模板按区接入覆盖（渲染端 clamp）；`POST /cover` 契约扩展。
- **Phase B 前端分区编辑器**：`CoverPreviewSelector` 重排为"全局区（模板/调色盘/字系）+ 三个分区编辑卡"；分区卡 = 文本输入 + AI 候选 chips（地域/主标/副标分区展开）+ 文字色板 + 描边色板 + 大小滑杆 + 位置滑杆 + 恢复默认；Canvas 同步应用。
- **Phase C 验证**：单测（覆盖渲染/clamp/持久化往返）+ 样张视觉验收（分区颜色与位移生效且不越界）+ 全量回归。

### 6.4 实施记录（2026-09-21，tasks.md T026~T032，全部完成）
- **数据与契约**：`CoverTextZoneStyle`（颜色 ^#[0-9A-Fa-f]{6}$ 校验、scale/offset_y 实体层双向 clamp）+ `zone_styles`（Literal 键，非法键/色 422）；`POST /cover` 携带并回显 zone_styles；持久化无损往返。
- **渲染端（Pillow 与 Canvas 双端同规）**：渲染取色三级优先级（分区覆盖→模板默认→调色盘）；画布级 clamp（±3% 边距）与色带级整块钳制（split 主文案+副标作为整块钳入白色通栏，块内行距固定，杜绝偏移导致行间互压或与同色底融合）；显式描边色对默认无描边元素补绘描边层；fog 补 main 手写钩子行（雾化区 80%）、editorial 补 location 衬线地域行（46.5% 高），六模板三分区均保证有可编辑元素。
- **前端**：三分区编辑卡（文本输入 + AI 分区候选 chips + 文字/描边色板[调色盘 main/sub/accent+纯白+纯黑] + 字号/位置滑杆 + 恢复默认），Canvas 逐算法镜像（同 clamp 常量与描边补绘），预览即所得。
- **验证**：新增 `tests/test_cover_zone_styles.py`（13 用例）；样张视觉验收经四轮迭代（split 白底隐形→行间互压→fog main 缺失→editorial location 缺失/描边无效）12/12 通过；全量回归 236 passed / 1 skipped；`pnpm build` 通过。

## 7. R4 修复：批量混剪 4/5 失败（UNIQUE constraint failed: subtitles.id）与批次状态误报 (2026-09-21 实测反馈)

### 7.1 用户反馈（实机截图）
批次 decdd89c 并发 4 跑 5 条口播：#1 完成、#2~#5 全部失败，但批次徽章却显示绿色"已完成 5/5"。
失败项点开工作台无工程内容（内容消失的观感来源：工程从未入库，无成片产出）。

### 7.2 根因（数据库实据）
- `storage/videocut.db` 中 4 条失败项错误一致：`批量剪辑失败: 保存剪辑工程到 SQLite 失败: UNIQUE constraint failed: subtitles.id`。
- ASR/纠偏引擎给字幕的编号是**确定性的** `s_1..s_N`（`asr_runner.py` 自然句切分、`api_engine.py` 兜底补号均如此），而 `subtitles.id` 是 SQLite **全局主键**。
- 批次内 #1 工程先保存成功，留下 `s_1..s_15` 行；#2~#5 工程携带相同编号保存时逐条撞主键 → 全部失败。
- 历史批次（09-17/19/20）能全绿是因为彼时库中无残留冲突行；该缺陷是确定性编号方案引入后的潜伏雷，任何"库里已有他工程字幕行"的保存都会触发。
- 次生问题：`batch.py` 把 `completed` 与 `failed` 都计入 `completed_count`，前端 `已完成 {completed_count}/{total}` 把失败批次渲染成"已完成 5/5"，掩盖真实失败。

### 7.3 修复决策（双防线 + 状态诚实化）
1. **源头去重（editor.analyze_and_cut）**：本次转写字幕一律重生成 uuid4（删除原 `seg_/sub_` 前缀条件重生成）。位置在粗剪/分镜决策/高光映射之前，prune、compact、scene_decision、highlights 全部基于新 ID 关联，链路内自洽；`raw_asr_segments` 仅持久化不做 ID 关联，不受影响。
2. **保存端零信任兜底（ProjectRepository.save）**：INSERT 前检测两类冲突——同项目内重复 ID、与其他工程存量行冲突——仅重映射 ID（uuid4）并显式告警，原文/高亮词/分镜决策全量保留，绝不静默丢行；内存对象同步重映射保证客户端后续编辑引用一致。
3. **批次状态诚实化**：`completed_count` 只计真实成功项；`/batch/jobs` 与 `/batch/jobs/{id}` 新增 `failed_count` 并对 items 实时结算（历史落库的脏 completed_count 亦被纠正展示）。前端 BatchCut 运行进度按 (成功+失败)/总数，历史徽章拆出红色"失败 N"芯片，未知条目状态不再默认渲染成"已完成"。

### 7.4 验证
- 新增 `tests/test_subtitle_pk_collision.py`：跨工程同 ID 双保存、同项目重复 ID、API 级双素材 analyze 链路（修复前 #2 必 500）。
- 更新 `tests/test_batch_api.py` 为诚实计数契约（completed=1 / failed=1）。
- 全量回归：223 passed, 1 skipped；前端 `tsc --noEmit` 通过。
