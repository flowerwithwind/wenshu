"""
生成器模块 - 基于 DeepSeek-V4-Pro 的智能回答生成
"""
import re
import json
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


SYSTEM_PROMPT = """你是一个专业的数据分析助手。你的任务是基于提供的参考资料，准确回答用户的数据相关问题。

请严格遵循以下规则：
1. 只根据提供的"参考资料"内容回答问题，不要使用你自己的知识
2. 如果参考资料中没有相关信息，请明确告知用户"根据现有数据无法回答该问题"
3. 在回答中引用具体的数据来源（标注来源编号）
4. 如果问题涉及数值计算或统计，请给出清晰的计算过程
5. 使用中文回答，保持专业、清晰、简洁的风格
6. 当数据支持时，优先使用列表、表格等形式组织信息
7. 对于包含数值数据的问题，在回答末尾用```chart_data```标记包裹JSON格式的图表数据，格式为：
   ```chart_data
   {"type": "bar|line|pie", "labels": ["标签1"], "datasets": [{"label": "系列名", "data": [数值]}]}
   ```
"""


class RAGGenerator:
    """RAG 生成器，使用 DeepSeek 模型生成回答"""

    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise ValueError(
                "请设置环境变量 DEEPSEEK_API_KEY，"
                "可在 https://platform.deepseek.com 获取"
            )

        self.llm = ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=2048,
        )

    def generate(
        self, question: str, context: str, sources: List[Any]
    ) -> Dict[str, Any]:
        """生成回答"""
        if not context:
            return {
                "answer": "当前知识库中没有与您问题相关的数据。请先上传或加载相关数据集。",
                "chart_data": None,
            }

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"""## 参考资料

{context}

## 用户问题

{question}

请基于以上参考资料回答问题。"""),
        ]

        response = self.llm.invoke(messages)
        answer = response.content

        chart_data = self._extract_chart_data(answer)
        if chart_data:
            answer = self._clean_chart_markdown(answer)

        return {"answer": answer, "chart_data": chart_data}

    def _extract_chart_data(self, text: str) -> Optional[Dict]:
        """从回答中提取图表数据"""
        pattern = r"```chart_data\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _clean_chart_markdown(self, text: str) -> str:
        """移除回答中的 chart_data 标记"""
        pattern = r"```chart_data\s*\n.*?\n```"
        return re.sub(pattern, "", text, flags=re.DOTALL).strip()

    def generate_stream(self, question: str, context: str):
        """流式生成回答"""
        if not context:
            yield "当前知识库中没有与您问题相关的数据。请先上传或加载相关数据集。"
            return

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"""## 参考资料

{context}

## 用户问题

{question}

请基于以上参考资料回答问题。"""),
        ]

        for chunk in self.llm.stream(messages):
            if chunk.content:
                yield chunk.content