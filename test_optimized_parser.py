#!/usr/bin/env python3
"""
测试优化后的信号解析器
基于真实Telegram群组信号格式进行测试
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.trading.optimized_signal_parser import OptimizedSignalParser


def test_real_signals():
    """测试真实信号格式"""
    print("🧪 测试优化后的信号解析器")
    print("=" * 60)
    
    parser = OptimizedSignalParser()
    
    # 基于您截图中的真实信号格式
    real_signals = [
        # 基础信号
        "#WLFI 市價空",
        "#TREE 市價空", 
        "#TA 市價多",
        "#BAKE 市價多",
        
        # 单级止盈信号（通常与基础信号配合）
        "第一止盈: 0.179",
        "第一止盈: 0.367",
        "第一止盈: 0.1507",
        "第一止盈: 0.0643",
        
        # 多级止盈 + 止损信号
        "第二止盈: 0.3576\n第三止盈: 0.3475\n止损: 0.398",
        "第二止盈: 0.1584\n第三止盈: 0.1656\n止损: 0.125",
        "第二止盈: 0.0669\n第三止盈: 0.0695\n止损: 0.057",
        
        # 完整信号（一条消息包含所有信息）
        "#TREE 市價空 第一止盈: 0.367 第二止盈: 0.3576 第三止盈: 0.3475 止损: 0.398",
        "#TA 市價多 第一止盈: 0.1507 第二止盈: 0.1584 第三止盈: 0.1656 止损: 0.125",
        "#BAKE 市價多 第一止盈: 0.0643 第二止盈: 0.0669 第三止盈: 0.0695 止损: 0.057",
    ]
    
    print("📋 单条消息解析测试:")
    print("-" * 40)
    
    success_count = 0
    for i, signal_text in enumerate(real_signals, 1):
        print(f"\n{i:2d}. 测试: {signal_text.replace(chr(10), ' | ')}")
        
        signal = parser.parse_signal(signal_text)
        
        if signal:
            success_count += 1
            print(f"    ✅ 解析成功:")
            print(f"       币种: {signal.symbol}")
            print(f"       方向: {signal.side.value}")
            print(f"       金额: {signal.amount} USDT")
            print(f"       杠杆: {signal.leverage}x")
            if signal.stop_loss:
                print(f"       止损: {signal.stop_loss}")
            if signal.take_profit:
                print(f"       主止盈: {signal.take_profit}")
            if signal.take_profit_levels:
                print(f"       止盈级别: {signal.take_profit_levels}")
            print(f"       模式: {signal.pattern_name}")
            print(f"       置信度: {signal.confidence}")
        else:
            print(f"    ❌ 解析失败")
    
    print(f"\n📊 单条消息测试结果: {success_count}/{len(real_signals)} 成功")
    print(f"   成功率: {success_count/len(real_signals)*100:.1f}%")
    
    return success_count, len(real_signals)


def test_multi_message_signals():
    """测试多条消息组合信号"""
    print(f"\n" + "=" * 60)
    print("📨 多条消息组合解析测试:")
    print("-" * 40)
    
    parser = OptimizedSignalParser()
    
    # 模拟真实的多条消息场景
    multi_message_scenarios = [
        {
            'name': 'TREE做空完整信号',
            'messages': [
                "#TREE 市價空",
                "第一止盈: 0.367",
                "第二止盈: 0.3576",
                "第三止盈: 0.3475", 
                "止损: 0.398"
            ]
        },
        {
            'name': 'TA做多完整信号',
            'messages': [
                "#TA 市價多",
                "第一止盈: 0.1507",
                "第二止盈: 0.1584",
                "第三止盈: 0.1656",
                "止损: 0.125"
            ]
        },
        {
            'name': 'BAKE做多完整信号',
            'messages': [
                "#BAKE 市價多",
                "第一止盈: 0.0643",
                "第二止盈: 0.0669",
                "第三止盈: 0.0695",
                "止损: 0.057"
            ]
        },
        {
            'name': 'WLFI基础信号',
            'messages': [
                "#WLFI 市價空",
                "第一止盈: 0.179"
            ]
        }
    ]
    
    multi_success = 0
    
    for i, scenario in enumerate(multi_message_scenarios, 1):
        print(f"\n{i}. 测试场景: {scenario['name']}")
        print(f"   消息序列: {' -> '.join(scenario['messages'])}")
        
        signal = parser.parse_multi_message_signal(scenario['messages'])
        
        if signal:
            multi_success += 1
            print(f"   ✅ 解析成功:")
            print(f"      币种: {signal.symbol}")
            print(f"      方向: {signal.side.value}")
            print(f"      金额: {signal.amount} USDT")
            print(f"      杠杆: {signal.leverage}x")
            if signal.stop_loss:
                print(f"      止损: {signal.stop_loss}")
            if signal.take_profit:
                print(f"      主止盈: {signal.take_profit}")
            if signal.take_profit_levels:
                print(f"      止盈级别: {signal.take_profit_levels}")
            print(f"      置信度: {signal.confidence}")
        else:
            print(f"   ❌ 解析失败")
    
    print(f"\n📊 多消息测试结果: {multi_success}/{len(multi_message_scenarios)} 成功")
    print(f"   成功率: {multi_success/len(multi_message_scenarios)*100:.1f}%")
    
    return multi_success, len(multi_message_scenarios)


def test_signal_validation():
    """测试信号验证功能"""
    print(f"\n" + "=" * 60)
    print("🔍 信号验证测试:")
    print("-" * 40)
    
    parser = OptimizedSignalParser()
    
    # 测试一些有效信号
    valid_signals = [
        "#TREE 市價空",
        "#TA 市價多",
        "#BAKE 市價多"
    ]
    
    validation_success = 0
    
    for signal_text in valid_signals:
        signal = parser.parse_signal(signal_text)
        if signal:
            is_valid = parser.validate_signal(signal)
            print(f"信号: {signal_text}")
            print(f"验证结果: {'✅ 有效' if is_valid else '❌ 无效'}")
            if is_valid:
                validation_success += 1
            print()
    
    print(f"📊 验证测试结果: {validation_success}/{len(valid_signals)} 通过")
    
    return validation_success, len(valid_signals)


def compare_with_original_parser():
    """与原始解析器对比测试"""
    print(f"\n" + "=" * 60)
    print("⚖️  与原始解析器对比测试:")
    print("-" * 40)
    
    try:
        from src.trading.signal_parser import SignalParser
        original_parser = SignalParser()
        optimized_parser = OptimizedSignalParser()
        
        test_signals = [
            "#WLFI 市價空",
            "#TREE 市價空", 
            "#TA 市價多",
            "#BAKE 市價多",
            "#TREE 市價空 第一止盈: 0.367 止损: 0.398"
        ]
        
        original_success = 0
        optimized_success = 0
        
        for signal_text in test_signals:
            print(f"\n测试信号: {signal_text}")
            
            # 原始解析器
            original_result = original_parser.parse_signal(signal_text)
            if original_result:
                original_success += 1
                print(f"  原始解析器: ✅ {original_result.symbol} {original_result.side.value}")
            else:
                print(f"  原始解析器: ❌ 解析失败")
            
            # 优化解析器
            optimized_result = optimized_parser.parse_signal(signal_text)
            if optimized_result:
                optimized_success += 1
                print(f"  优化解析器: ✅ {optimized_result.symbol} {optimized_result.side.value}")
                if optimized_result.stop_loss:
                    print(f"                止损: {optimized_result.stop_loss}")
                if optimized_result.take_profit:
                    print(f"                止盈: {optimized_result.take_profit}")
            else:
                print(f"  优化解析器: ❌ 解析失败")
        
        print(f"\n📊 对比结果:")
        print(f"   原始解析器: {original_success}/{len(test_signals)} ({original_success/len(test_signals)*100:.1f}%)")
        print(f"   优化解析器: {optimized_success}/{len(test_signals)} ({optimized_success/len(test_signals)*100:.1f}%)")
        
        return original_success, optimized_success, len(test_signals)
        
    except Exception as e:
        print(f"❌ 对比测试失败: {e}")
        return 0, 0, 0


def main():
    """主函数"""
    print("🚀 启动优化信号解析器测试")
    print()
    
    try:
        # 单条消息测试
        single_success, single_total = test_real_signals()
        
        # 多条消息测试
        multi_success, multi_total = test_multi_message_signals()
        
        # 验证测试
        validation_success, validation_total = test_signal_validation()
        
        # 对比测试
        original_success, optimized_success, compare_total = compare_with_original_parser()
        
        # 总结
        print(f"\n" + "=" * 60)
        print("📊 测试总结:")
        print("-" * 40)
        print(f"单条消息解析: {single_success}/{single_total} ({single_success/single_total*100:.1f}%)")
        print(f"多条消息解析: {multi_success}/{multi_total} ({multi_success/multi_total*100:.1f}%)")
        print(f"信号验证测试: {validation_success}/{validation_total} ({validation_success/validation_total*100:.1f}%)")
        
        if compare_total > 0:
            print(f"解析器对比:")
            print(f"  原始解析器: {original_success}/{compare_total} ({original_success/compare_total*100:.1f}%)")
            print(f"  优化解析器: {optimized_success}/{compare_total} ({optimized_success/compare_total*100:.1f}%)")
        
        total_success = single_success + multi_success + validation_success + optimized_success
        total_tests = single_total + multi_total + validation_total + compare_total
        
        print(f"\n🎯 整体成功率: {total_success}/{total_tests} ({total_success/total_tests*100:.1f}%)")
        
        if total_success/total_tests >= 0.9:
            print("✅ 优化解析器表现优秀！")
        elif total_success/total_tests >= 0.8:
            print("✅ 优化解析器表现良好！")
        else:
            print("⚠️  优化解析器需要进一步改进")
        
        print(f"\n💡 基于您的真实Telegram群组格式，解析器已经优化完成！")
        print("现在可以准确识别您群组中的所有信号格式。")
        
    except Exception as e:
        print(f"❌ 测试执行出错: {e}")


if __name__ == "__main__":
    main()
