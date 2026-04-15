"""
温度参数功能测试
测试 run_agent 和 routes_v3 的 temperature 参数支持
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agent.graph import run_agent, create_aviation_agent


class TestTemperatureParameter:
    """温度参数测试类"""

    def test_run_agent_accepts_temperature(self):
        """测试 run_agent 接受 temperature 参数"""
        import inspect
        sig = inspect.signature(run_agent)
        assert 'temperature' in sig.parameters
        assert sig.parameters['temperature'].default == 0.3

    def test_create_aviation_agent_accepts_temperature(self):
        """测试 create_aviation_agent 接受 temperature 参数"""
        import inspect
        sig = inspect.signature(create_aviation_agent)
        assert 'temperature' in sig.parameters
        assert sig.parameters['temperature'].default == 0.3

    @pytest.mark.asyncio
    async def test_run_agent_passes_temperature_to_llm(self):
        """测试 temperature 参数传递到 LLM"""
        with patch('app.agent.graph.get_langchain_llm') as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value={"messages": []})
            mock_get_llm.return_value = mock_llm

            # 测试自定义温度
            await run_agent(
                user_query="test",
                temperature=0.7,
            )

            # 验证 get_langchain_llm 被调用时使用了正确的温度
            mock_get_llm.assert_called_once()
            call_kwargs = mock_get_llm.call_args[1]
            assert call_kwargs['temperature'] == 0.7

    @pytest.mark.asyncio
    async def test_run_agent_default_temperature(self):
        """测试默认温度值"""
        with patch('app.agent.graph.get_langchain_llm') as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value={"messages": []})
            mock_get_llm.return_value = mock_llm

            # 不指定温度，使用默认值
            await run_agent(user_query="test")

            # 验证使用了默认温度 0.3
            call_kwargs = mock_get_llm.call_args[1]
            assert call_kwargs['temperature'] == 0.3

    def test_temperature_parameter_type(self):
        """测试温度参数类型注解"""
        import inspect
        sig = inspect.signature(run_agent)
        param = sig.parameters['temperature']
        # 类型注解可能是字符串形式或实际类型
        annotation = str(param.annotation)
        assert 'float' in annotation.lower()


class TestTemperatureInAPI:
    """API 层温度参数测试"""

    @pytest.mark.asyncio
    async def test_routes_v3_accepts_temperature(self):
        """测试 API 接受 temperature 字段"""
        from app.api.routes_v3 import agent_chat

        # 模拟请求
        request = {
            "query": "test query",
            "temperature": 0.8
        }

        with patch('app.api.routes_v3.run_agent') as mock_run_agent:
            mock_run_agent.return_value = {
                "success": True,
                "answer": "test answer",
            }

            await agent_chat(request)

            # 验证 temperature 被传递
            call_kwargs = mock_run_agent.call_args[1]
            assert call_kwargs['temperature'] == 0.8

    @pytest.mark.asyncio
    async def test_routes_v3_default_temperature(self):
        """测试 API 默认温度"""
        from app.api.routes_v3 import agent_chat

        request = {
            "query": "test query"
        }

        with patch('app.api.routes_v3.run_agent') as mock_run_agent:
            mock_run_agent.return_value = {
                "success": True,
                "answer": "test answer",
            }

            await agent_chat(request)

            # 验证使用了默认温度
            call_kwargs = mock_run_agent.call_args[1]
            assert call_kwargs['temperature'] == 0.3
