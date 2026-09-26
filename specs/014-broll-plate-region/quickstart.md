# Quickstart & Verification Guide: 场地与教学空镜地区车牌标签管理与精准匹配 (014-broll-plate-region)

**Branch**: `014-broll-plate-region`  
**Date**: 2026-09-24  
**Spec Reference**: [specs/014-broll-plate-region/spec.md](file:///d:/project/video_cut/specs/014-broll-plate-region/spec.md)

---

## 1. 验证目标概览

本指南用于指导并在实施后验证三大核心业务场景：
1. **素材入库与原地改签**：场地/教学空镜能单选 11 地市，卡片呈现车牌徽章，可原地改签；
2. **ASR 自动地名推导**：口播视频转写后自动推导并绑定目标城市，免去人工切换；
3. **分镜绝对防穿帮**：无论单条初剪还是批量混剪，空镜严格只使用同城素材，异地车牌混入率为 0%。

---

## 2. 自动化测试套件 (Automated Test Suite)

执行以下测试命令验证数据模型、API 与调度引擎完整性：

```powershell
# 1. 运行地区字典与 ASR 城市推导测试
pytest tests/test_plate_region_deduction.py -v

# 2. 运行素材上传、导入与原地改签 API 测试
pytest tests/test_material_region_api.py -v

# 3. 运行分镜调度绝对防穿帮集成测试
pytest tests/test_scene_decision_plate_region.py -v
```

---

## 3. 手工端到端业务流转验证 (Manual E2E Walkthrough)

### 场景一：素材入库与标签治理验证

1. 启动前后端服务；
2. 导航至 `/upload`（素材库），点击“场地空镜”标签；
3. 检查上传控制栏是否呈现单选下拉框 `[ 浙E · 湖州 ▼ ]`，包含完整的 11 个地级市（浙A ~ 浙L）；
4. 选择 `浙E · 湖州`，导入一段场地空镜视频；
5. 检查素材卡片上是否渲染蓝色精致徽章 `浙E · 湖州`；
6. 点击卡片上的地区徽章，将其原地修改为 `浙A · 杭州`；
7. 刷新页面，验证该素材持久化显示为 `浙A · 杭州`。

### 场景二：ASR 全自动识别与 0 穿帮初剪验证

1. 准备一段提及“湖州长兴考场”的口播视频（或模拟 ASR 文本中包含“湖州长兴考场”）；
2. 确保素材库中拥有：
   - 素材 A：`venue` 分类，`plate_region: "浙A·杭州"`
   - 素材 B：`venue` 分类，`plate_region: "浙E·湖州"`
3. 点击“⚡ 智能初剪与纠偏”；
4. 初剪完成后，检查时间轴分镜详情：
   - 界面识别并显示 `🎯 目标城市: 浙E · 湖州`；
   - 检查所有被切入空镜的片段，其 `material_id` 必须严格指向素材 B（湖州），绝对不得出现素材 A（杭州）；
5. 验证成功：跨地市车牌穿帮率为 0%。
