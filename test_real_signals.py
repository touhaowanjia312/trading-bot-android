#!/usr/bin/env python3
"""
真实信号解析测试工具
用于测试从Telegram群组获取的真实信号格式
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.trading.signal_parser import SignalParser


def test_signal_parsing():
    """测试信号解析"""
    print("🎯 真实信号解析测试")
    print("=" * 50)
    
    parser = SignalParser()
    
    # 预设的一些可能的信号格式
    test_signals = [
        # 基本格式
        "#BTC 市價多",
        "#ETH 市價空",
        "#PTB 市價多",
        "#ESPORTS 市價空",
        
        # 带金额格式
        "#BTC 市價多 5U",
        "#ETH 市價空 3USDT",
        "#SOL 市價多 2u",
        
        # 带止损止盈格式
        "#BTC 市價空 止损45000 目标42000",
        "#ETH 市價多 止损2500 目标2800",
        "#SOL 市價空 3U 止损180 目标160",
        
        # 其他可能的格式
        "#DOGE 市价多 目标0.25",
        "#ADA 市价空 止损1.5",
        "#BNB 市價多 5U 杠杆20x",
    ]
    
    print("📋 预设信号格式测试:")
    print("-" * 30)
    
    success_count = 0
    total_count = len(test_signals)
    
    for i, signal_text in enumerate(test_signals, 1):
        print(f"\n{i:2d}. 测试: {signal_text}")
        
        signal = parser.parse_signal(signal_text)
        
        if signal:
            print(f"    ✅ 解析成功:")
            print(f"       币种: {signal.symbol}")
            print(f"       方向: {signal.side.value}")
            print(f"       金额: {signal.amount} USDT")
            print(f"       杠杆: {signal.leverage}x")
            if signal.stop_loss:
                print(f"       止损: {signal.stop_loss}")
            if signal.take_profit:
                print(f"       止盈: {signal.take_profit}")
            success_count += 1
        else:
            print(f"    ❌ 解析失败")
    
    print(f"\n📊 测试结果: {success_count}/{total_count} 成功解析")
    print(f"   成功率: {success_count/total_count*100:.1f}%")
    
    return success_count, total_count


def test_custom_signal():
    """测试自定义信号"""
    print("\n" + "=" * 50)
    print("🔧 自定义信号测试")
    print("=" * 50)
    print("请输入您从Telegram群组中看到的真实信号格式")
    print("输入 'quit' 或 'exit' 退出")
    print("-" * 30)
    
    parser = SignalParser()
    
    while True:
        try:
            signal_text = input("\n请输入信号: ").strip()
            
            if signal_text.lower() in ['quit', 'exit', 'q']:
                print("👋 退出测试")
                break
            
            if not signal_text:
                continue
            
            print(f"🔍 解析: {signal_text}")
            signal = parser.parse_signal(signal_text)
            
            if signal:
                print("✅ 解析成功:")
                print(f"   币种: {signal.symbol}")
                print(f"   方向: {signal.side.value}")
                print(f"   金额: {signal.amount} USDT")
                print(f"   杠杆: {signal.leverage}x")
                if signal.stop_loss:
                    print(f"   止损: {signal.stop_loss}")
                if signal.take_profit:
                    print(f"   止盈: {signal.take_profit}")
                
                # 显示匹配的模式
                print(f"   匹配模式: {signal.pattern_name}")
                print(f"   置信度: {signal.confidence}")
            else:
                print("❌ 解析失败")
                print("💡 可能的原因:")
                print("   - 信号格式不在预设模式中")
                print("   - 币种符号格式不匹配")
                print("   - 缺少关键词如'市價'、'多'、'空'")
                print("   - 请将此信号格式告诉开发者以便优化")
        
        except KeyboardInterrupt:
            print("\n👋 退出测试")
            break
        except Exception as e:
            print(f"❌ 测试出错: {e}")


def main():
    """主函数"""
    print("🚀 启动信号解析测试工具")
    print()
    
    try:
        # 预设格式测试
        success, total = test_signal_parsing()
        
        # 如果成功率较低，提示优化
        if success / total < 0.8:
            print(f"\n⚠️  成功率较低 ({success/total*100:.1f}%)")
            print("建议:")
            print("1. 先运行 telegram_viewer.py 查看真实信号格式")
            print("2. 将真实格式告诉开发者进行优化")
        
        # 自定义信号测试
        if input(f"\n是否测试自定义信号? (y/n): ").lower() == 'y':
            test_custom_signal()
        
        print(f"\n✅ 测试完成!")
        print("如果发现解析问题，请:")
        print("1. 记录无法解析的信号格式")
        print("2. 将格式反馈给开发者")
        print("3. 开发者会优化解析器以支持您的信号格式")
        
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")


if __name__ == "__main__":
    main()
