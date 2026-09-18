import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.native_engine.asr_runner import asr_runner
from app.core import config

SAMPLE_MINIMAX_STT_RESPONSE = {
    "text": "从今年九月份开始，杭州驾校迎来了大改革。",
    "duration": 4.2,
    "n_speakers": 1,
    "segments": [
        {"id": 0, "start": 0.52, "end": 0.78, "speaker": "S1", "text": "从"},
        {"id": 1, "start": 0.78, "end": 0.94, "speaker": "S1", "text": "今"},
        {"id": 2, "start": 0.94, "end": 1.12, "speaker": "S1", "text": "年"},
        {"id": 3, "start": 1.12, "end": 1.30, "speaker": "S1", "text": "九"},
        {"id": 4, "start": 1.30, "end": 1.48, "speaker": "S1", "text": "月"},
        {"id": 5, "start": 1.48, "end": 1.66, "speaker": "S1", "text": "份"},
        {"id": 6, "start": 1.66, "end": 1.94, "speaker": "S1", "text": "开"},
        {"id": 7, "start": 1.94, "end": 2.20, "speaker": "S1", "text": "始"},
        {"id": 8, "start": 2.20, "end": 2.30, "speaker": "S1", "text": "，"},
        # 停顿 gap = 2.80 - 2.30 = 0.50s > 0.28s
        {"id": 9, "start": 2.80, "end": 3.02, "speaker": "S1", "text": "杭"},
        {"id": 10, "start": 3.02, "end": 3.20, "speaker": "S1", "text": "州"},
        {"id": 11, "start": 3.20, "end": 3.38, "speaker": "S1", "text": "驾"},
        {"id": 12, "start": 3.38, "end": 3.56, "speaker": "S1", "text": "校"},
        {"id": 13, "start": 3.56, "end": 3.74, "speaker": "S1", "text": "迎"},
        {"id": 14, "start": 3.74, "end": 3.90, "speaker": "S1", "text": "来"},
        {"id": 15, "start": 3.90, "end": 4.02, "speaker": "S1", "text": "了"},
        {"id": 16, "start": 4.02, "end": 4.10, "speaker": "S1", "text": "大"},
        {"id": 17, "start": 4.10, "end": 4.20, "speaker": "S1", "text": "改"},
        {"id": 18, "start": 4.20, "end": 4.35, "speaker": "S1", "text": "革"},
        {"id": 19, "start": 4.35, "end": 4.40, "speaker": "S1", "text": "。"}
    ],
    "trace_id": "test_trace_12345"
}

def test_parse_minimax_response():
    """测试 MiniMax 逐字 segments 映射为系统标准的 words 与句子分段"""
    raw_segments = asr_runner.parse_minimax_response(SAMPLE_MINIMAX_STT_RESPONSE)
    assert len(raw_segments) >= 2, "根据标点与静音停顿应切出至少两句"

    first_seg = raw_segments[0]
    assert "从今年九月份开始" in first_seg["raw_text"]
    assert first_seg["start_time"] == 0.52
    assert first_seg["end_time"] >= 2.20
    assert len(first_seg["words"]) > 0
    assert first_seg["words"][0]["word"] == "从"
    assert first_seg["words"][0]["start"] == 0.52

    second_seg = raw_segments[1]
    assert "杭州驾校迎来了大改革" in second_seg["raw_text"]
    assert second_seg["start_time"] >= 2.70
    assert len(second_seg["words"]) > 0

def test_minimax_words_with_golden_chunking():
    """测试 MiniMax 的 words 字级时间戳经 split_into_readable_segments 进行黄金意群切分"""
    raw_segments = asr_runner.parse_minimax_response(SAMPLE_MINIMAX_STT_RESPONSE)
    chunked = asr_runner.split_into_readable_segments(raw_segments, max_chars=12)

    assert len(chunked) >= 2
    for seg in chunked:
        assert len(seg["raw_text"]) <= 14
        assert "words" in seg
        assert seg["start_time"] < seg["end_time"]

def test_transcribe_minimax_success(tmp_path):
    """测试 transcribe_minimax 正常请求与解析"""
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(b"RIFF" + b"\x00" * 100)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_MINIMAX_STT_RESPONSE
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        segments = asr_runner.transcribe_minimax(dummy_wav, api_key="test-key", base_url="https://api.minimaxi.com/v1")
        assert len(segments) >= 2
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert "https://api.minimaxi.com/v1/speech_to_text" in args[0]
        assert kwargs["data"]["model"] == "asr-1.0"
        assert kwargs["data"]["response_format"] == "verbose_json"
        assert kwargs["data"]["timestamp_level"] == "word"

def test_transcribe_minimax_auth_error(tmp_path):
    """测试 MiniMax 401 报错时抛出异常以便上层降级"""
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(b"RIFF" + b"\x00" * 100)

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp)

    with patch("httpx.post", return_value=mock_resp):
        with pytest.raises(Exception):
            asr_runner.transcribe_minimax(dummy_wav, api_key="invalid-key")

def test_transcribe_fallback_to_local_on_cloud_failure(tmp_path):
    """测试当云端 ASR 异常（如超时或 500）时，transcribe 自动降级为本地转写"""
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"0" * 20000)  # > 10KB 模拟真实文件

    with patch.object(asr_runner, "extract_audio", return_value=True), \
         patch.object(asr_runner, "transcribe_minimax", side_effect=httpx.TimeoutException("Read timed out")), \
         patch.object(asr_runner, "_transcribe_local", return_value=[
             {"start_time": 0.0, "end_time": 2.0, "raw_text": "本地转写成功", "corrected_text": "本地转写成功"}
         ]) as mock_local, \
         patch("app.core.config.ASR_PROVIDER", "minimax"), \
         patch("app.core.config.get_minimax_api_key", return_value="sk-test-key"):
        
        segments = asr_runner.transcribe(dummy_video)
        assert len(segments) == 1
        assert segments[0]["raw_text"] == "本地转写成功"
        assert mock_local.called

