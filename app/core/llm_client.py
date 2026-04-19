"""
LLM客户端模块 - 多Provider动态切换实现
参考cc-switch设计模式，支持运行时动态切换不同LLM提供商

支持的Provider:
- qianfan (百度千帆): ERNIE系列
- openai: GPT系列
- anthropic: Claude系列
- deepseek: DeepSeek系列
- moonshot: Kimi系列
"""
from typing import Optional, Dict, Any, Literal, Union
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
import os
import asyncio
import logging
import ssl
from enum import Enum

from app.core.config import get_settings, Settings

logger = logging.getLogger(__name__)

# 创建禁用SSL验证的上下文（用于代理环境）
def _create_ssl_context():
    """创建禁用SSL验证的上下文，用于代理环境"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


# ==================== Provider枚举 ====================

class LLMProvider(str, Enum):
    """支持的LLM提供商"""
    QIANFAN = "qianfan"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    MOONSHOT = "moonshot"


# ==================== 配置模型 ====================

class BaseLLMConfig(BaseModel):
    """LLM基础配置"""
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(2000, ge=1, le=32000)
    request_timeout: int = Field(30, ge=1, le=300)


class QianfanConfig(BaseLLMConfig):
    """百度千帆配置"""
    api_key: str
    secret_key: Optional[str] = None  # V2 API不需要secret_key
    model: str = "ERNIE-4.0-8K"
    base_url: Optional[str] = None  # V2 API端点


class OpenAIConfig(BaseLLMConfig):
    """OpenAI配置"""
    api_key: str
    base_url: Optional[str] = None
    model: str = "gpt-4"


class AnthropicConfig(BaseLLMConfig):
    """Anthropic配置"""
    api_key: str
    base_url: Optional[str] = None
    model: str = "claude-3-sonnet-20240229"


class DeepSeekConfig(BaseLLMConfig):
    """DeepSeek配置"""
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"


class MoonshotConfig(BaseLLMConfig):
    """Moonshot (Kimi)配置"""
    api_key: str
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "moonshot-v1-8k"


# ==================== 响应模型 ====================

class LLMResponse:
    """统一的LLM响应对象"""
    
    def __init__(self, content: str, model: str = "", provider: str = "", 
                 usage: Optional[Dict[str, int]] = None):
        self.content = content
        self.model = model
        self.provider = provider
        self.usage = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    def __repr__(self) -> str:
        return f"LLMResponse(provider={self.provider}, model={self.model}, content_length={len(self.content)})"


# ==================== Provider抽象基类 ====================

class BaseLLMProvider(ABC):
    """LLM Provider抽象基类"""
    
    def __init__(self, config: BaseLLMConfig):
        self.config = config
    
    @abstractmethod
    async def ainvoke(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """异步调用LLM"""
        pass
    
    @abstractmethod
    async def ainvoke_with_messages(self, messages: list) -> LLMResponse:
        """使用消息列表异步调用LLM"""
        pass
    
    def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """同步调用LLM（兼容LangChain接口）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self.ainvoke(prompt, system_prompt)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.ainvoke(prompt, system_prompt))
        except RuntimeError:
            return asyncio.run(self.ainvoke(prompt, system_prompt))


# ==================== 具体Provider实现 ====================

