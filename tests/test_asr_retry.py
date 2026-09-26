"""
MiniMax ASR 故障容错与指数退避重试测试 (013-system-resilience-ux: US2, FR-201)
测试目标：
1. 遇到 502/503/429/Timeout 等瞬时网络错误时，自动执行指数退避重试 (1s, 2s, 4s)，并在重试成功后返回正确结果。
2. 连续 3 次全部失败时，抛出真实异常，不再无限死循环。
3. 遇到 401/400 等非瞬时客户端错误时，不进行无意义重试，立即抛错。
"""
from pathlib import Path
import httpx
import pytest
from unittest.mock import patch, MagicMock

from app.native_engine.asr_runner import ASRRunner


@pytest.fixture
def dummy_audio_file(tmp_path):
    audio = tmp_path / "test_retry_audio.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 1000)
    return audio


def test_asr_retry_success_after_transient_failure(dummy_audio_file):
    runner = ASRRunner()
    
    mock_success_resp = MagicMock()
    mock_success_resp.status_code = 200
    mock_success_resp.json.return_value = {
        "text": "测试重试成功",
        "duration": 2.0,
        "segments": [
            {"text": "测试重试成功", "start": 0.0, "end": 2.0}
        ]
    }
    
    # 第一次 502 失败，第二次成功
    mock_fail_resp = MagicMock()
    mock_fail_resp.status_code = 502
    req = httpx.Request("POST", "https://api.minimaxi.com/v1/speech_to_text")
    fail_err = httpx.HTTPStatusError("502 Bad Gateway", request=req, response=mock_fail_resp)
    mock_fail_resp.raise_for_status.side_effect = fail_err

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_fail_resp
        return mock_success_resp

    with patch("httpx.post", side_effect=side_effect), \
         patch("time.sleep") as mock_sleep:
        results = runner.transcribe_minimax(
            audio_path=dummy_audio_file,
            api_key="test-key",
            base_url="https://api.minimaxi.com/v1"
        )
        assert call_count == 2
        assert mock_sleep.call_count == 1
        assert len(results) >= 1
        assert "测试重试成功" in results[0]["raw_text"]


def test_asr_retry_exhaustion_raises(dummy_audio_file):
    runner = ASRRunner()
    
    # 模拟 3 次全部超时
    with patch("httpx.post", side_effect=httpx.ConnectTimeout("Network timed out")), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(httpx.ConnectTimeout):
            runner.transcribe_minimax(
                audio_path=dummy_audio_file,
                api_key="test-key",
                base_url="https://api.minimaxi.com/v1"
            )
        assert mock_sleep.call_count == 2  # 重试 2 次（第 1 次后睡 1s，第 2 次后睡 2s，第 3 次抛出）


def test_asr_401_fails_immediately_without_retry(dummy_audio_file):
    runner = ASRRunner()
    
    mock_401_resp = MagicMock()
    mock_401_resp.status_code = 401
    req = httpx.Request("POST", "https://api.minimaxi.com/v1/speech_to_text")
    err_401 = httpx.HTTPStatusError("401 Unauthorized", request=req, response=mock_401_resp)
    mock_401_resp.raise_for_status.side_effect = err_401

    with patch("httpx.post", return_value=mock_401_resp), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(httpx.HTTPStatusError):
            runner.transcribe_minimax(
                audio_path=dummy_audio_file,
                api_key="invalid-key",
                base_url="https://api.minimaxi.com/v1"
            )
        assert mock_sleep.call_count == 0  # 401 严禁重试


def test_asr_retry_on_malformed_json_response(dummy_audio_file):
    """验证当网关返回非标准内容（如 HTML 或截断 JSON 导致 ValueError）时也能触发退避重试并恢复"""
    runner = ASRRunner()
    
    mock_bad_resp = MagicMock()
    mock_bad_resp.status_code = 200
    mock_bad_resp.json.side_effect = ValueError("Invalid JSON from proxy")
    
    mock_success_resp = MagicMock()
    mock_success_resp.status_code = 200
    mock_success_resp.json.return_value = {
        "text": "畸变后重试成功",
        "duration": 1.5,
        "segments": [{"text": "畸变后重试成功", "start": 0.0, "end": 1.5}]
    }

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_bad_resp
        return mock_success_resp

    with patch("httpx.post", side_effect=side_effect), \
         patch("time.sleep") as mock_sleep:
        results = runner.transcribe_minimax(
            audio_path=dummy_audio_file,
            api_key="test-key",
            base_url="https://api.minimaxi.com/v1"
        )
        assert call_count == 2
        assert mock_sleep.call_count == 1
        assert len(results) == 1
        assert results[0]["raw_text"] == "畸变后重试成功"


def test_asr_retry_on_remote_protocol_error(dummy_audio_file):
    """验证遇到 peer closed connection (httpx.RemoteProtocolError) 时自动指数退避重试"""
    import socket
    runner = ASRRunner()

    mock_success_resp = MagicMock()
    mock_success_resp.status_code = 200
    mock_success_resp.json.return_value = {
        "text": "断连重试恢复成功",
        "duration": 2.0,
        "segments": [{"text": "断连重试恢复成功", "start": 0.0, "end": 2.0}]
    }

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.RemoteProtocolError("peer closed connection without sending complete message body (incomplete chunked read)")
        return mock_success_resp

    with patch("httpx.post", side_effect=side_effect), \
         patch("time.sleep") as mock_sleep:
        results = runner.transcribe_minimax(
            audio_path=dummy_audio_file,
            api_key="test-key",
            base_url="https://api.minimaxi.com/v1"
        )
        assert call_count == 2
        assert mock_sleep.call_count == 1
        assert len(results) == 1
        assert results[0]["raw_text"] == "断连重试恢复成功"


def test_asr_retry_on_dns_gaierror(dummy_audio_file):
    """验证遇到 DNS 解析失败 [Errno 11001] getaddrinfo failed 时自动退避重试"""
    import socket
    runner = ASRRunner()

    mock_success_resp = MagicMock()
    mock_success_resp.status_code = 200
    mock_success_resp.json.return_value = {
        "text": "DNS抖动后恢复",
        "duration": 1.8,
        "segments": [{"text": "DNS抖动后恢复", "start": 0.0, "end": 1.8}]
    }

    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise socket.gaierror(11001, "getaddrinfo failed")
        return mock_success_resp

    with patch("httpx.post", side_effect=side_effect), \
         patch("time.sleep") as mock_sleep:
        results = runner.transcribe_minimax(
            audio_path=dummy_audio_file,
            api_key="test-key",
            base_url="https://api.minimaxi.com/v1"
        )
        assert call_count == 2
        assert mock_sleep.call_count == 1
        assert len(results) == 1
        assert results[0]["raw_text"] == "DNS抖动后恢复"

