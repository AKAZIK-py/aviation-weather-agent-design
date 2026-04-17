"""
Pytest配置和共享fixtures
"""
import ssl
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# 全局跳过 SSL 验证（VPN 代理环境下证书验证失败修复）
ssl._create_default_https_context = ssl._create_unverified_context

from app.core.workflow_state import WorkflowState, create_initial_state
from app.core.llm_client import LLMClientManager, LLMResponse
from app.models.schemas import RiskLevel, UserRole


# ==================== METAR测试数据 ====================

@pytest.fixture
def sample_metar_vfr():
    """VFR天气示例 - 良好天气"""
    return "METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008"


@pytest.fixture
def sample_metar_ifr():
    """IFR天气示例 - 低能见度"""
    return "METAR ZSSS 110830Z 18008KT 0800 FG VV002 10/09 Q1013"


@pytest.fixture
def sample_metar_lifr():
    """LIFR天气示例 - 极低能见度和云层"""
    return "METAR ZSNJ 110900Z 24015G25KT 0400 FG VV001 08/07 Q1015"


@pytest.fixture
def sample_metar_thunderstorm():
    """雷暴天气示例"""
    return "METAR ZSHC 110845Z 27018G30KT 4000 +TSRA BKN010CB 25/23 Q1005"


@pytest.fixture
def sample_metar_strong_wind():
    """强风天气示例"""
    return "METAR ZSNB 110915Z 32035G45KT 9999 SCT050 15/08 Q1018"


@pytest.fixture
def sample_metar_freezing():
    """冻雨天气示例"""
    return "METAR ZSWZ 110930Z 05010KT 2000 FZFG OVC003 M02/M04 Q1020"


@pytest.fixture
def sample_metar_wind_units():
    """MPS风速单位示例"""
    return "METAR ZSPD 111000Z 24008MPS 9999 FEW030 30/25 Q1010"


@pytest.fixture
def sample_metar_cavok():
    """CAVOK天气示例"""
    return "METAR ZSSS 111030Z 35006KT CAVOK 22/15 Q1022"


@pytest.fixture
def sample_metar_malformed():
    """格式错误的METAR"""
    return "INVALID METAR DATA XXXX"


@pytest.fixture
def sample_metar_empty():
    """空METAR"""
    return ""


# ==================== Parsed METAR数据 ====================

@pytest.fixture
def parsed_metar_good() -> Dict[str, Any]:
    """解析后的良好天气数据"""
    return {
        "raw_text": "ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
        "icao_code": "ZSPD",
        "observation_time": "2024-01-11T08:00:00",
        "wind_direction": 250,
        "wind_speed": 12,
        "wind_gust": None,
        "visibility": 10.0,
        "temperature": 28,
        "dewpoint": 22,
        "altimeter": 1008.0,
        "present_weather": [],
        "cloud_layers": [
            {
                "type": "SCT",
                "description": "散云(3-4okta)",
                "height_feet": 4000,
                "height_meters": 1219,
                "tower_type": None,
            }
        ],
        "flight_rules": "VFR",
    }


@pytest.fixture
def parsed_metar_critical() -> Dict[str, Any]:
    """解析后的极端天气数据"""
    return {
        "raw_text": "ZSHC 110845Z 27018G30KT 4000 +TSRA BKN010CB 25/23 Q1005",
        "icao_code": "ZSHC",
        "observation_time": "2024-01-11T08:45:00",
        "wind_direction": 270,
        "wind_speed": 18,
        "wind_gust": 30,
        "visibility": 4.0,
        "temperature": 25,
        "dewpoint": 23,
        "altimeter": 1005.0,
        "present_weather": [
            {"code": "+TSRA", "description": "强雷暴伴雨"}
        ],
        "cloud_layers": [
            {
                "type": "BKN",
                "description": "裂云(5-7okta)",
                "height_feet": 1000,
                "height_meters": 305,
                "tower_type": "CB",
            }
        ],
        "flight_rules": "IFR",
    }


# ==================== Workflow State ====================

@pytest.fixture
def initial_state(sample_metar_vfr) -> WorkflowState:
    """初始工作流状态"""
    return create_initial_state(
        metar_raw=sample_metar_vfr,
        user_query="当前天气适合飞行吗？",
        user_role="pilot"
    )


@pytest.fixture
def state_with_parsed_metar(initial_state, parsed_metar_good) -> WorkflowState:
    """包含解析后METAR的状态"""
    state = initial_state.copy()
    state.update({
        "metar_parsed": parsed_metar_good,
        "parse_success": True,
        "parse_errors": [],
        "current_node": "parse_metar_node",
    })
    return state


