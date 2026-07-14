"""
NL2SQL 翻译器 - 使用 DeepSeek 将自然语言转换为 SQL 查询
RAG 作为辅助：提供表 Schema 和相似问题示例
"""
from __future__ import annotations

import re
import json
from typing import Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from app.models.provider import get_chat_model
from app.nl2sql.database import get_schema_info
from app.logger import get_logger

logger = get_logger(__name__)


# 内置电商演示库（SQLite）专用提示
NL2SQL_SYSTEM_PROMPT_SQLITE: str = """你是 SQLite 查询生成器。根据用户问题和表结构生成 SELECT 语句。

## 数据库信息
这是一个电商数据库，包含5张表(星型模型):
- [customers]: 客户维度表(客户ID, 姓名, 年龄, 性别, 注册日期, 会员等级, 所在省份)
- [products]: 商品维度表(商品ID, 商品名称, 品类, 品牌, 成本价_元, 售价_元, 上架日期)
- [orders]: 订单事实表(订单ID, 日期, 客户ID, 商品ID, 数量, 售价_元, 订单金额_元, 折扣金额_元, 实付金额_元, 支付方式, 订单状态, 收货省份)
- [monthly_targets]: 月度销售目标表(年份, 月份, 品类, 目标销售额_万元)
- [refunds]: 退款记录表(退款ID, 订单ID, 退款金额_元, 退款日期, 退款原因)

## 表关联关系
- [orders].[客户ID] -> [customers].[客户ID] : 查询客户维度信息时 JOIN
- [orders].[商品ID] -> [products].[商品ID] : 查询商品维度信息时 JOIN
- [refunds].[订单ID] -> [orders].[订单ID] : 查询退款信息时 JOIN
- 达成率分析: orders与monthly_targets通过 STRFTIME('%Y', 日期)=年份 AND STRFTIME('%m', 日期)=月份 AND 品类 关联

## 完整表结构
{schema}

## SQL 语法规则（必须严格遵守）
1. 所有表名和列名必须用方括号包裹，如 [表名]、[列名]
2. 别名不要用方括号，如 AS 品类名称
3. 字符串值用单引号，如 '电子'、'已完成'
4. GROUP BY 时必须 SELECT 分组列
5. JOIN 时用表别名简化，如 [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID]
6. 日期处理用 STRFTIME，如 STRFTIME('%Y', [日期]) = '2024'
7. 折扣金额可能为NULL，用 COALESCE([折扣金额_元], 0) 处理
8. 计算比率时用 CAST(... AS REAL) 避免整除

## 表选择规则
- 问题含"客户"、"会员"、"年龄"、"性别" → 考虑 JOIN [customers]
- 问题含"商品"、"产品"、"品牌"、"品类"、"成本"、"毛利率" → 考虑 JOIN [products]
- 问题含"退款"、"退货" → 考虑 JOIN [refunds]
- 问题含"目标"、"达成率"、"KPI" → 考虑 JOIN [monthly_targets]
- 问题含"销售额"、"订单"、"支付"、"省份" → 主表 [orders]
- 仅查询客户信息 → 主表 [customers]
- 仅查询商品信息 → 主表 [products]

## 参考示例
{examples}

## 对话历史
{history}

如果对话历史中包含指代（如"那个省""上个月""它"），请结合历史推断具体指向。
如果用户说"刚才那个""和去年比呢""再按品类分一下"，请结合上一轮的 SQL 和回答来生成新的 SQL。

## 输出
只输出 SQL 语句，无任何其他文字。若无法翻译则输出 CANNOT_TRANSLATE。
"""

