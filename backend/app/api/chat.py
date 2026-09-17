import json
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.harness_bridge.factory import get_tier_b_harness
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service

router = APIRouter()

class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str

class ChatStreamRequest(BaseModel):
    message: str
    project_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = []
    model_override: Optional[str] = None

@router.post("/stream")
async def chat_stream(req: ChatStreamRequest):
    project_context = ""
    p = project_storage_service.get_by_project_id(req.project_id) if req.project_id else None
    if p:
        # 上下文纪律：只传摘要（字幕 id+文本+时长、空镜分类计数），不 dump 全量模型字段
        sub_summary = [
            {"id": s.id, "text": s.corrected_text or s.raw_text, "dur": round(s.end_time - s.start_time, 1)}
            for s in p.subtitles
        ]
        broll_stats: Dict[str, int] = {}
        for b in p.broll_replacements:
            key = str(b.material_category) if b.material_category else "unknown"
            broll_stats[key] = broll_stats.get(key, 0) + 1
        project_context = f"""
【当前用户正在编辑的视频工程摘要】：
- 工程ID: {p.id}
- 视频比例: {p.aspect_ratio}
- 字幕片段 (共 {len(sub_summary)} 句): {json.dumps(sub_summary, ensure_ascii=False)}
- 空镜统计 (按分类计数): {json.dumps(broll_stats, ensure_ascii=False)}
"""

    all_materials = storage_service.list_materials()
    mat_stats: Dict[str, int] = {}
    for m in all_materials:
        key = str(m.category)
        mat_stats[key] = mat_stats.get(key, 0) + 1
    materials_context = f"素材库分类统计: {json.dumps(mat_stats, ensure_ascii=False)}"

    system_instructions = f"""你是一个专业而富有创意的短视频剪辑与创意副驾驶 (VideoCut Harness Copilot)。
你具备以下核心能力：
1. 驾校与短视频行业的脚本策划、网感爆款文案撰写、流量黄金3秒口播设计、视频结构诊断。
2. 剪辑策略调整中枢：你可以分析用户当前视频工程的节奏、空镜头匹配度、字幕通顺度。
3. 行动触发 (Action Trigger)：如果用户的意图是明确要求【修改当前工程字幕】、【重新指定/替换空镜素材】或【微调剪辑节奏】，请在给出自然语言分析与建议的同时，在回复的最后单独附带一个合法的 JSON 动作块。

{project_context}

【可用素材库】：
{materials_context}

【动作块格式规范】：
如果你识别到需要帮用户应用剪辑策略调整，必须在回复正文的最后一行使用以下严格标记包裹动作 JSON（若只是普通问答或闲聊，则不要输出任何动作块）：
<<<ACTION>>>
{{
  "action_type": "update_project",
  "explanation": "简要总结本次对工程应用的改动",
  "updated_subtitles": [ ...更新后的完整或修改字幕列表... ],
  "updated_brolls": [ ...更新后的完整或修改空镜列表... ]
}}
<<<END_ACTION>>>
"""

    # 组装对话历史
    prompt_builder = [system_instructions, "\n【对话历史】:"]
    for h in (req.history or [])[-6:]:
        role_label = "用户" if h.role == "user" else "AI副驾驶"
        prompt_builder.append(f"{role_label}: {h.content}")
    prompt_builder.append(f"用户: {req.message}\nAI副驾驶:")
    full_prompt = "\n".join(prompt_builder)

    # 聊天属开放式任务：走 Tier B（codex/zcode → embedded），与字幕纠偏的 active_harness 解耦
    harness = get_tier_b_harness()

    async def event_generator():
        try:
            async for chunk in harness.stream_chat(full_prompt, model_override=req.model_override):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"
            yield f'data: {json.dumps({"type": "done"})}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )