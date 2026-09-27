"""粮食领域模拟数据与工具函数。

数据贴近我国粮食仓储与质量安全现状：
- 储粮品种 / 仓型（平房仓、浅圆仓、立筒仓）
- 粮情测控（粮温分层、水分、仓湿、粮堆 O2/CO2/PH3 气体浓度）
- 质量安全限量（GB 2761 真菌毒素、GB 2762 重金属、容重/不完善粒/脂肪酸值等品质指标）
- 虫霉防治（储粮害虫密度、磷化氢熏蒸、充氮气调）
- 储存品质判定（宜存 / 轻度不宜存 / 重度不宜存）

所有函数均为纯函数（同步、无副作用），后续可替换为真实粮情测控系统
（粮库智能化改造平台 / 传感器网关 / 检测实验室 LIMS）接口，无需改动 Agent 框架。
"""
from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------
# 库点 / 仓型定义
# ---------------------------------------------------------------
WAREHOUSES: Dict[str, Dict] = {
    "直属库A": {
        "仓型": "平房仓", "品种": "小麦", "仓容吨": 50000, "库存吨": 46500,
        "入库日期": "2025-06", "产地": "河南", "等级": "一等", "储粮状态": "宜存",
        "储粮方式": "机械通风 + 环流熏蒸备用",
        "水分": 11.8, "粮温均温": 18.6, "最高粮温": 23.4, "仓湿": 58.0,
        "O2": 20.8, "CO2": 0.04, "PH3": 0.0,
        "虫害密度": 2, "霉菌": "未检出",
        "品质指标": {"容重": "802 g/L", "不完善粒": "4.2%", "杂质": "0.8%", "脂肪酸值": "22 mgKOH/100g"},
    },
    "直属库B": {
        "仓型": "浅圆仓", "品种": "稻谷", "仓容吨": 30000, "库存吨": 28800,
        "入库日期": "2025-08", "产地": "黑龙江", "等级": "一等", "储粮状态": "宜存",
        "储粮方式": "充氮气调（富氮储粮）",
        "水分": 14.1, "粮温均温": 21.3, "最高粮温": 27.8, "仓湿": 62.0,
        "O2": 2.8, "CO2": 3.5, "PH3": 0.0,
        "虫害密度": 0, "霉菌": "未检出",
        "品质指标": {"出糙率": "79.5%", "整精米率": "62.0%", "杂质": "0.9%", "脂肪酸值": "24 mgKOH/100g"},
    },
    "储备库C": {
        "仓型": "立筒仓", "品种": "玉米", "仓容吨": 20000, "库存吨": 19500,
        "入库日期": "2025-10", "产地": "吉林", "等级": "二等", "储粮状态": "轻度不宜存",
        "储粮方式": "谷物冷却 + 机械通风",
        "水分": 14.6, "粮温均温": 25.4, "最高粮温": 32.1, "仓湿": 55.0,
        "O2": 19.5, "CO2": 0.12, "PH3": 0.0,
        "虫害密度": 18, "霉菌": "局部检出（曲霉属）",
        "品质指标": {"容重": "685 g/L", "不完善粒": "8.6%", "杂质": "1.2%", "脂肪酸值": "58 mgKOH/100g"},
    },
}

# 24h 仓温曲线（℃）：夏季典型昼夜变化，午后最高、凌晨最低
WAREHOUSE_TEMP_PROFILE = [
    26.0, 25.4, 24.9, 24.5, 24.2, 24.1, 25.0, 26.6, 28.3, 29.8, 30.9, 31.7,
    32.1, 31.8, 31.2, 30.0, 28.8, 27.8, 26.9, 26.2, 25.7, 25.3, 25.0, 25.7,
]

# 24h 粮温曲线（℃）：粮堆热惯性大、变化平缓，围绕均温微幅波动
GRAIN_TEMP_PROFILE = [
    18.9, 18.8, 18.7, 18.6, 18.6, 18.5, 18.5, 18.4, 18.5, 18.6, 18.7, 18.8,
    18.9, 18.9, 18.8, 18.7, 18.6, 18.6, 18.5, 18.5, 18.6, 18.7, 18.8, 18.9,
]

