"""
API集成测试
测试FastAPI端点的HTTP请求/响应
"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.api.schemas import WeatherAnalyzeRequest, WeatherAnalyzeResponse
from app.core.llm_client import LLMResponse


# ==================== /analyze端点测试 ====================

class TestAnalyzeEndpoint:
    """分析端点测试类"""

    @pytest.mark.asyncio
    async def test_analyze_with_metar_raw_success(self, mock_llm_client, sample_metar_vfr):
        """测试使用METAR原文成功分析"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_vfr,
                        "user_query": "当前天气适合飞行吗？",
                        "role": "pilot",
                        "session_id": "test-session-123"
                    }
                )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["metar_parsed"] is not None
        assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert "explanation" in data
        assert data["processing_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_analyze_with_airport_icao_success(
        self,
        mock_llm_client,
        mock_metar_fetcher,
        mock_metar_fetch_success
    ):
        """测试使用机场ICAO代码成功分析"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "airport_icao": "ZSPD",
                        "user_query": "浦东机场天气如何？",
                        "role": "dispatcher"
                    }
                )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["metar_metadata"] is not None
        assert data["metar_metadata"]["icao"] == "ZSPD"

    @pytest.mark.asyncio
    async def test_analyze_missing_parameters(self):
        """测试缺少必需参数"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/analyze",
                json={
                    "user_query": "天气如何？",
                    "role": "pilot"
                }
            )

        assert response.status_code == 400
        data = response.json()
        assert "必须提供metar_raw或airport_icao" in data["detail"]

    @pytest.mark.asyncio
    async def test_analyze_both_parameters_error(self):
        """测试同时提供两个参数错误"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/analyze",
                json={
                    "metar_raw": "ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
                    "airport_icao": "ZSPD",
                    "role": "pilot"
                }
            )

        assert response.status_code == 400
        data = response.json()
        assert "只能提供其中之一" in data["detail"]

    @pytest.mark.asyncio
    async def test_analyze_invalid_metar(self, mock_llm_client):
        """测试无效METAR报文"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": "INVALID METAR DATA",
                        "role": "pilot"
                    }
                )

        # 应返回200但success=False或解析错误
        assert response.status_code == 200
        data = response.json()
        # 即使解析失败，也应该返回响应
        assert "success" in data

    @pytest.mark.asyncio
    async def test_analyze_empty_metar(self):
        """测试空METAR报文"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/analyze",
                json={
                    "metar_raw": "",
                    "role": "pilot"
                }
            )

        # 应返回400错误
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_analyze_malformed_request(self):
        """测试格式错误的请求"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/analyze",
                json={
                    # 缺少role字段
                    "metar_raw": "ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008"
                }
            )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_analyze_with_critical_risk(self, mock_llm_client, sample_metar_thunderstorm):
        """测试CRITICAL风险天气分析"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_thunderstorm,
                        "role": "pilot"
                    }
                )

        assert response.status_code == 200
        data = response.json()

        assert data["risk_level"] == "CRITICAL"
        assert data["intervention_required"] is True
        assert data["intervention_reason"] is not None

    @pytest.mark.asyncio
    async def test_analyze_with_different_roles(self, mock_llm_client, sample_metar_vfr):
        """测试不同角色的分析结果"""
        from app.main import app

        roles = ["pilot", "dispatcher", "forecaster", "ground_crew"]

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                for role in roles:
                    response = await client.post(
                        "/analyze",
                        json={
                            "metar_raw": sample_metar_vfr,
                            "role": role
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True

    @pytest.mark.asyncio
    async def test_analyze_metar_fetch_failure(self, mock_llm_client):
        """测试METAR获取失败"""
        from app.main import app
        from app.services.metar_fetcher import MetarFetchError

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            with patch("app.api.routes.fetch_metar_for_airport") as mock_fetch:
                mock_fetch.side_effect = MetarFetchError("无法获取METAR数据")

                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/analyze",
                        json={
                            "airport_icao": "ZSPD",
                            "role": "pilot"
                        }
                    )

        assert response.status_code == 503
        data = response.json()
        assert "无法获取" in data["detail"]

    @pytest.mark.asyncio
    async def test_analyze_llm_failure(self, mock_llm_client_error, sample_metar_vfr):
        """测试LLM调用失败"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client_error):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_vfr,
                        "role": "pilot"
                    }
                )

        # 应返回500或错误响应
        assert response.status_code == 200
        data = response.json()
        # 成功= False 或有错误信息
        assert data["success"] is False or data.get("error") is not None