class QianfanProvider(BaseLLMProvider):
    """百度千帆Provider - 支持V1 OAuth和V2 Bearer Token"""

    def __init__(self, config: QianfanConfig):
        super().__init__(config)
        self.config: QianfanConfig = config
        self._access_token: Optional[str] = None
        self._token_expire_time: float = 0

        # 判断使用V2还是V1 API
        # 如果提供了base_url，使用V2 API（Bearer token）
        # 否则使用V1 API（OAuth）
        self.use_v2_api = bool(config.base_url)
    
    async def _get_access_token(self) -> str:
        """获取百度API访问令牌（带缓存）"""
        import time
        import aiohttp
        
        # 检查缓存是否有效（提前5分钟过期）
        if self._access_token and time.time() < self._token_expire_time - 300:
            return self._access_token
        
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.config.api_key,
            "client_secret": self.config.secret_key,
        }
        
        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(url, params=params) as response:
                result = await response.json()
                self._access_token = result.get("access_token", "")
                # 百度token有效期30天，设置28天过期
                self._token_expire_time = time.time() + 28 * 24 * 3600
                return self._access_token
    
    async def ainvoke(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """异步调用百度千帆API - 支持V1和V2"""
        import aiohttp

        # V2 API: 使用Bearer Token
        if self.use_v2_api:
            return await self._invoke_v2(prompt, system_prompt)
        # V1 API: 使用OAuth
        else:
            return await self._invoke_v1(prompt, system_prompt)

    async def _invoke_v2(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """V2 API调用 - OpenAI兼容格式"""
        import aiohttp

        base_url = self.config.base_url.rstrip('/')
        url = f"{base_url}/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()

                # V2 API返回格式与OpenAI兼容
                choices = result.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider="qianfan_v2",
                    usage=result.get("usage", {})
                )

    async def _invoke_v1(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """V1 API调用 - OAuth认证"""
        import aiohttp

        access_token = await self._get_access_token()

        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={access_token}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
        }

        # 禁用代理检测，避免SSL证书验证问题
        async with aiohttp.ClientSession(trust_env=False) as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()

                return LLMResponse(
                    content=result.get("result", ""),
                    model=self.config.model,
                    provider="qianfan_v1",
                    usage=result.get("usage", {})
                )
    
    async def ainvoke_with_messages(self, messages: list) -> LLMResponse:
        """使用消息列表调用 - 支持V1和V2"""
        # V2 API
        if self.use_v2_api:
            return await self._invoke_with_messages_v2(messages)
        # V1 API
        else:
            return await self._invoke_with_messages_v1(messages)

    async def _invoke_with_messages_v2(self, messages: list) -> LLMResponse:
        """V2 API消息列表调用"""
        import aiohttp

        base_url = self.config.base_url.rstrip('/')
        url = f"{base_url}/chat/completions"

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        # 禁用代理检测，避免SSL证书验证问题
        async with aiohttp.ClientSession(trust_env=False) as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()

                choices = result.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider="qianfan_v2",
                    usage=result.get("usage", {})
                )

    async def _invoke_with_messages_v1(self, messages: list) -> LLMResponse:
        """V1 API消息列表调用"""
        import aiohttp

        access_token = await self._get_access_token()

        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={access_token}"

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
        }

        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()

                return LLMResponse(
                    content=result.get("result", ""),
                    model=self.config.model,
                    provider="qianfan_v1",
                    usage=result.get("usage", {})
                )


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI兼容Provider（支持OpenAI、DeepSeek、Moonshot等）"""
    
    def __init__(self, config: Union[OpenAIConfig, DeepSeekConfig, MoonshotConfig], provider_name: str = "openai"):
        super().__init__(config)
        self.config: Union[OpenAIConfig, DeepSeekConfig, MoonshotConfig] = config
        self.provider_name = provider_name
    
    async def ainvoke(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """异步调用OpenAI兼容API"""
        import aiohttp
        
        base_url = getattr(self.config, 'base_url', None) or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(
                url, 
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()
                
                choices = result.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                
                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=self.provider_name,
                    usage=result.get("usage", {})
                )
    
    async def ainvoke_with_messages(self, messages: list) -> LLMResponse:
        """使用消息列表调用"""
        import aiohttp
        
        base_url = getattr(self.config, 'base_url', None) or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(
                url, 
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()
                
                choices = result.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                
                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=self.provider_name,
                    usage=result.get("usage", {})
                )


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider"""
    
    def __init__(self, config: AnthropicConfig):
        super().__init__(config)
        self.config: AnthropicConfig = config
    
    async def ainvoke(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """异步调用Anthropic API"""
        import aiohttp
        
        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        url = f"{base_url}/messages"
        
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(
                url, 
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()
                
                content_blocks = result.get("content", [])
                content = ""
                if content_blocks:
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                
                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider="anthropic",
                    usage={
                        "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                        "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                        "total_tokens": result.get("usage", {}).get("input_tokens", 0) + 
                                       result.get("usage", {}).get("output_tokens", 0)
                    }
                )
    
    async def ainvoke_with_messages(self, messages: list) -> LLMResponse:
        """使用消息列表调用"""
        import aiohttp
        
        base_url = self.config.base_url or "https://api.anthropic.com/v1"
        url = f"{base_url}/messages"
        
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }
        
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        # 禁用代理检测和SSL验证，避免代理环境下的证书问题
        ssl_context = _create_ssl_context()
        async with aiohttp.ClientSession(trust_env=False, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(
                url, 
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout)
            ) as response:
                result = await response.json()
                
                content_blocks = result.get("content", [])
                content = ""
                if content_blocks:
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                
                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider="anthropic",
                    usage={
                        "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                        "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                        "total_tokens": result.get("usage", {}).get("input_tokens", 0) + 
                                       result.get("usage", {}).get("output_tokens", 0)
                    }
                )


