#!/usr/bin/env python3
"""
简化版LLM测试 - 直接测试百度千帆V2 API
不依赖整个应用框架
"""
import asyncio
import aiohttp
import json
import sys
import os

# 从.env文件读取配置
def load_env():
    """手动加载.env文件"""
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    config = {}

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()

    return config


async def test_qianfan_v2_api():
    """测试百度千帆V2 API"""
    print("=" * 60)
    print("百度千帆V2 API连接测试")
    print("=" * 60)

    # 加载配置
    config = load_env()

    api_key = config.get('QIANFAN_API_KEY')
    base_url = config.get('QIANFAN_API_BASE_URL')
    model = config.get('QIANFAN_MODEL', 'qianfan-code-latest')

    print(f"\n配置信息:")
    print(f"  API Key: {api_key[:20]}..." if api_key else "  API Key: 未设置")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")

    if not api_key or not base_url:
        print("\n✗ 错误: 缺少必要的配置")
        return False

    # 构建请求
    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个航空气象分析助手。"},
            {"role": "user", "content": "你好，请用一句话介绍你自己。"}
        ],
        "temperature": 0.1,
        "max_tokens": 100,
    }

    print(f"\n请求URL: {url}")
    print(f"请求头: Authorization: Bearer {api_key[:20]}...")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    try:
        print("\n发送请求...")
        # 创建不验证SSL的连接器（仅用于测试）
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"响应状态: {response.status}")

                if response.status == 200:
                    result = await response.json()

                    print("\n✓ API调用成功!")
                    print(f"\n响应内容:")
                    print(json.dumps(result, ensure_ascii=False, indent=2))

                    # 提取回复内容
                    choices = result.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        print(f"\n助手回复: {content}")

                    return True
                else:
                    error_text = await response.text()
                    print(f"\n✗ API调用失败!")
                    print(f"状态码: {response.status}")
                    print(f"错误信息: {error_text}")
                    return False

    except asyncio.TimeoutError:
        print("\n✗ 请求超时")
        return False
    except Exception as e:
        print(f"\n✗ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_metar_analysis():
    """测试METAR分析"""
    print("\n" + "=" * 60)
    print("测试METAR分析能力")
    print("=" * 60)

    config = load_env()

    api_key = config.get('QIANFAN_API_KEY')
    base_url = config.get('QIANFAN_API_BASE_URL')
    model = config.get('QIANFAN_MODEL', 'qianfan-code-latest')

    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    test_metar = "ZBAA 110530Z 35008MPS 9999 FEW040 12/M05 Q1018 NOSIG"

    system_prompt = """你是一个资深航线飞行员，持有ATPL执照。
职责：从飞行安全角度解读METAR报文，提供关键气象参数分析和飞行决策建议。

安全约束：
1. 禁止编造气象数据，仅基于METAR原文分析
2. 所有建议必须符合CCAR-121部运行规范
3. 风险优先，不确定时倾向保守建议"""

    user_prompt = f"""请分析以下METAR报文：

{test_metar}

请输出：
1. 天气概况
2. 飞行安全评估
3. 建议（GO/NO-GO）
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    try:
        print(f"\n分析METAR: {test_metar}")
        print("发送分析请求...")

        # 创建不验证SSL的连接器（仅用于测试）
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    choices = result.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        print("\n✓ 分析完成!")
                        print(f"\n分析结果:")
                        print(content)
                        return True
                else:
                    error_text = await response.text()
                    print(f"\n✗ 分析失败: {response.status} - {error_text}")
                    return False

    except Exception as e:
        print(f"\n✗ 分析异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print("\n🚀 百度千帆V2 API测试套件\n")

    # 测试1: 基础连接
    test1_passed = await test_qianfan_v2_api()

    # 测试2: METAR分析
    if test1_passed:
        test2_passed = await test_metar_analysis()
    else:
        test2_passed = False

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"  基础连接: {'✓ 通过' if test1_passed else '✗ 失败'}")
    print(f"  METAR分析: {'✓ 通过' if test2_passed else '✗ 失败'}")
    print("=" * 60)

    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过！API配置正确。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