def test_transcribe_direct_local_when_provider_is_local(tmp_path):
    """测试当 asr_provider 配置为 local 时，直接调用本地识别，不发起网络请求"""
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"0" * 20000)

    with patch.object(asr_runner, "extract_audio", return_value=True), \
         patch.object(asr_runner, "transcribe_minimax") as mock_minimax, \
         patch.object(asr_runner, "_transcribe_local", return_value=[
             {"start_time": 0.0, "end_time": 2.0, "raw_text": "本地优先识别", "corrected_text": "本地优先识别"}
         ]) as mock_local, \
         patch("app.core.config.ASR_PROVIDER", "local"):
        
        segments = asr_runner.transcribe(dummy_video)
        assert len(segments) == 1
        assert segments[0]["raw_text"] == "本地优先识别"
        assert not mock_minimax.called
        assert mock_local.called

def test_trailing_punctuation_and_no_word_chopping():
    """测试词尾附带标点（如 '要报。'）被正确识别并剥离标点，触发分句且词中不含标点"""
    sample_response = {
        "text": "千万不要报。我是小陈在杭州教车。",
        "duration": 5.0,
        "segments": [
            {"id": 0, "start": 0.1, "end": 0.3, "text": "千"},
            {"id": 1, "start": 0.3, "end": 0.5, "text": "万"},
            {"id": 2, "start": 0.5, "end": 0.7, "text": "不"},
            {"id": 3, "start": 0.7, "end": 1.0, "text": "要"},
            {"id": 4, "start": 1.0, "end": 1.3, "text": "报。"}, # 词尾附带句号
            {"id": 5, "start": 1.5, "end": 1.7, "text": "我"},
            {"id": 6, "start": 1.7, "end": 1.9, "text": "是"},
            {"id": 7, "start": 1.9, "end": 2.1, "text": "小"},
            {"id": 8, "start": 2.1, "end": 2.3, "text": "陈"},
            {"id": 9, "start": 2.3, "end": 2.5, "text": "在"},
            {"id": 10, "start": 2.5, "end": 2.7, "text": "杭"},
            {"id": 11, "start": 2.7, "end": 2.9, "text": "州"},
            {"id": 12, "start": 2.9, "end": 3.1, "text": "教"},
            {"id": 13, "start": 3.1, "end": 3.3, "text": "车。"}
        ]
    }
    raw_segments = asr_runner.parse_minimax_response(sample_response)
    assert len(raw_segments) == 2, f"应该以句号断为2句，实际切分了 {len(raw_segments)} 句"
    assert raw_segments[0]["raw_text"] == "千万不要报"
    assert raw_segments[1]["raw_text"] == "我是小陈在杭州教车"
    # 验证 words 中的物理词不带尾随标点
    for seg in raw_segments:
        for w in seg["words"]:
            assert not any(p in w["word"] for p in "，。？！,!?"), f"物理词单元不应含标点: {w['word']}"

def test_natural_clause_elastic_merging():
    """测试 15~18 字完整意群设问句不被机械 14 字腰斩"""
    long_clause = [{
        "id": "seg_0",
        "start_time": 0.0,
        "end_time": 3.2,
        "raw_text": "就知道现在很多踩坑的原因是什么",
        "corrected_text": "就知道现在很多踩坑的原因是什么",
        "words": [
            {"word": "就", "start": 0.0, "end": 0.2},
            {"word": "知", "start": 0.2, "end": 0.4},
            {"word": "道", "start": 0.4, "end": 0.6},
            {"word": "现", "start": 0.6, "end": 0.8},
            {"word": "在", "start": 0.8, "end": 1.0},
            {"word": "很", "start": 1.0, "end": 1.2},
            {"word": "多", "start": 1.2, "end": 1.4},
            {"word": "踩", "start": 1.4, "end": 1.6},
            {"word": "坑", "start": 1.6, "end": 1.8},
            {"word": "的", "start": 1.8, "end": 2.0},
            {"word": "原", "start": 2.0, "end": 2.2},
            {"word": "因", "start": 2.2, "end": 2.4},
            {"word": "是", "start": 2.4, "end": 2.6},
            {"word": "什", "start": 2.6, "end": 2.8},
            {"word": "么", "start": 2.8, "end": 3.1}
        ]
    }]
    # 采用 8~18 字弹性单行
    chunked = asr_runner.split_into_readable_segments(long_clause, max_chars=18)
    assert len(chunked) == 1, "15字完整设问句不应被机械切开"
    assert chunked[0]["raw_text"] == "就知道现在很多踩坑的原因是什么"

def test_micro_segment_absorption():
    """测试极短碎片词（如 '第一个' 0.46s）能被吸附进相邻句子，不会成为孤立走马灯碎词"""
    micro_segments = [
        {
            "id": "s1",
            "start_time": 0.0,
            "end_time": 0.46,
            "raw_text": "第一个",
            "corrected_text": "第一个"
        },
        {
            "id": "s2",
            "start_time": 0.60,
            "end_time": 2.50,
            "raw_text": "就是低价引流套路",
            "corrected_text": "就是低价引流套路"
        }
    ]
    merged = asr_runner.merge_short_segments(micro_segments, max_chars=18, min_chars=4, min_duration=1.0)
    assert len(merged) == 1, f"0.46s 极短片段应被吸附，当前切成了 {len(merged)} 句"
    assert "第一个就是低价引流套路" in merged[0]["raw_text"]