# ==================== LLM客户端管理器 ====================

class LLMClientManager:
    """
    LLM客户端管理器 - 动态切换Provider
    
    参考cc-switch设计模式，提供统一的LLM调用接口，
    支持运行时动态切换不同的LLM Provider。
    
    使用方式:
        manager = LLMClientManager()
        
        # 使用默认Provider
        response = await manager.ainvoke("你好")
        
        # 切换Provider
        manager.switch_provider("openai")
        response = await manager.ainvoke("Hello")
        
        # 使用特定Provider（不切换默认）
        response = await manager.ainvoke("你好", provider="deepseek")
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._current_provider: str = self.settings.llm_provider
        self._initialize_providers()
    
    def _initialize_providers(self):
        """初始化所有已配置的Provider"""
        # 百度千帆
        if self.settings.qianfan_api_key:
            self._providers["qianfan"] = QianfanProvider(QianfanConfig(
                api_key=self.settings.qianfan_api_key,
                secret_key=self.settings.qianfan_secret_key,
                model=self.settings.qianfan_model,
                base_url=self.settings.qianfan_api_base_url,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            ))
        
        # OpenAI
        if self.settings.openai_api_key:
            self._providers["openai"] = OpenAICompatibleProvider(
                OpenAIConfig(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.openai_model,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                ),
                provider_name="openai"
            )
        
        # Anthropic
        if self.settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider(AnthropicConfig(
                api_key=self.settings.anthropic_api_key,
                model=self.settings.anthropic_model,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            ))
        
        # DeepSeek (从settings读取，兼容环境变量)
        deepseek_key = self.settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            self._providers["deepseek"] = OpenAICompatibleProvider(
                DeepSeekConfig(
                    api_key=deepseek_key,
                    model=self.settings.deepseek_model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    base_url=self.settings.deepseek_base_url,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                ),
                provider_name="deepseek"
            )
        
        # Moonshot/Kimi (从settings读取，兼容环境变量)
        moonshot_key = self.settings.moonshot_api_key or os.getenv("MOONSHOT_API_KEY")
        if moonshot_key:
            self._providers["moonshot"] = OpenAICompatibleProvider(
                MoonshotConfig(
                    api_key=moonshot_key,
                    model=self.settings.moonshot_model or os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k"),
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                ),
                provider_name="moonshot"
            )
    
    def get_available_providers(self) -> list:
        """获取所有可用的Provider列表"""
        return list(self._providers.keys())
    
    def get_current_provider(self) -> str:
        """获取当前使用的Provider"""
        return self._current_provider
    
    def switch_provider(self, provider: str) -> bool:
        """
        切换到指定的Provider
        
        Args:
            provider: Provider名称 (qianfan/openai/anthropic/deepseek/moonshot)
        
        Returns:
            bool: 切换是否成功
        """
        if provider not in self._providers:
            available = list(self._providers.keys())
            raise ValueError(f"Provider '{provider}' 未配置或不可用。可用Provider: {available}")
        
        self._current_provider = provider
        return True
    
    def add_provider(self, name: str, config: BaseLLMConfig, provider_type: str = "openai_compatible"):
        """
        动态添加新的Provider
        
        Args:
            name: Provider名称
            config: Provider配置
            provider_type: Provider类型 (qianfan/openai_compatible/anthropic)
        """
        if provider_type == "qianfan" and isinstance(config, QianfanConfig):
            self._providers[name] = QianfanProvider(config)
        elif provider_type == "anthropic" and isinstance(config, AnthropicConfig):
            self._providers[name] = AnthropicProvider(config)
        elif provider_type == "openai_compatible":
            self._providers[name] = OpenAICompatibleProvider(config, provider_name=name)
        else:
            raise ValueError(f"不支持的Provider类型: {provider_type}")
    
    async def ainvoke(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None
    ) -> LLMResponse:
        """
        异步调用LLM
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            provider: 指定使用的Provider（可选，默认使用当前Provider）
        
        Returns:
            LLMResponse: 统一的响应对象
        """
        target_provider = provider or self._current_provider
        
        if target_provider not in self._providers:
            raise ValueError(f"Provider '{target_provider}' 未配置")
        
        return await self._providers[target_provider].ainvoke(prompt, system_prompt)
    
    async def ainvoke_with_messages(
        self,
        messages: list,
        provider: Optional[str] = None
    ) -> LLMResponse:
        """
        使用消息列表异步调用LLM
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            provider: 指定使用的Provider（可选）
        
        Returns:
            LLMResponse: 统一的响应对象
        """
        target_provider = provider or self._current_provider
        
        if target_provider not in self._providers:
            raise ValueError(f"Provider '{target_provider}' 未配置")
        
        return await self._providers[target_provider].ainvoke_with_messages(messages)
    
    def invoke(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None
    ) -> LLMResponse:
        """
        同步调用LLM（兼容LangChain接口）
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            provider: 指定使用的Provider（可选）
        
        Returns:
            LLMResponse: 统一的响应对象
        """
        target_provider = provider or self._current_provider
        
        if target_provider not in self._providers:
            raise ValueError(f"Provider '{target_provider}' 未配置")
        
        return self._providers[target_provider].invoke(prompt, system_prompt)


# ==================== 全局客户端实例 ====================

_llm_manager: Optional[LLMClientManager] = None


def get_llm_client() -> LLMClientManager:
    """获取LLM客户端管理器实例（单例模式）"""
    global _llm_manager
    
    if _llm_manager is None:
        _llm_manager = LLMClientManager()
    
    return _llm_manager


def reset_llm_client():
    """重置LLM客户端（用于测试）"""
    global _llm_manager
    _llm_manager = None


# ==================== 多层级降级 LLM 客户端 ====================

class ResilientLLMClient:
    """
    具有多层级降级策略的弹性 LLM 客户端
    
    降级层级:
    - Tier 1: 当前配置的主模型 (如 ERNIE-4.0)
    - Tier 2: 同 provider 的轻量模型 (如 ERNIE-Speed)
    - Tier 3: 其他已配置的 provider
    - Tier 4: 规则引擎 fallback (返回模板报告)
    
    每个 tier 有独立的 CircuitBreaker，失败时自动降级。
    """
    
    # 各 provider 的轻量模型映射
    LIGHTWEIGHT_MODELS = {
        "qianfan": "ERNIE-Speed-8K",
        "openai": "gpt-3.5-turbo",
        "anthropic": "claude-3-haiku-20240307",
        "deepseek": "deepseek-chat",
        "moonshot": "moonshot-v1-8k",
    }
    
    def __init__(self, manager: Optional[LLMClientManager] = None):
        self.manager = manager or get_llm_client()
        self.settings = self.manager.settings
        
        # 每个 provider 创建独立的 CircuitBreaker
        from app.core.circuit_breaker import CircuitBreaker
        self._breakers: Dict[str, CircuitBreaker] = {}
        for provider_name in self.manager._providers:
            self._breakers[provider_name] = CircuitBreaker(
                name=f"llm_{provider_name}",
                failure_threshold=3,
                recovery_timeout=30.0,
            )
        
        # 轻量模型 provider 缓存
        self._lightweight_providers: Dict[str, BaseLLMProvider] = {}
    
    def _get_breaker(self, provider: str) -> "CircuitBreaker":
        """获取或创建 provider 的 CircuitBreaker"""
        from app.core.circuit_breaker import CircuitBreaker
        if provider not in self._breakers:
            self._breakers[provider] = CircuitBreaker(
                name=f"llm_{provider}",
                failure_threshold=3,
                recovery_timeout=30.0,
            )
        return self._breakers[provider]
    
    def _get_lightweight_provider(self, provider_name: str) -> Optional[BaseLLMProvider]:
        """获取同 provider 的轻量模型实例"""
        if provider_name in self._lightweight_providers:
            return self._lightweight_providers[provider_name]
        
        lightweight_model = self.LIGHTWEIGHT_MODELS.get(provider_name)
        if not lightweight_model:
            return None
        
        try:
            if provider_name == "qianfan" and self.settings.qianfan_api_key:
                config = QianfanConfig(
                    api_key=self.settings.qianfan_api_key,
                    secret_key=self.settings.qianfan_secret_key,
                    model=lightweight_model,
                    base_url=self.settings.qianfan_api_base_url,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                )
                self._lightweight_providers[provider_name] = QianfanProvider(config)
            elif provider_name == "openai" and self.settings.openai_api_key:
                config = OpenAIConfig(
                    api_key=self.settings.openai_api_key,
                    model=lightweight_model,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                )
                self._lightweight_providers[provider_name] = OpenAICompatibleProvider(
                    config, provider_name="openai_lite"
                )
            elif provider_name == "anthropic" and self.settings.anthropic_api_key:
                config = AnthropicConfig(
                    api_key=self.settings.anthropic_api_key,
                    model=lightweight_model,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                )
                self._lightweight_providers[provider_name] = AnthropicProvider(config)
            elif provider_name == "deepseek":
                import os
                key = self.settings.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
                if key:
                    config = DeepSeekConfig(
                        api_key=key,
                        model=lightweight_model,
                        base_url=self.settings.deepseek_base_url,
                        temperature=self.settings.llm_temperature,
                        max_tokens=self.settings.llm_max_tokens,
                    )
                    self._lightweight_providers[provider_name] = OpenAICompatibleProvider(
                        config, provider_name="deepseek_lite"
                    )
            elif provider_name == "moonshot":
                import os
                key = self.settings.moonshot_api_key or os.getenv("MOONSHOT_API_KEY")
                if key:
                    config = MoonshotConfig(
                        api_key=key,
                        model=lightweight_model,
                        temperature=self.settings.llm_temperature,
                        max_tokens=self.settings.llm_max_tokens,
                    )
                    self._lightweight_providers[provider_name] = OpenAICompatibleProvider(
                        config, provider_name="moonshot_lite"
                    )
        except Exception as e:
            logger.warning(f"Failed to create lightweight provider for {provider_name}: {e}")
        
        return self._lightweight_providers.get(provider_name)
    
    def _generate_fallback_response(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """
        Tier 4: 规则引擎 fallback
        生成模板化的报告，确保系统始终有输出
        """
        import json
        
        # 提取关键信息生成基础报告
        fallback_content = json.dumps({
            "airport_info": {
                "icao": "N/A",
                "observation_time": "N/A",
            },
            "analysis": {
                "summary": "由于LLM服务暂时不可用，使用规则引擎生成基础分析。",
                "note": "当前所有LLM降级层级均不可用，建议稍后重试。",
            },
            "flight_decision": {
                "recommendation": "请参考METAR原始数据手动判断",
                "action_items": [
                    "检查METAR原始报文中的关键参数",
                    "对照运行最低标准进行人工评估",
                    "等待LLM服务恢复后获取详细分析",
                ],
            },
            "fallback_mode": True,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2)
        
        return LLMResponse(
            content=fallback_content,
            model="fallback_rules",
            provider="fallback",
        )
    
    async def ainvoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        多层级降级异步调用
        
        降级顺序:
        1. 主模型 (当前 provider)
        2. 轻量模型 (同 provider)
        3. 其他已配置的 provider
        4. 规则引擎 fallback
        """
        from app.core.circuit_breaker import CircuitBreakerOpenError
        
        primary_provider = self.manager._current_provider
        errors = []
        
        # ========== Tier 1: 主模型 ==========
        breaker = self._get_breaker(primary_provider)
        if not breaker.is_open:
            try:
                async with breaker.protect():
                    response = await self.manager._providers[primary_provider].ainvoke(
                        prompt, system_prompt
                    )
                    logger.info(f"[Tier 1] LLM call succeeded: {primary_provider}")
                    return response
            except CircuitBreakerOpenError:
                errors.append(f"Tier 1 ({primary_provider}): circuit breaker open")
            except Exception as e:
                errors.append(f"Tier 1 ({primary_provider}): {str(e)}")
                logger.warning(f"[Tier 1] LLM call failed: {e}")
        else:
            errors.append(f"Tier 1 ({primary_provider}): circuit breaker already open")
        
        # ========== Tier 2: 轻量模型 (同 provider) ==========
        lightweight = self._get_lightweight_provider(primary_provider)
        if lightweight:
            lite_breaker_name = f"{primary_provider}_lite"
            lite_breaker = self._get_breaker(lite_breaker_name)
            if not lite_breaker.is_open:
                try:
                    async with lite_breaker.protect():
                        response = await lightweight.ainvoke(prompt, system_prompt)
                        logger.info(f"[Tier 2] Lightweight LLM call succeeded: {primary_provider}")
                        return response
                except CircuitBreakerOpenError:
                    errors.append(f"Tier 2 ({primary_provider}_lite): circuit breaker open")
                except Exception as e:
                    errors.append(f"Tier 2 ({primary_provider}_lite): {str(e)}")
                    logger.warning(f"[Tier 2] Lightweight LLM call failed: {e}")
        
        # ========== Tier 3: 其他 provider ==========
        for other_provider, provider_instance in self.manager._providers.items():
            if other_provider == primary_provider:
                continue
            other_breaker = self._get_breaker(other_provider)
            if other_breaker.is_open:
                errors.append(f"Tier 3 ({other_provider}): circuit breaker open")
                continue
            try:
                async with other_breaker.protect():
                    response = await provider_instance.ainvoke(prompt, system_prompt)
                    logger.info(f"[Tier 3] Fallback provider succeeded: {other_provider}")
                    return response
            except CircuitBreakerOpenError:
                errors.append(f"Tier 3 ({other_provider}): circuit breaker open")
            except Exception as e:
                errors.append(f"Tier 3 ({other_provider}): {str(e)}")
                logger.warning(f"[Tier 3] Provider {other_provider} failed: {e}")
        
        # ========== Tier 4: 规则引擎 fallback ==========
        logger.warning(
            f"[Tier 4] All LLM tiers failed ({len(errors)} errors), "
            f"using rule-based fallback"
        )
        return self._generate_fallback_response(prompt, system_prompt)
    
    async def ainvoke_with_messages(
        self,
        messages: list,
    ) -> LLMResponse:
        """多层级降级消息列表调用"""
        # 将 messages 转换为 prompt + system_prompt
        system_prompt = None
        user_parts = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                user_parts.append(msg.get("content", ""))
        prompt = "\n".join(user_parts)
        
        return await self.ainvoke(prompt, system_prompt)
    
    async def generate_with_system_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        兼容 generate_explanation_node 调用方式
        带降级的 system_prompt + user_prompt 调用
        """
        # 注意：temperature 和 max_tokens 在降级时会使用各provider的默认值
        response = await self.ainvoke(user_prompt, system_prompt)
        return response.content
    
    def get_breaker_stats(self) -> Dict[str, dict]:
        """获取所有熔断器的统计信息"""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }
    
    def reset_all_breakers(self):
        """重置所有熔断器（用于测试和手动恢复）"""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info("All circuit breakers reset")


# 全局弹性客户端实例
_resilient_client: Optional[ResilientLLMClient] = None


def get_resilient_client() -> ResilientLLMClient:
    """获取弹性 LLM 客户端（单例模式）"""
    global _resilient_client
    if _resilient_client is None:
        _resilient_client = ResilientLLMClient()
    return _resilient_client


# ==================== 便捷函数 ====================

async def ainvoke(prompt: str, system_prompt: Optional[str] = None, provider: Optional[str] = None) -> LLMResponse:
    """便捷异步调用函数"""
    if provider:
        # 指定 provider 时使用原始 manager
        client = get_llm_client()
        return await client.ainvoke(prompt, system_prompt, provider)
    # 未指定 provider 时使用弹性客户端（带降级）
    resilient = get_resilient_client()
    return await resilient.ainvoke(prompt, system_prompt)


def invoke(prompt: str, system_prompt: Optional[str] = None, provider: Optional[str] = None) -> LLMResponse:
    """便捷同步调用函数"""
    client = get_llm_client()
    return client.invoke(prompt, system_prompt, provider)