# 24h 仓湿曲线（%RH）：与仓温反相，午后干、凌晨湿
HUMIDITY_PROFILE = [
    64, 66, 68, 69, 70, 70, 66, 62, 58, 54, 51, 49,
    48, 49, 50, 53, 56, 59, 62, 64, 66, 67, 68, 65,
]

# 各品种安全水分上限（%）
SAFE_MOISTURE = {"小麦": 12.5, "稻谷": 14.5, "玉米": 14.0, "大豆": 13.0}

# 储粮害虫（头/公斤）密度分级
PEST_LEVEL = [(0, 5, "基本无虫"), (5, 30, "一般虫粮"), (30, 1e9, "严重虫粮，需立即熏蒸")]

# 真菌毒素限量（GB 2761-2017，μg/kg）
TOXIN_LIMITS = {
    "黄曲霉毒素B1": {"玉米/稻谷": 20, "小麦": 5},
    "呕吐毒素DON": {"小麦/玉米": 1000},
    "玉米赤霉烯酮ZEN": {"小麦/玉米": 60},
}

# 重金属限量（GB 2762-2022，mg/kg，谷物）
METAL_LIMITS = {
    "铅": 0.2, "镉": 0.2, "无机砷": 0.2, "汞": 0.02, "铬": 1.0,
}

# 储存品质判定（GB/T 20569 / 20570 等）：脂肪酸值阈值 mgKOH/100g
QUALITY_GRADES = {
    "宜存": "品质正常，可继续储存，按计划轮换",
    "轻度不宜存": "品质有所下降，应尽快安排出库轮换",
    "重度不宜存": "品质严重劣变，必须立即出库，不得继续储存",
}


# ---------------------------------------------------------------
# 基础曲线
# ---------------------------------------------------------------
def warehouse_temp_curve(warehouse: str) -> List[float]:
    """仓温 24h 曲线：以库点最高粮温为基准做缩放，体现不同库点差异。"""
    base = WAREHOUSES[warehouse]["最高粮温"]
    return [round(base + d, 1) for d in [x - 32.1 for x in WAREHOUSE_TEMP_PROFILE]]


def grain_temp_curve(warehouse: str) -> List[float]:
    """粮温 24h 曲线：以库点平均粮温为基准。"""
    avg = WAREHOUSES[warehouse]["粮温均温"]
    return [round(avg + (x - 18.6), 1) for x in GRAIN_TEMP_PROFILE]


def humidity_curve(warehouse: str) -> List[float]:
    """仓湿 24h 曲线：以库点仓湿为基准。"""
    base = WAREHOUSES[warehouse]["仓湿"]
    return [round(base + (x - 58), 1) for x in HUMIDITY_PROFILE]


# ---------------------------------------------------------------
# 领域工具函数（返回可读文本，供 LLM 阅读）
# ---------------------------------------------------------------
def get_grain_condition(warehouse: str = "直属库A") -> str:
    """获取库点粮情测控数据：粮温/水分/仓湿/气体浓度，并研判发热、结露风险。"""
    w = WAREHOUSES[warehouse]
    safe = SAFE_MOISTURE[w["品种"]]
    risk = []
    if w["最高粮温"] >= 30:
        risk.append("最高粮温≥30℃，存在发热风险，需核查局部粮温梯度")
    elif w["最高粮温"] >= 25:
        risk.append("最高粮温处于 25~30℃ 高温区间，需加强测温频次")
    if w["水分"] > safe:
        risk.append(f"水分 {w['水分']}% 超过安全水分 {safe}%，存在霉变风险")
    if w["仓湿"] > 70:
        risk.append("仓湿偏高，注意仓壁结露与表层吸湿")
    return (
        f"库点：{warehouse}（{w['仓型']}，品种 {w['品种']}）\n"
        f"粮温：平均 {w['粮温均温']}℃，最高 {w['最高粮温']}℃；水分 {w['水分']}%；仓湿 {w['仓湿']}%RH\n"
        f"粮堆气体：O2 {w['O2']}%，CO2 {w['CO2']}%，PH3 {w['PH3']} ppm\n"
        f"储粮状态：{w['储粮状态']}；储粮方式：{w['储粮方式']}\n"
        f"风险研判：{'；'.join(risk) if risk else '粮情基本稳定，无发热/结露/霉变异常'}"
    )


