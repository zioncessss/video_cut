# Implementation Plan: 抖音平台违禁词字幕合规清洗与多策略脱敏管线 (douyin-banned-words)

**Branch**: `011-douyin-banned-words` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-douyin-banned-words/spec.md`

## Summary

实现针对抖音平台的视频字幕合规清洗系统。通过纯函数式的 `ComplianceSanitizer` 引擎与 `storage/banned_words.json` 权威词库，在字幕烧录与导出阶段采用用户终选的“形似字 / 生僻同形 / 偏旁部首拆字”进行最长匹配优先替换，同时在剪辑工作台导出时弹出确认弹窗，透明展示敏感词预检明细，确保成片 100% 避开平台 OCR 违规限流且完全无损高亮视觉与原声音频。

---

## Technical Context

**Language/Version**: Python 3.11+ (Backend), TypeScript / React 18+ (Frontend)

**Primary Dependencies**: 
- Backend: FastAPI, Pydantic v2, FFmpeg 8.x + libass, SQLite3
- Frontend: React, Vite, Lucide React, Tailwind CSS

**Storage**: 
- `storage/banned_words.json` (违禁词映射配置，基于 mtime 内存缓存热加载)
- `storage/videocut.db` (SQLite 权威库，保存工程策略字段 `banned_words_enabled`)

**Testing**: `pytest tests/test_compliance_sanitizer.py` (自动化单测与边界测试)

**Target Platform**: Windows 11 / macOS 双端桌面环境

**Project Type**: Desktop Web App (FastAPI + React + Electron/Local browser)

**Performance Goals**: 
- 字幕脱敏文本重构耗时 < 1ms
- 导出预检检测耗时 < 5ms
- FFmpeg 视频编码维持 100% 标准单次耗时，零冗余算力

**Constraints**: 
- 严格遵循 AGENTS.md 准则：高亮词（Highlight Words）全生命周期无损绑定
- 口播音频音轨 100% 保留讲者原声，绝不进行粗暴消音
- 原版识别文本与校正文本（`corrected_text`）保持干净，仅在渲染层动态脱敏

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I: C端体验与免终端启动**: 导出弹窗以图形化 Modal 交互呈现，敏感词以直观 Tag 徽章展示，禁止任何终端命令行干预。
- [x] **Principle II: Harness 抽象与引擎解耦**: 违禁词处理作为独立的数据合规清洗层（Compliance Sanitizer），与大模型纠偏引擎和底层 FFmpeg 渲染完全解耦。
- [x] **Principle III: 智能音视频管线与声画解耦**: 仅清洗字幕渲染层，保留讲者真实音轨与空镜时间轴，高亮词无损传递。
- [x] **Principle IV: 硬件感知与批处理并发调度**: 采用策略驱动单次压制架构（100% 算力与存储），杜绝强制双倍压制导致的算力暴涨。
- [x] **Principle V: 极简高效与防无用循环**: 采用 Python 原生贪婪替换与缓存，拒绝第三方复杂依赖，代码链路清晰紧凑。

---

## Project Structure

### Documentation (this feature)

```text
specs/011-douyin-banned-words/
├── spec.md              # 需求规格说明书
├── plan.md              # 本实施规划文件
├── research.md          # Phase 0 技术决策与调研报告
├── data-model.md        # Phase 1 实体结构与数据流
├── contracts/           # Phase 1 接口契约
│   └── editor-compliance.md
├── quickstart.md        # Phase 1 端到端验证指南
├── checklists/
│   └── requirements.md  # 规格质量核验清单
└── tasks.md             # Phase 2 实施任务清单 (/speckit-tasks 输出)
```

### Source Code Architecture Layout

```text
backend/app/
├── core/
│   └── compliance_sanitizer.py  # [NEW] 核心脱敏清洗器 (mtime缓存, 贪婪匹配, 字幕/高亮词同步)
├── api/
│   └── editor.py                # [MODIFY] 注入 banned_words_check 预检接口，render_project 接入合规过滤
├── models/
│   └── project.py               # [MODIFY] StrategyConfig 扩展 banned_words_enabled 字段
├── native_engine/
│   └── subtitle_styler.py       # [MODIFY] 确保生成 ASS/SRT 时支持无损高亮词脱敏
storage/
└── banned_words.json            # [NEW] 固化 26 项形似/拆字映射字典
frontend/src/
├── components/
│   └── ExportConfirmModal.tsx   # [NEW] 导出确认弹窗 (展示违禁词预检明细与合规开关)
├── pages/
│   └── VideoEditor.tsx          # [MODIFY] 导出按钮唤起 ExportConfirmModal
└── services/
    └── api.ts                   # [MODIFY] 接入 banned_words_check 与 renderProject 参数
tests/
└── test_compliance_sanitizer.py # [NEW] 纯函数单测与边界测试
```

---

## Phase 0: Outline & Research (Completed)

已在 `research.md` 中完成如下关键决策：
1. 建立独立 `storage/banned_words.json` 作为唯一事实源，按 mtime 缓存热更新；
2. 采用长词优先倒序贪婪匹配，杜绝长短词替换截断冲突；
3. 高亮词字典项 `word` 字段同步脱敏，保证 ASS 标签 100% 精准绑定；
4. 设计轻量预检 API 支持前端导出弹窗透明展示。

---

## Phase 1: Design & Contracts (Completed)

已完成如下设计交付物：
1. `data-model.md`: 定义了 `BannedWordsConfig`、`StrategyConfig` 扩展字段及数据流转换；
2. `contracts/editor-compliance.md`: 规范了 `GET /banned_words_check` 和 `POST /render` 接口；
3. `quickstart.md`: 提供了自动化单测、成片渲染与界面交互三维一体的验证流程；
4. `AGENTS.md`: 上下文指针已指向本 plan.md。

---

## Phase 2: Implementation Planning (Ready for /speckit-tasks)

核心任务拆解预演：
1. **Task 1: 字典落盘与核心清洗器 (Backend Core)**
   - 创建 `storage/banned_words.json`；
   - 编写 `backend/app/core/compliance_sanitizer.py`，实现 `sanitize_text`、`sanitize_subtitles` 与 `detect_banned_words`。
2. **Task 2: 单测与边界验证 (Backend Tests)**
   - 编写 `tests/test_compliance_sanitizer.py`，覆盖全部 26 个敏感词、贪婪排序、以及高亮词联动无损测试。
3. **Task 3: 导出预检 API 与渲染路由接入 (Backend API)**
   - 在 `backend/app/api/editor.py` 新增 `GET /projects/{id}/banned_words_check`；
   - 在 `POST /projects/{id}/render` 中将脱敏逻辑接入 `_prepare_render_subtitles`。
4. **Task 4: 前端导出弹窗组件与工作台交互 (Frontend UI)**
   - 创建 `ExportConfirmModal.tsx`，展示合规复选框与检测到的词汇替换预览；
   - 在 `VideoEditor.tsx` 中绑定导出确认流程。
5. **Task 5: 全链路端到端回归验证 (Verification)**
   - 真实素材压制成片，核验画面字幕、字体与高亮显示。