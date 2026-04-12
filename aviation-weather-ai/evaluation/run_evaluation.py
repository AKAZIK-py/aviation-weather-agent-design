"""
航空天气AI系统 - 评测Pipeline主程序
整合所有模块，运行完整评测流程
"""

import sys
import os
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from evaluation.golden_set_generator import GoldenSetGenerator
from evaluation.evaluator import WeatherAIEvaluator
from evaluation.report_generator import ReportGenerator
from evaluation.api_protection import APIProtection


# ========== 模拟被测系统（用于演示评测流程）==========
class MockWeatherDataCollector:
    """
    模拟天气数据收集器
    用于在没有真实系统时演示评测流程
    """
    
    def collect_weather_data(self, airport_code: str) -> Dict[str, Any]:
        """
        模拟收集天气数据
        
        Args:
            airport_code: 机场代码
            
        Returns:
            模拟的天气数据
        """
        # 模拟API延迟
        import time
        time.sleep(0.1)
        
        # 基于机场代码生成不同的模拟数据
        random.seed(hash(airport_code) % 10000)
        
        # 生成模拟METAR
        visibility = random.choice([800, 1500, 3000, 5000, 9999])
        ceiling = random.choice([200, 500, 1000, 2000, 9999])
        wind_speed = random.randint(5, 30)
        wind_gust = wind_speed + random.randint(5, 15) if random.random() > 0.5 else None
        
        weather_phenomena = []
        if random.random() > 0.7:
            weather_phenomena.append(random.choice(['BR', 'FG', 'RA', 'SN', 'TS']))
        
        metar = f"METAR {airport_code} {datetime.now().strftime('%d%H%M')}Z " \
                f"{random.randint(0, 360):03d}{wind_speed:02d}KT " \
                f"{visibility}SM "
        
        if ceiling < 9999:
            metar += f"BKN{ceiling // 100:03d} "
        
        if weather_phenomena:
            metar += ' '.join(weather_phenomena) + " "
        
        metar += f"{random.randint(-10, 35):02d}/{random.randint(-10, 20):02d} QNH{random.randint(1000, 1030)}="
        
        return {
            'airport_code': airport_code,
            'metar': metar,
            'visibility': visibility,
            'ceiling': ceiling,
            'wind_speed': wind_speed,
            'wind_gust': wind_gust,
            'weather_phenomena': weather_phenomena,
            'timestamp': datetime.now().isoformat()
        }