def get_quality_inspection(warehouse: str = "直属库A") -> str:
    """获取库点粮食质量检测结果：毒素、重金属与品质指标，并判定等级。"""
    w = WAREHOUSES[warehouse]
    items = "；".join(f"{k} {v}" for k, v in w["品质指标"].items())
    return (
        f"库点：{warehouse}（品种 {w['品种']}，等级 {w['等级']}，产地 {w['产地']}）\n"
        f"品质指标：{items}\n"
        f"水分 {w['水分']}%（安全水分 {SAFE_MOISTURE[w['品种']]}%），"
        f"虫害密度 {w['虫害密度']} 头/公斤，霉菌 {w['霉菌']}\n"
        f"储存品质判定：{w['储粮状态']} —— {QUALITY_GRADES[w['储粮状态']]}"
    )


def get_quality_limits() -> str:
    """查询粮食质量安全国标限量（真菌毒素 + 重金属）。"""
    lines = ["粮食质量安全限量标准："]
    lines.append("一、真菌毒素限量（GB 2761-2017，μg/kg）：")
    for name, vals in TOXIN_LIMITS.items():
        lines.append(f"- {name}：{'；'.join(f'{k} {v}' for k, v in vals.items())}")
    lines.append("二、重金属限量（GB 2762-2022，谷物，mg/kg）：")
    lines.append("；".join(f"{k} {v}" for k, v in METAL_LIMITS.items()))
    return "\n".join(lines)


def get_pest_monitor(warehouse: str = "直属库A") -> str:
    """获取库点虫霉监测数据与防治建议。"""
    w = WAREHOUSES[warehouse]
    density = w["虫害密度"]
    level = next(lv for lo, hi, lv in PEST_LEVEL if lo <= density < hi)
    if density >= 30:
        advice = "密度严重超标，建议立即安排磷化氢熏蒸（200~400 ppm，密闭 5~7 天）"
    elif density >= 5:
        advice = "达到一般虫粮标准，建议加强监测，结合充氮气调或局部熏蒸处理"
    else:
        advice = "处于基本无虫水平，维持常规监测与防虫隔离即可"
    return (
        f"库点：{warehouse}（品种 {w['品种']}）\n"
        f"虫害密度：{density} 头/公斤（{level}）；霉菌：{w['霉菌']}\n"
        f"当前气调/熏蒸状态：O2 {w['O2']}%，PH3 {w['PH3']} ppm\n"
        f"防治建议：{advice}"
    )


def get_storage_control(warehouse: str = "直属库A") -> str:
    """获取库点智能仓储管控方案：通风/气调/谷物冷却与能耗损耗评估。"""
    w = WAREHOUSES[warehouse]
    # 根据粮温与季节给出通风/气调建议
    if w["最高粮温"] >= 30:
        ctrl = "建议启动谷物冷却或夜间机械通风，将粮温降至 15℃ 以下安全区间"
    elif w["最高粮温"] >= 25:
        ctrl = "建议开启智能通风（低温时段）并加密测温，必要时充氮气调抑虫防霉"
    else:
        ctrl = "粮温已处安全区间，维持智能通风自动控制与气调护粮即可"
    return (
        f"库点：{warehouse}（{w['仓型']}，品种 {w['品种']}，仓容 {w['仓容吨']} 吨，库存 {w['库存吨']} 吨）\n"
        f"当前储粮方式：{w['储粮方式']}\n"
        f"环境管控建议：{ctrl}\n"
        f"备注：智能化粮库通过智能通风、充氮气调、谷物冷却与粮情测控，"
        f"可将储粮损耗率从传统 2%~3% 降至 1% 以下，并显著降低熏蒸药剂用量。"
    )


