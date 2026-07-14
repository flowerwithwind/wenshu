"""数据源抽象接口"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataSourceMeta:
    """数据源元信息（管理端展示）"""
    id: str
    name: str
    type: str  # sqlite | mysql | postgres
    dialect: str
    description: str = ""
    is_default: bool = False
    is_builtin: bool = False
    host: str = ""
    port: int | None = None
    database: str = ""
    username: str = ""
    # 密码不在此明文暴露
    extra: dict[str, Any] = field(default_factory=dict)


class DataSource(ABC):
    """统一数据源接口：Schema 获取 + 只读 SQL 执行"""

    @property
    @abstractmethod
    def meta(self) -> DataSourceMeta:
        ...

    @property
    def dialect(self) -> str:
        return self.meta.dialect

    @abstractmethod
    def is_ready(self) -> bool:
        """数据源是否可查询"""
        ...

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """测试连接，返回 {ok, message, latency_ms?}"""
        ...

    @abstractmethod
    def get_schema_info(self) -> str:
        """供 NL2SQL Prompt 使用的 Schema 文本"""
        ...

    @abstractmethod
    def execute_sql(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        """执行只读 SQL，返回 (rows, columns)"""
        ...

    def get_table_sample(self, table_name: str, limit: int = 3) -> str:
        """默认实现：按方言拼 LIMIT 查询"""
        limit = max(1, min(int(limit), 20))
        dialect = self.dialect.lower()
        if dialect == "sqlserver":
            sql = f"SELECT TOP {limit} * FROM [{table_name}]"
        else:
            # sqlite / mysql / postgres
            quoted = self._quote_ident(table_name)
            sql = f"SELECT * FROM {quoted} LIMIT {limit}"
        try:
            rows, columns = self.execute_sql(sql)
        except Exception as e:
            return f"获取样本失败: {e}"
        if not rows:
            return f"表 {table_name} 存在但无数据"
        lines = [f"表 {table_name} 样本（{len(rows)} 行）列: {', '.join(columns)}"]
        for i, row in enumerate(rows, 1):
            lines.append(f"  {i}. {row}")
        return "\n".join(lines)

    def _quote_ident(self, name: str) -> str:
        dialect = self.dialect.lower()
        if dialect == "mysql":
            return f"`{name.replace('`', '``')}`"
        if dialect in ("postgres", "postgresql"):
            return f'"{name.replace(chr(34), chr(34)+chr(34))}"'
        return f"[{name}]"

    def close(self) -> None:
        """释放连接资源（可选）"""
        return None
