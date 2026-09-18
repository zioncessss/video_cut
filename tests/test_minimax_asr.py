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