# 多数据源通用提示（MySQL / PostgreSQL 等）
NL2SQL_SYSTEM_PROMPT_GENERIC: str = """你是 SQL 查询生成器。根据用户问题和**当前数据源的真实表结构**生成只读 SELECT 语句。

## 当前数据库方言
{dialect}

## 完整表结构（以此为准，不要臆造表名/列名）
{schema}

## SQL 语法规则（必须严格遵守）
{dialect_rules}

## 通用规则
1. 只生成 SELECT（可含 JOIN / 子查询 / 聚合 / 窗口函数）
2. 必须使用上方 schema 中真实存在的表名与列名
3. GROUP BY 时 SELECT 聚合表达式或分组列
4. 字符串用单引号；LIMIT 控制结果规模（默认不超过 100）
5. 不要使用 SQLite 方括号标识符 [name]（除非方言是 sqlite）
6. 不要输出解释文字，只输出一条 SQL

## 参考示例（仅当与当前 schema 相关时参考；列名以 schema 为准）
{examples}

## 对话历史
{history}

## 输出
只输出 SQL 语句。若无法翻译则输出 CANNOT_TRANSLATE。
"""

# 兼容旧名称
NL2SQL_SYSTEM_PROMPT = NL2SQL_SYSTEM_PROMPT_SQLITE


def _normalize_dialect(dialect: str | None) -> str:
    d = (dialect or "sqlite").lower().strip()
    if d in ("postgresql", "postgres"):
        return "postgres"
    if d in ("mariadb",):
        return "mysql"
    return d


def _dialect_rules(dialect: str) -> str:
    d = _normalize_dialect(dialect)
    if d == "mysql":
        return """1. 标识符用反引号，如 `orders`、`order_id`（或无需引号的合法标识符）
2. 禁止使用方括号 [table]（那是 SQL Server/SQLite 风格）
3. 日期：DATE_FORMAT(col, '%Y-%m')、YEAR(col)、MONTH(col)
4. 字符串拼接用 CONCAT()；空值 COALESCE()
5. 限行：LIMIT n"""
    if d == "postgres":
        return """1. 标识符用双引号（如有必要）"orders"；普通小写可不加
2. 禁止使用方括号 [table]
3. 日期：to_char(col, 'YYYY-MM')、date_trunc('month', col)
4. 限行：LIMIT n"""
    return """1. 标识符用方括号，如 [orders]、[order_id]
2. 日期：STRFTIME('%Y-%m', col)
3. 限行：LIMIT n"""


def _resolve_dialect(explicit: str | None = None) -> str:
    if explicit:
        return _normalize_dialect(explicit)
    try:
        from app.datasources.context import get_current_datasource

        return _normalize_dialect(get_current_datasource().dialect)
    except Exception:
        return "sqlite"

