#!/usr/bin/env python3
"""
LLM连接测试脚本 - 验证百度千帆V2 API配置
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.llm_client import get_llm_client
from app.core.config import get_settings


async def test_llm_connection():
    """测试LLM连接"""
    print("=" * 60)
    print("LLM连接测试")
    print("=" * 60)

    # 加载配置
    settings = get_settings()
    print(f"\n当前配置:")
    print(f"  Provider: {settings.llm_provider}")
    print(f"  API Key: {settings.qianfan_api_key[:20]}..." if settings.qianfan_api_key else "  API Key: 未设置")
    print(f"  Base URL: {settings.qianfan_api_base_url}")
    print(f"  Model: {settings.qianfan_model}")
    print(f"  Temperature: {settings.llm_temperature}")
    print(f"  Max Tokens: {settings.llm_max_tokens}")

    # 获取LLM客户端
    try:
        llm_client = get_llm_client()
        print(f"\n✓ LLM客户端初始化成功")
        print(f"  当前Provider: {llm_client.get_current_provider()}")
        print(f"  可用Providers: {llm_client.get_available_providers()}")
    except Exception as e:
        print(f"\n✗ LLM客户端初始化失败: {e}")
        return False

    # 测试简单调用
    print("\n" + "=" * 60)
    print("测试LLM调用...")
    print("=" * 60)

    test_prompt = "你好，请用一句话介绍你自己。"
    test_system_prompt = "你是一个航空气象分析助手，请用简洁专业的语言回答。"

    try:
        print(f"\n发送提示词: {test_prompt}")
        response = await llm_client.ainvoke(
            prompt=test_prompt,
            system_prompt=test_system_prompt,
            provider="qianfan"
        )

        print(f"\n✓ LLM调用成功!")
        print(f"  Provider: {response.provider}")
        print(f"  Model: {response.model}")
        print(f"  Response: {response.content[:200]}..." if len(response.content) > 200 else f"  Response: {response.content}")
        print(f"  Usage: {response.usage}")

        return True

    except Exception as e:
        print(f"\n✗ LLM调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_metar_analysis():
    """测试METAR分析（完整流程）"""
    print("\n" + "=" * 60)
    print("测试METAR分析（PE组合策略）")
    print("=" * 60)

    from app.prompts import build_analysis_prompt, get_system_prompt
    import json

    # 测试METAR报文
    test_metar = "ZBAA 110530Z 35008MPS 9999 FEW040 12/M05 Q1018 NOSIG"
    test_role = "pilot"

    # 模拟解析后的数据
    parsed_data = {
        "icao_code": "ZBAA",
        "observation_time": "2024-01-11T05:30:00Z",
        "wind_direction": 350,
        "wind_speed": 8,
        "wind_gust": None,
        "visibility": 9999,
        "temperature": 12,
        "dewpoint": -5,
        "altimeter": 1018,
        "flight_rules": "VFR",
        "present_weather": [],
        "cloud_layers": [{"amount": "FEW", "height": 4000}]
    }

    # 构建分析提示词
    analysis_prompt = build_analysis_prompt(
        role=test_role,
        raw_metar=test_metar,
        parsed_data=parsed_data,
        risk_level="LOW",
        risk_factors=[]
    )

    system_prompt = get_system_prompt(test_role)

    print(f"\n角色: {test_role}")
    print(f"METAR: {test_metar}")
    print(f"\n系统提示词长度: {len(system_prompt)} 字符")
    print(f"分析提示词长度: {len(analysis_prompt)} 字符")

    try:
        llm_client = get_llm_client()

        print(f"\n开始LLM分析...")
        response = await llm_client.ainvoke(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            provider="qianfan"
        )

        print(f"\n✓ 分析完成!")
        print(f"  响应长度: {len(response.content)} 字符")
        print(f"  Provider: {response.provider}")

        # 尝试解析JSON
        try:
            # 提取JSON块
            content = response.content
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
            elif "{" in content and "}" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end]
            else:
                json_str = content

            parsed_response = json.loads(json_str)
            print(f"\n✓ JSON解析成功!")
            print(f"  结构化数据keys: {list(parsed_response.keys())[:5]}")

        except json.JSONDecodeError as e:
            print(f"\n⚠ JSON解析失败: {e}")
            print(f"  原始响应前200字符: {response.content[:200]}")

        return True

    except Exception as e:
        print(f"\n✗ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print("\n" + "🚀" * 30)
    print("航空气象Agent - LLM连接测试套件")
    print("🚀" * 30 + "\n")

    # 测试1: 基础连接
    test1_passed = await test_llm_connection()

    # 测试2: METAR分析
    if test1_passed:
        test2_passed = await test_metar_analysis()
    else:
        test2_passed = False

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"  基础连接测试: {'✓ 通过' if test1_passed else '✗ 失败'}")
    print(f"  METAR分析测试: {'✓ 通过' if test2_passed else '✗ 失败'}")
    print("=" * 60)

    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过！LLM配置正确。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
