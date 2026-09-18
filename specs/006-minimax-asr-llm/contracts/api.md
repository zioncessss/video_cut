# Interface Contracts: MiniMax 统一接管 ASR 与智能剪辑 (006-minimax-asr-llm)

## 1. 外部 MiniMax 云端接口契约 (External MiniMax APIs)

### 1.1 极速语音转文字 (Speech to Text)
- **Method**: `POST`
- **URL**: `https://api.minimaxi.com/v1/speech_to_text`
- **Headers**:
  ```http
  Authorization: Bearer <MINIMAX_API_KEY>
  Content-Type: multipart/form-data
  ```
- **Form Data**:
  - `file`: 16kHz PCM 单声道 WAV 二进制流
  - `model`: `"asr-1.0"`
  - `response_format`: `"verbose_json"`
  - `timestamp_level`: `"word"`
  - `stream`: `false`
- **Response 200 OK**:
  ```json
  {
    "text": "从今年九月份开始，杭州驾校迎来了大改革。",
    "duration": 4.2,
    "n_speakers": 1,
    "segments": [
      { "id": 0, "start": 0.52, "end": 0.78, "speaker": "S1", "text": "从" },
      { "id": 1, "start": 0.78, "end": 0.94, "speaker": "S1", "text": "今" },
      { "id": 2, "start": 0.94, "end": 1.12, "speaker": "S1", "text": "年" }
    ],
    "trace_id": "06fbfc8060138b7665f0a7ada8404866"
  }
  ```

### 1.2 大模型智能分镜决策 (Chat Completions - 稀疏指示清单契约)
- **Method**: `POST`
- **URL**: `https://api.minimaxi.com/v1/chat/completions`
- **Headers**:
  ```http
  Authorization: Bearer <MINIMAX_API_KEY>
  Content-Type: application/json
  ```
- **Payload**:
  ```json
  {
    "model": "MiniMax-Text-01",
    "messages": [
      {
        "role": "system",
        "content": "你是短视频智能剪辑导演。你的任务是通读全片口播文字与时间戳，识别与【场地(venue) / 练车(lesson) / 流程体验(experience)】强相关的场景，仅输出建议切入空镜的区间列表。普通段落不要输出，严禁逐句填空。输出严格JSON。"
      },
      {
        "role": "user",
        "content": "【时间线字幕】：[{\"start\": 1.6, \"end\": 4.2, \"text\": \"...\"}, ...]\n\n严格输出格式：\n{\"broll_cues\": [{\"start_time\": 18.5, \"end_time\": 24.0, \"category\": \"venue\", \"visual_intent\": \"场地与门面展示\"}]}"
      }
    ],
    "temperature": 0.1,
    "max_tokens": 1024
  }
  ```
- **Response 200 OK (极速流式返回，Token < 300)**:
  ```json
  {
    "choices": [
      {
        "message": {
          "role": "assistant",
          "content": "{\"broll_cues\": [{\"start_time\": 18.5, \"end_time\": 24.0, \"category\": \"venue\", \"visual_intent\": \"低价套路引出驾校实景门面\"}, {\"start_time\": 54.6, \"end_time\": 61.8, \"category\": \"lesson\", \"visual_intent\": \"承诺教练更换与车接车送实景\"}]}"
        }
      }
    ]
  }
  ```

---

## 2. 内部设置与连通性接口契约 (Internal Settings APIs)

### 2.1 获取当前系统配置
- **Method**: `GET`
- **URL**: `/api/v1/settings`
- **Response 200 OK**:
  ```json
  {
    "active_harness": "api",
    "engine_config": {
      "api": {
        "base_url": "https://api.minimaxi.com/v1",
        "model": "MiniMax-Text-01",
        "has_token": true,
        "asr_provider": "minimax"
      },
      "codex": { "has_token": false },
      "zcode": { "has_token": false }
    }
  }
  ```
  *(红线注：严禁返回 `llm_api_key` 明文值，仅以下发布尔态 `has_token: true` 表达就绪)*

### 2.2 更新系统配置
- **Method**: `PUT`
- **URL**: `/api/v1/settings`
- **Payload**:
  ```json
  {
    "active_harness": "api",
    "llm_api_key": "sk-api-...",
    "llm_base_url": "https://api.minimaxi.com/v1",
    "llm_model": "MiniMax-Text-01",
    "llm_protocol": "openai",
    "asr_provider": "minimax"
  }
  ```
- **Response 200 OK**:
  ```json
  {
    "code": 0,
    "message": "设置已更新并生效"
  }
  ```

### 2.3 综合连通性健康探测
- **Method**: `POST`
- **URL**: `/api/v1/settings/test-connection`
- **Response 200 OK**:
  ```json
  {
    "code": 0,
    "data": {
      "llm_status": "ok",
      "llm_latency_ms": 523.4,
      "asr_status": "ok",
      "asr_latency_ms": 1120.5,
      "model_used": "MiniMax-Text-01"
    }
  }
  ```
- **Response 500 (鉴权失败或网络故障时)**:
  ```json
  {
    "code": 500,
    "detail": "MiniMax 连通性测试失败: 鉴权失败或余额不足 (HTTP 401)"
  }
  ```