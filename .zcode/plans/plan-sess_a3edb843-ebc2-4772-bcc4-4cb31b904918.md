## 归因结论

**架构冲突（根因层，5 个）**：A1 存储三层真相源（SQLite+JSON 双写+内存缓存，delete_material 会用仅含 DB 的缓存重写 JSON 静默毁数据）；A2 打包/进程架构（spec 决策是 sidecar，代码是 dev-only spawn `.venv` + 硬编码 18888 + 引擎失败静默）；A3 Harness 契约错乱（base.py 注解 List、zcode 返回裸 List，激活即崩）；A4 知识/配置多源（词表 4 份、settings 双处、端口 3 处硬编码、opacity 3 默认值）；A5 schema 双轨（schema.sql 与 session.py ALTER 自愈不一致，3 新列自愈缺失）。
**代码逻辑冲突（9 个）**：repository 丢 6 字段+broll 字段；ffmpeg 失败复制原文件充成功（违铁律）；openPath 相对路径；`_pipeline_progress` 无界；mac artifactName 缺 `${arch}`；.gitignore 缺口+垃圾文件；test_editor_api 直写真实 DB；tasks.md 虚勾；手动编辑不过词库（**by-design，不动**）。

已确认决策：SQLite 单一权威 / 完整 sidecar / DB 留 storage/ / 词库空兜底+告警。分三阶段，**每阶段末跑全量测试并停下向用户汇报验证结果，确认后再进下一阶段**（关键节点探讨验证）。

---

## Stage 0：止血（契约 + 铁律 + 局部 bug）

1. `harness_bridge/base.py:50` 抽象注解改为 `-> HarnessCorrectionResponse`；新建 `harness_bridge/prompting.py`：`build_correction_prompt(clean_input)` 从 glossary 动态生成纠错提示词（codex.py 现有逻辑迁入）。
2. `harness_bridge/zcode.py`：删 :124 硬编码词表改用 prompting；`correct_subtitles` 组装 `HarnessCorrectionResponse`（解析失败降级 embedded）。
3. `native_engine/ffmpeg_filter.py`：4 处失败 `copyfile` 兜底（:228/276/370/376）全部改为 `raise RuntimeError`，真实合成失败必须暴露。
4. `core/config.py`：删 `DRIVING_SCHOOL_KEYWORDS` 死快照；`load_glossary()` 缺失/损坏时返回全空词库 + 打印告警（去掉内置"湖州驾校"默认词表，符合铁律）。
5. `AssetLibrary.tsx`：openPath 改用后端 `_enrich_project_export_meta` 已返回的绝对路径。
6. `electron-builder.yml` mac `artifactName` 加 `${arch}`；`.gitignore` 补 `storage/videocut.db*`、`storage/backups/`、`storage/database.sqlite`、`test_banner.png`、`dist/`、`out/`；删垃圾文件 `storage/database.sqlite`、`test_banner.png`（已确认零引用）。
7. `api/editor.py`：`_pipeline_progress` 加容量上限（>500 淘汰最旧）。
8. 测试隔离：新增/改 conftest 设 `VIDEOCUT_DB_PATH=tmp_path`；`test_editor_api.py` mock explorer 副作用。
9. 文档对齐：tasks.md 撤回 T015/T018-T021 不实勾选、补录词库功能条目；plan.md 记录 DB 留 storage/ 的决策修订。

**闸门 0**：全量 pytest + 新增「zcode 契约（fake CLI）」「ffmpeg 缺失必须抛错」单测 → 停下汇报。

## Stage 1：存储单一真相源（SQLite 权威）

1. `db/schema.sql`：projects 补 `last_engine_used / corrections_summary_json / correction_latency_ms`；subtitles 补 `broll_playback_mode / broll_assignment_id`（修复 broll id/playback_mode 丢失）。
2. `db/session.py`：DDL 收敛为 schema.sql 单权威 + 一份列清单派生自愈（projects 新列纳入 `get_db_connection` 自愈），消除两份手写 ALTER。
3. `db/repository.py`：save/_assemble 补齐全部缺口字段（含 corrections_summary 序列化往返）。
4. `native_engine/project_storage.py`：`save_project` 默认只写 SQLite；JSON 双写仅 env `VIDEOCUT_LEGACY_JSON=1` 时保留；JSON 读取保留为只读迁移路径。
5. `native_engine/storage.py`：删 `_save_meta` 全量重写 JSON（save/delete 仅写 DB）。
6. `db/migrator.py`：迁移成功后源 JSON 一律移入 `storage/legacy/` 归档（含孤儿，兑现「零丢失」），迁移清单写入 settings 表。
7. `scripts/apply_glossary.py` 改用 config 的 DB_PATH（尊重 `VIDEOCUT_DB_PATH`/`VIDEOCUT_STORAGE_DIR`）。

**闸门 1**：新增 roundtrip 测试（保存→SQLite 重载→字段全等断言）+ 迁移演练（备份→migrator→断言 legacy 归档与字段不丢）→ 停下汇报。

## Stage 2：sidecar 产品化（兑现 T015/T018-T021）

1. 引擎打包：新增 `scripts/build-engine.*`，PyInstaller 将 backend 打为 `resources/engine/videocut-engine(.exe)`，ffmpeg 随包进 `resources/engine/bin`；ASR 模型路径参数化（首跑下载需提示，打包冒烟用干净环境验证）。
2. `src/main/engine-manager.ts`：production 从 `process.resourcesPath/engine/` 启动 sidecar；启动前选空闲端口经 `VIDEOCUT_PORT` 传递；设 `VIDEOCUT_STORAGE_DIR`（便携：安装目录旁 storage）；健康失败 → 渲染层显式错误页 + 重试（去掉静默开窗）。
3. 前端：preload bridge 暴露 `getApiBase()`；`api.ts` 动态 base（bridge → env → 默认 18888）。
4. 桌面集成：Tray（引擎状态/重启/打开数据目录/退出）+ `requestSingleInstanceLock`（补 T015）；收敛 `webSecurity:false`。
5. CI：`release.yml` 每平台先构建引擎再 electron-builder。

**闸门 2**：本地 `pnpm build:win` + 安装实测冒烟（引擎拉起/健康检查/字幕链路/退出回收进程/无 .venv 环境可运行）→ 最终汇报。

## 不做的事
- 手动编辑字幕不经过词库（用户手改的词不被机器再改，by-design）。
- 不迁移 DB 到 userData（已决策留 storage/）。
- 不调整 renderer 目录布局（与 plan.md 的 src/renderer 差异仅记录在案）。

## 风险
- PyInstaller 打 faster-whisper 体积大、模型首跑需下载（ASR base 模型）——打包脚本参数化模型路径并在冒烟中验证。
- 打包后环境无 node/codex CLI：zcode/codex harness 在产品模式需显式报错降级 embedded（诚实提示，不静默）。
