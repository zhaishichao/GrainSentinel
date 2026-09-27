"""轻量多智能体框架：Tool / Agent / Supervisor。

设计要点：
1. 子智能体即工具 —— 主控把子智能体封装成可调用工具，实现层级委派（subAgent 模式）；
2. 统一 ReAct 循环 —— 每个智能体在「系统提示词 + 工具集」下循环执行
   「思考 → 调工具 → 观察 → 再思考」，直至给出结论；
3. 两阶段输出 —— 工具循环阶段非流式（稳定），最终回答阶段真流式（体验好）。

不依赖 LangChain/LangGraph 等重框架，全部逻辑 ~200 行，便于阅读与扩展。
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from agent.llm import llm
from config import settings


# ---------------------------------------------------------------
# 工具
# ---------------------------------------------------------------
@dataclass
class Tool:
    name: str
    description: str
    func: Callable          # async func(**kwargs) -> str；needs_emit=True 时签名含 emit
    needs_emit: bool = False

    def brief(self) -> str:
        return f"- {self.name}：{self.description}"


# ---------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------
def parse_json(text: str) -> Dict[str, Any]:
    """稳健地从 LLM 输出中提取 JSON 对象（容忍代码块包裹与前后杂文）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def clip(text: str, n: int = 160) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"


# ---------------------------------------------------------------
# 智能体
# ---------------------------------------------------------------
class Agent:
    """一个具备系统提示词与工具集的智能体，可独立完成一类专业任务。"""

    def __init__(self, name: str, role: str, system_prompt: str, tools: List[Tool]):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools
        self._tool_map = {t.name: t for t in tools}

    # -- 提示词 --
    def _loop_prompt(self) -> str:
        tool_desc = "\n".join(t.brief() for t in self.tools) or "- （无工具，直接回答）"
        return (
            f"你是粮情哨兵智能体「{self.name}」，职责：{self.role}。\n\n"
            f"{self.system_prompt}\n\n"
            f"你可调用以下工具获取数据（每次只调用一个工具）：\n{tool_desc}\n\n"
            f"请严格按以下 JSON 之一回复，不要输出其它内容：\n"
            f'需要数据时：{{"action":"tool","tool":"工具名","args":{{...}}}}\n'
            f'分析完成时：{{"action":"finish","plan":"一句话概述你的分析思路"}}'
        )

    def _syn_prompt(self, task: str, observations: List[str], findings: bool) -> List[Dict]:
        ctx = "\n\n".join(observations) if observations else "（未调用工具）"
        if findings:
            system = (
                f"你是粮情哨兵智能体「{self.name}」，{self.role}。\n"
                f"请基于任务与已获取的数据，输出一份简洁的调研结论（关键数据 + 主要发现 + 建议），\n"
                f"供主控智能体汇总，用中文，Markdown 排版，尽量精炼。"
            )
        else:
            system = (
                f"你是粮情哨兵智能体「{self.name}」，{self.role}。\n"
                f"请基于任务与已获取的数据，输出专业、简洁、可执行的分析结论，\n"
                f"用中文，Markdown 排版，适当给出量化结论与行动建议。"
            )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"任务：{task}\n\n已获取数据：\n{ctx}"},
        ]

    # -- 执行 --
    async def run(self, task: str, emit, stream_text: bool = True) -> str:
        """执行任务。stream_text=True 时流式输出最终回答并逐块 emit。

        emit 为异步回调：emit(dict)，事件类型见 app.py。
        """
        await emit({"type": "agent", "agent": self.name, "content": self.role})
        messages: List[Dict] = [
            {"role": "system", "content": self._loop_prompt()},
            {"role": "user", "content": task},
        ]
        observations: List[str] = []

        for _ in range(settings.max_tool_rounds):
            raw = await llm.complete(messages)
            decision = parse_json(raw)
            if decision.get("action") != "tool":
                break

            tool = self._tool_map.get(decision.get("tool", ""))
            if tool is None:
                messages.append({"role": "user", "content": f"工具 {decision.get('tool')} 不存在，请重新选择。"})
                continue

            args = decision.get("args") or {}
            await emit({"type": "tool", "agent": self.name, "tool": tool.name, "args": args})
            try:
                result = await self._invoke(tool, args, emit)
            except Exception as exc:  # 工具异常不中断整体流程
                result = f"工具调用出错：{exc}"
            observations.append(f"[{tool.name}] {result}")
            await emit({"type": "tool_result", "agent": self.name, "tool": tool.name, "preview": clip(result)})

            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {"role": "user", "content": f"工具 {tool.name} 返回：\n{result}\n\n请继续：调用下一个工具，或输出 finish。"}
            )

        findings = not stream_text
        if stream_text:
            answer = ""
            async for chunk in llm.stream(self._syn_prompt(task, observations, findings)):
                answer += chunk
                await emit({"type": "text", "content": chunk})
            return answer
        return await llm.complete(self._syn_prompt(task, observations, findings))

    async def _invoke(self, tool: Tool, args: Dict, emit) -> str:
        kwargs = dict(args or {})
        if tool.needs_emit:
            kwargs["emit"] = emit
        # 仅传入函数实际接受的参数，避免 LLM 多余参数导致 TypeError
        sig = inspect.signature(tool.func)
        accepted = {k for k, p in sig.parameters.items() if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}
        result = tool.func(**{k: v for k, v in kwargs.items() if k in accepted})
        # 工具既支持异步函数，也支持同步纯函数（领域计算）
        if inspect.isawaitable(result):
            result = await result
        return result


# ---------------------------------------------------------------
# 主控智能体：把子智能体封装成工具，实现层级委派
# ---------------------------------------------------------------
class Supervisor(Agent):
    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        subagents: List[Agent],
        extra_tools: Optional[List[Tool]] = None,
    ):
        self.subagents = subagents
        tools = [self._delegate_tool(a) for a in subagents] + (extra_tools or [])
        super().__init__(name, role, system_prompt, tools)

    def _delegate_tool(self, agent: Agent) -> Tool:
        async def delegate(emit, task: str = "") -> str:
            return await agent.run(task, emit, stream_text=False)

        return Tool(
            name=f"ask_{agent.name}",
            description=f"委派给「{agent.name}」子智能体处理：{agent.role}。参数 task 为具体指令。",
            func=delegate,
            needs_emit=True,
        )
