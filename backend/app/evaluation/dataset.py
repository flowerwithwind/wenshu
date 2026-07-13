"""
NL2SQL 评估数据集 — 包含人工标注的 Question-SQL 对

覆盖电商数据库(5表星型模型)的主要查询模式:
- 简单聚合 (COUNT, SUM, AVG)
- 多表 JOIN
- GROUP BY + 聚合
- ORDER BY + LIMIT
- 日期/时间查询
- NULL 处理
- 窗口函数
- 多轮指代场景
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """单个评测用例"""
    id: str                 # 唯一标识，如 "E001"
    question: str           # 自然语言问题
    sql: str                # 标准 SQL
    description: str        # 测试场景描述
    category: str           # 类别: simple / join / agg / complex / nulls / date
    must_contain: list[str] = field(default_factory=list)  # SQL 必需包含的关键词
    must_not_contain: list[str] = field(default_factory=list)  # 禁止出现的关键词
    expected_row_count: int | None = None  # 期望行数（可选）


# 完整评测集
EVAL_DATASET: list[EvalCase] = [
    # ========== 简单聚合 ==========
    EvalCase(
        id="E001",
        question="订单总数是多少",
        sql="SELECT COUNT(*) AS 订单总数 FROM [orders] WHERE [订单状态] = '已完成'",
        description="简单 COUNT 聚合",
        category="simple",
        must_contain=["COUNT"],
    ),
    EvalCase(
        id="E002",
        question="总销售额是多少",
        sql="SELECT SUM([订单金额_元]) AS 总销售额_元 FROM [orders] WHERE [订单状态] = '已完成'",
        description="SUM 聚合",
        category="simple",
        must_contain=["SUM", "订单金额_元"],
    ),
    EvalCase(
        id="E003",
        question="平均客单价是多少",
        sql="SELECT AVG([订单金额_元]) AS 平均客单价_元 FROM [orders] WHERE [订单状态] = '已完成'",
        description="AVG 聚合",
        category="simple",
        must_contain=["AVG"],
    ),

    # ========== GROUP BY 聚合 ==========
    EvalCase(
        id="E004",
        question="各省份销售额排名",
        sql="SELECT [收货省份], SUM([订单金额_元]) AS 销售额_元 FROM [orders] WHERE [订单状态] = '已完成' GROUP BY [收货省份] ORDER BY 销售额_元 DESC",
        description="GROUP BY + ORDER BY 排名",
        category="agg",
        must_contain=["GROUP BY", "ORDER BY"],
        expected_row_count=31,
    ),
    EvalCase(
        id="E005",
        question="销售额最高的品类",
        sql="SELECT [p].[品类], SUM([o].[订单金额_元]) AS 销售额_元 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] WHERE [o].[订单状态] = '已完成' GROUP BY [p].[品类] ORDER BY 销售额_元 DESC LIMIT 1",
        description="JOIN + 聚合 + LIMIT",
        category="agg",
        must_contain=["JOIN", "GROUP BY", "LIMIT"],
    ),
    EvalCase(
        id="E006",
        question="2024年各月销售额趋势",
        sql="SELECT STRFTIME('%Y-%m', [日期]) AS 月份, SUM([订单金额_元]) AS 销售额_元 FROM [orders] WHERE STRFTIME('%Y', [日期]) = '2024' AND [订单状态] = '已完成' GROUP BY 月份 ORDER BY 月份",
        description="日期聚合 + 趋势",
        category="date",
        must_contain=["STRFTIME", "GROUP BY"],
    ),

    # ========== JOIN 查询 ==========
    EvalCase(
        id="E007",
        question="各品类毛利率",
        sql="SELECT [p].[品类], ROUND((SUM([o].[订单金额_元]) - SUM([p].[成本价_元] * [o].[数量])) * 100.0 / SUM([o].[订单金额_元]), 1) AS 毛利率_百分比 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] WHERE [o].[订单状态] = '已完成' GROUP BY [p].[品类]",
        description="JOIN 计算毛利率",
        category="join",
        must_contain=["JOIN", "成本价", "毛利率"],
    ),
    EvalCase(
        id="E008",
        question="金牌会员的平均客单价",
        sql="SELECT [c].[会员等级], AVG([o].[订单金额_元]) AS 平均客单价_元 FROM [orders] [o] JOIN [customers] [c] ON [o].[客户ID] = [c].[客户ID] WHERE [c].[会员等级] = '金牌' AND [o].[订单状态] = '已完成' GROUP BY [c].[会员等级]",
        description="JOIN 客户表 + 筛选 + 聚合",
        category="join",
        must_contain=["JOIN", "customers"],
    ),

    # ========== NULL 处理 ==========
    EvalCase(
        id="E009",
        question="折扣订单占比",
        sql="SELECT CAST(SUM(CASE WHEN [折扣金额_元] IS NOT NULL THEN 1 ELSE 0 END) AS REAL) * 100.0 / COUNT(*) AS 折扣订单占比_百分比 FROM [orders] WHERE [订单状态] = '已完成'",
        description="NULL 判断 + 计算占比",
        category="nulls",
        must_contain=["NULL", "COALESCE"],
        must_not_contain=["DELETE", "DROP"],
    ),

    # ========== 退款/复杂查询 ==========
    EvalCase(
        id="E010",
        question="退款率最高的品类",
        sql="SELECT [p].[品类], CAST(COUNT(DISTINCT [r].[订单ID]) AS REAL) * 100.0 / COUNT(DISTINCT [o].[订单ID]) AS 退款率_百分比 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] LEFT JOIN [refunds] [r] ON [o].[订单ID] = [r].[订单ID] GROUP BY [p].[品类] ORDER BY 退款率_百分比 DESC",
        description="LEFT JOIN + 高级计算",
        category="complex",
        must_contain=["LEFT JOIN", "refunds"],
    ),
    EvalCase(
        id="E011",
        question="电子品类2024年达成率",
        sql="SELECT CAST(STRFTIME('%m', [o].[日期]) AS INTEGER) AS 月份, SUM([o].[订单金额_元]) AS 实际_元, [mt].[目标销售额_万元]*10000 AS 目标_元, ROUND(SUM([o].[订单金额_元])*100.0/([mt].[目标销售额_万元]*10000),1) AS 达成率_百分比 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID]=[p].[商品ID] JOIN [monthly_targets] [mt] ON STRFTIME('%Y',[o].[日期])=CAST([mt].[年份] AS TEXT) AND STRFTIME('%m',[o].[日期])=CAST([mt].[月份] AS TEXT) AND [p].[品类]=[mt].[品类] WHERE [p].[品类]='电子' AND STRFTIME('%Y',[o].[日期])='2024' GROUP BY 月份 ORDER BY 月份",
        description="3表JOIN + 达成率",
        category="complex",
        must_contain=["monthly_targets", "JOIN"],
    ),

    # ========== 时间窗口/环比 ==========
    EvalCase(
        id="E012",
        question="每月销售额环比增长",
        sql="SELECT 月份, ROUND((销售额 - LAG(销售额) OVER (ORDER BY 月份)) * 100.0 / LAG(销售额) OVER (ORDER BY 月份), 1) AS 环比增长率_百分比 FROM (SELECT STRFTIME('%Y-%m', [日期]) AS 月份, SUM([订单金额_元]) AS 销售额 FROM [orders] WHERE [订单状态] = '已完成' GROUP BY 月份)",
        description="窗口函数 LAG 计算环比",
        category="complex",
        must_contain=["LAG", "OVER"],
    ),

    # ========== TOP N ==========
    EvalCase(
        id="E013",
        question="销售额前5的商品",
        sql="SELECT [p].[商品名称], SUM([o].[订单金额_元]) AS 销售额_元 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] WHERE [o].[订单状态] = '已完成' GROUP BY [p].[商品名称] ORDER BY 销售额_元 DESC LIMIT 5",
        description="LIMIT TOP N",
        category="simple",
        must_contain=["LIMIT", "ORDER BY"],
    ),
    EvalCase(
        id="E014",
        question="退款原因分布",
        sql="SELECT COALESCE([退款原因], '未记录') AS 退款原因, COUNT(*) AS 次数 FROM [refunds] GROUP BY [退款原因] ORDER BY 次数 DESC",
        description="NULL 值分组 + COALESCE",
        category="nulls",
        must_contain=["COALESCE", "GROUP BY"],
    ),
    EvalCase(
        id="E015",
        question="支付方式使用占比",
        sql="SELECT [支付方式], COUNT(*) AS 使用次数, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM [orders] WHERE [订单状态] = '已完成'), 1) AS 占比_百分比 FROM [orders] WHERE [订单状态] = '已完成' GROUP BY [支付方式] ORDER BY 占比_百分比 DESC",
        description="子查询 + 占比计算",
        category="complex",
        must_contain=["SELECT"],
    ),
    EvalCase(
        id="E016",
        question="2024年订单最多的省份",
        sql="SELECT [收货省份], COUNT(*) AS 订单数 FROM [orders] WHERE STRFTIME('%Y', [日期]) = '2024' AND [订单状态] = '已完成' GROUP BY [收货省份] ORDER BY 订单数 DESC LIMIT 1",
        description="日期筛选 + 聚合",
        category="date",
        must_contain=["STRFTIME"],
    ),
    EvalCase(
        id="E017",
        question="各品牌平均售价",
        sql="SELECT [品牌], ROUND(AVG([售价_元]), 1) AS 平均售价_元 FROM [products] GROUP BY [品牌] ORDER BY 平均售价_元 DESC",
        description="简单 GROUP BY",
        category="simple",
        must_contain=["AVG", "GROUP BY"],
    ),
    EvalCase(
        id="E018",
        question="2024年销售额同比增长率",
        sql="WITH 年度销售 AS (SELECT STRFTIME('%Y', [日期]) AS 年份, SUM([订单金额_元]) AS 销售额 FROM [orders] WHERE [订单状态] = '已完成' AND STRFTIME('%Y', [日期]) IN ('2023', '2024') GROUP BY 年份) SELECT 年份, 销售额, ROUND((销售额 - LAG(销售额) OVER (ORDER BY 年份)) * 100.0 / LAG(销售额) OVER (ORDER BY 年份), 1) AS 同比增长率_百分比 FROM 年度销售 ORDER BY 年份 DESC LIMIT 1",
        description="CTE + 窗口函数同比增长",
        category="complex",
        must_contain=["LAG", "OVER", "WITH"],
    ),
    EvalCase(
        id="E019",
        question="各省份退款金额排名",
        sql="SELECT [o].[收货省份], ROUND(SUM(COALESCE([r].[退款金额_元], 0)), 1) AS 退款总额_元 FROM [orders] [o] LEFT JOIN [refunds] [r] ON [o].[订单ID] = [r].[订单ID] GROUP BY [o].[收货省份] ORDER BY 退款总额_元 DESC",
        description="LEFT JOIN + COALESCE + 排名",
        category="join",
        must_contain=["LEFT JOIN", "COALESCE"],
    ),
    EvalCase(
        id="E020",
        question="男性和女性客户的订单数对比",
        sql="SELECT [c].[性别], COUNT(*) AS 订单数 FROM [orders] [o] JOIN [customers] [c] ON [o].[客户ID] = [c].[客户ID] GROUP BY [c].[性别]",
        description="JOIN + 分组对比",
        category="join",
        must_contain=["JOIN", "GROUP BY"],
    ),
]


def get_eval_case(case_id: str) -> EvalCase | None:
    """按 ID 获取评测用例"""
    for case in EVAL_DATASET:
        if case.id == case_id:
            return case
    return None


def get_cases_by_category(category: str) -> list[EvalCase]:
    """按类别筛选评测用例"""
    return [c for c in EVAL_DATASET if c.category == category]


def list_categories() -> list[str]:
    """列出所有评测类别"""
    return list({c.category for c in EVAL_DATASET})
