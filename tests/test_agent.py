"""框架与数据逻辑测试（不依赖真实大模型，用 StubLLM 验证全链路）。

运行：python tests/test_agent.py   或   pytest tests/
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent.core as core
from agent.build import build_supervisor
from agent.core import parse_json
from data import mock_data as d


# ---------------------------------------------------------------
# 模拟 LLM：按智能体名返回预设的工具调用脚本，验证 ReAct 循环
# ---------------------------------------------------------------
class StubLLM:
    def __init__(self, plans: dict):
        self.plans = plans  # {agent_name: [(tool_name, args), ...]}
        self.calls = {}  # {agent_name: 已调用工具次数}

    def _agent(self, messages) -> str:
        sys_msg = messages[0]["content"]
        for name in self.plans:
            if f"「{name}」" in sys_msg:
                return name
        return ""

    async def complete(self, messages) -> str:
        name = self._agent(messages)
        seq = self.plans.get(name, [])
        called = self.calls.get(name, 0)
        if called < len(seq):
            tool, args = seq[called]
            self.calls[name] = called + 1
            return json.dumps({"action": "tool", "tool": tool, "args": args}, ensure_ascii=False)
        return json.dumps({"action": "finish", "plan": "完成"}, ensure_ascii=False)

    async def stream(self, messages):
        for ch in ["结论", "（", "测试", "）"]:
            yield ch


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------
def test_parse_json():
    assert parse_json('{"action":"tool","tool":"x","args":{"a":1}}')["tool"] == "x"
    assert parse_json('```json\n{"action":"finish"}\n```')["action"] == "finish"
    assert parse_json('好的。{"action":"finish","plan":"p"} 以上')["plan"] == "p"
    assert parse_json("乱码") == {}


def test_mock_data():
    assert len(d.grain_temp_curve("直属库A")) == 24
    assert d.get_grain_condition("直属库A").startswith("库点")
    assert "安全水分" in d.get_quality_inspection("直属库A")
    assert "熏蒸" in d.get_pest_monitor("储备库C") or "气调" in d.get_pest_monitor("储备库C")
    out = d.assess_risk("储备库C")
    assert "风险评分" in out and "等级" in out
    assert d.get_overview("直属库A")["grain"] == "小麦"
    assert set(d.get_overview("直属库A")) >= {"temp_profile", "grain_profile", "humidity_profile", "stock"}


def test_agent_tool_loop():
    """单个子智能体：调用领域工具 → 合成答案 → 发出事件。"""
    async def _t():
        core.llm = StubLLM({"grain_condition_agent": [("get_grain_condition", {"warehouse": "储备库C"})]})
        agent = build_supervisor().subagents[0]  # grain_condition_agent
        events = []

        async def emit(e):
            events.append(e)

        answer = await agent.run("分析储备库C粮情", emit, stream_text=True)
        assert answer == "结论（测试）"
        types = [e["type"] for e in events]
        assert types.count("tool") == 1 and "tool_result" in types and "text" in types

    run(_t())


def test_supervisor_delegation():
    """主控智能体：委派子智能体（subAgent），子智能体再调用工具。"""
    async def _t():
        core.llm = StubLLM({
            "supervisor": [("ask_warning_agent", {"task": "评估储备库C粮情风险"})],
            "warning_agent": [("assess_risk", {"warehouse": "储备库C"})],
        })
        supervisor = build_supervisor()
        events = []

        async def emit(e):
            events.append(e)

        answer = await supervisor.run("帮我评估储备库C的粮情安全风险", emit, stream_text=True)
        assert answer == "结论（测试）"
        tools = [e for e in events if e["type"] == "tool"]
        assert any(e["tool"] == "ask_warning_agent" for e in tools)
        assert any(e["tool"] == "assess_risk" for e in tools)
        assert any(e["type"] == "text" for e in events)

    run(_t())


def test_supervisor_registry():
    """主控应注册 6 个子智能体委派工具。"""
    sup = build_supervisor()
    assert len(sup.subagents) == 6
    assert {t.name for t in sup.tools} == {f"ask_{a.name}" for a in sup.subagents}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✓ {fn.__name__}")
    print(f"\n全部 {len(fns)} 个测试通过。")
