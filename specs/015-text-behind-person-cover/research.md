# Research & Architecture Decisions: 015-text-behind-person-cover

## 1. 核心需求与视觉解构

根据参考爆款视频号/小红书/抖音同城驾校封面（兔牙教练同款），提炼出 4 个不可或缺的视觉要素：
1. **空间层级（Z-Index / Depth of Field）**：大字在人像后方穿插，人物头顶墨镜和头发自然压住文字下方边缘。
2. **人像白光贴纸感（Sticker White Glow）**：人物外轮廓带有一圈 8~14px 的纯白高光外沿，将主体从复杂实景背景强力抽离。
3. **彩虹拱形与逐字独立凹凸（Non-flat Arched Glyph Sticker）**：
   - 顶部主标如“杭州学车”呈彩虹拱形向上弯曲，两端字符外倾，中间字符抬高。
   - 逐字独立拥有描边，描边严格贴合笔画起伏（如“学”字头上三点形成三个波浪小山丘），杜绝整行字死板黏连为一整块矩形底板。
4. **经典高反差爆款调色**：
   - 主标：纯白字芯 + 皇家宝蓝厚描边（#1650CC） + 纯白外边。
   - 转化大字：高饱和柠檬亮黄（#FFEE0A） + 皇家宝蓝厚描边。

---

## 2. GitHub 5k+ ⭐ 项目（RexanWONG/text-behind-image）源码解构与复用分析

已将官方发行源码下载至本地目录：`specs/015-text-behind-person-cover/vendor_reference/package/`。通过对 `index.js`、`backgroundRemoval.js`、`textRendering.js` 的逐行研读，形成以下复用与改造决策矩阵：

### 2.1 100% 可直接复用模块 (Direct Reuse)
1. **Canvas 三层绘制时序管线 (`index.js:38-43`)**：
   - 底层绘制：`ctx.drawImage(img, 0, 0)`
   - 中层渲染文字：`addTextToCanvas(ctx, textSettings)`
   - 顶层覆盖主体：`ctx.drawImage(bgRemovedCanvas, 0, 0)`
   - 这套核心生命周期已被工业界几千项目验证，结构清晰精炼，可直接复用该绘制时序。
2. **Mask 蒙版高速混合 (`backgroundRemoval.js:27-28`)**：
   - 采用原生 Canvas API：`ctx.globalCompositeOperation = 'destination-in'` 进行 Alpha 蒙版通道切割。
   - 零第三方绘图库依赖，浏览器 GPU 原生加速。
3. **文字参数控制矩阵 (`textRendering.js:4-16`)**：
   - `fontSize, color, position, alignment, rotation, shadowColor, shadowBlur, strokeColor, strokeWidth, letterSpacing` 参数规范成熟，可直接继承。

### 2.2 必须针对本项目深度改造与增强的模块 (Adapted / Enhanced)

| 维度 | RexanWONG 原始实现 | 本项目专属改造方案（为什么改） |
| :--- | :--- | :--- |
| **抠图后端供给** | 前端浏览器请求 `@imgly/background-removal` 下载 ~40MB WASM 模型（内网或断网易失败） | **本地毫秒级离线协同**：后端基于已验证的本地视觉管线（GrabCut / RemBG 离线快速产出透明 PNG），前端直接通过 `new Image().src = personUrl` 加载，0 网络消耗、0 外部依赖。 |
| **文字排版形态** | 纯线性水平排列（`y = i * fontSize * lineHeight`，极其呆板平整） | **彩虹拱形自适应算法**：按正弦/抛物线计算字符偏转角 $\theta_i$ 与抬升量 $\Delta y_i$，中间抬高、两端外倾，完美环抱人物头顶。 |
| **描边与贴纸凹凸** | 仅单层简单 stroke，字与字之间无起伏感 | **逐字独立气泡贴纸**：每个字独立两层膨胀（字芯 → 宝蓝厚边 → 纯白外边），严格贴合笔画边缘，凹凸分明。 |
| **人物贴纸白光** | 无白光，人物直接盖在文字上，杂乱背景下缺乏立体感 | **人物白光贴纸层**：利用 `ctx.shadowColor = '#FFFFFF'; ctx.shadowBlur = 12` 预先绘制人物白色发光边缘，再绘制主体。 |
| **第四层转化层** | 仅有 3 层结构（无前景互动信息） | **扩展第四层（Layer 3）**：胸前斜角圆角卡片“避坑课” + 底部柠檬黄转化大字“2980全公开”。 |

---

## 3. 架构设计与向后兼容考量

- 模板 ID 命名为 `text_behind_person`（人后拱形 3D 穿插款），作为系统第 7 大实战模板。
- 原有的 6 大模板（`sticker_double_stroke`、`split_contrast_bar`、`rainbow_arc_header` 等）逻辑与测试完全保留，保证存量工程 100% 正常打开与渲染。
- 后端 `cover_generator.py` 同步增加 `text_behind_person` 渲染分支，保证前端导出成片时第一帧像素级 1:1 镜像一致。
