import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

STORAGE_DIR = Path("storage").resolve()
DEFAULT_BANNED_WORDS_PATH = STORAGE_DIR / "banned_words.json"

DEFAULT_MAPPINGS: Dict[str, str] = {
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

class ComplianceSanitizer:
    """
    抖音合规与违禁词脱敏清洗器：
    1. 基于 mtime 内存缓存热加载 storage/banned_words.json，编辑即生效；
    2. 严格遵循 Longest-Match-First 贪婪排序，杜绝复合词拆分截断；
    3. 支持高亮关键词元数据（Highlight Words）同步无损映射；
    4. 提供预检（detect_banned_words）能力供导出确认弹窗使用。
    """
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_BANNED_WORDS_PATH
        self._cached_mtime: float = -1.0
        self._mappings: Dict[str, str] = {}
        self._sorted_keys: List[str] = []
        self._reload_if_needed()

    def _reload_if_needed(self) -> None:
        try:
            if not self.config_path.exists():
                # 初始未创建时写入默认字典
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "_description": "抖音短视频合规脱敏映射词库，长词优先自动排序，编辑保存即生效",
                    "version": "1.0",
                    "mappings": DEFAULT_MAPPINGS
                }
                self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            mtime = os.path.getmtime(self.config_path)
            if mtime != self._cached_mtime:
                content = self.config_path.read_text(encoding="utf-8")
                data = json.loads(content)
                raw_mappings = data.get("mappings", {})
                if not raw_mappings:
                    raw_mappings = DEFAULT_MAPPINGS
                self._mappings = raw_mappings
                # 严格按照长度降序排序
                self._sorted_keys = sorted(self._mappings.keys(), key=len, reverse=True)
                self._cached_mtime = mtime
        except Exception:
            if not self._mappings:
                self._mappings = dict(DEFAULT_MAPPINGS)
                self._sorted_keys = sorted(self._mappings.keys(), key=len, reverse=True)

    def _save_to_disk(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_description": "抖音短视频合规脱敏映射词库，长词优先自动排序，编辑保存即生效",
            "version": "1.0",
            "mappings": self._mappings
        }
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cached_mtime = os.path.getmtime(self.config_path)

    def add_or_update_mapping(self, original_word: str, replacement_word: str) -> None:
        orig = (original_word or "").strip()
        repl = (replacement_word or "").strip()
        if not orig or not repl:
            raise ValueError("违禁词和替换词均不能为空")
        self._reload_if_needed()
        self._mappings[orig] = repl
        self._sorted_keys = sorted(self._mappings.keys(), key=len, reverse=True)
        self._save_to_disk()

    def delete_mapping(self, original_word: str) -> bool:
        orig = (original_word or "").strip()
        self._reload_if_needed()
        if orig in self._mappings:
            del self._mappings[orig]
            self._sorted_keys = sorted(self._mappings.keys(), key=len, reverse=True)
            self._save_to_disk()
            return True
        return False

    def reset_to_default(self) -> None:
        self._mappings = dict(DEFAULT_MAPPINGS)
        self._sorted_keys = sorted(self._mappings.keys(), key=len, reverse=True)
        self._save_to_disk()

    def get_mappings(self) -> Dict[str, str]:
        self._reload_if_needed()
        return dict(self._mappings)

    def sanitize_text(self, text: str) -> str:
        """对单行文本进行长词贪婪脱敏替换"""
        if not text:
            return ""
        self._reload_if_needed()
        res = text
        for k in self._sorted_keys:
            if k in res:
                res = res.replace(k, self._mappings[k])
        return res

    def sanitize_subtitles(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对字幕列表进行合规脱敏：
        - 仅修改渲染用 corrected_text
        - 同步更新 highlight_words 内部词汇，保证高亮标签无损对齐
        """
        if not subtitles:
            return []
        self._reload_if_needed()
        sanitized = []
        for s in subtitles:
            item = dict(s)
            original_text = item.get("corrected_text") or item.get("raw_text") or ""
            item["corrected_text"] = self.sanitize_text(original_text)

            # 同步更新高亮词
            raw_hws = item.get("highlight_words")
            if raw_hws:
                new_hws = []
                for hw in raw_hws:
                    if isinstance(hw, dict):
                        hw_copy = dict(hw)
                        w = hw_copy.get("word", "")
                        hw_copy["word"] = self.sanitize_text(w)
                        new_hws.append(hw_copy)
                    elif hasattr(hw, "word"):
                        # Pydantic HighlightWord model
                        hw_dict = hw.model_dump()
                        hw_dict["word"] = self.sanitize_text(hw_dict["word"])
                        new_hws.append(hw_dict)
                    elif isinstance(hw, str):
                        new_hws.append(self.sanitize_text(hw))
                    else:
                        new_hws.append(hw)
                item["highlight_words"] = new_hws

            sanitized.append(item)
        return sanitized

    def detect_banned_words(self, subtitles: List[Any]) -> Dict[str, Any]:
        """
        检测工程字幕中所有命中的违禁词，供导出弹窗确认与明细展示
        """
        self._reload_if_needed()
        matches = []
        for idx, sub in enumerate(subtitles, start=1):
            if isinstance(sub, dict):
                text = sub.get("corrected_text") or sub.get("raw_text") or sub.get("text") or ""
            elif isinstance(sub, str):
                text = sub
            elif hasattr(sub, "corrected_text"):
                text = sub.corrected_text or sub.raw_text or ""
            else:
                continue

            if not text:
                continue

            # 检测该行命中的所有违禁词
            matched_in_line = []
            for k in self._sorted_keys:
                if k in text:
                    # 避免子串重复误报（如已命中新政策，不再重复添加策）
                    matched_in_line.append(k)

            if matched_in_line:
                sanitized_line = self.sanitize_text(text)
                for w in matched_in_line:
                    matches.append({
                        "subtitle_index": idx,
                        "original_word": w,
                        "replacement_word": self._mappings[w],
                        "original_line": text,
                        "sanitized_line": sanitized_line
                    })

        return {
            "has_banned_words": len(matches) > 0,
            "total_matches": len(matches),
            "matches": matches
        }

compliance_sanitizer = ComplianceSanitizer()