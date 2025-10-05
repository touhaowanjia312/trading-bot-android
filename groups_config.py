#!/usr/bin/env python3
"""
群组配置文件
用于配置要监控的Telegram群组
"""

# 要监控的群组关键词配置
# 每个列表包含必须同时出现在群组名称中的关键词
MONITOR_GROUPS = [
    # Seven的手工壽司鋪系列群组
    ['Seven', '司'],        # Seven的手工壽司鋪🍣（VIP）
    ['Seven', 'VIP'],       # 其他包含Seven和VIP的群组
    
    # Seven合約策略王群组
    ['Seven', '合約'],      # Seven-合約策略王
    ['Seven', '策略'],      # Seven-合約策略王（备用匹配）
    
    # 可以添加更多群组配置
    # 例如：
    # ['币圈', '交易'],      # 包含"币圈"和"交易"的群组
    # ['期货', '信号'],      # 包含"期货"和"信号"的群组
    # ['BTC', '分析'],       # 包含"BTC"和"分析"的群组
]

# 群组配置说明
GROUP_CONFIG_HELP = """
群组配置说明：

1. 在 MONITOR_GROUPS 列表中添加新的群组关键词
2. 每个群组用一个列表表示，包含必须同时出现的关键词
3. 关键词匹配是大小写敏感的
4. 机器人会自动搜索包含所有关键词的群组

示例配置：
    ['Seven', '司'],        # 匹配包含"Seven"和"司"的群组
    ['交易', 'VIP'],        # 匹配包含"交易"和"VIP"的群组
    ['BTC', '分析', '专业'], # 匹配包含"BTC"、"分析"和"专业"的群组

添加新群组步骤：
1. 打开此文件 (groups_config.py)
2. 在 MONITOR_GROUPS 列表中添加新的关键词列表
3. 保存文件
4. 重启交易机器人

注意事项：
- 关键词越具体，匹配越精准
- 避免使用过于通用的关键词（如"群"、"chat"等）
- 建议使用群组名称中的特征词汇
"""

def get_monitor_groups():
    """获取要监控的群组关键词列表"""
    return MONITOR_GROUPS

def add_group(keywords):
    """
    添加新的监控群组
    
    Args:
        keywords: 关键词列表，例如 ['BTC', '交易']
    """
    if keywords not in MONITOR_GROUPS:
        MONITOR_GROUPS.append(keywords)
        print(f"已添加群组关键词: {keywords}")
        return True
    else:
        print(f"群组关键词已存在: {keywords}")
        return False

def remove_group(keywords):
    """
    移除监控群组
    
    Args:
        keywords: 要移除的关键词列表
    """
    if keywords in MONITOR_GROUPS:
        MONITOR_GROUPS.remove(keywords)
        print(f"已移除群组关键词: {keywords}")
        return True
    else:
        print(f"群组关键词不存在: {keywords}")
        return False

def list_groups():
    """列出所有配置的群组关键词"""
    print("当前配置的监控群组关键词:")
    for i, keywords in enumerate(MONITOR_GROUPS, 1):
        print(f"{i}. {keywords}")

if __name__ == "__main__":
    # 测试配置
    print("群组配置测试:")
    list_groups()
    print(f"\n{GROUP_CONFIG_HELP}")
