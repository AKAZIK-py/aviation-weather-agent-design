#!/usr/bin/env python3
"""
完整Workflow测试 - 定位错误
"""
import sys
sys.path.insert(0, '/mnt/user-data/workspace/aviation-weather-agent')

import asyncio
import traceback
from app.core.workflow import run_workflow

async def test_workflow_simple():
    """测试简单METAR的完整workflow"""
    print("\n" + "="*60)
    print("测试1: 简单METAR完整Workflow")
    print("="*60)
    
    metar = "METAR ZSPD 111800Z 27008MPS 9999 FEW040 18/08 Q1018 NOSIG"
    
    try:
        result = await run_workflow(
            metar_raw=metar,
            user_query="测试",
            user_role="ground_crew",
            session_id="test-001"
        )
        
        print(f"成功: {result.get('success', True)}")
        print(f"风险等级: {result.get('risk_level')}")
        print(f"解释长度: {len(result.get('explanation', '')) if result.get('explanation') else 0}")
        
        return result
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        traceback.print_exc()
        return None


async def test_workflow_complex():
    """测试复杂METAR的完整workflow"""
    print("\n" + "="*60)
    print("测试2: 复杂METAR完整Workflow")
    print("="*60)
    
    metar = "METAR ZBAA 111800Z 27025G35MPS 3000 TSRA SCT010 CB 15/14 Q0985"
    
    try:
        result = await run_workflow(
            metar_raw=metar,
            user_query="能起飞吗？",
            user_role="pilot",
            session_id="test-002"
        )
        
        print(f"成功: {result.get('success', True)}")
        print(f"风险等级: {result.get('risk_level')}")
        print(f"解释长度: {len(result.get('explanation', '')) if result.get('explanation') else 0}")
        
        return result
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        traceback.print_exc()
        return None


async def main():
    print("\n" + "🔄"*30)
    print("完整Workflow测试")
    print("🔄"*30)
    
    result1 = await test_workflow_simple()
    result2 = await test_workflow_complex()
    
    print("\n" + "="*60)
    print("测试结果")
    print("="*60)
    
    print(f"简单METAR: {'✓' if result1 else '✗'}")
    print(f"复杂METAR: {'✓' if result2 else '✗'}")


if __name__ == "__main__":
    asyncio.run(main())
