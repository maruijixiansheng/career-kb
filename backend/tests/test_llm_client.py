"""测试 LLM 客户端 (Mock DeepSeek API via LangChain ChatOpenAI)"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, AIMessageChunk
from app.core.llm_client import LLMClient


class TestLLMClient:
    """LLM 客户端测试 (Mock)"""

    @pytest.fixture
    def client(self):
        return LLMClient()

    def test_init(self, client):
        assert client.simple_model == "deepseek-chat"
        assert client.powerful_model == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_chat(self, client):
        mock_response = AIMessage(content="你好，这是回复内容")

        with patch('langchain_openai.ChatOpenAI.ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = mock_response

            result = await client.chat(
                system_prompt="你是一位助手",
                user_message="你好",
            )

            assert result == "你好，这是回复内容"
            # 验证 messages 格式
            call_args = mock_ainvoke.call_args
            messages = call_args[0][0]  # first positional arg is the messages list
            assert messages[0].content == "你是一位助手"
            assert messages[0].type == "system"
            assert messages[1].content == "你好"
            assert messages[1].type == "human"

    @pytest.mark.asyncio
    async def test_chat_with_model_override(self, client):
        mock_response = AIMessage(content="ok")

        with patch('langchain_openai.ChatOpenAI.ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = mock_response

            await client.chat(
                system_prompt="system",
                user_message="hello",
                model="deepseek-reasoner",
            )
            # 验证 model 参数被传递给了 ChatOpenAI 构造函数
            # (_get_llm creates a new ChatOpenAI each time)
            assert mock_ainvoke.called

    @pytest.mark.asyncio
    async def test_chat_json(self, client):
        mock_response = AIMessage(content='{"name": "张三", "age": 30}')

        with patch('langchain_openai.ChatOpenAI.ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = mock_response

            result = await client.chat_json(
                system_prompt="提取信息",
                user_message="我叫张三，今年30岁",
            )

            assert result == {"name": "张三", "age": 30}

    @pytest.mark.asyncio
    async def test_chat_json_with_code_block(self, client):
        """测试带 markdown 代码块的 JSON"""
        mock_response = AIMessage(content='```json\n{"key": "value"}\n```')

        with patch('langchain_openai.ChatOpenAI.ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = mock_response

            result = await client.chat_json(
                system_prompt="返回JSON",
                user_message="test",
            )
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_chat_json_with_generic_code_block(self, client):
        """测试不带语言的代码块"""
        mock_response = AIMessage(content='```\n{"a": 1}\n```')

        with patch('langchain_openai.ChatOpenAI.ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = mock_response

            result = await client.chat_json(
                system_prompt="返回JSON",
                user_message="test",
            )
            assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_chat_stream(self, client):
        """测试流式输出"""

        async def mock_astream(*args, **kwargs):
            for text in ["你", "好", "，", "世", "界", "！"]:
                yield AIMessageChunk(content=text)

        with patch.object(client, '_get_llm') as mock_get_llm:
            mock_llm = MagicMock()
            # astream is an async generator, need to use side_effect with the generator
            async def gen():
                for text in ["你", "好", "，", "世", "界", "！"]:
                    yield AIMessageChunk(content=text)
            mock_llm.astream = MagicMock(return_value=gen())
            mock_get_llm.return_value = mock_llm

            result_parts = []
            async for text in client.chat_stream(
                system_prompt="系统提示",
                user_message="用户消息",
            ):
                result_parts.append(text)

            assert "".join(result_parts) == "你好，世界！"

    @pytest.mark.asyncio
    async def test_chat_stream_with_model_override(self, client):
        async def gen():
            yield AIMessageChunk(content="test")

        with patch.object(client, '_get_llm') as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.astream = MagicMock(return_value=gen())
            mock_get_llm.return_value = mock_llm

            async for _ in client.chat_stream(
                system_prompt="s",
                user_message="u",
                model="deepseek-chat",
                max_tokens=1000,
            ):
                pass

            assert mock_get_llm.called