FEW_SHOT_EXAMPLES: str = """问题: 销售额最高的品类
SQL: SELECT [p].[品类], SUM([o].[订单金额_元]) AS 销售额_元 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] WHERE [o].[订单状态] = '已完成' GROUP BY [p].[品类] ORDER BY 销售额_元 DESC LIMIT 1

问题: 2024年各月销售额趋势
SQL: SELECT STRFTIME('%Y-%m', [日期]) AS 月份, SUM([订单金额_元]) AS 销售额_元 FROM [orders] WHERE STRFTIME('%Y', [日期]) = '2024' AND [订单状态] = '已完成' GROUP BY 月份 ORDER BY 月份

问题: 金牌会员的平均客单价
SQL: SELECT [c].[会员等级], AVG([o].[订单金额_元]) AS 平均客单价_元 FROM [orders] [o] JOIN [customers] [c] ON [o].[客户ID] = [c].[客户ID] WHERE [c].[会员等级] = '金牌' AND [o].[订单状态] = '已完成' GROUP BY [c].[会员等级]

问题: 折扣订单占比
SQL: SELECT CAST(SUM(CASE WHEN [折扣金额_元] IS NOT NULL THEN 1 ELSE 0 END) AS REAL) * 100.0 / COUNT(*) AS 折扣订单占比_百分比 FROM [orders] WHERE [订单状态] = '已完成'

问题: 退款率最高的品类
SQL: SELECT [p].[品类], CAST(COUNT(DISTINCT [r].[订单ID]) AS REAL) * 100.0 / COUNT(DISTINCT [o].[订单ID]) AS 退款率_百分比 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] LEFT JOIN [refunds] [r] ON [o].[订单ID] = [r].[订单ID] GROUP BY [p].[品类] ORDER BY 退款率_百分比 DESC

问题: 每月销售额环比增长
SQL: SELECT 月份, ROUND((销售额 - LAG(销售额) OVER (ORDER BY 月份)) * 100.0 / LAG(销售额) OVER (ORDER BY 月份), 1) AS 环比增长率_百分比 FROM (SELECT STRFTIME('%Y-%m', [日期]) AS 月份, SUM([订单金额_元]) AS 销售额 FROM [orders] WHERE [订单状态] = '已完成' GROUP BY 月份)

问题: 电子品类达成率
SQL: SELECT CAST(STRFTIME('%m', [o].[日期]) AS INTEGER) AS 月份, SUM([o].[订单金额_元]) AS 实际_元, [mt].[目标销售额_万元]*10000 AS 目标_元, ROUND(SUM([o].[订单金额_元])*100.0/([mt].[目标销售额_万元]*10000),1) AS 达成率_百分比 FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID]=[p].[商品ID] JOIN [monthly_targets] [mt] ON STRFTIME('%Y',[o].[日期])=CAST([mt].[年份] AS TEXT) AND STRFTIME('%m',[o].[日期])=CAST([mt].[月份] AS TEXT) AND [p].[品类]=[mt].[品类] WHERE [p].[品类]='电子' AND STRFTIME('%Y',[o].[日期])='2024' GROUP BY 月份 ORDER BY 月份"""


