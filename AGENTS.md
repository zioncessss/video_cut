<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan at:
specs/004-electron-sqlite-cross-build/plan.md
<!-- SPECKIT END -->

## 🚨 严禁测试函数替代真实运行准则 (Real Execution & Anti-Mock Rules)
1. **禁止假运行与模拟数据替代 (No Mock/Fallback for Real Workflows)**：
   - 在真实工程链路（ASR 语音转写、大模型纠错与指令理解、FFmpeg 视频压制与播放）中，必须严格调用真实的底层引擎。
   - **对于用户上传或系统已有真实素材（文件大小 > 10KB），严禁在发生错误或超时时静默回退到预置示范文字（如“自建五万平训练场”）或直接复制原文件假装合成成功！**
   - 真实链路失败时必须立即抛出真实异常或返回明确错误详情，如实反馈给用户并驱动定位，绝不允许以“成功”掩盖根本问题。
2. **模型真实性准则 (Truthful Model Identity)**：
   - 严禁在界面或配置中硬编码假模型名（如 `gpt-4o-mini`）。
   - 当前使用的模型必须 100% 动态读取自用户本地真实配置（`~/.codex/config.toml`），并在调用与界面展示中如实呈现（如 `glm-5.3-flash`）。
3. **测试代码隔离准则 (Test Isolation)**：
   - 测试专用的 Mock、假数据或快速桩函数仅允许存在于 `tests/` 目录中。
   - 生产代码（`backend/app/`）中不得为了让单测通过而向真实业务注入静默伪造数据的逻辑。
