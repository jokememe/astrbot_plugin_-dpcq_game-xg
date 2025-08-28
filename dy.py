# 标准化的丹药数据结构
from typing import Optional, Dict, List, Tuple
from main import *

PILLS_DATA = [
    # ===== 修炼辅助类丹药 =====
    {
        "id": "train_boost_1",
        "name": "1品聚气丹",
        "type": "cultivation",
        "rank": "一品",
        "effect": "train_boost",
        "effect_value": 0.1,
        "effect_duration": 1800,
        "price": 150,
        "value": 100,
        "description": "修炼速度+10%持续30分钟"
    },
    {
        "id": "train_boost_2",
        "name": "2品聚气散",
        "type": "cultivation",
        "rank": "二品",
        "effect": "train_boost",
        "effect_value": 0.2,
        "effect_duration": 3600,
        "price": 450,
        "value": 300,
        "description": "修炼速度+20%持续1小时"
    },
    {
        "id": "train_boost_4",
        "name": "4品玄灵丹",
        "type": "cultivation",
        "rank": "四品",
        "effect": "train_boost",
        "effect_value": 0.3,
        "effect_duration": 7200,
        "price": 2250,
        "value": 1500,
        "description": "修炼速度+30%持续2小时"
    },
    {
        "id": "train_boost_6",
        "name": "6品造化丹",
        "type": "cultivation",
        "rank": "六品",
        "effect": "train_boost",
        "effect_value": 0.5,
        "effect_duration": 10800,
        "price": 10500,
        "value": 7000,
        "description": "修炼速度+50%持续3小时"
    },
    {
        "id": "train_boost_8",
        "name": "8品混沌丹",
        "type": "cultivation",
        "rank": "八品",
        "effect": "train_boost",
        "effect_value": 1.0,
        "effect_duration": 3600,
        "price": 45000,
        "value": 30000,
        "description": "修炼速度+100%持续1小时"
    },
    {
        "id": "train_safe_1",
        "name": "1品凝神丹",
        "type": "cultivation",
        "rank": "一品",
        "effect": "train_safe",
        "effect_value": 0.1,
        "effect_duration": 3600,
        "price": 135,
        "value": 90,
        "description": "修炼时减少10%走火入魔概率"
    },
    {
        "id": "train_safe_4",
        "name": "4品凝神丹",
        "type": "cultivation",
        "rank": "四品",
        "effect": "train_safe",
        "effect_value": 0.3,
        "effect_duration": 3600,
        "price": 2400,
        "value": 1600,
        "description": "修炼时减少30%走火入魔概率"
    },
    {
        "id": "train_immune_5",
        "name": "5品凝神丹",
        "type": "cultivation",
        "rank": "五品",
        "effect": "train_immune",
        "effect_value": 1.0,
        "effect_duration": 7200,
        "price": 5250,
        "value": 3500,
        "description": "修炼时不会走火入魔"
    },
    {
        "id": "train_perfect_8",
        "name": "8品凝神丹",
        "type": "cultivation",
        "rank": "八品",
        "effect": "train_perfect",
        "effect_value": 0.2,
        "effect_duration": 7200,
        "price": 57000,
        "value": 38000,
        "description": "修炼时不会走火入魔且效率+20%"
    },
    {
        "id": "train_extra_3",
        "name": "3品玄灵丹",
        "type": "cultivation",
        "rank": "三品",
        "effect": "train_extra",
        "effect_value": 0.05,
        "effect_duration": 3600,
        "price": 1125,
        "value": 750,
        "description": "修炼时额外获得5%斗气"
    },
    {
        "id": "train_extra_6",
        "name": "6品玄灵丹",
        "type": "cultivation",
        "rank": "六品",
        "effect": "train_extra",
        "effect_value": 0.15,
        "effect_duration": 3600,
        "price": 12000,
        "value": 8000,
        "description": "修炼时额外获得15%斗气"
    },
    {
        "id": "train_extra_7",
        "name": "7品玄灵丹",
        "type": "cultivation",
        "rank": "七品",
        "effect": "train_extra",
        "effect_value": 0.25,
        "effect_duration": 3600,
        "price": 25500,
        "value": 17000,
        "description": "修炼时额外获得25%斗气"
    },
    {
        "id": "train_extra_9",
        "name": "9品玄灵丹",
        "type": "cultivation",
        "rank": "九品",
        "effect": "train_extra",
        "effect_value": 0.5,
        "effect_duration": 3600,
        "price": 127500,
        "value": 85000,
        "description": "修炼时额外获得50%斗气"
    },

    # ===== 突破辅助类丹药 =====
    {
        "id": "breakthrough_boost_3",
        "name": "3品破障丹",
        "type": "breakthrough",
        "rank": "三品",
        "effect": "breakthrough_boost",
        "effect_value": 0.15,
        "effect_duration": 3600,
        "price": 1200,
        "value": 800,
        "description": "突破概率+15%"
    },
    {
        "id": "breakthrough_boost_4",
        "name": "4品破境丹",
        "type": "breakthrough",
        "rank": "四品",
        "effect": "breakthrough_boost",
        "effect_value": 0.20,
        "effect_duration": 3600,
        "price": 2700,
        "value": 1800,
        "description": "突破概率+20%"
    },
    {
        "id": "breakthrough_boost_6",
        "name": "6品破界丹",
        "type": "breakthrough",
        "rank": "六品",
        "effect": "breakthrough_boost",
        "effect_value": 0.25,
        "effect_duration": 3600,
        "price": 13500,
        "value": 9000,
        "description": "突破概率+25%"
    },
    {
        "id": "breakthrough_boost_8",
        "name": "8品天劫丹",
        "type": "breakthrough",
        "rank": "八品",
        "effect": "breakthrough_boost",
        "effect_value": 0.30,
        "effect_duration": 3600,
        "price": 52500,
        "value": 35000,
        "description": "突破概率+30%"
    },
    {
        "id": "breakthrough_protect_2",
        "name": "2品护脉丹",
        "type": "breakthrough",
        "rank": "二品",
        "effect": "breakthrough_protect",
        "effect_value": 1.0,
        "effect_duration": 0,
        "price": 600,
        "value": 400,
        "description": "突破失败保护"
    },

    # ===== 战斗辅助类丹药 =====
    {
        "id": "battle_boost_3",
        "name": "3品龙力丹",
        "type": "battle",
        "rank": "三品",
        "effect": "battle_strength",
        "effect_value": 0.3,
        "effect_duration": 3600,
        "price": 1050,
        "value": 700,
        "description": "力量+30%持续1小时"
    },
    {
        "id": "defense_boost_4",
        "name": "4品金刚丹",
        "type": "battle",
        "rank": "四品",
        "effect": "battle_defense",
        "effect_value": 0.5,
        "effect_duration": 3600,
        "price": 1950,
        "value": 1300,
        "description": "防御+50%持续1小时"
    },
    {
        "id": "super_boost_5",
        "name": "5品战神丹",
        "type": "battle",
        "rank": "五品",
        "effect": "battle_all",
        "effect_value": 0.5,
        "effect_duration": 1800,
        "price": 6000,
        "value": 4000,
        "description": "全属性+50%持续30分钟"
    },
    {
        "id": "god_mode_9",
        "name": "9品至尊丹",
        "type": "battle",
        "rank": "九品",
        "effect": "battle_all",
        "effect_value": 2.0,
        "effect_duration": 1800,
        "price": 135000,
        "value": 90000,
        "description": "全属性+200%持续30分钟"
    },
    {
        "id": "desperate_boost_7",
        "name": "7品阴阳丹",
        "type": "battle",
        "rank": "七品",
        "effect": "battle_desperate",
        "effect_value": 1.0,
        "effect_duration": 600,
        "price": 19500,
        "value": 13000,
        "description": "濒死时全属性翻倍持续10分钟"
    },
    {
        "id": "invincible_8",
        "name": "8品不朽丹",
        "type": "battle",
        "rank": "八品",
        "effect": "battle_invincible",
        "effect_value": 1.0,
        "effect_duration": 3600,
        "price": 60000,
        "value": 40000,
        "description": "1小时内无敌"
    },

    # ===== 恢复类丹药 =====
    {
        "id": "restore_qi_1",
        "name": "1品回气丹",
        "type": "recovery",
        "rank": "一品",
        "effect": "restore_qi",
        "effect_value": 0.1,
        "effect_duration": 0,
        "price": 120,
        "value": 80,
        "description": "恢复10%斗气"
    },
    {
        "id": "heal_1",
        "name": "1品疗伤丹",
        "type": "healing",
        "rank": "一品",
        "effect": "heal",
        "effect_value": 0.2,
        "effect_duration": 0,
        "price": 180,
        "value": 120,
        "description": "恢复20%生命值"
    },
    {
        "id": "recover_3",
        "name": "3品复元丹",
        "type": "recovery",
        "rank": "三品",
        "effect": "recover",
        "effect_value": 0.5,
        "effect_duration": 0,
        "price": 1500,
        "value": 1000,
        "description": "脱离濒死状态并恢复50%生命和斗气"
    },

    # ===== 复活类丹药 =====
    {
        "id": "revive_2",
        "name": "2品回魂丹",
        "type": "revival",
        "rank": "二品",
        "effect": "revive",
        "effect_value": 0.3,
        "effect_duration": 0,
        "price": 750,
        "value": 500,
        "description": "脱离濒死状态"
    },
    {
        "id": "auto_revive_5",
        "name": "5品不死丹",
        "type": "revival",
        "rank": "五品",
        "effect": "auto_revive",
        "effect_value": 1.0,
        "effect_duration": 86400,
        "price": 7500,
        "value": 5000,
        "description": "死亡后自动复活"
    },
    {
        "id": "reincarnate_6",
        "name": "6品轮回丹",
        "type": "revival",
        "rank": "六品",
        "effect": "reincarnate",
        "effect_value": 1.0,
        "effect_duration": 259200,
        "price": 15000,
        "value": 10000,
        "description": "死亡后保留记忆转世"
    },
    {
        "id": "full_revive_7",
        "name": "7品涅槃丹",
        "type": "revival",
        "rank": "七品",
        "effect": "full_revive",
        "effect_value": 1.0,
        "effect_duration": 0,
        "price": 30000,
        "value": 20000,
        "description": "死亡后满状态复活"
    },
    {
        "id": "immortal_9",
        "name": "9品永生丹",
        "type": "revival",
        "rank": "九品",
        "effect": "immortal",
        "effect_value": 1.0,
        "effect_duration": 600,
        "price": 150000,
        "value": 100000,
        "description": "死亡后立即满状态复活并获得10分钟无敌状态"
    },

    # ===== 升级类丹药 =====
    {
        "id": "level_up_5",
        "name": "5品天元丹",
        "type": "upgrade",
        "rank": "五品",
        "effect": "level_up",
        "effect_value": 1,
        "effect_duration": 0,
        "price": 4500,
        "value": 3000,
        "description": "直接提升1星等级"
    },
    {
        "id": "realm_up_9",
        "name": "9品天道丹",
        "type": "upgrade",
        "rank": "九品",
        "effect": "realm_up",
        "effect_value": 1,
        "effect_duration": 0,
        "price": 120000,
        "value": 80000,
        "description": "直接突破1个大境界"
    },

    # ===== 探索辅助类丹药 =====
    {
        "id": "explore_cd_2",
        "name": "2品风行丹",
        "type": "exploration",
        "rank": "二品",
        "effect": "explore_cd",
        "effect_value": 0.3,
        "effect_duration": 3600,
        "price": 525,
        "value": 350,
        "description": "探索冷却减少30%持续1小时"
    },
    {
        "id": "explore_cd_3",
        "name": "3品风行丹",
        "type": "exploration",
        "rank": "三品",
        "effect": "explore_cd",
        "effect_value": 0.5,
        "effect_duration": 7200,
        "price": 1350,
        "value": 900,
        "description": "探索冷却减少50%持续2小时"
    },
    {
        "id": "explore_cd_6",
        "name": "6品风行丹",
        "type": "exploration",
        "rank": "六品",
        "effect": "explore_cd",
        "effect_value": 0.7,
        "effect_duration": 10800,
        "price": 12750,
        "value": 8500,
        "description": "探索冷却减少70%持续3小时"
    },

    # ===== 永久增益类丹药 =====
    {
        "id": "perm_health_1",
        "name": "1品淬体丹",
        "type": "permanent",
        "rank": "一品",
        "effect": "perm_health",
        "effect_value": 5,
        "effect_duration": 0,
        "price": 300,
        "value": 200,
        "description": "永久增加5点生命上限"
    },
    {
        "id": "perm_health_2",
        "name": "2品洗髓丹",
        "type": "permanent",
        "rank": "二品",
        "effect": "perm_health",
        "effect_value": 10,
        "effect_duration": 0,
        "price": 750,
        "value": 500,
        "description": "永久增加10点生命上限"
    },
    {
        "id": "perm_health_4",
        "name": "4品洗髓丹",
        "type": "permanent",
        "rank": "四品",
        "effect": "perm_health",
        "effect_value": 30,
        "effect_duration": 0,
        "price": 3000,
        "value": 2000,
        "description": "永久增加30点生命上限"
    },
    {
        "id": "perm_health_5",
        "name": "5品洗髓丹",
        "type": "permanent",
        "rank": "五品",
        "effect": "perm_health",
        "effect_value": 50,
        "effect_duration": 0,
        "price": 6750,
        "value": 4500,
        "description": "永久增加50点生命上限"
    },
    {
        "id": "perm_health_7",
        "name": "7品洗髓丹",
        "type": "permanent",
        "rank": "七品",
        "effect": "perm_health",
        "effect_value": 100,
        "effect_duration": 0,
        "price": 27000,
        "value": 18000,
        "description": "永久增加100点生命上限"
    },
    {
        "id": "perm_health_8",
        "name": "8品洗髓丹",
        "type": "permanent",
        "rank": "八品",
        "effect": "perm_health",
        "effect_value": 200,
        "effect_duration": 0,
        "price": 67500,
        "value": 45000,
        "description": "永久增加200点生命上限"
    },
    {
        "id": "perm_health_9",
        "name": "9品洗髓丹",
        "type": "permanent",
        "rank": "九品",
        "effect": "perm_health",
        "effect_value": 500,
        "effect_duration": 0,
        "price": 150000,
        "value": 100000,
        "description": "永久增加500点生命上限"
    }
]

