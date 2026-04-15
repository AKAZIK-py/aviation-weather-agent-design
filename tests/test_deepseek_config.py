#!/usr/bin/env python3
"""
DeepSeek 配置验证测试
验证 DeepSeek Provider 已正确集成到项目中
"""
import pytest
from app.core.config import get_settings
from app.core.llm_client import get_llm_client, DeepSeekConfig


class TestDeepSeekConfiguration:
    """DeepSeek 配置测试套件"""

    def test_deepseek_config_fields_exist(self):
        """测试 DeepSeek 配置字段存在"""
        settings = get_settings()

        assert hasattr(settings, 'deepseek_api_key'), "缺少 deepseek_api_key 字段"
        assert hasattr(settings, 'deepseek_model'), "缺少 deepseek_model 字段"
        assert hasattr(settings, 'deepseek_base_url'), "缺少 deepseek_base_url 字段"

    def test_deepseek_default_values(self):
        """测试 DeepSeek 默认值"""
        settings = get_settings()

        assert settings.deepseek_model == "deepseek-chat", \
            f"默认模型错误: {settings.deepseek_model}"
        assert settings.deepseek_base_url == "https://api.deepseek.com/v1", \
            f"默认URL错误: {settings.deepseek_base_url}"

    def test_deepseek_provider_available(self):
        """测试 DeepSeek Provider 可用性"""
        client = get_llm_client()
        available = client.get_available_providers()

        # 如果设置了 DEEPSEEK_API_KEY，应该可用
        settings = get_settings()
        if settings.deepseek_api_key:
            assert 'deepseek' in available, \
                f"DeepSeek 应该在可用 providers 中，但只有: {available}"

    def test_deepseek_provider_config_correct(self):
        """测试 DeepSeek Provider 配置正确"""
        client = get_llm_client()
        settings = get_settings()

        if not settings.deepseek_api_key:
            pytest.skip("DEEPSEEK_API_KEY 未设置")

        if 'deepseek' not in client.get_available_providers():
            pytest.skip("DeepSeek provider 不可用")

        provider = client._providers['deepseek']
        config = provider.config

        assert isinstance(config, DeepSeekConfig), \
            f"配置类型错误: {type(config)}"
        assert config.model == settings.deepseek_model, \
            f"模型不匹配: {config.model} != {settings.deepseek_model}"
        assert config.base_url == settings.deepseek_base_url, \
            f"Base URL 不匹配: {config.base_url} != {settings.deepseek_base_url}"

    def test_deepseek_provider_switch(self):
        """测试切换到 DeepSeek Provider"""
        client = get_llm_client()
        settings = get_settings()

        if not settings.deepseek_api_key:
            pytest.skip("DEEPSEEK_API_KEY 未设置")

        if 'deepseek' not in client.get_available_providers():
            pytest.skip("DeepSeek provider 不可用")

        # 切换到 DeepSeek
        client.switch_provider('deepseek')
        current = client.get_current_provider()

        assert current == 'deepseek', \
            f"切换失败，当前 provider: {current}"

    def test_deepseek_in_llm_config_function(self):
        """测试 get_llm_config 函数包含 DeepSeek 配置"""
        from app.core.config import get_llm_config

        settings = get_settings()
        config = get_llm_config(settings)

        # 设置为 deepseek 时应该返回 deepseek 配置
        original_provider = settings.llm_provider
        try:
            # 临时切换
            settings.llm_provider = 'deepseek'
            config = get_llm_config(settings)

            assert 'api_key' in config or 'model' in config, \
                f"配置应该包含必要字段: {config}"
            assert 'base_url' in config, \
                f"配置应该包含 base_url: {config}"
        finally:
            # 恢复
            settings.llm_provider = original_provider


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
