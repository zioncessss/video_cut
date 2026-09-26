# Research: 抖音平台违禁词字幕合规清洗与多策略脱敏管线

**Feature**: `011-douyin-banned-words`
**Date**: 2026-09-21
**Status**: Completed

## 1. 核心技术决策与调研结果

### 决策 1: 违禁词库的权威存储与热生效架构
- **决定方案**: 在 `storage/banned_words.json` 中独立维护违禁词与形似字映射字典，后端采用基于 `mtime` 的单例内存缓存器（`ComplianceSanitizer`）。
- **理由 (Rationale)**: 
  1. 严格契约：遵循 AGENTS.md“词库单一事实源”准则，严禁在业务代码中硬编码任何字符映射表；
  2. 热更新：短视频平台风控词库变动频繁，剪辑师或运营修改 `storage/banned_words.json` 保存后立即生效，无需重启 FastAPI 后端；
  3. 纯函数解耦：文本脱敏只在字幕渲染与预览层执行，原版 ASR 转写与校正文本（`corrected_text`）保持干净，不污染数据库核心实体。
- **替代方案评估 (Alternatives Considered)**:
  - *合并进 `storage/glossary.json`*: `glossary.json` 目前服务于 ASR 热词、同音错别字纠正与关键词分类。违禁词脱敏属于平台风控层，职责不同；若混合在一起，容易导致 ASR 纠错阶段误将讲者的正规发音纠错为生僻形似字。因此独立配置 `banned_words.json` 职责最为清晰。

---

### 决策 2: 字符串贪婪匹配与单趟正则编译 (Longest-Match-First)
- **决定方案**: 对字典按词长倒序排序（`sorted(keys, key=len, reverse=True)`），并使用单趟正则分组匹配或长词优先替换。
- **理由 (Rationale)**:
  - 词库中存在大量前缀/后缀包含关系（如“最”与“最低”/“最快”，“费”与“学费”/“模拟费”/“费用”，“评论”与“评论区”）。若先替换短词，会导致“最低”被破坏为“蕞低”而后无法匹配“最低”专属规则。长词优先确保语义最贴切的规则先命中。
- **替代方案评估 (Alternatives Considered)**:
  - *AC自动机 (Aho-Corasick)*: 当词表在 50~200 个词以内时，Python 原生单趟编译的 Regex / 倒序替换执行耗时 < 0.1ms，引入第三方 C 扩展依赖违背宪章“极简高效、防过度工程”准则。

---

### 决策 3: 高亮关键词元数据无损级联传递 (Highlight Zero-Loss)
- **决定方案**: 当对每行字幕执行脱敏时，同步对 `highlight_words`（如 `[{"word": "多少钱", "color": "#EF4444"}]`）中的 `word` 字段应用同一套脱敏函数（转换为 `"多少銭"`）。
- **理由 (Rationale)**:
  - 严格遵守 AGENTS.md 准则 1：“高亮词全生命周期无损传递”。若仅替换字幕正文而不替换高亮关键词，`generate_ass_file` 在生成高亮标签时将无法在正文中找到原词，导致高亮丢失或标签错位。同步变换确保颜色与字号 100% 精确渲染。

---

### 决策 4: 导出弹窗透明确认与预检 API
- **决定方案**: 
  - 后端提供 `GET /api/editor/projects/{id}/banned_words_check`，返回当前视频是否含有违禁词及命中位置明细；
  - `POST /api/editor/projects/{id}/render` 支持可选查询参数 `filter_banned_words: bool = True`；
  - 前端导出按钮点击后弹出优雅的导出设置弹窗（Modal），展示“开启抖音违禁词脱敏处理”复选框（默认勾选）与敏感词替换明细卡片。
- **理由 (Rationale)**:
  - 既满足用户“进入剪辑台导出时询问”的明确指示，又通过预检卡片让剪辑师对导出的成片效果 100% 放心。