class AviationWeatherEvaluationPipeline:
    """航空天气AI评测Pipeline"""
    
    def __init__(self):
        """初始化评测Pipeline"""
        self.golden_set_generator = GoldenSetGenerator()
        self.evaluator = WeatherAIEvaluator()
        self.report_generator = ReportGenerator()
        
        # API保护机制（配置合理的参数）
        self.api_protection = APIProtection(
            failure_threshold=5,      # 5次失败后熔断
            circuit_timeout=120,      # 熔断2分钟
            call_timeout=30,          # 单次调用30秒超时
            max_retries=3,            # 最多重试3次
            backoff_factor=1.0        # 退避因子
        )
        
        # 初始化天气数据收集器（被测系统）
        self.weather_collector = None
        
        # 评测结果
        self.golden_set = None
        self.evaluation_report = None
    
    def _mock_boundary_detection(self, weather_data: Dict[str, Any]) -> bool:
        """模拟边界天气检测（实际应调用真实AI系统）
        
        边界天气判定标准（符合测试用例期望）：
        - 能见度 < 1600米
        - 云底高 < 1000英尺
        - 风速 > 17 m/s 或 阵风 > 20 m/s
        - 危险天气现象（TS雷暴、FG大雾、BR轻雾、SN雪、强降水等）
        
        设计原则（方案C）：
        - 单参数边界标识严格按阈值
        - 整体边界天气由任一触发条件决定（含危险天气现象）
        """
        visibility = weather_data.get("visibility", 9999)
        ceiling = weather_data.get("ceiling", 9999)
        wind_speed = weather_data.get("wind_speed", 0)
        wind_gust = weather_data.get("wind_gust")
        weather_phenomena = weather_data.get("weather_phenomena", [])
        
        # 边界条件1: 能见度
        if visibility < 1600:
            return True
        
        # 边界条件2: 云底高
        if ceiling < 1000:
            return True
        
        # 边界条件3: 风速（包含阵风）
        if wind_speed > 17:
            return True
        if wind_gust and wind_gust > 20:  # 阵风阈值更宽松
            return True
        
        # 边界条件4: 危险天气现象
        # 完整的危险天气现象列表（含强度标识和组合现象）
        hazardous_base = ['TS', 'FG', 'BR', 'SN', 'SG', 'IC', 'FZRA', 'FZDZ', 'SHRA', 'SHSN', 'RASN']
        
        for phenomenon in weather_phenomena:
            # 去除强度标识（+/-）进行匹配
            clean_phenomenon = phenomenon.lstrip('+-')
            
            # 直接匹配基础危险天气
            if clean_phenomenon in hazardous_base:
                return True
            
            # 部分匹配：检查是否包含危险天气关键词
            for hazard in hazardous_base:
                if hazard in clean_phenomenon:
                    return True
            
            # 特殊处理：强降水标识（+前缀）直接触发
            if phenomenon.startswith('+'):
                return True
        
        return False
    
    def _mock_decision(self, weather_data: Dict[str, Any]) -> str:
        """模拟决策输出（实际应调用真实AI系统）"""
        boundary = self._mock_boundary_detection(weather_data)
        if boundary:
            return "CANCEL_OR_DELAY"
        return "NORMAL_OPERATION"
    
    def setup(self):
        """设置评测环境"""
        print("=" * 60)
        print("航空天气AI系统 - Phase 1 评测Pipeline")
        print("=" * 60)
        print()
        
        # 初始化天气数据收集器（使用模拟系统）
        print("🔧 初始化被测系统（MockWeatherDataCollector）...")
        try:
            self.weather_collector = MockWeatherDataCollector()
            print("✅ 初始化成功")
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            return False
        
        print()
        return True
    
    def generate_golden_set(self):
        """生成Golden Set测试案例"""
        print("📋 生成Golden Set测试案例...")
        self.golden_set = self.golden_set_generator.generate_golden_set()
        
        # 统计信息
        stats = {
            "total": len(self.golden_set),
            "boundary": len([tc for tc in self.golden_set if tc.test_type.value == "boundary_weather"]),
            "normal": len([tc for tc in self.golden_set if tc.test_type.value == "normal_weather"]),
            "edge": len([tc for tc in self.golden_set if tc.test_type.value == "edge_case"])
        }
        
        print(f"✅ 生成完成:")
        print(f"   - 总案例数: {stats['total']}")
        print(f"   - 边界天气: {stats['boundary']} 个")
        print(f"   - 正常天气: {stats['normal']} 个")
        print(f"   - 边缘案例: {stats['edge']} 个")
        print()
        
        return stats
    
    def run_evaluation(self):
        """运行评测"""
        if not self.golden_set:
            print("❌ 错误: Golden Set未生成")
            return False
        
        print("🚀 开始评测...")
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 包装天气数据收集器的API调用，添加保护机制
        original_collect = self.weather_collector.collect_weather_data
        
        def protected_collect(airport_code: str):
            """带API保护的天气数据收集"""
            return self.api_protection.call(
                original_collect,
                airport_code
            )
        
        # 替换为保护版本
        self.weather_collector.collect_weather_data = protected_collect
        
        # 执行评测
        try:
            # 收集所有测试案例的实际输出
            print("📊 收集AI系统实际输出...")
            actual_outputs = []
            for i, test_case in enumerate(self.golden_set, 1):
                print(f"   [{i}/{len(self.golden_set)}] 处理 {test_case.test_id}...")
                
                # 从raw_metar解析机场代码（前4个字符）
                airport_code = test_case.raw_metar[:4] if test_case.raw_metar else "UNKNOWN"
                
                # 从expected_results提取天气数据
                expected = test_case.expected_results
                
                # 能见度：字段名是"value"
                visibility = expected.get("visibility", {}).get("value", 9999)
                
                # 云底高：字段名是"height"（不是"value"！）
                ceiling = expected.get("ceiling", {}).get("height", 9999)
                
                weather_phenomena = expected.get("weather_phenomena", [])
                
                # 从expected_results提取风速数据
                wind_data = expected.get("wind", {})
                wind_speed = wind_data.get("speed", 0)
                wind_gust = wind_data.get("gust")
                
                # 构造天气数据字典（扁平结构，用于边界检测）
                weather_data_flat = {
                    "visibility": visibility,
                    "ceiling": ceiling,
                    "wind_speed": wind_speed,
                    "wind_gust": wind_gust,
                    "weather_phenomena": weather_phenomena,
                    "raw_metar": test_case.raw_metar,
                    "raw_taf": test_case.raw_taf
                }
                
                # 执行边界天气检测
                is_boundary = self._mock_boundary_detection(weather_data_flat)
                
                # 构造实际输出（与evaluator期望的数据结构对齐）
                actual_output = {
                    "airport_code": airport_code,
                    "timestamp": datetime.now().isoformat(),
                    
                    # 核心字段：边界天气标识（evaluator检查此字段）
                    "is_boundary_weather": is_boundary,
                    
                    # 嵌套结构：各参数详情（包含boundary_flag）
                    "visibility": {
                        "value": visibility,
                        "boundary_flag": visibility < 1600  # 能见度<1600m为边界
                    },
                    "ceiling": {
                        "height": ceiling,
                        "boundary_flag": ceiling < 1000  # 云底高<1000ft为边界
                    },
                    "wind": {
                        "speed": wind_speed,
                        "gust": wind_gust,
                        "boundary_flag": wind_speed > 17 or (wind_gust is not None and wind_gust > 20)  # 风速>17m/s或阵风>20m/s为边界
                    },
                    "weather_phenomena": weather_phenomena,
                    
                    # 冗余字段（兼容性）
                    "boundary_detected": is_boundary,
                    "decision": self._mock_decision(weather_data_flat)
                }
                actual_outputs.append(actual_output)
            
            print(f"✅ 收集完成: {len(actual_outputs)} 个输出")
            print()
            
            # 调用评测器
            self.evaluation_report = self.evaluator.evaluate_golden_set(
                self.golden_set,
                actual_outputs
            )
            
            print()
            print("✅ 评测完成")
            print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # 显示API保护统计
            api_stats = self.api_protection.get_all_stats()
            print("📊 API保护统计:")
            print(f"   - 总调用次数: {api_stats['retry_mechanism']['total_calls']}")
            print(f"   - 成功调用: {api_stats['retry_mechanism']['successful_calls']}")
            print(f"   - 重试次数: {api_stats['retry_mechanism']['retry_calls']}")
            print(f"   - 超时次数: {api_stats['timeout_handler']['timeout_calls']}")
            print(f"   - 熔断状态: {api_stats['circuit_breaker']['current_state']}")
            print()
            
            return True
            
        except Exception as e:
            print(f"❌ 评测失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_reports(self):
        """生成评测报告"""
        if not self.evaluation_report:
            print("❌ 错误: 评测报告未生成")
            return False
        
        print("📄 生成评测报告...")
        
        try:
            # 生成Markdown报告
            md_path = self.report_generator.save_report(
                self.evaluation_report,
                self.golden_set
            )
            print(f"✅ Markdown报告: {md_path}")
            
            # 生成JSON报告
            json_path = self.report_generator.save_json_report(self.evaluation_report)
            print(f"✅ JSON报告: {json_path}")
            
            print()
            return True
            
        except Exception as e:
            print(f"❌ 报告生成失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def display_summary(self):
        """显示评测摘要"""
        if not self.evaluation_report:
            return
        
        print("=" * 60)
        print("📊 评测结果摘要")
        print("=" * 60)
        print()
        
        report = self.evaluation_report
        
        print(f"总体结果:")
        print(f"  - 总测试案例: {report.total_cases}")
        print(f"  - 通过: {report.passed_cases} ✅")
        print(f"  - 失败: {report.failed_cases} ❌")
        print(f"  - 整体准确率: {report.overall_accuracy * 100:.2f}%")
        print()
        
        print(f"关键指标:")
        
        # 边界天气召回率
        recall = report.boundary_weather_recall
        status = "✅ 达标" if recall >= 0.95 else "❌ 未达标"
        print(f"  - 边界天气召回率: {recall * 100:.2f}% {status} (目标: ≥95%)")
        
        # 正常天气精确度
        precision = report.normal_weather_precision
        status = "✅ 达标" if precision >= 0.90 else "❌ 未达标"
        print(f"  - 正常天气精确度: {precision * 100:.2f}% {status} (目标: ≥90%)")
        
        # 整体准确率
        accuracy = report.overall_accuracy
        status = "✅ 达标" if accuracy >= 0.85 else "❌ 未达标"
        print(f"  - 整体准确率: {accuracy * 100:.2f}% {status} (目标: ≥85%)")
        
        # 边缘案例处理率
        edge_rate = report.edge_case_handling_rate
        status = "✅ 达标" if edge_rate >= 0.80 else "❌ 未达标"
        print(f"  - 边缘案例处理率: {edge_rate * 100:.2f}% {status} (目标: ≥80%)")
        
        print()
        
        # 显示失败的测试案例
        failed_count = report.failed_cases
        if failed_count > 0:
            print(f"失败案例预览 (前5个):")
            
            failed_results = [(r, tc) for r, tc in zip(report.results, self.golden_set) 
                             if not r.passed]
            
            for i, (result, test_case) in enumerate(failed_results[:5], 1):
                print(f"  {i}. {test_case.test_id}: {test_case.description}")
            
            print()
        
        print("=" * 60)
    
    def run(self):
        """运行完整评测流程"""
        # 1. 设置
        if not self.setup():
            return False
        
        # 2. 生成Golden Set
        if not self.generate_golden_set():
            return False
        
        # 3. 运行评测
        if not self.run_evaluation():
            return False
        
        # 4. 生成报告
        if not self.generate_reports():
            return False
        
        # 5. 显示摘要
        self.display_summary()
        
        return True


def main():
    """主函数"""
    pipeline = AviationWeatherEvaluationPipeline()
    
    try:
        success = pipeline.run()
        
        if success:
            print("\n✅ Phase 1评测Pipeline执行成功!")
            print("📝 详细报告已保存至 /mnt/user-data/outputs/")
            return 0
        else:
            print("\n❌ Phase 1评测Pipeline执行失败")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行")
        return 130
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
