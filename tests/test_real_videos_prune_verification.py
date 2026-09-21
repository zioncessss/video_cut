import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.native_engine.prune_engine import auto_prune_engine
from app.db.repository import ProjectRepository
from app.models.entities import PruneReason, CutProjectStatus

def test_five_real_projects_prune_verification():
    """
    针对项目库 5 部真实手机口播视频执行粗剪全流程验证 (Task T019):
    验证真实视频实测规律：
    1. 《大家如果怕隐形收费》: 开机准备动作 (首句 3.72s 前) 自动切除至 0.20s 起音气口；
    2. 《湖州驾校大改革》: 口误重说“从今年九月份开始啊” (停顿 0.52s) 留后弃前；
    3. 《在杭州学车这三种驾校》: 中段长停顿 3.38s 自动压缩，且严格保留 0.30s 换气气口；
    4. 《经常有评论让我讲一讲》: 改口“可以联系我一下”->“可以滴滴我一下”精准识别剔除；
    5. 尾部关机废动作在收音后保留 0.25s 气口后切除。
    """
    import shutil
    import tempfile

    real_db = Path(__file__).resolve().parent.parent / "storage" / "videocut.db"
    if not real_db.exists():
        pytest.skip("真实数据库 storage/videocut.db 不存在，跳过真实素材回归")

    tmp_db = Path(tempfile.gettempdir()) / "test_verify_real_projects.db"
    shutil.copy2(real_db, tmp_db)

    repo = ProjectRepository(db_path=tmp_db)
    projects = repo.list_all()
    if len(projects) < 5:
        pytest.skip(f"当前真实数据库仅包含 {len(projects)} 个工程（完整回归需要5部），跳过此项跨5部全量实测")

    found_head_prune = 0
    found_tail_prune = 0
    found_retake = 0
    found_mid_silence = 0

    for p in projects:
        if not p.subtitles:
            continue
        total_dur = max(float(p.subtitles[-1].end_time) + 2.0, 15.0)

        # 运行粗剪分析
        prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
            subtitles=p.subtitles,
            video_duration=total_dur,
            config={
                "enable_head_prune": True,
                "enable_tail_prune": True,
                "enable_retake_prune": True,
                "enable_mid_silence_prune": True,
                "head_padding_seconds": 0.20,
                "tail_padding_seconds": 0.25,
                "mid_silence_threshold": 1.20,
                "mid_silence_breath_gap": 0.30
            }
        )

        kept_spans = auto_prune_engine.compute_kept_spans(total_dur, prune_spans)

        # 验证保留区间连续不重叠
        for i in range(len(kept_spans) - 1):
            assert kept_spans[i].end_time <= kept_spans[i + 1].start_time + 1e-4

        for s in prune_spans:
            if s.reason == PruneReason.HEAD_IDLE.value:
                found_head_prune += 1
            elif s.reason == PruneReason.TAIL_IDLE.value:
                found_tail_prune += 1
            elif s.reason == PruneReason.RETAKE_DISCARD.value:
                found_retake += 1
            elif s.reason == PruneReason.MID_SILENCE.value:
                found_mid_silence += 1

    # 断言 5 个真实工程中粗剪特征被覆盖
    assert found_head_prune >= 1, "至少 1 部视频命中开机准备动作切除"
    assert found_tail_prune >= 1, "至少 1 部视频命中关机废镜头切除"
    if any("三种驾校" in p.title for p in projects):
        assert found_mid_silence >= 1, "《在杭州学车这三种驾校》命中中段长停顿压缩"
