#!/usr/bin/env python3
"""
信号格式收集器
专门用于收集和分析Telegram群组中的真实交易信号格式
"""

import os
import sys
import asyncio
from pathlib import Path
import re
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

class SignalFormatCollector:
    """信号格式收集器"""
    
    def __init__(self):
        self.client = None
        self.signals_found = []
        self.format_patterns = {}
    
    async def initialize_client(self):
        """初始化Telegram客户端"""
        try:
            from telethon import TelegramClient
            from dotenv import load_dotenv
            
            # 加载环境变量
            load_dotenv()
            
            api_id = os.getenv('TELEGRAM_API_ID')
            api_hash = os.getenv('TELEGRAM_API_HASH')
            phone = os.getenv('TELEGRAM_PHONE_NUMBER')
            
            if not all([api_id, api_hash, phone]) or api_id == '你的API_ID':
                print("❌ 请先在 .env 文件中配置Telegram API信息:")
                print("   TELEGRAM_API_ID=您的API_ID")
                print("   TELEGRAM_API_HASH=您的API_HASH")
                print("   TELEGRAM_PHONE_NUMBER=+86您的手机号")
                return False
            
            print("🔗 正在初始化Telegram客户端...")
            self.client = TelegramClient('signal_collector_session', api_id, api_hash)
            await self.client.connect()
            
            # 检查认证状态
            if not await self.client.is_user_authorized():
                print("📱 需要进行手机验证...")
                await self.client.send_code_request(phone)
                
                code = input("请输入收到的验证码: ")
                try:
                    await self.client.sign_in(phone, code)
                    print("✅ 认证成功!")
                except Exception as e:
                    if 'password' in str(e).lower():
                        password = input("请输入两步验证密码: ")
                        await self.client.sign_in(password=password)
                        print("✅ 认证成功!")
                    else:
                        print(f"❌ 认证失败: {e}")
                        return False
            else:
                print("✅ 已认证")
            
            return True
            
        except ImportError:
            print("❌ 缺少依赖库，请安装: pip install telethon python-dotenv")
            return False
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            return False
    
    async def select_group(self):
        """选择要监控的群组"""
        print("\n📋 您的群组列表:")
        print("-" * 50)
        
        groups = []
        async for dialog in self.client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                groups.append({
                    'id': dialog.id,
                    'title': dialog.title,
                    'entity': dialog.entity
                })
        
        if not groups:
            print("❌ 未找到任何群组")
            return None
        
        for i, group in enumerate(groups, 1):
            print(f"{i:2d}. {group['title']}")
        
        while True:
            try:
                choice = input(f"\n请选择群组编号 (1-{len(groups)}): ")
                index = int(choice) - 1
                if 0 <= index < len(groups):
                    selected = groups[index]
                    print(f"✅ 已选择: {selected['title']}")
                    return selected['entity']
                else:
                    print("请输入有效的编号")
            except ValueError:
                print("请输入数字")
            except KeyboardInterrupt:
                print("\n👋 退出")
                return None
    
    async def collect_messages(self, group_entity, limit=100):
        """收集群组消息"""
        print(f"\n📨 正在收集最近 {limit} 条消息...")
        print("=" * 60)
        
        messages = []
        signal_count = 0
        
        try:
            async for message in self.client.iter_messages(group_entity, limit=limit):
                if message.text:
                    sender = await message.get_sender()
                    sender_name = self._get_sender_name(sender)
                    
                    msg_data = {
                        'id': message.id,
                        'date': message.date,
                        'sender': sender_name,
                        'text': message.text,
                        'is_signal': self._is_trading_signal(message.text)
                    }
                    
                    messages.append(msg_data)
                    
                    if msg_data['is_signal']:
                        signal_count += 1
                        self.signals_found.append(message.text)
                        print(f"🎯 [{message.date.strftime('%m-%d %H:%M')}] {sender_name}:")
                        print(f"    {message.text}")
                        print("-" * 40)
        
        except Exception as e:
            print(f"❌ 收集消息失败: {e}")
            return []
        
        print(f"\n📊 收集完成: 共 {len(messages)} 条消息，其中 {signal_count} 条交易信号")
        return messages
    
    def _get_sender_name(self, sender):
        """获取发送者名称"""
        if not sender:
            return "Unknown"
        
        if hasattr(sender, 'username') and sender.username:
            return f"@{sender.username}"
        elif hasattr(sender, 'first_name') and sender.first_name:
            name = sender.first_name
            if hasattr(sender, 'last_name') and sender.last_name:
                name += f" {sender.last_name}"
            return name
        elif hasattr(sender, 'title'):
            return sender.title
        else:
            return f"User_{getattr(sender, 'id', 'Unknown')}"
    
    def _is_trading_signal(self, text):
        """判断是否为交易信号"""
        if not text:
            return False
        
        # 检查交易信号关键词
        signal_keywords = [
            '#', '市價', '市价', '多', '空', 'long', 'short', 
            '买入', '卖出', '开多', '开空', '止损', '止盈', '目标'
        ]
        
        return any(keyword in text for keyword in signal_keywords)
    
    def analyze_signal_formats(self):
        """分析信号格式"""
        if not self.signals_found:
            print("❌ 未找到交易信号")
            return
        
        print(f"\n🔍 信号格式深度分析 ({len(self.signals_found)} 条信号)")
        print("=" * 60)
        
        # 格式分类
        format_categories = {
            'basic_long': [],      # 基础做多
            'basic_short': [],     # 基础做空
            'with_amount': [],     # 带金额
            'with_sl': [],         # 带止损
            'with_tp': [],         # 带止盈
            'with_sl_tp': [],      # 带止损止盈
            'complex': []          # 复杂格式
        }
        
        # 分析每个信号
        for signal in self.signals_found:
            self._categorize_signal(signal, format_categories)
        
        # 输出分析结果
        for category, signals in format_categories.items():
            if signals:
                category_name = self._get_category_name(category)
                print(f"\n📋 {category_name} ({len(signals)} 条):")
                print("-" * 40)
                
                # 显示前5个例子
                for i, signal in enumerate(signals[:5], 1):
                    print(f"{i}. {signal}")
                
                if len(signals) > 5:
                    print(f"   ... 还有 {len(signals) - 5} 条类似信号")
        
        # 提取关键模式
        self._extract_patterns()
    
    def _categorize_signal(self, signal, categories):
        """对信号进行分类"""
        signal_lower = signal.lower()
        
        # 检查各种特征
        has_hash = '#' in signal
        has_long = '多' in signal or 'long' in signal_lower
        has_short = '空' in signal or 'short' in signal_lower
        has_amount = any(unit in signal for unit in ['u', 'U', 'usdt', 'USDT'])
        has_sl = '止损' in signal or '止損' in signal
        has_tp = '目标' in signal or '目標' in signal or '止盈' in signal
        
        # 分类逻辑
        if has_sl and has_tp:
            categories['with_sl_tp'].append(signal)
        elif has_sl:
            categories['with_sl'].append(signal)
        elif has_tp:
            categories['with_tp'].append(signal)
        elif has_amount:
            categories['with_amount'].append(signal)
        elif has_long:
            categories['basic_long'].append(signal)
        elif has_short:
            categories['basic_short'].append(signal)
        else:
            categories['complex'].append(signal)
    
    def _get_category_name(self, category):
        """获取分类名称"""
        names = {
            'basic_long': '基础做多格式',
            'basic_short': '基础做空格式',
            'with_amount': '带金额格式',
            'with_sl': '带止损格式',
            'with_tp': '带止盈格式',
            'with_sl_tp': '完整信号(止损+止盈)',
            'complex': '复杂格式'
        }
        return names.get(category, category)
    
    def _extract_patterns(self):
        """提取信号模式"""
        print(f"\n🎯 提取的关键模式:")
        print("=" * 40)
        
        patterns = set()
        
        for signal in self.signals_found:
            # 提取币种模式
            coin_match = re.search(r'#(\w+)', signal)
            if coin_match:
                patterns.add(f"币种格式: #{coin_match.group(1)}")
            
            # 提取方向模式
            if '市價多' in signal or '市价多' in signal:
                patterns.add("做多格式: 市價多")
            if '市價空' in signal or '市价空' in signal:
                patterns.add("做空格式: 市價空")
            
            # 提取金额模式
            amount_match = re.search(r'(\d+(?:\.\d+)?)\s*[uU](?:SDT)?', signal)
            if amount_match:
                patterns.add(f"金额格式: {amount_match.group(0)}")
            
            # 提取止损模式
            sl_match = re.search(r'止[损損]\s*(\d+(?:\.\d+)?)', signal)
            if sl_match:
                patterns.add(f"止损格式: 止损{sl_match.group(1)}")
            
            # 提取止盈模式
            tp_match = re.search(r'目[标標]\s*(\d+(?:\.\d+)?)', signal)
            if tp_match:
                patterns.add(f"止盈格式: 目标{tp_match.group(1)}")
        
        for i, pattern in enumerate(sorted(patterns), 1):
            print(f"{i:2d}. {pattern}")
    
    def generate_parser_recommendations(self):
        """生成解析器优化建议"""
        if not self.signals_found:
            return
        
        print(f"\n💡 解析器优化建议:")
        print("=" * 40)
        
        recommendations = []
        
        # 分析常见格式
        coin_symbols = set()
        for signal in self.signals_found:
            coin_match = re.search(r'#(\w+)', signal)
            if coin_match:
                coin_symbols.add(coin_match.group(1))
        
        if coin_symbols:
            recommendations.append(f"1. 支持币种: {', '.join(sorted(coin_symbols))}")
        
        # 检查特殊格式
        has_chinese_price = any('市價' in s or '市价' in s for s in self.signals_found)
        if has_chinese_price:
            recommendations.append("2. 需要支持中文'市價'/'市价'格式")
        
        has_sl_tp = any('止损' in s and ('目标' in s or '止盈' in s) for s in self.signals_found)
        if has_sl_tp:
            recommendations.append("3. 需要解析止损止盈组合")
        
        has_amounts = any(re.search(r'\d+[uU]', s) for s in self.signals_found)
        if has_amounts:
            recommendations.append("4. 需要提取金额信息")
        
        for rec in recommendations:
            print(rec)
        
        print(f"\n📝 建议的正则表达式模式:")
        print("=" * 30)
        
        # 生成建议的正则表达式
        if coin_symbols:
            coin_pattern = '|'.join(sorted(coin_symbols))
            print(f"币种匹配: r'#({coin_pattern})'")
        
        print(f"完整信号: r'#(\\w+)\\s+市[價价]([多空])(?:.*?(\\d+(?:\\.\\d+)?)\\s*[Uu])?.*?(?:止[损損]\\s*(\\d+(?:\\.\\d+)?))?.*?(?:目[标標]\\s*(\\d+(?:\\.\\d+)?))?'")
    
    async def run(self):
        """运行收集器"""
        print("🚀 Telegram信号格式收集器")
        print("=" * 50)
        
        # 初始化客户端
        if not await self.initialize_client():
            return
        
        try:
            # 选择群组
            group = await self.select_group()
            if not group:
                return
            
            # 收集消息
            messages = await self.collect_messages(group, limit=200)
            
            if messages:
                # 分析格式
                self.analyze_signal_formats()
                
                # 生成建议
                self.generate_parser_recommendations()
                
                # 保存结果
                self.save_results()
                
                print(f"\n✅ 分析完成!")
                print("请将以上分析结果提供给开发者以优化信号解析器")
            
        except KeyboardInterrupt:
            print("\n👋 用户中断")
        except Exception as e:
            print(f"❌ 运行出错: {e}")
        finally:
            if self.client:
                await self.client.disconnect()
    
    def save_results(self):
        """保存分析结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"signal_analysis_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("Telegram交易信号格式分析结果\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"信号总数: {len(self.signals_found)}\n\n")
            
            f.write("原始信号列表:\n")
            f.write("-" * 30 + "\n")
            for i, signal in enumerate(self.signals_found, 1):
                f.write(f"{i:2d}. {signal}\n")
        
        print(f"📄 分析结果已保存到: {filename}")


async def main():
    """主函数"""
    collector = SignalFormatCollector()
    await collector.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
