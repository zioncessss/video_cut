# Data Model: 抖音平台违禁词字幕合规清洗与多策略脱敏管线

**Feature**: `011-douyin-banned-words`
**Date**: 2026-09-21

## 1. 核心实体定义

### 1.1 违禁词配置集合 (`BannedWordsConfig`)
存储在 `storage/banned_words.json` 中的权威字典：

```json
{
  "_description": "抖音短视频合规脱敏映射词库，长词优先自动排序，编辑保存即生效",
  "version": "1.0",
  "mappings": {
    "新政策": "新正攵朿",
    "快至35天": "忄夬至35天",
    "驾驶证": "加驶正",
    "身份证": "身分正",
    "评论区": "平沦区",
    "绿泡泡": "菉泡泡",
    "最低": "蕞低",
    "最快": "蕞快",
    "特惠": "待惠",
    "优惠": "尤惠",
    "价格": "阶格",
    "很快": "很忄夬",
    "便宜": "便冝",
    "私信": "俬信",
    "学费": "学弗",
    "驾照": "贺照",
    "关注": "关主",
    "改革": "改草",
    "绝对": "决对",
    "体检": "体脸",
    "费用": "弗用",
    "评论": "平沦",
    "最": "蕞",
    "钱": "銭",
    "骗": "马扁",
    "费": "弗"
  }
}
```

- **字段说明**:
  - `mappings`: 敏感原词到形似字的映射字典。在内存载入时自动按字符串长度降序排序。

---

### 1.2 剪辑策略实体扩展 (`StrategyConfig`)
扩展现有 `backend/app/models/project.py` 中的 `StrategyConfig` 模型：

```python
class StrategyConfig(BaseModel):
    # ... 现有字段 (subtitle_theme, font_size, video_speed, etc.)
    
    # 违禁词合规处理配置
    banned_words_enabled: bool = Field(default=True, description="是否启用违禁词合规脱敏")
    banned_words_mode: str = Field(default="glyph", description="脱敏模式: glyph(形似拆字), redact(删除), pinyin(拼音缩写)")
```

---

### 1.3 导出预检匹配项实体 (`BannedWordCheckResult`)

```python
class BannedWordMatch(BaseModel):
    subtitle_index: int = Field(..., description="字幕行索引")
    original_word: str = Field(..., description="命中的原始违禁词")
    replacement_word: str = Field(..., description="替换后的形似字")
    original_line: str = Field(..., description="原字幕整句")
    sanitized_line: str = Field(..., description="脱敏后整句")

class BannedWordCheckResponse(BaseModel):
    project_id: str
    has_banned_words: bool = Field(..., description="当前工程字幕是否包含违禁词")
    total_matches: int = Field(..., description="命中的违禁词总次数")
    matches: List[BannedWordMatch] = Field(default_factory=list, description="命中明细列表")
```

---

### 1.4 渲染字幕实体数据流转换 (`RenderSubtitleTransform`)

```text
Database: SubtitleRow
  corrected_text: "在杭州考一个驾照要多少钱"
  highlight_words_json: [{"word": "多少钱", "color": "#EF4444"}]
       │
       ▼ (ComplianceSanitizer.sanitize_subtitles)
Memory Render Item:
  corrected_text: "在杭州考一个贺照要多少銭"
  highlight_words: [{"word": "多少銭", "color": "#EF4444"}]
       │
       ▼ (generate_ass_file)
ASS Output Event:
  Dialogue: ...{\an5\pos(540,1420)}在杭州考一个贺照要{\c&H004444EF&}多少銭{\r}
```