# ==================== /health端点测试 ====================

class TestHealthEndpoint:
    """健康检查端点测试类"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_llm_client):
        """测试健康检查成功"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["llm_available"] is True

    @pytest.mark.asyncio
    async def test_health_check_llm_unavailable(self):
        """测试LLM不可用时的健康检查"""
        from app.main import app

        mock_client = MagicMock()
        mock_client.get_current_provider.return_value = None
        mock_client.get_available_providers.return_value = []

        with patch("app.core.llm_client.get_llm_client", return_value=mock_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["llm_available"] is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """测试健康检查异常处理"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", side_effect=Exception("LLM错误")):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["llm_available"] is False


# ==================== /airports端点测试 ====================

class TestAirportsEndpoint:
    """机场列表端点测试类"""

    @pytest.mark.asyncio
    async def test_get_airports_success(self):
        """测试获取机场列表成功"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/airports")

        assert response.status_code == 200
        data = response.json()

        assert "airports" in data
        assert isinstance(data["airports"], list)
        assert len(data["airports"]) > 0

        # 验证机场数据结构
        airport = data["airports"][0]
        assert "icao" in airport
        assert "name" in airport
        assert "city" in airport

    @pytest.mark.asyncio
    async def test_airports_contains_expected_icao(self):
        """测试机场列表包含预期的ICAO代码"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/airports")

        data = response.json()
        icao_codes = [airport["icao"] for airport in data["airports"]]

        # 验证包含江浙沪主要机场
        expected_icao = ["ZSPD", "ZSSS", "ZSNJ", "ZSHC"]
        for icao in expected_icao:
            assert icao in icao_codes


# ==================== /metrics端点测试 ====================

class TestMetricsEndpoint:
    """服务指标端点测试类"""

    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        """测试获取服务指标成功"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "requests_total" in data
        assert "requests_success" in data
        assert "requests_failed" in data
        assert "avg_processing_time_ms" in data
        assert "llm_calls_total" in data


# ==================== 请求/响应模型验证测试 ====================

class TestRequestResponseModels:
    """请求/响应模型测试类"""

    def test_weather_analyze_request_validation(self):
        """测试请求模型验证"""
        # 有效请求
        request = WeatherAnalyzeRequest(
            metar_raw="ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
            user_query="天气如何？",
            role="pilot"
        )
        assert request.metar_raw is not None

        # 无效请求（缺少metar_raw和airport_icao）
        with pytest.raises(Exception):
            WeatherAnalyzeRequest(
                user_query="天气如何？",
                role="pilot"
            )

    def test_weather_analyze_request_validate_method(self):
        """测试请求验证方法"""
        # 只提供metar_raw
        request1 = WeatherAnalyzeRequest(
            metar_raw="ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
            role="pilot"
        )
        is_valid, error_msg = request1.validate_request()
        assert is_valid is True

        # 只提供airport_icao
        request2 = WeatherAnalyzeRequest(
            airport_icao="ZSPD",
            role="pilot"
        )
        is_valid, error_msg = request2.validate_request()
        assert is_valid is True

        # 同时提供两个
        request3 = WeatherAnalyzeRequest(
            metar_raw="ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
            airport_icao="ZSPD",
            role="pilot"
        )
        is_valid, error_msg = request3.validate_request()
        assert is_valid is False

        # 都不提供
        request4 = WeatherAnalyzeRequest(role="pilot")
        is_valid, error_msg = request4.validate_request()
        assert is_valid is False

    def test_weather_analyze_response_model(self):
        """测试响应模型"""
        response = WeatherAnalyzeResponse(
            success=True,
            metar_parsed={"icao_code": "ZSPD"},
            risk_level="LOW",
            processing_time_ms=150.5
        )

        assert response.success is True
        assert response.processing_time_ms == 150.5

    def test_health_check_response_model(self):
        """测试健康检查响应模型"""
        from app.api.schemas import HealthCheckResponse

        response = HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            llm_available=True
        )

        assert response.status == "healthy"
        assert response.llm_available is True


# ==================== 集成测试 ====================