# ==================== 完整的丹药效果处理器映射 ====================

# 丹药效果处理器映射
PILL_EFFECT_HANDLERS = {
    # 修炼辅助类
    "train_boost": lambda player, pill: player.apply_temp_boost("train_boost", pill["effect_value"],
                                                                pill["effect_duration"]),
    "train_safe": lambda player, pill: player.apply_temp_boost("train_safe", pill["effect_value"],
                                                               pill["effect_duration"]),
    "train_immune": lambda player, pill: player.apply_temp_boost("train_immune", pill["effect_value"],
                                                                 pill["effect_duration"]),
    "train_perfect": lambda player, pill: (
        player.apply_temp_boost("train_boost", pill["effect_value"], pill["effect_duration"]),
        player.apply_temp_boost("train_immune", 1.0, pill["effect_duration"])
    ),
    "train_extra": lambda player, pill: player.apply_temp_boost("train_extra", pill["effect_value"],
                                                                pill["effect_duration"]),

    # 突破辅助类
    "breakthrough_boost": lambda player, pill: player.apply_temp_boost("breakthrough", pill["effect_value"],
                                                                       pill["effect_duration"]),
    "breakthrough_protect": lambda player, pill: player.add_item(pill["name"]),  # 护脉丹直接添加到背包

    # 战斗辅助类
    "battle_strength": lambda player, pill: player.apply_temp_boost("strength", pill["effect_value"],
                                                                    pill["effect_duration"]),
    "battle_defense": lambda player, pill: player.apply_temp_boost("defense", pill["effect_value"],
                                                                   pill["effect_duration"]),
    "battle_all": lambda player, pill: player.apply_temp_boost("all", pill["effect_value"], pill["effect_duration"]),
    "battle_desperate": lambda player, pill: player.apply_temp_boost("desperate", pill["effect_value"],
                                                                     pill["effect_duration"]),
    "battle_invincible": lambda player, pill: player.apply_temp_boost("invincible", pill["effect_value"],
                                                                      pill["effect_duration"]),

    # 恢复类
    "restore_qi": lambda player, pill: player.gain_qi(int(player.required_qi * pill["effect_value"])),
    "heal": lambda player, pill: player.heal(int(player.max_health * pill["effect_value"])),
    "recover": lambda player, pill: (
        player.heal(int(player.max_health * pill["effect_value"])),
        player.gain_qi(int(player.required_qi * pill["effect_value"]))
    ),

    # 复活类
    "revive": lambda player, pill: player.revive(full=False),
    "auto_revive": lambda player, pill: player.apply_temp_boost("auto_revive", pill["effect_value"],
                                                                pill["effect_duration"]),
    "reincarnate": lambda player, pill: player.apply_temp_boost("reincarnate", pill["effect_value"],
                                                                pill["effect_duration"]),
    "full_revive": lambda player, pill: player.revive(full=True),
    "immortal": lambda player, pill: (
        player.revive(full=True),
        player.apply_temp_boost("immortal", pill["effect_value"], pill["effect_duration"])
    ),

    # 升级类
    "level_up": lambda player, pill: (
        setattr(player, 'level', player.level + pill["effect_value"]),
        setattr(player, 'current_qi', 0),
        setattr(player, 'required_qi', player._calculate_required_qi())
    ),
    "realm_up": lambda player, pill: (
        setattr(player, 'realm_index', player.realm_index + pill["effect_value"]),
        setattr(player, 'level', 1),
        setattr(player, 'current_qi', 0),
        setattr(player, 'required_qi', player._calculate_required_qi())
    ),

    # 探索辅助类
    "explore_cd": lambda player, pill: player.apply_temp_boost("explore_cd", pill["effect_value"],
                                                               pill["effect_duration"]),

    # 永久增益类
    "perm_health": lambda player, pill: (
        setattr(player, 'max_health', player.max_health + pill["effect_value"]),
        setattr(player, 'health', player.health + pill["effect_value"])
    )
}