class NL2SQLTranslator:
    """NL2SQL 翻译器（LLM 延迟初始化）"""

    def __init__(self) -> None:
        self._llm: BaseChatModel | None = None

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_chat_model(temperature=0.1, max_tokens=1024)
        return self._llm

    def translate(
        self,
        question: str,
        schema: str = "",
        rag_context: str = "",
        history_context: str = "",
        dialect: str | None = None,
    ) -> str:
        """将自然语言问题翻译为 SQL（按数据源方言生成）"""
        dialect_name = _resolve_dialect(dialect)

        if not schema:
            try:
                from app.datasources.context import get_current_datasource

                schema = get_current_datasource().get_schema_info()
            except Exception:
                schema = get_schema_info()

        # 构建示例：外部数据源不要强行注入内置电商 SQLite few-shot
        examples: str = FEW_SHOT_EXAMPLES if dialect_name == "sqlite" else "（无固定示例，严格依据 schema）"
        if rag_context:
            rag_examples: str = self._extract_examples_from_context(rag_context)
            if rag_examples:
                examples = rag_examples
            elif dialect_name == "sqlite":
                examples = rag_context[:2000] + "\n\n" + FEW_SHOT_EXAMPLES
            else:
                examples = rag_context[:1500]

        history = history_context if history_context else "无对话历史"
        if dialect_name == "sqlite":
            system_prompt = NL2SQL_SYSTEM_PROMPT_SQLITE.format(
                schema=schema,
                examples=examples,
                history=history,
            )
        else:
            system_prompt = NL2SQL_SYSTEM_PROMPT_GENERIC.format(
                dialect=dialect_name,
                schema=schema,
                dialect_rules=_dialect_rules(dialect_name),
                examples=examples,
                history=history,
            )

        user_message: str = f"## 用户问题\n{question}"

        if rag_context:
            user_message = (
                f"## 参考资料（同义词、领域映射）\n{rag_context[:2000]}\n\n"
                f"## 用户问题\n{question}"
            )

        messages: list = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        response = self.llm.invoke(messages)
        sql: str = response.content.strip()

        # 清理可能的 markdown 包裹
        sql = self._clean_sql(sql)
        sql = self._normalize_sql_for_dialect(sql, dialect_name)

        if not self._is_valid_sql(sql):
            logger.warning(f"NL2SQL 返回无效结果: {sql[:200]}")

        return sql

    def _normalize_sql_for_dialect(self, sql: str, dialect: str) -> str:
        """把误用的 SQLite 方括号标识符转换为目标方言写法。"""
        d = _normalize_dialect(dialect)
        if d == "sqlite" or "[" not in sql:
            return sql
        # [ident] -> `ident` (mysql) or "ident" (postgres)
        def repl(m: re.Match[str]) -> str:
            name = m.group(1)
            if d == "mysql":
                return f"`{name}`"
            if d == "postgres":
                return f'"{name}"'
            return m.group(0)

        return re.sub(r"\[([^\]]+)\]", repl, sql)

    def _extract_examples_from_context(self, context: str) -> str:
        """从 RAG 上下文中提取 Question-SQL 示例"""
        lines: list[str] = context.split('\n')
        examples: list[str] = []
        in_example: bool = False
        current_question: str = ""
        current_sql: str = ""

        for line in lines:
            if '【示例问题】' in line:
                if current_question and current_sql:
                    examples.append(f"问题: {current_question}\nSQL: {current_sql}")
                current_question = line.split('【示例问题】', 1)[1].strip()
                current_sql = ""
                in_example = True
            elif '【对应SQL】' in line and in_example:
                current_sql = line.split('【对应SQL】', 1)[1].strip()
            elif '【领域术语】' in line or '【数据表】' in line:
                if current_question and current_sql:
                    examples.append(f"问题: {current_question}\nSQL: {current_sql}")
                current_question = ""
                current_sql = ""
                in_example = False

        if current_question and current_sql:
            examples.append(f"问题: {current_question}\nSQL: {current_sql}")

        if examples:
            return '\n\n'.join(examples[:4])
        return ""

    def _clean_sql(self, sql: str) -> str:
        """清理 SQL 中的 markdown 标记"""
        sql = re.sub(r"^```(?:sql)?\s*\n?", "", sql)
        sql = re.sub(r"\n?```\s*$", "", sql)
        sql = sql.strip()
        return sql

    def _is_valid_sql(self, sql: str) -> bool:
        """检查是否是有效的 SQL 语句"""
        if not sql:
            return False
        sql_upper: str = sql.upper().strip()
        if sql_upper.startswith("CANNOT_TRANSLATE"):
            return False
        if sql_upper.startswith("无法"):
            return False
        if not sql_upper.startswith("SELECT"):
            return False
        return True


