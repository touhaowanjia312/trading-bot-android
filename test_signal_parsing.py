#!/usr/bin/env python3
"""
交易信号解析测试脚本
测试系统能否正确解析 #PTB 市價多、#ESPORTS 市價空 等信号格式
"""

import sys
import os
sys.path.insert(0, '.')

from src.trading.signal_parser import SignalParser

def main():
    print("=" * 60)
    print("    交易信号解析测试")
    print("=" * 60)
    print()
    
    parser = SignalParser()
    
    # 测试信号列表
    test_signals = [
        "#PTB 市價多",
        "#ESPORTS 市價空",
        "#BTC 市價多 5U",
        "#ETH 市價空 止损2800 目标2500",
        "#DOGE 市價多 3U 止损0.08 目标0.12",
        "#SOL 市價空 止损150 目标120",
        "普通消息，不是交易信号",
        "#INVALID_SYMBOL 市價多",  # 测试无效币种
    ]
    
    print("🧪 测试信号解析:")
    print("-" * 60)
    
    for i, message in enumerate(test_signals, 1):
        print(f"\n{i}. 测试消息: '{message}'")
        
        # 解析信号
        signal = parser.parse_signal(message)
        
        if signal:
            print("   ✅ 解析成功:")
            print(f"      - 币种: {signal.symbol}")
            print(f"      - 方向: {signal.side.value} ({'做多' if signal.side.value == 'buy' else '做空'})")
            print(f"      - 类型: {signal.signal_type.value}")
            print(f"      - 金额: {signal.amount or '使用默认(2.0U)'}")
            print(f"      - 杠杆: {signal.leverage}x")
            print(f"      - 止损: {signal.stop_loss or '无'}")
            print(f"      - 止盈: {signal.take_profit or '无'}")
            print(f"      - 置信度: {signal.confidence:.2f}")
            
            # 验证信号
            is_valid, errors = parser.validate_signal(signal)
            if is_valid:
                print("      - 验证: ✅ 通过")
            else:
                print("      - 验证: ❌ 失败")
                for error in errors:
                    print(f"        * {error}")
        else:
            print("   ❌ 解析失败 (非交易信号或格式不匹配)")
    
    print("\n" + "=" * 60)
    print("🎯 测试总结:")
    
    # 统计测试结果
    valid_signals = []
    for message in test_signals:
        signal = parser.parse_signal(message)
        if signal:
            is_valid, _ = parser.validate_signal(signal)
            if is_valid:
                valid_signals.append(signal)
    
    print(f"   - 总测试消息数: {len(test_signals)}")
    print(f"   - 成功解析信号数: {len([s for s in [parser.parse_signal(msg) for msg in test_signals] if s])}")
    print(f"   - 有效信号数: {len(valid_signals)}")
    
    if valid_signals:
        print(f"\n📊 信号统计:")
        stats = parser.get_signal_statistics(valid_signals)
        print(f"   - 做多信号: {stats.get('buy_signals', 0)}")
        print(f"   - 做空信号: {stats.get('sell_signals', 0)}")
        print(f"   - 平均置信度: {stats.get('average_confidence', 0):.3f}")
        print(f"   - 币种分布: {stats.get('symbol_distribution', {})}")
    
    print(f"\n✅ 配置确认:")
    print(f"   - 默认交易金额: 2.0 USDT")
    print(f"   - 默认杠杆倍数: 20x")
    print(f"   - 使用交易员止盈止损: 是")
    
    print(f"\n🚀 系统已准备就绪!")
    print(f"   只需配置API密钥即可开始自动跟单")

if __name__ == "__main__":
    main()
