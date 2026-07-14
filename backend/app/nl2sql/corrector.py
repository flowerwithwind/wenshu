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
from app.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_RETRIES: int = 3

CORRECTION_SYSTEM_PROMPT: str = """你是 SQL 调试专家。当前 SQL 执行失败，请根据错误信息和真实 Schema 修正。

## 完整表结构（以此为准，禁止编造表/列）
{schema}

## 通用规则
1. 只输出一条可执行的 SELECT，无解释文字
2. 表名/列名必须来自上方 Schema
3. GROUP BY 需包含非聚合列（注意 MySQL ONLY_FULL_GROUP_BY）
4. 字符串用单引号；只读查询
5. 方言：Schema 末尾若标注 mysql，禁止方括号 []，改用反引号或不用引号；sqlite 可用方括号；日期函数按方言选择
6. 计算比率用 CAST(... AS REAL) 或等价写法避免整除

## 任务
分析错误原因并给出修正后的 SQL。只输出 SQL。
"""


class SQLCorrector:
    """SQL 自纠错器（LLM 延迟初始化，避免遮蔽/无网络时导入失败）"""

    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.max_retries: int = max_retries
        self._llm: BaseChatModel | None = None
        self._attempt_count: int = 0

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_chat_model(temperature=0.1, max_tokens=1024)
        return self._llm

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

        dialect = "sqlite"
        try:
            from app.datasources.context import get_current_datasource

            dialect = (get_current_datasource().dialect or "sqlite").lower()
        except Exception:
            pass

        system_prompt = CORRECTION_SYSTEM_PROMPT.format(schema=schema)
        if dialect in ("mysql", "mariadb"):
            system_prompt += (
                "\n\n## 重要：当前方言是 MySQL\n"
                "必须使用反引号标识符 `col`，禁止方括号 [col]；"
                "日期用 DATE_FORMAT/YEAR/MONTH。"
            )
        elif dialect in ("postgres", "postgresql"):
            system_prompt += (
                "\n\n## 重要：当前方言是 PostgreSQL\n"
                "禁止方括号 [col]；日期用 to_char/date_trunc。"
            )

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
        if dialect in ("mysql", "mariadb"):
            corrected = re.sub(r"\[([^\]]+)\]", r"`\1`", corrected)
        elif dialect in ("postgres", "postgresql"):
            corrected = re.sub(r"\[([^\]]+)\]", r'"\1"', corrected)

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
