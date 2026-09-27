"""LLM 客户端：封装 OpenAI 兼容协议，支持流式与非流式调用。

一套代码即可对接 DeepSeek / 通义千问 / 智谱 GLM / OpenAI 等任意
OpenAI 兼容的大模型服务，只需在 .env 中修改 base_url 与 model。
"""
from __future__ import annotations

from typing import AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from config import settings


class LLM:
    """惰性初始化异步客户端，仅在首次调用时创建。"""

    def __init__(self) -> None:
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
        return self._client

    async def complete(self, messages: List[Dict]) -> str:
        """非流式补全，返回完整文本。"""
        resp = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=settings.temperature,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    async def stream(self, messages: List[Dict]) -> AsyncIterator[str]:
        """流式补全，逐块产出增量文本。"""
        resp = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=settings.temperature,
            stream=True,
        )
        async for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# 全局单例
llm = LLM()