# ==================== 增强的丹药系统工具函数 ====================

class PillSystem:
    """丹药系统管理类"""

    @staticmethod
    def get_pill_by_name(name: str) -> Optional[Dict]:
        """根据名称获取丹药数据"""
        for pill in PILLS_DATA:
            if pill["name"] == name:
                return pill
        return None

    @staticmethod
    def get_pill_by_id(pill_id: str) -> Optional[Dict]:
        """根据ID获取丹药数据"""
        for pill in PILLS_DATA:
            if pill["id"] == pill_id:
                return pill
        return None

    @staticmethod
    def get_pills_by_type(pill_type: str) -> List[Dict]:
        """根据类型获取丹药列表"""
        return [pill for pill in PILLS_DATA if pill["type"] == pill_type]

    @staticmethod
    def get_pills_by_rank(rank: str) -> List[Dict]:
        """根据品阶获取丹药列表"""
        return [pill for pill in PILLS_DATA if pill["rank"] == rank]

    @staticmethod
    def get_pills_by_effect(effect: str) -> List[Dict]:
        """根据效果类型获取丹药列表"""
        return [pill for pill in PILLS_DATA if pill["effect"] == effect]

    @staticmethod
    def get_pill_effect_handler(effect_type: str):
        """获取丹药效果处理器"""
        return PILL_EFFECT_HANDLERS.get(effect_type)

    @staticmethod
    def use_pill(player: Player, pill_name: str) -> Tuple[bool, str]:
        """使用丹药的统一入口"""
        pill = PillSystem.get_pill_by_name(pill_name)
        if not pill:
            return False, "无效的丹药"

        if pill_name not in player.inventory:
            return False, "你没有这个丹药"

        # 获取效果处理器
        handler = PillSystem.get_pill_effect_handler(pill["effect"])
        if not handler:
            return False, "该丹药暂时无法使用"

        # 执行效果
        try:
            result = handler(player, pill)
            player.inventory.remove(pill_name)

            # 生成使用结果消息
            duration_msg = ""
            if pill["effect_duration"] > 0:
                minutes = pill["effect_duration"] // 60
                duration_msg = f"，持续{minutes}分钟" if minutes < 60 else f"，持续{minutes // 60}小时"

            return True, f"使用【{pill_name}】，{pill['description']}{duration_msg}"
        except Exception as e:
            logger.error(f"使用丹药失败: {e}")
            return False, "使用丹药失败"

    @staticmethod
    def get_pill_description(pill_name: str) -> str:
        """获取丹药的详细描述"""
        pill = PillSystem.get_pill_by_name(pill_name)
        if not pill:
            return "未知丹药"

        description = f"【{pill['name']}】\n"
        description += f"类型：{pill['type']} | 品阶：{pill['rank']}\n"
        description += f"效果：{pill['description']}\n"

        if pill["effect_duration"] > 0:
            minutes = pill["effect_duration"] // 60
            duration = f"{minutes}分钟" if minutes < 60 else f"{minutes // 60}小时"
            description += f"持续时间：{duration}\n"

        description += f"价值：{pill['value']} | 价格：{pill['price']}金币"

        return description

    @staticmethod
    def generate_random_pill(min_rank: int = 1, max_rank: int = 9) -> Optional[Dict]:
        """随机生成一个指定品阶范围内的丹药"""
        available_pills = [
            pill for pill in PILLS_DATA
            if min_rank <= int(pill["rank"][0]) <= max_rank
        ]

        if not available_pills:
            return None

        return random.choice(available_pills)
