#!/usr/bin/env python3
"""
更新群组ID工具
"""

import re


def update_group_id():
    """更新群组ID"""
    print("🔧 群组ID更新工具")
    print("=" * 40)
    
    # 从您的截图中，我看到群组名称是 "Seven的手工高司令🚀 (VIP)"
    # 通常这种群组的ID格式应该不同
    
    print("请提供正确的群组ID或群组用户名")
    print("格式示例:")
    print("1. @群组用户名 (如 @trading_signals)")
    print("2. -1001234567890 (数字ID)")
    print("3. 群组完整名称")
    
    new_group_id = input("\n请输入正确的群组ID: ").strip()
    
    if not new_group_id:
        print("❌ 群组ID不能为空")
        return
    
    # 读取.env文件
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 更新群组ID
        updated_content = re.sub(
            r'TELEGRAM_GROUP_ID=.*',
            f'TELEGRAM_GROUP_ID={new_group_id}',
            content
        )
        
        # 写回文件
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✅ 群组ID已更新为: {new_group_id}")
        print("现在可以重新启动机器人: python simple_trading_bot.py")
        
    except Exception as e:
        print(f"❌ 更新失败: {e}")


if __name__ == "__main__":
    update_group_id()
