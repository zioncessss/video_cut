"""LLM 直连共享传输层（OpenAI 兼容协议）。

api / codex 桥接器共用：提供方解析、/chat/completions（备用 /responses）调用、
响应 JSON 提取。错误如实上报，严禁静默吞掉。
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core import config


def normalize_base_url(base_url: str) -> str:
    """规范化 Base URL，智能补全 /v1 后缀与剔除多余子路径"""
    url = (base_url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        url = url[:-len("/chat/completions")].rstrip("/")
    if url.endswith("/v1"):
        return url
    if "api.minimaxi.com" in url or "api.openai.com" in url or "api.deepseek.com" in url:
        return f"{url}/v1"
    return url


def resolve_api_provider() -> Optional[Dict[str, str]]:
    """解析直连提供方配置。

    优先级：设置页显式配置（llm_api_key 非空，或 base_url 非默认占位）
    → ~/.codex/config.toml（同一真实端点与 token）→ None（不可用）。
    返回 {base_url, token, model, source}。
    """
    cfg = config.load_settings
    settings_base = (config.LLM_BASE_URL or "").strip()
    settings_key = (config.LLM_API_KEY or "").strip()
    default_base = "https://api.openai.com/v1"
    if settings_key or (settings_base and settings_base != default_base):
        return {
            "base_url": settings_base or default_base,
            "token": settings_key,
            "model": (config.LLM_MODEL or "").strip(),
            "source": "设置页配置",
        }

    provider_cfg = config.get_codex_provider_config()
    toml_base = (provider_cfg.get("base_url") or "").strip()
    toml_model = (provider_cfg.get("model") or "").strip()
    if toml_base:
        return {
            "base_url": toml_base,
            "token": (provider_cfg.get("token") or "").strip(),
            "model": toml_model,
            "source": "codex 本地配置 (~/.codex/config.toml)",
        }
    return None


def codex_provider() -> Optional[Dict[str, str]]:
    """codex 引擎专用提供方：只读本地 ~/.codex/config.toml（本地代理/CLI 自带配置）。

    绝不读取设置页的 base_url/api_key——引擎切换时配置必须随之隔离。
    """
    cfg = config.get_codex_provider_config()
    base_url = (cfg.get("base_url") or "").strip()
    if not base_url:
        return None
    return {
        "base_url": base_url,
        "token": (cfg.get("token") or "").strip(),
        "model": (cfg.get("model") or "").strip(),
        "source": "codex 本地配置 (~/.codex/config.toml)",
    }


async def chat_completion(
    prompt: str,
    timeout: float = 30.0,
    system: Optional[str] = None,
    model_override: Optional[str] = None,
    provider: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str, float]:
    """调用 /chat/completions（本地 codex 代理兼容模式下备用 /responses）。

    provider 显式传入时用之（如 codex 引擎绑定本地配置）；否则自动解析（api 引擎：设置页 → codex toml）。
    返回 (成功, 正文文本, 耗时ms)；失败时正文携带真实错误详情，绝不静默吞异常。
    """
    provider = provider or resolve_api_provider()
    if not provider:
        return False, "未配置直连大模型提供方：请在设置页填写 base_url 与 api_key，或确保 ~/.codex/config.toml 存在", 0.0
    return await _chat_via_provider(provider, prompt, timeout, system, model_override)


async def _chat_via_provider(
    provider: Dict[str, str],
    prompt: str,
    timeout: float = 30.0,
    system: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Tuple[bool, str, float]:
    import httpx

    start_time = time.time()
    base_url = normalize_base_url(provider["base_url"])
    active_model = (model_override or provider.get("model") or config.LLM_MODEL or "glm-5.3-flash").strip()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {"Authorization": f"Bearer {provider['token']}"} if provider["token"] else {}

    # trust_env=False：防止本机 127.0.0.1 请求被系统 VPN/代理截获导致超时
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={"model": active_model, "messages": messages},
                headers=headers,
                timeout=timeout,
            )
            if resp.status_code == 200:
                content = _content_from_chat_completion(resp.json())
                if content:
                    return True, content, (time.time() - start_time) * 1000
                return False, f"直连响应 200 但未含正文（model={active_model}）", (time.time() - start_time) * 1000
            return False, f"直连 /chat/completions 失败 HTTP {resp.status_code}: {resp.text[:200]}", (time.time() - start_time) * 1000
    except httpx.TimeoutException as e:
        last_err = f"读取响应超时({timeout:.0f}s)，模型未在时限内完成生成（提示词过大或模型过慢，建议减小单次请求句数）[{e.__class__.__name__}]"
    except httpx.HTTPError as e:
        last_err = f"直连 /chat/completions 网络异常: {str(e) or e.__class__.__name__}"
    except Exception as e:
        last_err = f"直连 /chat/completions 异常: {str(e) or e.__class__.__name__}"

    # 备用：本地 codex 代理的 /responses 端点（仅本地代理提供该协议；
    # 远端供应商如 open.bigmodel.cn 返回 404，重试只会白白再等一轮，直接返回首因错误）
    is_local_proxy = ("127.0.0.1" in base_url or "localhost" in base_url
                      or "codex" in str(provider.get("source", "")))
    if not is_local_proxy:
        return False, last_err, (time.time() - start_time) * 1000
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.post(
                f"{base_url}/responses",
                json={"model": active_model, "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]},
                headers=headers,
                timeout=timeout,
            )
            if resp.status_code == 200:
                output_text = _content_from_responses(resp.json())
                if output_text:
                    return True, output_text, (time.time() - start_time) * 1000
            return False, f"备用 /responses 失败 HTTP {resp.status_code}: {resp.text[:200]}（首因：{last_err}）", (time.time() - start_time) * 1000
    except Exception as e:
        return False, f"{last_err}；备用 /responses 亦异常: {e}", (time.time() - start_time) * 1000


async def chat_completion_stream_full(
    prompt: str,
    timeout: float = 120.0,
    system: Optional[str] = None,
    model_override: Optional[str] = None,
    provider: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str, float]:
    """流式请求并收集完整回复。

    推理模型（如 glm-5.3-flash）思考链很长，非流式一次性等待完整生成极易触发读超时
    （实测 11 句纠偏需 82s）；流式下 timeout 只约束"相邻 token 间空闲"，token 持续流出
    即不会超时，生成本身不限时。超长生成任务的正确姿势。
    返回 (成功, 完整正文, 耗时ms)。
    """
    import httpx

    provider = provider or resolve_api_provider()
    if not provider:
        return False, "未配置直连大模型提供方：请在设置页填写 base_url 与 api_key，或确保 ~/.codex/config.toml 存在", 0.0
    start_time = time.time()
    base_url = normalize_base_url(provider["base_url"])
    active_model = (model_override or provider.get("model") or config.LLM_MODEL or "glm-5.3-flash").strip()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {"Authorization": f"Bearer {provider['token']}"} if provider["token"] else {}
    # 分段超时：连接 10s，相邻块读取 timeout s（token 流动即不触发），整体生成不限时
    req_timeout = httpx.Timeout(10.0, read=timeout, write=10.0, pool=10.0)

    content_parts: List[str] = []
    reasoning_parts: List[str] = []
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json={"model": active_model, "messages": messages, "stream": True},
                headers=headers,
                timeout=req_timeout,
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    return False, f"流式请求失败 HTTP {resp.status_code}: {body[:200]}", (time.time() - start_time) * 1000
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        data = json.loads(payload)
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    choices = data.get("choices") or [{}]
                    delta = (choices[0].get("delta") or {}) if choices else {}
                    if delta.get("content"):
                        content_parts.append(str(delta["content"]))
                    if delta.get("reasoning_content"):
                        reasoning_parts.append(str(delta["reasoning_content"]))
        text = "".join(content_parts).strip() or "".join(reasoning_parts).strip()
        if not text:
            return False, f"流式连接正常结束但未收到任何内容（model={active_model}）", (time.time() - start_time) * 1000
        return True, text, (time.time() - start_time) * 1000
    except httpx.TimeoutException as e:
        return False, f"流式读取空闲超时({timeout:.0f}s)，token 流中断 [{e.__class__.__name__}]", (time.time() - start_time) * 1000
    except httpx.HTTPError as e:
        return False, f"流式网络异常: {str(e) or e.__class__.__name__}", (time.time() - start_time) * 1000
    except Exception as e:
        return False, f"流式请求异常: {str(e) or e.__class__.__name__}", (time.time() - start_time) * 1000


def _model_name(item: Any) -> Optional[str]:
    """从 /models 条目中提取模型名：兼容 {id} / {slug, display_name} / 裸字符串"""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("id", "slug", "model", "name"):
            if item.get(key):
                return str(item[key])
    return None


def parse_models_payload(data: Any) -> list:
    """解析 /models 响应体为模型 id 列表。

    兼容：OpenAI 标准 {"data": [{id}]}；codex 本地代理 {"models": [{slug, display_name}]}；极简 [id, ...]
    """
    items = data.get("data") if isinstance(data, dict) else data
    if not items and isinstance(data, dict):
        items = data.get("models")
    return sorted({name for name in (_model_name(x) for x in (items or [])) if name})


async def list_models(base_url: str, token: str = "", timeout: float = 15.0) -> Tuple[bool, list, str]:
    """调用 OpenAI 兼容 GET {base_url}/models 拉取可用模型列表。

    返回 (成功, 模型id列表, 消息)；失败时消息携带真实错误详情。
    """
    import httpx

    base = normalize_base_url(base_url)
    if not base:
        return False, [], "base_url 为空，无法获取模型列表"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        # trust_env=False：防止本机/内网请求被系统 VPN/代理截获
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.get(f"{base}/models", headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return False, [], f"GET /models 失败 HTTP {resp.status_code}: {resp.text[:200]}"
        models = parse_models_payload(resp.json())
        if not models:
            return False, [], "接口返回 200 但未解析到任何模型 id"
        return True, models, f"获取成功，共 {len(models)} 个模型"
    except Exception as e:
        return False, [], f"获取模型列表异常: {e}"


def parse_stream_line(line: str) -> bool:
    """判断 SSE data 行是否携带首个内容 token（delta.content / delta.reasoning_content 非空）。

    role 声明帧、空 delta、[DONE]、非 data 行均不算。
    """
    if not line.startswith("data:"):
        return False
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return False
    try:
        data = json.loads(payload)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    choices = data.get("choices") or [{}]
    delta = (choices[0].get("delta") or {}) if choices else {}
    return bool(delta.get("content") or delta.get("reasoning_content"))


async def chat_completion_ttft(
    prompt: str,
    timeout: float = 20.0,
    system: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Tuple[bool, float, str]:
    """流式请求测量首 Token 延迟（TTFT）：从发出请求到收到第一个内容 token 的时间。

    TTFT 只含网络往返与提示词处理，不含完整生成耗时，是衡量直连链路质量的正确指标。
    返回 (成功, TTFT毫秒, 详情)；成功时详情为生效模型名，失败时为真实错误信息。
    """
    import httpx

    provider = resolve_api_provider()
    if not provider:
        return False, 0.0, "未配置直连大模型提供方：请在设置页填写 base_url 与 api_key，或确保 ~/.codex/config.toml 存在"
    start_time = time.time()
    base_url = normalize_base_url(provider["base_url"])
    active_model = (model_override or provider.get("model") or config.LLM_MODEL or "glm-5.3-flash").strip()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {"Authorization": f"Bearer {provider['token']}"} if provider["token"] else {}

    try:
        # trust_env=False：防止本机/内网请求被系统 VPN/代理截获
        async with httpx.AsyncClient(trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json={"model": active_model, "messages": messages, "stream": True},
                headers=headers,
                timeout=timeout,
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    return False, 0.0, f"流式请求失败 HTTP {resp.status_code}: {body[:200]}"
                async for line in resp.aiter_lines():
                    if parse_stream_line(line):
                        return True, (time.time() - start_time) * 1000, active_model
        return False, (time.time() - start_time) * 1000, "流式连接已结束但未收到任何内容 token"
    except Exception as e:
        return False, 0.0, f"流式请求异常: {e}"


def _content_from_chat_completion(data: Dict[str, Any]) -> str:
    choices = data.get("choices", [])
    if not choices:
        return ""
    msg = choices[0].get("message", {}) or {}
    content = (msg.get("content") or "").strip()
    if not content and msg.get("reasoning_content"):
        # 部分推理模型把正文放在 reasoning_content
        content = (msg.get("reasoning_content") or "").strip()
    return content


def _content_from_responses(data: Dict[str, Any]) -> str:
    output_text = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    output_text += c.get("text", "")
    return output_text.strip()


def extract_json(text: Optional[str]) -> Optional[Any]:
    """从 LLM 响应中剥离 markdown 标记并提取合法 JSON（对象或数组）"""
    if not text:
        return None
    text = text.strip()
    if "```" in text:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()

    try:
        return json.loads(text)
    except Exception:
        start_bracket = text.find("[")
        end_bracket = text.rfind("]")
        if start_bracket != -1 and end_bracket > start_bracket:
            try:
                return json.loads(text[start_bracket:end_bracket + 1])
            except Exception:
                pass

        start_brace = text.find("{")
        end_brace = text.rfind("}")
        if start_brace != -1 and end_brace > start_brace:
            try:
                return json.loads(text[start_brace:end_brace + 1])
            except Exception:
                pass
    return None
