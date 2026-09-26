# Implementation Plan: 场地与教学空镜地区车牌标签管理与精准匹配 (014-broll-plate-region)

**Branch**: `014-broll-plate-region` | **Date**: 2026-09-24 | **Spec**: [specs/014-broll-plate-region/spec.md](file:///d:/project/video_cut/specs/014-broll-plate-region/spec.md)

**Input**: Feature specification from `specs/014-broll-plate-region/spec.md` with user clarifications (ASR 自动识别免切换、严格浙江 11 地市、0 穿帮安全模式).

---

## Summary

实现驾培空镜素材的**地域车牌标签化管理**与**AI 全自动防穿帮分镜调度**全闭环：
1. **入库属地化**：在素材库针对“场地空镜（venue）”与“教学学车空镜（lesson）”引入浙江 11 地市（`浙A · 杭州` ~ `浙L · 舟山`）严格单选标签，卡片支持原地快捷修改；
2. **ASR 地理感知**：构建本地轻量级浙江行政区划与考场常识库，语音识别后自动提取地名实体，零人工干预锁定视频目标城市；
3. **分镜绝对防穿帮**：调度引擎实行 100% 同城强隔离，仅选用目标城市空镜素材；若素材匮乏则同城循环复用或保留口播原画面，坚决杜绝任何异地车牌混入。

---

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.2+, React 18.2+  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLite3, Axios, TailwindCSS, Lucide-React, Electron 30  
**Storage**: SQLite (`storage/videocut.db`) 为单一权威库，平滑扩展 `materials.plate_region` 与 `projects.target_region` 列  
**Testing**: pytest (后端核心推导与分镜防穿帮单测/集成测试)、前端组件交互验证  
**Target Platform**: Windows 10/11 64-bit、macOS (Darwin)  
**Project Type**: Desktop Application (Electron + Python Backend)  
**Performance Goals**:
- ASR 文本地名推导耗时 < 1ms，对初剪整体管线无额外延迟；
- 批量上传/导入素材时，属地属性绑定无额外 IO 损耗；
- 分镜调度候选池过滤耗时 < 5ms。  
**Constraints**: 严格执行真实运行准则（AGENTS.md），零假数据替代；不引入笨重的大型 NLP/NER 模型，采用高效确定的字典分词打分；绝对 0 跨市穿帮。

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Gate | Compliance Analysis | Status |
| :--- | :--- | :---: |
| **I. C端体验与免终端启动** | 上传界面直观提供下拉单选；剪辑端 ASR 全自动推导城市，用户全程零繁琐表单配置，符合极简 C 端标准。 | **PASS** |
| **II. Harness 抽象与引擎解耦** | ASR 地名实体推导作为 ASR 后的独立结构化处理层，无论底层是 MiniMax 还是本地 whisper 均完全解耦兼容。 | **PASS** |
| **III. 智能音视频管线与声画解耦** | 真正将“语义文字地名”与“空镜画面地域车牌”强关联，解决长期存在的声画不符、异地穿帮问题，强化分镜质量。 | **PASS** |
| **IV. 硬件感知与批处理并发** | 纯规则与元数据查询，在毫秒级完成同城候选池筛选，对 CPU/GPU 算力零额外开销。 | **PASS** |
| **V. 极简高效与防无用循环** | 使用确定的区划考场映射字典与加权打分，摒弃复杂的远程 API，代码短小精炼、易读高内聚。 | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/014-broll-plate-region/
├── spec.md              # 需求规格说明书 (已定稿)
├── plan.md              # 本实现计划 (Implementation Plan)
├── research.md          # Phase 0 技术决策与调研报告
├── data-model.md        # Phase 1 数据模型与 SQLite 迁移设计
├── quickstart.md        # Phase 1 自动化与端到端验证指南
├── contracts/           # Phase 1 接口与分镜契约
│   ├── material-region-api.json
│   └── scene-decision-region-contract.json
└── checklists/
    └── requirements.md  # 需求质量验证清单 (100% Pass)
```

### Source Code Impact

```text
backend/app/
├── core/
│   └── plate_regions.py      # [新增] 浙江 11 地市、区县、考场常识库与 ASR 地名打分推导算法
├── models/
│   └── entities.py           # [修改] Material 增加 plate_region，Project 增加 target_region
├── db/
│   ├── session.py            # [修改] SQLite 初始化平滑执行 ALTER TABLE 迁移追加列
│   └── repository.py         # [修改] MaterialRepository 支持 plate_region 持久化、改签与条件查询
├── api/
│   └── editor.py             # [修改] 上传/导入接口接收 plate_region；分镜生成调度实施同城过滤
└── native_engine/
    └── scene_decision.py     # [修改] 提取 target_region 并在分配 material_id 时实施严格防穿帮过滤

frontend/src/
├── constants/
│   └── regions.ts            # [新增] 前端浙江 11 地市标准常量字典
├── services/
│   └── api.ts                # [修改] uploadMaterial/importLocalMaterial 扩展 plate_region，新增 updateMaterialRegion API
└── pages/
    ├── AssetLibrary.tsx      # [修改] 场地/教学标签页呈现单选 Select，素材卡片展示徽章并支持原地改签
    └── VideoEditor.tsx       # [修改] 呈现 AI 自动识别出的目标城市徽章，空镜候选池严格展示同城素材
```

---

## Implementation Outline (Phase-by-Phase)

### Phase 0: 调研与决策确认 (已完成)
- 参见 [`research.md`](file:///d:/project/video_cut/specs/014-broll-plate-region/research.md)。

### Phase 1: 契约、数据模型与验证指南 (已完成)
- 数据模型演进：[`data-model.md`](file:///d:/project/video_cut/specs/014-broll-plate-region/data-model.md)；
- 接口与调度契约：[`contracts/`](file:///d:/project/video_cut/specs/014-broll-plate-region/contracts/)；
- 验证流程与测试用例：[`quickstart.md`](file:///d:/project/video_cut/specs/014-broll-plate-region/quickstart.md)；
- Agent 上下文引用已更新至 `AGENTS.md`。

### Phase 2: 任务拆解与顺序实施 (待执行 `/speckit-tasks`)

1. **Step 1 (地名常识库与推导算法)**:
   - 编写 `backend/app/core/plate_regions.py`：定义浙江 11 地市映射结构；
   - 实现 `deduce_target_region(subtitles)` 打分推导函数；
   - 编写单测 `tests/test_plate_region_deduction.py` 验证各区县、考场命中率与兜底逻辑。

2. **Step 2 (数据库模式演进与素材 API)**:
   - 更新 `backend/app/db/session.py` 执行 `ALTER TABLE` 幂等自愈迁移；
   - 更新 `backend/app/models/entities.py` 的 `Material` 与 `Project` 模型；
   - 更新 `backend/app/db/repository.py` 与 `backend/app/api/editor.py`：上传接收 `plate_region`，增加原地修改端点 `PATCH /api/v1/materials/{id}/region`；
   - 编写接口单测 `tests/test_material_region_api.py`。

3. **Step 3 (智能分镜引擎 0 穿帮调度改造)**:
   - 改造 `backend/app/native_engine/scene_decision.py` 与 `backend/app/api/editor.py` 中的分镜匹配循环；
   - ASR 识别后自动推导 `target_region` 并写入工程；
   - 在挑选 `venue` / `lesson` 空镜素材时，严格施加 `plate_region == target_region` 过滤；
   - 编写分镜防穿帮集成测试 `tests/test_scene_decision_plate_region.py`。

4. **Step 4 (前端素材库单选上传与卡片改签)**:
   - 创建 `frontend/src/constants/regions.ts` 导出 11 地市列表；
   - 改造 `frontend/src/services/api.ts` 传入 `plate_region` 与新增改签方法；
   - 改造 `frontend/src/pages/AssetLibrary.tsx`：为场地/教学上传区添加简洁精致的 Select 单选框，素材卡片呈现徽章并支持点击改签。

5. **Step 5 (前端剪辑工作台目标城市感知与端到端验收)**:
   - 改造 `frontend/src/pages/VideoEditor.tsx`：顶部或分镜栏呈现 `🎯 目标城市: 浙E · 湖州 (AI自动推导)` 状态徽章；
   - 运行完整测试套件，执行手工流转验证，确保 0 跨市穿帮。
