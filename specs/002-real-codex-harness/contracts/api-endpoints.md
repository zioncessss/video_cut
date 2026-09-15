# API 契约协议: 真实 Codex 引擎与工作台接口

## 1. POST /api/settings/test-harness
测试选定 Harness（尤其是 Codex CLI）的可用性、连通性及延时。

### Request
```json
{
  "engine": "codex",
  "model_override": "glm-5.3-flash"
}
```

### Response (Success)
```json
{
  "code": 0,
  "data": {
    "success": true,
    "engine": "codex",
    "active_model": "glm-5.3-flash",
    "latency_ms": 2840,
    "message": "Codex CLI 连通正常，探针检测通过"
  }
}
```

---

## 2. POST /api/editor/correct
利用 Codex CLI 大模型对传入字幕进行全量专有词纠偏。

### Request
```json
{
  "subtitles": [
    {
      "id": "sub-1",
      "start_time": 0.0,
      "end_time": 3.2,
      "raw_text": "欢迎来到我们科尔训练场",
      "corrected_text": "欢迎来到我们科尔训练场"
    }
  ],
  "domain": "driving_school"
}
```

### Response (Success)
```json
{
  "code": 0,
  "data": {
    "subtitles": [
      {
        "id": "sub-1",
        "start_time": 0.0,
        "end_time": 3.2,
        "raw_text": "欢迎来到我们科尔训练场",
        "corrected_text": "欢迎来到我们科目二训练场",
        "is_corrected": true
      }
    ],
    "corrections": [
      {
        "subtitle_id": "sub-1",
        "original_text": "科尔",
        "corrected_text": "科目二",
        "reason": "驾考专有名词同音纠错"
      }
    ],
    "harness_engine_used": "codex",
    "latency_ms": 3120
  }
}
```

---

## 3. POST /api/instruction/apply
利用 Codex CLI 解析全能自然语言微调指令，动态更新字幕文案、时间轴或空镜素材关联。

### Request
```json
{
  "instruction": "把第一句改得更有激情一点，第二句的空镜换成体检素材",
  "current_subtitles": [...],
  "current_brolls": [...],
  "available_materials": [...]
}
```

### Response (Success)
```json
{
  "code": 0,
  "message": "自然语言微调应用成功",
  "data": {
    "explanation": "已将第一句开场白润色为激动昂扬口吻，并将第二句关联的空镜素材替换为体检分类素材",
    "updated_subtitles": [...],
    "updated_brolls": [...],
    "harness_engine_used": "codex",
    "latency_ms": 3450
  }
}
```