@pytest.fixture
def state_with_role(state_with_parsed_metar) -> WorkflowState:
    """包含角色识别结果的状态"""
    state = state_with_parsed_metar.copy()
    state.update({
        "detected_role": "pilot",
        "role_confidence": 0.95,
        "role_keywords": ["飞行", "起降"],
        "current_node": "classify_role_node",
    })
    return state


@pytest.fixture
def state_with_risk(state_with_role) -> WorkflowState:
    """包含风险评估结果的状态"""
    state = state_with_role.copy()
    state.update({
        "risk_level": "LOW",
        "risk_factors": [],
        "risk_reasoning": "飞行员视角下的风险评估：各项指标均在正常范围内",
        "current_node": "assess_risk_node",
    })
    return state


@pytest.fixture
def state_critical_risk(parsed_metar_critical) -> WorkflowState:
    """CRITICAL风险状态"""
    state = create_initial_state(
        metar_raw=parsed_metar_critical["raw_text"],
        user_role="pilot"
    )
    state.update({
        "metar_parsed": parsed_metar_critical,
        "parse_success": True,
        "detected_role": "pilot",
        "risk_level": "CRITICAL",
        "risk_factors": ["雷暴天气", "低能见度"],
        "risk_reasoning": "发现强雷暴伴雨、能见度4.0km",
    })
    return state


# ==================== Mock LLM Client ====================

@pytest.fixture
def mock_llm_response():
    """Mock LLM响应"""
    return LLMResponse(
        content="当前天气条件良好，适合飞行。能见度大于10公里，风速适中，无显著天气现象。",
        model="ERNIE-4.0-8K",
        provider="qianfan",
        usage={"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200}
    )


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Mock LLM客户端管理器"""
    client = MagicMock(spec=LLMClientManager)
    client.ainvoke = AsyncMock(return_value=mock_llm_response)
    client.invoke = MagicMock(return_value=mock_llm_response)
    client.get_current_provider = MagicMock(return_value="qianfan")
    client.get_available_providers = MagicMock(return_value=["qianfan", "openai"])
    # 兼容 workflow 中引用 client.settings 的代码路径
    mock_settings = MagicMock()
    mock_settings.llm_provider = "qianfan"
    mock_settings.qianfan_model = "ERNIE-4.0-8K"
    client.settings = mock_settings
    # 兼容引用 client._providers 的代码路径
    mock_provider = MagicMock()
    mock_provider.ainvoke = AsyncMock(return_value=mock_llm_response)
    client._providers = {"qianfan": mock_provider}
    client._current_provider = "qianfan"
    return client


@pytest.fixture
def mock_llm_client_error():
    """Mock LLM客户端（抛出异常）"""
    client = MagicMock(spec=LLMClientManager)
    client.ainvoke = AsyncMock(side_effect=Exception("LLM服务不可用"))
    client.invoke = MagicMock(side_effect=Exception("LLM服务不可用"))
    return client


# ==================== Mock METAR Fetcher ====================

@pytest.fixture
def mock_metar_fetch_success():
    """Mock METAR获取成功"""
    metar_raw = "ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008"
    metadata = {
        "icao": "ZSPD",
        "fetch_time": "2024-01-11T08:00:00Z",
        "observation_time": "2024-01-11T08:00:00Z",
        "station_name": "SHANGHAI PUDONG",
        "latitude": 31.1433,
        "longitude": 121.805,
        "temperature": 28,
        "flight_category": "VFR",
    }
    return metar_raw, metadata


@pytest.fixture
def mock_metar_fetcher(mock_metar_fetch_success):
    """Mock METAR获取服务"""
    with patch("app.services.metar_fetcher.fetch_metar_for_airport") as mock_fetch:
        mock_fetch.return_value = mock_metar_fetch_success
        yield mock_fetch


# ==================== 测试配置 ====================

@pytest.fixture
def test_settings():
    """测试环境配置"""
    from app.core.config import Settings
    return Settings(
        llm_provider="qianfan",
        qianfan_api_key="test_api_key",
        qianfan_secret_key="test_secret_key",
        qianfan_model="ERNIE-4.0-8K",
        llm_temperature=0.7,
        llm_max_tokens=2000,
    )


# ==================== 辅助函数 ====================

@pytest.fixture
def assert_valid_metar_parsed():
    """验证METAR解析结果的有效性"""
    def _assert(parsed: Dict[str, Any]):
        assert "icao_code" in parsed
        assert "observation_time" in parsed
        assert "wind_speed" in parsed
        assert "visibility" in parsed
        assert "flight_rules" in parsed
        assert parsed["flight_rules"] in ["VFR", "MVFR", "IFR", "LIFR"]
    return _assert


# ==================== 异步测试标记 ====================

def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async test"
    )
    config.addinivalue_line(
        "markers", "unit: unit test marker"
    )
    config.addinivalue_line(
        "markers", "integration: integration test marker"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow"
    )
