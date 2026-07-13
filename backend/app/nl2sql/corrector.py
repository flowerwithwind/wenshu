"""
SQL 自纠错器 — 分析 SQL 执行错误并自动修正

支持修正的典型错误:
- 语法错误（表名/列名拼写、缺少括号、引号不匹配）
- 列不存在（推测正确的列名）
- 表缺失或别名冲突
- 分组聚合错误（GROUP BY 缺少非聚合列）
- SQLite 特定语法兼容性问题
"""
from __future__ import annotations

import re
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from app.models.provider import get_chat_model
from app.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_RETRIES: int = 3

CORRECTION_SYSTEM_PROMPT: str = """你是 SQLite SQL 调试专家。当前 SQL 执行失败，请根据错误信息修正。

## 数据库信息
这是一个电商数据库（SQLite），包含5张表(星型模型):
- [customers]: 客户维度表(客户ID, 姓名, 年龄, 性别, 注册日期, 会员等级, 所在省份)
- [products]: 商品维度表(商品ID, 商品名称, 品类, 品牌, 成本价_元, 售价_元, 上架日期)
- [orders]: 订单事实表(订单ID, 日期, 客户ID, 商品ID, 数量, 售价_元, 订单金额_元, 折扣金额_元(NULL), 实付金额_元, 支付方式, 订单状态, 收货省份)
- [monthly_targets]: 月度销售目标表(年份, 月份, 品类, 目标销售额_万元)
- [refunds]: 退款记录表(退款ID, 订单ID, 退款金额_元, 退款日期, 退款原因(NULL))

## 表关联关系
- [orders].[客户ID] -> [customers].[客户ID]
- [orders].[商品ID] -> [products].[商品ID]
- [refunds].[订单ID] -> [orders].[订单ID]
- [monthly_targets] 与 [orders] 关联: STRFTIME('%Y', [orders].[日期])=CAST([monthly_targets].[年份] AS TEXT) AND STRFTIME('%m', [orders].[日期])=CAST([monthly_targets].[月份] AS TEXT) AND [products].[品类]=[monthly_targets].[品类]

## 完整表结构
{schema}

## SQLite 语法规则（必须严格遵守）
1. 所有表名和列名用方括号包裹，如 [表名]、[列名]
2. 别名不要用方括号，如 AS 品类名称
3. 字符串值用单引号，如 '电子'、'已完成'
4. GROUP BY 时必须 SELECT 分组列
5. JOIN 时用表别名简化，如 [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID]
6. 日期处理用 STRFTIME，如 STRFTIME('%Y', [日期]) = '2024'
7. 折扣金额可能为NULL，用 COALESCE([折扣金额_元], 0) 处理
8. SQLite 不支持 RIGHT JOIN / FULL OUTER JOIN，请用 LEFT JOIN + 交换表顺序
9. 窗口函数需要 FROM 子查询包裹
10. 计算比率时用 CAST(... AS REAL) * 1.0 避免整除

## 任务
分析错误原因并提供一个修正后的 SQL。只输出修正后的 SQL，不要任何解释。
"""


class SQLCorrector:
    """SQL 自纠错器"""

    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.max_retries: int = max_retries
        self.llm: BaseChatModel = get_chat_model(temperature=0.1, max_tokens=1024)
        self._attempt_count: int = 0

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    @property
    def exhausted(self) -> bool:
        return self._attempt_count >= self.max_retries

    def correct(
        self,
        question: str,
        sql: str,
        error: str,
        schema: str,
        history: str = "",
    ) -> str:
        """尝试修正 SQL，返回修正后的 SQL 或空字符串"""
        self._attempt_count += 1

        system_prompt = CORRECTION_SYSTEM_PROMPT.format(schema=schema)

        correction_prompt = f"""## 原始问题
{question}

## 有问题的 SQL
```sql
{sql}
```

## 错误信息
{error}
"""

        if history:
            correction_prompt += f"\n## 之前的修正尝试（供参考，避免重蹈覆辙）\n{history}\n"

        correction_prompt += (
            "\n请分析错误原因并输出修正后的 SQL（只输出 SQL，不要任何其他文字）："
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=correction_prompt),
        ]

        logger.info(
            f"SQL 自纠错 第 {self._attempt_count}/{self.max_retries} 次尝试",
            extra={"sql": sql[:150], "error": error[:150]},
        )

        response = self.llm.invoke(messages)
        corrected: str = response.content.strip()
        corrected = self._clean_sql(corrected)

        logger.debug(f"修正结果: {corrected[:200]}")
        return corrected

    def _clean_sql(self, sql: str) -> str:
        sql = re.sub(r"^```(?:sql)?\s*\n?", "", sql)
        sql = re.sub(r"\n?```\s*$", "", sql)
        sql = sql.strip()
        return sql

    def reset(self) -> None:
        """重置尝试计数（用于新问题的纠错）"""
        self._attempt_count = 0
