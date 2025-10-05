#!/usr/bin/env python3
"""
手动信号输入分析器
如果无法直接连接Telegram，可以手动输入信号进行分析
"""

import sys
import re
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

class ManualSignalAnalyzer:
    """手动信号分析器"""
    
    def __init__(self):
        self.signals = []
        self.analysis_results = {}
    
    def collect_signals_manually(self):
        """手动收集信号"""
        print("📝 手动信号输入模式")
        print("=" * 50)
        print("请将您从Telegram群组中看到的交易信号逐条输入")
        print("每输入一条信号后按回车，输入 'done' 完成输入")
        print("输入 'quit' 退出程序")
        print("-" * 50)
        
        signal_count = 0
        
        while True:
            try:
                signal = input(f"\n信号 #{signal_count + 1}: ").strip()
                
                if signal.lower() == 'quit':
                    print("👋 退出程序")
                    return False
                
                if signal.lower() == 'done':
                    break
                
                if signal:
                    self.signals.append(signal)
                    signal_count += 1
                    print(f"✅ 已添加: {signal}")
                
            except KeyboardInterrupt:
                print("\n👋 程序被中断")
                return False
        
        print(f"\n📊 共收集到 {len(self.signals)} 条信号")
        return len(self.signals) > 0
    
    def analyze_signals(self):
        """分析信号格式"""
        if not self.signals:
            print("❌ 没有信号可分析")
            return
        
        print(f"\n🔍 开始分析 {len(self.signals)} 条信号...")
        print("=" * 60)
        
        # 分类存储
        categories = {
            'basic_long': [],      # 基础做多
            'basic_short': [],     # 基础做空
            'with_amount': [],     # 带金额
            'with_sl': [],         # 带止损
            'with_tp': [],         # 带止盈
            'with_sl_tp': [],      # 带止损止盈
            'other': []            # 其他格式
        }
        
        # 分析每个信号
        for i, signal in enumerate(self.signals, 1):
            print(f"\n{i:2d}. 分析信号: {signal}")
            category = self._categorize_signal(signal)
            categories[category].append(signal)
            
            # 提取关键信息
            info = self._extract_signal_info(signal)
            print(f"    分类: {self._get_category_name(category)}")
            if info['symbol']:
                print(f"    币种: {info['symbol']}")
            if info['side']:
                print(f"    方向: {info['side']}")
            if info['amount']:
                print(f"    金额: {info['amount']}")
            if info['stop_loss']:
                print(f"    止损: {info['stop_loss']}")
            if info['take_profit']:
                print(f"    止盈: {info['take_profit']}")
        
        # 输出分类统计
        print(f"\n📋 信号分类统计:")
        print("=" * 40)
        for category, signals in categories.items():
            if signals:
                name = self._get_category_name(category)
                print(f"{name}: {len(signals)} 条")
                for signal in signals[:3]:  # 显示前3个例子
                    print(f"  例: {signal}")
                if len(signals) > 3:
                    print(f"  ... 还有 {len(signals) - 3} 条")
                print()
        
        # 生成解析器建议
        self._generate_parser_suggestions(categories)
        
        # 保存结果
        self._save_analysis_results(categories)
    
    def _categorize_signal(self, signal):
        """对信号进行分类"""
        signal_lower = signal.lower()
        
        has_long = '多' in signal or 'long' in signal_lower
        has_short = '空' in signal or 'short' in signal_lower
        has_amount = any(unit in signal for unit in ['u', 'U', 'usdt', 'USDT']) or re.search(r'\d+\s*[uU]', signal)
        has_sl = '止损' in signal or '止損' in signal
        has_tp = '目标' in signal or '目標' in signal or '止盈' in signal
        
        # 分类逻辑
        if has_sl and has_tp:
            return 'with_sl_tp'
        elif has_sl:
            return 'with_sl'
        elif has_tp:
            return 'with_tp'
        elif has_amount:
            return 'with_amount'
        elif has_long:
            return 'basic_long'
        elif has_short:
            return 'basic_short'
        else:
            return 'other'
    
    def _extract_signal_info(self, signal):
        """提取信号信息"""
        info = {
            'symbol': None,
            'side': None,
            'amount': None,
            'stop_loss': None,
            'take_profit': None
        }
        
        # 提取币种
        symbol_match = re.search(r'#(\w+)', signal)
        if symbol_match:
            info['symbol'] = symbol_match.group(1)
        
        # 提取方向
        if '多' in signal:
            info['side'] = '做多'
        elif '空' in signal:
            info['side'] = '做空'
        
        # 提取金额
        amount_match = re.search(r'(\d+(?:\.\d+)?)\s*[uU](?:SDT)?', signal)
        if amount_match:
            info['amount'] = amount_match.group(1) + 'U'
        
        # 提取止损
        sl_match = re.search(r'止[损損]\s*(\d+(?:\.\d+)?)', signal)
        if sl_match:
            info['stop_loss'] = sl_match.group(1)
        
        # 提取止盈
        tp_match = re.search(r'目[标標]\s*(\d+(?:\.\d+)?)', signal)
        if tp_match:
            info['take_profit'] = tp_match.group(1)
        
        return info
    
    def _get_category_name(self, category):
        """获取分类名称"""
        names = {
            'basic_long': '基础做多',
            'basic_short': '基础做空',
            'with_amount': '带金额',
            'with_sl': '带止损',
            'with_tp': '带止盈',
            'with_sl_tp': '完整信号(止损+止盈)',
            'other': '其他格式'
        }
        return names.get(category, category)
    
    def _generate_parser_suggestions(self, categories):
        """生成解析器建议"""
        print(f"💡 解析器优化建议:")
        print("=" * 40)
        
        # 收集所有币种
        symbols = set()
        for signal in self.signals:
            symbol_match = re.search(r'#(\w+)', signal)
            if symbol_match:
                symbols.add(symbol_match.group(1))
        
        if symbols:
            print(f"1. 需要支持的币种: {', '.join(sorted(symbols))}")
        
        # 检查格式特征
        features = []
        if any('市價' in s or '市价' in s for s in self.signals):
            features.append("中文市價格式")
        if any('止损' in s for s in self.signals):
            features.append("止损功能")
        if any('目标' in s or '止盈' in s for s in self.signals):
            features.append("止盈功能")
        if any(re.search(r'\d+[uU]', s) for s in self.signals):
            features.append("金额解析")
        
        if features:
            print(f"2. 需要支持的特征: {', '.join(features)}")
        
        # 建议正则表达式
        print(f"\n📝 建议的正则表达式模式:")
        print("-" * 30)
        
        if symbols:
            symbol_pattern = '|'.join(sorted(symbols))
            print(f"币种: r'#({symbol_pattern})'")
        
        print(f"基础信号: r'#(\\w+)\\s+市[價价]([多空])'")
        print(f"带金额: r'#(\\w+)\\s+市[價价]([多空]).*?(\\d+(?:\\.\\d+)?)\\s*[Uu]'")
        print(f"完整信号: r'#(\\w+)\\s+市[價价]([多空])(?:.*?(\\d+(?:\\.\\d+)?)\\s*[Uu])?.*?(?:止[损損]\\s*(\\d+(?:\\.\\d+)?))?.*?(?:目[标標]\\s*(\\d+(?:\\.\\d+)?))?'")
        
        # 测试现有解析器
        print(f"\n🧪 测试当前解析器:")
        print("-" * 30)
        self._test_current_parser()
    
    def _test_current_parser(self):
        """测试当前解析器"""
        try:
            from src.trading.signal_parser import SignalParser
            
            parser = SignalParser()
            success_count = 0
            
            for i, signal in enumerate(self.signals, 1):
                parsed = parser.parse_signal(signal)
                if parsed:
                    success_count += 1
                    print(f"✅ {i:2d}. {signal}")
                else:
                    print(f"❌ {i:2d}. {signal}")
            
            success_rate = success_count / len(self.signals) * 100
            print(f"\n📊 当前解析器成功率: {success_count}/{len(self.signals)} ({success_rate:.1f}%)")
            
            if success_rate < 80:
                print("⚠️  成功率偏低，建议优化解析器")
            else:
                print("✅ 解析器表现良好")
        
        except Exception as e:
            print(f"❌ 测试解析器失败: {e}")
    
    def _save_analysis_results(self, categories):
        """保存分析结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_signal_analysis_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("手动信号格式分析结果\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"信号总数: {len(self.signals)}\n\n")
            
            f.write("原始信号列表:\n")
            f.write("-" * 30 + "\n")
            for i, signal in enumerate(self.signals, 1):
                f.write(f"{i:2d}. {signal}\n")
            
            f.write(f"\n分类统计:\n")
            f.write("-" * 30 + "\n")
            for category, signals in categories.items():
                if signals:
                    f.write(f"{self._get_category_name(category)}: {len(signals)} 条\n")
                    for signal in signals:
                        f.write(f"  - {signal}\n")
                    f.write("\n")
        
        print(f"\n📄 分析结果已保存到: {filename}")
    
    def run(self):
        """运行分析器"""
        print("🚀 手动信号格式分析器")
        print("=" * 50)
        print("如果无法直接连接Telegram群组，可以手动输入信号进行分析")
        print()
        
        # 收集信号
        if self.collect_signals_manually():
            # 分析信号
            self.analyze_signals()
            
            print(f"\n✅ 分析完成!")
            print("基于以上分析结果，我可以为您优化信号解析器")
        else:
            print("❌ 未收集到信号")


def main():
    """主函数"""
    analyzer = ManualSignalAnalyzer()
    analyzer.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