class AnswerGenerator:
    """基于 SQL 执行结果生成自然语言回答"""

    ANSWER_SYSTEM_PROMPT: str = """你是一个专业的数据分析助手。根据 SQL 查询结果生成清晰、专业的回答。

## 规则
1. 用中文回答，保持专业、简洁
2. 如果结果包含多行数据，优先使用列表或表格组织
3. 对关键数值进行简单解读
4. 当数据支持图表展示时，在回答末尾用```chart_data```标记包裹JSON格式的图表数据
5. 图表数据格式：
   ```chart_data
   {"type": "bar|line|pie", "title": "图表标题", "colorScheme": "indigo|ocean|forest|sunset|rose|violet", "labels": ["标签1"], "datasets": [{"label": "系列名", "data": [数值]}]}
   ```
6. 图表类型选择规则：
   - 饼图(pie)：占比类问题（如各品类销售占比、支付方式分布）
   - 柱状图(bar)：排名对比（如TOP5省份、各品类对比）
   - 折线图(line)：时间趋势（如月度销售额、累计增长）
   - 图表标题(title)：添加简短的图表标题
   - 颜色方案(colorScheme)：从 ['indigo','ocean','forest','sunset','rose','violet'] 中选择，默认为 indigo
7. 如果 SQL 执行失败或无结果，如实告知用户
"""

    def __init__(self) -> None:
        self._llm: BaseChatModel | None = None

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_chat_model(temperature=0.3, max_tokens=2048)
        return self._llm

    def generate(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """生成自然语言回答"""
        if not rows:
            result_text: str = "查询结果为空"
        else:
            result_lines: list[str] = [f"列: {', '.join(columns)}"]
            result_lines.append(f"共 {len(rows)} 行数据:")
            for i, row in enumerate(rows[:50]):
                result_lines.append(f"  {i+1}. {dict(row)}")
            if len(rows) > 50:
                result_lines.append(f"  ... 共 {len(rows)} 行，仅显示前 50 行")
            result_text = "\n".join(result_lines)

        messages: list = [
            SystemMessage(content=self.ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=f"""## 用户问题
{question}

## 执行的 SQL
{sql}

## 查询结果
{result_text}

请基于以上查询结果回答用户问题。"""),
        ]

        response = self.llm.invoke(messages)
        answer: str = response.content

        chart_data: dict[str, Any] | None = self._extract_chart_data(answer)
        if chart_data:
            answer = self._clean_chart_markdown(answer)

        return {"answer": answer, "chart_data": chart_data}

    def generate_stream(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ):
        """流式生成回答"""
        if not rows:
            result_text: str = "查询结果为空"
        else:
            result_lines: list[str] = [f"列: {', '.join(columns)}"]
            result_lines.append(f"共 {len(rows)} 行数据:")
            for i, row in enumerate(rows[:50]):
                result_lines.append(f"  {i+1}. {dict(row)}")
            if len(rows) > 50:
                result_lines.append(f"  ... 共 {len(rows)} 行，仅显示前 50 行")
            result_text = "\n".join(result_lines)

        messages: list = [
            SystemMessage(content=self.ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=f"""## 用户问题
{question}

## 执行的 SQL
{sql}

## 查询结果
{result_text}

请基于以上查询结果回答用户问题。"""),
        ]

        for chunk in self.llm.stream(messages):
            if chunk.content:
                yield chunk.content

    def _extract_chart_data(self, text: str) -> dict[str, Any] | None:
        pattern: str = r"```chart_data\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _clean_chart_markdown(self, text: str) -> str:
        pattern: str = r"```chart_data\s*\n.*?\n```"
        return re.sub(pattern, "", text, flags=re.DOTALL).strip()


class RecommendedQuestionsGenerator:
    """基于当前问题和回答生成推荐问题"""

    RECOMMEND_SYSTEM_PROMPT: str = """你是数据问答推荐引擎。根据用户刚才的提问、系统回答和**真实 Schema**，生成3个后续问题。

## 规则
1. 问题必须能被当前 Schema 中的表/列回答，禁止编造不存在的业务实体
2. 问题多样化：计数、分组排名、时间趋势、关联分析等
3. 优先能出图的问题（趋势、排名、占比）
4. 简洁，20字以内
5. 只输出 JSON 数组：["问题1","问题2","问题3"]

## 当前数据源表结构
{schema}"""

    def __init__(self) -> None:
        self._llm: BaseChatModel | None = None

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_chat_model(temperature=0.5, max_tokens=512)
        return self._llm

    def generate(self, question: str, answer: str, schema: str) -> list[str]:
        """生成推荐问题"""
        try:
            messages: list = [
                SystemMessage(content=self.RECOMMEND_SYSTEM_PROMPT.format(schema=schema)),
                HumanMessage(content=f"""用户刚刚提问: {question}

系统回答摘要: {answer[:500]}

请根据以上信息，推荐3个后续问题。"""),
            ]
            response = self.llm.invoke(messages)
            text: str = response.content.strip()
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                questions: list[str] = json.loads(match.group())
                return questions[:3]
            return []
        except Exception as e:
            logger.warning(f"推荐问题生成失败: {e}")
            return []