class TestAPIIntegration:
    """API集成测试类"""

    @pytest.mark.asyncio
    async def test_full_workflow_with_good_weather(
        self,
        mock_llm_client,
        sample_metar_vfr
    ):
        """完整工作流测试：良好天气"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # 发送分析请求
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_vfr,
                        "user_query": "当前天气适合起降吗？",
                        "role": "pilot"
                    }
                )

        assert response.status_code == 200
        data = response.json()

        # 验证完整工作流输出
        assert data["success"] is True
        assert data["metar_parsed"]["icao_code"] == "ZSPD"
        assert data["metar_parsed"]["flight_rules"] == "VFR"
        assert data["detected_role"] == "pilot"
        assert data["risk_level"] == "LOW"
        assert len(data["risk_factors"]) == 0
        assert data["intervention_required"] is False
        assert data["explanation"] is not None
        assert data["llm_calls"] >= 0

    @pytest.mark.asyncio
    async def test_full_workflow_with_critical_weather(
        self,
        mock_llm_client,
        sample_metar_thunderstorm
    ):
        """完整工作流测试：极端天气"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_thunderstorm,
                        "user_query": "可以起飞吗？",
                        "role": "pilot"
                    }
                )

        assert response.status_code == 200
        data = response.json()

        # 验证极端天气处理
        assert data["success"] is True
        assert data["risk_level"] == "CRITICAL"
        assert len(data["risk_factors"]) > 0
        assert data["intervention_required"] is True
        assert data["intervention_reason"] is not None

    @pytest.mark.asyncio
    async def test_workflow_with_airport_fetch(
        self,
        mock_llm_client,
        mock_metar_fetcher
    ):
        """测试使用机场ICAO的完整工作流"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "airport_icao": "ZSSS",
                        "role": "dispatcher"
                    }
                )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["metar_metadata"]["icao"] == "ZSSS"

    @pytest.mark.asyncio
    async def test_session_tracking(self, mock_llm_client, sample_metar_vfr):
        """测试会话跟踪"""
        from app.main import app

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                session_id = "test-session-456"

                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_vfr,
                        "role": "pilot",
                        "session_id": session_id
                    }
                )

        assert response.status_code == 200
        # 注意：session_id可能不会在响应中返回，取决于实现


# ==================== 性能测试 ====================

class TestAPIPerformance:
    """API性能测试类"""

    @pytest.mark.asyncio
    async def test_response_time(self, mock_llm_client, sample_metar_vfr):
        """测试响应时间"""
        from app.main import app
        import time

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                start_time = time.time()
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_vfr,
                        "role": "pilot"
                    }
                )
                end_time = time.time()

        assert response.status_code == 200
        processing_time = (end_time - start_time) * 1000  # ms

        # 响应时间应小于5秒（根据实际情况调整）
        assert processing_time < 5000

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_llm_client, sample_metar_vfr):
        """测试并发请求"""
        from app.main import app
        import asyncio

        with patch("app.core.llm_client.get_llm_client", return_value=mock_llm_client):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # 发送10个并发请求
                tasks = []
                for i in range(10):
                    task = client.post(
                        "/analyze",
                        json={
                            "metar_raw": sample_metar_vfr,
                            "role": "pilot",
                            "session_id": f"session-{i}"
                        }
                    )
                    tasks.append(task)

                responses = await asyncio.gather(*tasks)

        # 所有请求应成功
        for response in responses:
            assert response.status_code == 200


# ==================== 错误处理测试 ====================

class TestAPIErrorHandling:
    """API错误处理测试类"""

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self, sample_metar_vfr):
        """测试意外错误处理"""
        from app.main import app

        with patch("app.core.workflow.run_workflow", side_effect=Exception("意外错误")):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/analyze",
                    json={
                        "metar_raw": sample_metar_vfr,
                        "role": "pilot"
                    }
                )

        # 应返回500错误或包含错误信息的响应
        assert response.status_code in [500, 200]

    @pytest.mark.asyncio
    async def test_invalid_json_handling(self):
        """测试无效JSON处理"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/analyze",
                content="invalid json",
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 422  # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_method_not_allowed(self):
        """测试不支持的HTTP方法"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/analyze")  # 应该是POST

        assert response.status_code == 405  # Method Not Allowed

    @pytest.mark.asyncio
    async def test_not_found_endpoint(self):
        """测试不存在的端点"""
        from app.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/nonexistent")

        assert response.status_code == 404
