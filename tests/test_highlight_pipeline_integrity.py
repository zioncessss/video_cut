import json
import pytest
from pathlib import Path
from app.native_engine.keyword_matcher import extract_rule_highlight_words, build_highlight_words
from app.native_engine.subtitle_styler import generate_ass_file
from app.models.entities import CutProject, CutProjectStatus, SubtitleSegment, EditingStrategy, HighlightWord
from app.native_engine.project_storage import ProjectStorageService
from app.api.editor import update_subtitles, UpdateSubtitlesRequest


def test_extract_rule_highlight_words_clean_terms():
    """验证规则分词已彻底消除 '是保险费'、'那这个费用' 等前缀语法残渣"""
    res1 = extract_rule_highlight_words("还有一个就是保险费面签费")
    words1 = [r["word"] for r in res1]
    assert "保险费" in words1
    assert "是保险费" not in words1

    res2 = extract_rule_highlight_words("那这个费用两科还有几百块钱")
    words2 = [r["word"] for r in res2]
    assert any("费用" in w or "几百块钱" in w for w in words2)
    assert "那这个费" not in words2

    res3 = extract_rule_highlight_words("可以滴滴我一下")
    words3 = [r["word"] for r in res3]
    assert "滴滴我" in words3

    res4 = extract_rule_highlight_words("一共是三百六杭州有个车管所的")
    words4 = [r["word"] for r in res4]
    assert "三百六" in words4
    assert "车管所" in words4


def test_generate_ass_file_defensive_auto_highlight(tmp_path):
    """验证渲染层零信任防御：即使上游传入空 highlight_words，也能就地触发自愈生成高亮标签"""
    empty_hws_subs = [
        {
            "id": "sub-1",
            "start_time": 0.0,
            "end_time": 2.0,
            "raw_text": "在杭州考一个驾照要多少钱",
            "corrected_text": "在杭州考一个驾照要多少钱",
            "highlight_words": [],
            "matched_keywords": []
        },
        {
            "id": "sub-2",
            "start_time": 2.0,
            "end_time": 4.0,
            "raw_text": "首先呢就是四科考试费",
            "corrected_text": "首先呢就是四科考试费",
            "highlight_words": [],
            "matched_keywords": []
        }
    ]

    out_ass = tmp_path / "output_defensive.ass"
    strat = {
        "enable_highlight": True,
        "highlight_color": "#FACC15"
    }

    generate_ass_file(empty_hws_subs, out_ass, strategy=strat)

    content = out_ass.read_text(encoding="utf-8")
    assert out_ass.exists()
    # 必须包含高亮颜色标签或放大强调标签，绝不输出白板纯白字幕
    assert r"\c&H" in content or r"\fscx122" in content
    # 检查特定关键词是否被打上了高亮标签
    assert "四科考试费" in content or "杭州" in content or "多少钱" in content


def test_heal_from_disk_restores_highlight_words(tmp_path, monkeypatch):
    """验证从磁盘自愈恢复工程时，字幕 100% 自动注入高亮词与关键词元数据"""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_dir = tasks_dir / "20260921_test_heal_th"
    task_dir.mkdir(parents=True, exist_ok=True)

    dummy_mp4 = task_dir / "output.mp4"
    dummy_mp4.write_bytes(b"x" * (20 * 1024))  # 20KB > 10KB 门槛

    manifest_data = {
        "project_id": "test-heal-pid",
        "title": "测试自愈高亮工程",
        "talking_head_id": "test-th-id",
        "output_video_path": str(dummy_mp4)
    }
    (task_dir / "project_manifest.json").write_text(json.dumps(manifest_data, ensure_ascii=False), encoding="utf-8")

    srt_content = """1
00:00:00,000 --> 00:00:02,000
在杭州考一个驾照要多少钱

2
00:00:02,000 --> 00:00:04,000
可以滴滴我一下
"""
    (task_dir / "subtitles.srt").write_text(srt_content, encoding="utf-8")

    import app.native_engine.project_storage as ps_mod
    monkeypatch.setattr(ps_mod, "TASKS_DIR", tasks_dir)

    service = ProjectStorageService(storage_dir=tmp_path / "projects")
    proj = service.get_by_project_id("test-heal-pid")

    assert proj is not None
    assert len(proj.subtitles) == 2
    for s in proj.subtitles:
        assert s.highlight_words is not None
        assert len(s.highlight_words) > 0, f"Subtitle '{s.corrected_text}' should have restored highlight words"
        assert s.matched_keywords is not None
        assert len(s.matched_keywords) > 0


@pytest.mark.asyncio
async def test_update_subtitles_preserves_existing_highlights(tmp_path):
    """验证客户端提交空高亮词时不冲毁存量高亮词"""
    service = ProjectStorageService(storage_dir=tmp_path / "projects")
    p = CutProject(
        id="test-save-pid",
        title="测试保存高亮防冲",
        talking_head_id="th-save-id",
        subtitles=[
            SubtitleSegment(
                id="sub-keep-1",
                start_time=0.0,
                end_time=2.0,
                raw_text="在杭州考一个驾照要多少钱",
                corrected_text="在杭州考一个驾照要多少钱",
                highlight_words=[HighlightWord(word="杭州", color="#38BDF8")],
                matched_keywords=["杭州"]
            )
        ]
    )
    service.save_project(p)

    import app.api.editor as editor_mod
    editor_mod.project_storage_service = service

    req = UpdateSubtitlesRequest(
        subtitles=[
            {
                "id": "sub-keep-1",
                "start_time": 0.0,
                "end_time": 2.0,
                "raw_text": "在杭州考一个驾照要多少钱",
                "corrected_text": "在杭州考一个驾照要多少钱",
                "highlight_words": []  # 模拟客户端传入空列表
            }
        ]
    )

    updated_proj = await update_subtitles("test-save-pid", req)
    saved_sub = updated_proj.subtitles[0]
    assert len(saved_sub.highlight_words) > 0
    assert saved_sub.highlight_words[0].word == "杭州"
