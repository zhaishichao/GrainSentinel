"""FastAPI 服务：静态前端托管 + 流式问答接口（SSE）。

运行：python app.py  （默认 http://localhost:8000）
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.build import supervisor
from config import settings
from data import mock_data as d

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="粮情哨兵智能体", description="面向粮食安全、粮情实时监测与仓储数据问答的多智能体系统")


# ---------------------------------------------------------------
# 页面与静态资源
# ---------------------------------------------------------------
@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------
# 基础接口
# ---------------------------------------------------------------
@app.get("/api/overview")
async def overview(warehouse: str = "直属库A"):
    """供前端可视化面板使用的粮情监测曲线数据。"""
    return d.get_overview(warehouse)


@app.get("/api/agents")
async def agents():
    """供前端展示的智能体清单。"""
    return {
        "supervisor": supervisor.role,
        "subagents": [{"name": a.name, "role": a.role} for a in supervisor.subagents],
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_ready": settings.llm_ready, "model": settings.llm_model}


# ---------------------------------------------------------------
# 流式问答
# ---------------------------------------------------------------
@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    question = (body.get("message") or "").strip()
    if not question:
        raise HTTPException(400, "消息不能为空")
    if not settings.llm_ready:
        raise HTTPException(503, "未配置 LLM_API_KEY，请复制 .env.example 为 .env 并填入 Key")

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event: dict):
            await queue.put(event)

        async def run():
            try:
                await supervisor.run(question, emit, stream_text=True)
            except Exception as exc:  # 捕获 LLM/工具异常，友好反馈
                hint = "请检查 .env 中的 LLM_API_KEY/LLM_BASE_URL/LLM_MODEL" if "401" in str(exc) or "key" in str(exc).lower() else ""
                await emit({"type": "error", "content": f"{type(exc).__name__}: {exc}{'（' + hint + '）' if hint else ''}"})
            finally:
                await emit({"type": "done"})

        task = asyncio.create_task(run())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