def get_reserve_rotation(warehouse: str = "直属库A") -> str:
    """获取储备粮轮换管理信息：宜存判定、轮换计划与出入库建议。"""
    w = WAREHOUSES[warehouse]
    status = w["储粮状态"]
    if status == "宜存":
        plan = "可继续储存，按轮换计划（一般小麦 3~5 年、稻谷 2~3 年、玉米 2~3 年）有序轮换"
    elif status == "轻度不宜存":
        plan = "品质下降，应优先纳入下一轮轮换计划，尽快安排出库"
    else:
        plan = "必须立即出库，不得继续储存，并启动质量追溯"
    return (
        f"库点：{warehouse}（品种 {w['品种']}，入库日期 {w['入库日期']}，库存 {w['库存吨']} 吨）\n"
        f"储存品质判定：{status} —— {QUALITY_GRADES[status]}\n"
        f"轮换建议：{plan}\n"
        f"品质指标：{'；'.join(f'{k} {v}' for k, v in w['品质指标'].items())}"
    )


def assess_risk(warehouse: str = "直属库A") -> str:
    """综合评估库点粮情安全风险：打分、分级并给出处置预案。"""
    w = WAREHOUSES[warehouse]
    score = 100
    reasons = []
    if w["最高粮温"] >= 30:
        score -= 30; reasons.append("最高粮温≥30℃（发热）")
    elif w["最高粮温"] >= 25:
        score -= 15; reasons.append("粮温 25~30℃（高温）")
    if w["水分"] > SAFE_MOISTURE[w["品种"]]:
        score -= 25; reasons.append("水分超安全线")
    if w["虫害密度"] >= 30:
        score -= 25; reasons.append("虫害密度严重超标")
    elif w["虫害密度"] >= 5:
        score -= 12; reasons.append("虫害密度偏高")
    if w["储粮状态"] == "重度不宜存":
        score -= 30; reasons.append("储存品质重度不宜存")
    elif w["储粮状态"] == "轻度不宜存":
        score -= 15; reasons.append("储存品质轻度不宜存")

    if score >= 90:
        level, plan = "低风险（Ⅰ级）", "维持常规监测与智能通风，无需额外处置"
    elif score >= 75:
        level, plan = "一般风险（Ⅱ级）", "加密测温测湿、加强虫霉检查，视情启动气调/局部熏蒸"
    elif score >= 60:
        level, plan = "较高风险（Ⅲ级）", "立即启动通风降温/气调，安排质量复检，纳入重点监控"
    else:
        level, plan = "高风险（Ⅳ级）", "立即启动应急处置：紧急通风/熏蒸、质量检测、上报并安排出库"
    return (
        f"库点：{warehouse}（品种 {w['品种']}）粮情安全综合评估\n"
        f"风险评分：{score}/100，等级：{level}\n"
        f"扣分因素：{'；'.join(reasons) if reasons else '无显著风险因素'}\n"
        f"处置预案：{plan}"
    )


# ---------------------------------------------------------------
# 概览数据（供前端可视化面板）
# ---------------------------------------------------------------
def get_overview(warehouse: str = "直属库A") -> Dict:
    w = WAREHOUSES[warehouse]
    return {
        "warehouse": warehouse,
        "type": w["仓型"],
        "grain": w["品种"],
        "stock": w["库存吨"],
        "capacity": w["仓容吨"],
        "avg_temp": w["粮温均温"],
        "max_temp": w["最高粮温"],
        "moisture": w["水分"],
        "humidity": w["仓湿"],
        "pest": w["虫害密度"],
        "status": w["储粮状态"],
        "temp_profile": warehouse_temp_curve(warehouse),
        "grain_profile": grain_temp_curve(warehouse),
        "humidity_profile": humidity_curve(warehouse),
        "o2": w["O2"],
        "co2": w["CO2"],
    }
