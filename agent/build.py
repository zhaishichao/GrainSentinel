"""组装子智能体与主控智能体。

6 个专职子智能体各司其职，覆盖粮食安全「粮情监测 → 质量检测 → 虫霉防治 →
仓储管控 → 储备轮换 → 安全预警」全链条，主控 Supervisor 通过「子智能体即工具」
实现层级委派与多智能体协同，最终汇总输出。
"""
from __future__ import annotations

from agent.core import Agent, Supervisor, Tool
from data import mock_data as d


def _tool(name: str, desc: str, fn) -> Tool:
    return Tool(name=name, description=desc, func=fn)


# ---------------------------------------------------------------
# 子智能体
# ---------------------------------------------------------------
def grain_condition_agent() -> Agent:
    return Agent(
        name="grain_condition_agent",
        role="粮情实时监测与粮堆状态分析",
        system_prompt="擅长分析粮温、水分、仓湿与粮堆气体浓度，研判发热、结露、霉变等异常粮情。",
        tools=[
            _tool("get_grain_condition", "获取库点粮温/水分/仓湿/气体浓度等粮情测控数据，并研判风险。参数 warehouse：直属库A/直属库B/储备库C。", d.get_grain_condition),
            _tool("get_storage_control", "获取库点智能仓储管控方案（通风/气调/谷物冷却）。参数 warehouse 同上。", d.get_storage_control),
        ],
    )


def quality_agent() -> Agent:
    return Agent(
        name="quality_agent",
        role="粮食质量检测与等级判定",
        system_prompt="擅长依据国标分析真菌毒素、重金属、容重、水分、脂肪酸值等指标，判定质量等级与储存品质。",
        tools=[
            _tool("get_quality_inspection", "获取库点粮食质量检测结果（品质指标+储存品质判定）。参数 warehouse 同上。", d.get_quality_inspection),
            _tool("get_quality_limits", "查询粮食质量安全国标限量（真菌毒素 GB 2761 + 重金属 GB 2762）。", d.get_quality_limits),
        ],
    )


def pest_agent() -> Agent:
    return Agent(
        name="pest_agent",
        role="储粮虫霉监测与防治",
        system_prompt="擅长评估储粮害虫密度与霉菌风险，制定磷化氢熏蒸、充氮气调等防治方案。",
        tools=[
            _tool("get_pest_monitor", "获取库点虫害密度、霉菌与气调/熏蒸状态，并给出防治建议。参数 warehouse 同上。", d.get_pest_monitor),
            _tool("get_storage_control", "获取库点气调/熏蒸/通风管控方案。参数 warehouse 同上。", d.get_storage_control),
        ],
    )


def storage_agent() -> Agent:
    return Agent(
        name="storage_agent",
        role="智能仓储环境管控与损耗控制",
        system_prompt="擅长制定智能通风、充氮气调、谷物冷却方案，降低储粮损耗与能耗。",
        tools=[
            _tool("get_storage_control", "获取库点仓储管控方案与损耗评估。参数 warehouse 同上。", d.get_storage_control),
            _tool("get_grain_condition", "获取库点粮情数据（用于匹配通风/气调策略）。参数 warehouse 同上。", d.get_grain_condition),
        ],
    )


def reserve_agent() -> Agent:
    return Agent(
        name="reserve_agent",
        role="储备粮轮换与出入库管理",
        system_prompt="擅长依据储存品质判定（宜存/不宜存）制定轮换计划，指导出入库顺序与质量追溯。",
        tools=[
            _tool("get_reserve_rotation", "获取库点储存品质判定与轮换建议。参数 warehouse 同上。", d.get_reserve_rotation),
            _tool("get_quality_inspection", "获取库点质量检测结果（用于宜存判定）。参数 warehouse 同上。", d.get_quality_inspection),
        ],
    )


def warning_agent() -> Agent:
    return Agent(
        name="warning_agent",
        role="粮情安全预警与应急处置",
        system_prompt="擅长综合多源粮情数据评估风险等级，输出分级预警与应急处置预案。",
        tools=[
            _tool("assess_risk", "综合评估库点粮情安全风险（评分+等级+处置预案）。参数 warehouse 同上。", d.assess_risk),
            _tool("get_grain_condition", "获取库点粮情数据。参数 warehouse 同上。", d.get_grain_condition),
            _tool("get_pest_monitor", "获取库点虫霉监测数据。参数 warehouse 同上。", d.get_pest_monitor),
        ],
    )


# ---------------------------------------------------------------
# 主控智能体
# ---------------------------------------------------------------
def build_supervisor() -> Supervisor:
    subagents = [
        grain_condition_agent(),
        quality_agent(),
        pest_agent(),
        storage_agent(),
        reserve_agent(),
        warning_agent(),
    ]
    return Supervisor(
        name="supervisor",
        role="粮情哨兵智能体总控",
        system_prompt=(
            "你是「粮情哨兵」智能体总控，面向粮食安全、粮情实时监测与仓储管理场景，"
            "帮助用户完成粮情分析、质量检测、虫霉防治、仓储管控、储备轮换与安全预警等任务。\n"
            "工作方式：\n"
            "1. 概念性、知识性、政策标准类问题（如「什么是安全水分」「黄曲霉毒素限量是多少」）"
            "请直接输出 finish 回答，不必调用工具；\n"
            "2. 需要数据或专业分析的粮食安全问题，选择合适的子智能体委派（可委派多个再汇总）；\n"
            "3. 委派时给出清晰、具体的 task 指令（可指定库点：直属库A/直属库B/储备库C），"
            "并在汇总时整合各子智能体的结论，给出量化结论与行动建议。"
        ),
        subagents=subagents,
    )


# 启动时构建一次（子智能体为无状态对象，可复用）
supervisor = build_supervisor()
