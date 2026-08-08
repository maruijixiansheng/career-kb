"""DeepSeek API 客户端封装 (基于 LangChain ChatOpenAI 兼容接口)"""

import json
import logging
import re
from typing import Optional, AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..config import settings

# LLM 审计日志
audit_logger = logging.getLogger("career-kb.llm-audit")


class LLMClient:
    """DeepSeek API 异步客户端 (通过 LangChain ChatOpenAI)"""

    def __init__(self):
        self._simple_llm = ChatOpenAI(
            model=settings.LLM_MODEL_SIMPLE,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=4096,
            timeout=120,
            max_retries=3,
        )
        self._powerful_llm = ChatOpenAI(
            model=settings.LLM_MODEL_POWERFUL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=4096,
            timeout=120,
            max_retries=3,
        )
        self.simple_model = settings.LLM_MODEL_SIMPLE
        self.powerful_model = settings.LLM_MODEL_POWERFUL

    def _get_llm(self, model: str, temperature: float, max_tokens: int) -> ChatOpenAI:
        """获取或创建指定配置的 LLM 实例"""
        return ChatOpenAI(
            model=model,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=60,
            max_retries=2,
        )

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """同步聊天 (等待完整响应)"""
        model_name = model or self.simple_model
        llm = self._get_llm(model_name, temperature, max_tokens)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        # 估算输入 token 数
        input_chars = len(system_prompt) + len(user_message)
        input_tokens_est = input_chars // 4

        response = await llm.ainvoke(messages)

        # 审计日志
        output_tokens_est = len(response.content) // 4
        # DeepSeek 定价: chat ~$0.14/1M input, $0.28/1M output
        cost_est = (input_tokens_est * 0.14 + output_tokens_est * 0.28) / 1_000_000
        audit_logger.info(
            f"LLM call | model={model_name} | "
            f"input_tokens≈{input_tokens_est} | output_tokens≈{output_tokens_est} | "
            f"cost_est≈${cost_est:.6f} | temp={temperature} | max_tokens={max_tokens}"
        )

        return response.content

    async def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> dict:
        """聊天并返回 JSON 格式结果"""
        text = await self.chat(
            system_prompt=system_prompt + "\n请只返回 JSON 格式，不要包含其他文字。",
            user_message=user_message,
            model=model,
            temperature=temperature,
        )
        # 提取 JSON — 处理 markdown 代码块和多余文本
        text = text.strip()
        # 移除 markdown 代码块标记
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # 提取最外层 JSON — 先匹配对象（更常见），再匹配数组
        extracted = None
        for pattern in [r'\{.*\}', r'\[.*\]']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    extracted = json.loads(match.group(0))
                    return extracted
                except json.JSONDecodeError:
                    continue  # 匹配到内层嵌套，继续尝试
        # 如果正则都失败，尝试直接解析
        return json.loads(text)

    async def chat_stream(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """流式聊天 (逐 token 返回)"""
        llm = self._get_llm(model or self.powerful_model, temperature, max_tokens)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content


# 全局单例
llm_client = LLMClient()
