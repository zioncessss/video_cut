# Specification Quality Checklist: 导出弹窗交互与即时预览体验 (Export Modal UX & Live Preview)

**Purpose**: Validate specification completeness, clarity, and consistency for the video cover export workflow before implementation  
**Created**: 2026-09-21  
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)  
**Domain**: Export UX, Live Preview & Image Selection  
**Audience**: PR Reviewer & Feature Author  

---

## 1. 需求完备性 (Requirement Completeness)

- [x] CHK001 是否完整定义了导出确认弹窗（`ExportConfirmModal`）内封面选择区的整体版式、弹窗宽高比例及与既有违禁词预检区的布局关系？ [Completeness, Spec §FR-001]
- [x] CHK002 是否明确规定了候选帧缩略图的显示数量、尺寸比例（9:16）及在弹窗内的滑动/排布规范？ [Completeness, Spec §FR-002]
- [x] CHK003 是否对 4 大口播模板（`gold_bold`, `color_badge`, `dual_contrast`, `clean_editorial`）的排版结构、字号层级、底块衬色及文字行间距进行了详尽规范？ [Completeness, Spec §FR-003]
- [x] CHK004 是否枚举了模板支持的所有预置配色方案及其对应的十六进制色值代码？ [Completeness, Spec §FR-004]
- [x] CHK005 是否清晰定义了 AI 伴随提炼标题在导出弹窗内的呈现样式与“一键点击替换文本”的交互触发机制？ [Completeness, Spec §FR-005]
- [x] CHK006 是否明确了点击“打开文件夹选择封面”后调用系统文件选择器时支持的文件类型白名单（JPG/PNG/WebP）？ [Completeness, Spec §FR-006]

---

## 2. 需求明确性与无歧义性 (Requirement Clarity)

- [x] CHK007 需求中“各个封面的效果可以预览”是否明确量化了客户端渲染技术（Canvas/SVG）与毫秒级延迟阈值（<50ms）？ [Clarity, Spec §SC-002]
- [x] CHK008 平台安全区视框需求是否以明确的百分比或数学比例精确量化了抖音避让区与小红书 3:4 居中视框，而非主观模糊描述？ [Clarity, Spec §FR-007]
- [x] CHK009 “打开文件夹选择封面”的交互行为是否明确指代调用原生系统文件对话框，还是浏览项目内部素材目录？ [Clarity, User Request & Spec §FR-006]
- [x] CHK010 自定义图片上传后的画幅比例适配模式默认值（`blur_padding`）及与居中裁切（`center_crop`）的切换形式是否具有唯一确定定义？ [Clarity, Spec §FR-010]
- [x] CHK011 模板卡片处于选中态（Active/Selected）与未选中态的边框高亮、徽章与视觉反馈是否具备无歧义的说明？ [Clarity, Spec §FR-003]

---

## 3. 需求一致性与冲突防范 (Requirement Consistency)

- [x] CHK012 导出弹窗中的封面操作卡片与既有抖音违禁词合规检查卡片在视觉设计语言（Clean Light Mode、圆角、阴影）上是否保持严格一致？ [Consistency, Spec §FR-001, Plan §Structure]
- [x] CHK013 前端 Canvas 客户端预览渲染的文字自适应折行逻辑是否与后端 Pillow 高清合成的折行计算保持 100% 规则对齐？ [Consistency, Spec §FR-004, Plan §Phase 0]
- [x] CHK014 当用户从“自定义上传图片”重新切换回“视频抽帧”时，状态流转与历史配置保留逻辑是否在数据模型中一致定义？ [Consistency, Spec §Key Entities]

---

## 4. 可度量性与验收准则质量 (Acceptance Criteria & Measurability)

- [x] CHK015 “模板切换与文字实时预览在客户端渲染延迟低于 50 毫秒”是否具备不依赖主观感知的自动化度量手段？ [Measurability, Spec §SC-002]
- [x] CHK016 “用户从打开导出弹窗到完成封面确认导出全流程在 30 秒内完成”是否有明确的起始事件与结束动作边界界定？ [Measurability, Spec §SC-001]
- [x] CHK017 针对任意比例（16:9, 1:1, 4:3）上传图片自适应成功率达到 100% 的验收指标，是否规定了量化的长宽比与无变形校验方法？ [Measurability, Spec §SC-005]

---

## 5. 场景与异常覆盖度 (Scenario & Edge Case Coverage)

- [x] CHK018 是否明确定义了用户通过文件夹选择器上传了超大（>15MB）或损坏图片文件时的即时错误拦截与 Toast 提示规范？ [Edge Case, Spec §Edge Cases]
- [x] CHK019 打开导出弹窗并异步抓取视频候选帧时，界面是否定义了优雅的骨架屏（Skeleton）或加载占位反馈？ [Coverage, Spec §FR-002]
- [x] CHK020 当离线或大模型未返回封面标题文案时，弹窗候选标题区是否定义了确定性的兜底提示与预设文案呈现？ [Edge Case, Spec §Edge Cases]
- [x] CHK021 当用户输入超长标题（超过 20 汉字）时，预览区是否明确规定了字体自动等比缩小还是溢出省略规范？ [Edge Case, Spec §Edge Cases]
- [x] CHK022 是否明确规范了用户关闭/取消导出弹窗时，当前草稿态的封面微调配置是就地放弃回滚还是自动暂存？ [Coverage, Gap]

---

## 6. 平台无障碍与响应式交互 (Non-Functional & Responsive UX)

- [x] CHK023 是否为导出弹窗内的模板切换与确认导出按钮定义了键盘快捷交互（如 Enter 确认、Esc 退出）支持？ [Non-Functional, Gap]
- [x] CHK024 在常见低分辨率笔记本屏幕（如 1366x768）环境下，导出弹窗内纵向 9:16 封面大图与控制选项是否定义了自适应防溢出滚动策略？ [Non-Functional, Gap]
- [x] CHK025 界面是否严格符合项目宪章规定的 Clean Light Mode 规范，杜绝低对比度灰色与刺眼纯白底色冲突？ [Non-Functional, Constitution Principle I]
