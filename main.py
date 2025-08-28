import json
import math
import os
import random
import time
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


# ==================== 游戏常量定义 ====================
# 探索等级定义
EXPLORE_LEVELS = {
    "初级": {
        "weight": 50,
        "danger": 0.2,
        "reward_factor": 0.8,
        "min_realm": 0,  # 斗之气
        "max_realm": 10
    },
    "中级": {
        "weight": 30,
        "danger": 0.4,
        "reward_factor": 1.2,
        "min_realm": 0,  # 斗者
        "max_realm": 10   # 大斗师
    },
    "高级": {
        "weight": 20,
        "danger": 0.6,
        "reward_factor": 1.5,
        "min_realm": 0,  # 大斗师
        "max_realm": 10  # 斗帝
    }
}

EXPLORE_EVENTS = [
    {
        "name": "灵药发现",
        "description": "在深山中发现一株散发着灵光的草药",
        "effects": [
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("healing")[:3 + ["初级", "中级", "高级"].index(level) * 2]]
            )), "获得疗伤丹药")
        ],
        "weight": 30
    },
    {
        "name": "古洞探险",
        "description": "发现一个布满符文的神秘洞窟",
        "effects": [
            lambda p, level: (
                p.gain_qi(qi := int(p.required_qi * (0.1 + 0.05 * ["初级", "中级", "高级"].index(level)**2))),
                f"吸收洞中灵气，获得{qi}斗气"),
            lambda p, level: (setattr(p, 'gold', p.gold + (
                gold := random.randint(50, 200) * (1 + ["初级", "中级", "高级"].index(level)**2))),
                f"找到前辈遗留的{gold}金币"),
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("recovery")[:1 + ["初级", "中级", "高级"].index(level)]]
            )), "获得恢复丹药") if random.random() < 0.3 else (None, ""),
            lambda p, level: (
                p.add_item(tech := random.choices(
                    ["黄阶功法", "玄阶功法", "地阶功法", "天阶功法"],
                    weights=[45, 35, 1, 0.1]
                )[0]),
                f"发现上古修炼秘籍【{tech}】"
            ) if random.random() < (0.1 + ["初级", "中级", "高级"].index(level)*0.05) else (None, "")
        ],
        "weight": 25
    },
    {
        "name": "灵石矿洞",
        "description": "发现一座未被开采的灵石矿脉",
        "effects": [
            lambda p, level: (
                setattr(p, 'gold', p.gold + (gold := random.randint(200, 500))),
                f"挖掘到{gold}金币"
            ),
            lambda p, level: (
                p.take_damage(dmg := random.randint(30, 80)*(p.realm_index**2)),
                f"矿洞突然塌方！损失{dmg}点生命值"
            ) if random.random() < 0.4 else (None, "")
        ],
        "weight": 18
    },
    {
        "name": "顿悟石碑",
        "description": "一块刻满古老文字的石碑，隐约散发道韵",
        "effects": [
            lambda p, level: (
                p.add_item(tech := random.choices(
                    ["黄阶功法", "玄阶功法", "地阶功法", "天阶功法"],
                    weights=[
                        60 if level != "高级" else 30,  # 黄阶
                        30 if level != "高级" else 20,  # 玄阶
                        0 if level != "高级" else 10,   # 地阶
                        0 if level != "高级" else 0.1   # 天阶
                    ]
                )[0]),
                f"顿悟石碑奥义，领悟【{tech}】"
            ) if level == "高级" or random.random() < 0.6 else (None, ""),
            lambda p, level: (
                p.take_damage(int(p.health * 0.5)),
                "参悟时走火入魔，气血逆冲！"
            ) if random.random() < 0.3 else (None, "")
        ],
        "weight": 8
    },
    {
        "name": "灵脉暴走",
        "description": "地下灵脉突然暴动，狂暴的灵气四处奔涌",
        "effects": [
            lambda p, level: (
                p.gain_qi(qi := int(p.required_qi * (0.4 + 0.1 * ["初级", "中级", "高级"].index(level)**2))),
                f"强行吸收暴走灵气，获得{qi}斗气"
            ),
            lambda p, level: (
                p.take_damage(dmg := random.randint(5, 10)*(["初级", "中级", "高级"].index(level)**3)*p.realm_index/2),
                f"经脉受损，喷出一口鲜血，损失{dmg}点生命值"
            ) if random.random() < 0.8 else (None, "")
        ],
        "weight": 15
    },
    {
        "name": "魔兽遭遇",
        "description": "遭遇一头凶猛的魔兽，生死一线！",
        "effects": [
            lambda p, level: (
                p.add_item("魔兽内丹"),
                "奋勇击败魔兽！获得【魔兽内丹】"
            ) if random.random() < 0.5 else (
                p.take_damage(
                    dmg := random.randint(5, 10) * (["初级", "中级", "高级"].index(level) ** 3) * p.realm_index / 2),
                f"战斗失败，受到攻击，损失{dmg}点生命值" +
                (f"，并丢失了【{p.inventory[-1]}】" if p.inventory and random.random() < (0.3 + 0.1 * ["初级", "中级", "高级"].index(level)) else "")
            )
        ],
        "weight": 20
    },
    {
        "name": "前辈遗泽",
        "description": "发现一位前辈修炼者的坐化之地",
        "effects": [
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("cultivation")[:2 + ["初级", "中级", "高级"].index(level) ** 2]]
            )), f"获得前辈遗留的丹药"),
            lambda p, level: (setattr(p, 'gold', p.gold + (
                gold := random.randint(100, 300) * (1 + ["初级", "中级", "高级"].index(level)**2))),
                f"发现{gold}金币"),
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("breakthrough")[:1 + ["初级", "中级", "高级"].index(level)**2]]
            )), "获得突破丹药") if random.random() < 0.4 else (None, ""),
            lambda p, level: (
                p.add_item(tech := random.choices(
                    ["黄阶功法", "玄阶功法", "地阶功法", "天阶功法"],
                    weights=[
                        60 if level != "高级" else 30,  # 黄阶
                        30 if level != "高级" else 20,  # 玄阶
                        0 if level != "高级" else 10,   # 地阶
                        0 if level != "高级" else 0.1   # 天阶
                    ]
                )[0]),
                f"顿悟石碑奥义，领悟【{tech}】"
            ) if level == "高级" or random.random() < 0.6 else (None, ""),
        ],
        "weight": 15
    },
    {
        "name": "灵气漩涡",
        "description": "遇到一个灵气异常浓郁的漩涡",
        "effects": [
            lambda p, level: (
                p.gain_qi(qi := int(p.required_qi * (0.15 + 0.05 * ["初级", "中级", "高级"].index(level)**2))),
                f"吸收大量灵气，获得{qi}斗气"),
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("cultivation")[:1 + ["初级", "中级", "高级"].index(level)]]
            )), "获得修炼丹药") if random.random() < 0.5 else (None, "")
        ],
        "weight": 10
    },
    {
        "name": "秘境奇遇",
        "description": "误入一处远古秘境",
        "effects": [
            lambda p, level: (p.gain_qi(qi := int(p.required_qi * (0.2 + 0.1 * ["初级", "中级", "极高级"].index(level)**2))),
                f"吸收秘境灵气，获得{qi}斗气"),
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("battle")[:1 + ["初级", "中级", "高级"].index(level) * 2]]
            )), f"获得秘境宝物丹药"),
            lambda p, level: (setattr(p, 'gold', p.gold + (
                gold := random.randint(200, 500) * (1 + ["初级", "中级", "高级"].index(level)**2))),
                f"发现秘境宝藏{gold}金币")
        ],
        "weight": 5
    },
    {
        "name": "灵兽巢穴",
        "description": "发现一个灵兽的巢穴",
        "effects": [
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("recovery")[:2 + ["初级", "中级", "高级"].index(level)]]
            )), f"获得灵兽守护的丹药"),
            lambda p, level: (p.take_damage(dmg := random.randint(5, 20) * (1 + ["初级", "中级", "高级"].index(level)**2)),
                f"被灵兽攻击，损失{dmg}点生命值") if random.random() < 0.6 else (None, "")
        ],
        "weight": 8
    },
    {
        "name": "上古遗迹",
        "description": "发现一处上古修炼者的遗迹",
        "effects": [
            lambda p, level: (p.add_item(random.choice(
                [pill["name"] for pill in PillSystem.get_pills_by_type("revival")[:1 + ["初级", "中级", "高级"].index(level)]]
            )), f"发现上古遗宝丹药"),
            lambda p, level: (
                p.gain_qi(qi := int(p.required_qi * (0.25 + 0.05 * ["初级", "中级", "高级"].index(level)**2))),
                f"感悟上古道韵，获得{qi}斗气"),
            lambda p, level: (
                p.add_item(tech := random.choices(
                    ["黄阶功法", "玄阶功法", "地阶功法", "天阶功法"],
                    weights=[30, 25, 5, 0.1]
                )[0]),
                f"领悟上古秘法【{tech}】"
            ) if random.random() < (0.3 + ["初级", "中级", "高级"].index(level)*0.15) else (None, "")
        ],
        "weight": 3
    },
    {
        "name": "功法传承",
        "description": "在一处古老石碑前感受到强大的功法波动",
        "effects": [
            lambda p, level: (
                p.add_item(tech := random.choices(
                    ["黄极功法", "玄阶功法", "地阶功法", "天阶功法"],
                    weights=[50, 40, 1, 0.1]
                )[0]),
                f"领悟石碑中的【{tech}】"
            )
        ],
        "weight": 5
    }
]

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

REALMS = [
    {"name": "斗之气", "levels": 10, "breakthrough_chance": 0.9, "base_qi": 50, "train_gain": (5, 10)},
    {"name": "斗者", "levels": 10, "breakthrough_chance": 0.7, "base_qi": 200, "train_gain": (5, 20)},
    {"name": "斗师", "levels": 10, "breakthrough_chance": 0.6, "base_qi": 300, "train_gain": (10, 20)},
    {"name": "大斗师", "levels": 10, "breakthrough_chance": 0.5, "base_qi": 500, "train_gain": (15, 20)},
    {"name": "斗灵", "levels": 10, "breakthrough_chance": 0.4, "base_qi": 800, "train_gain": (25, 30)},
    {"name": "斗王", "levels": 10, "breakthrough_chance": 0.3, "base_qi": 1000, "train_gain": (25, 40)},
    {"name": "斗皇", "levels": 10, "breakthrough_chance": 0.25, "base_qi": 1200, "train_gain": (30, 70)},
    {"name": "斗宗", "levels": 10, "breakthrough_chance": 0.2, "base_qi": 3000, "train_gain": (100, 300)},
    {"name": "斗尊", "levels": 10, "breakthrough_chance": 0.15, "base_qi": 7000, "train_gain": (600, 1200)},
    {"name": "斗圣", "levels": 10, "breakthrough_chance": 0.1, "base_qi": 30000, "train_gain": (800, 1600)},
    {"name": "斗帝", "levels": 10, "breakthrough_chance": 0.05, "base_qi": 100000, "train_gain": (1000, 2000)},
    {"name": "天至尊", "levels": 3, "breakthrough_chance": 0.01, "base_qi": 1000000, "train_gain": (10000, 20000)},
    {"name": "主宰", "levels": 1000000000000, "breakthrough_chance": 0.05, "base_qi": 100000000, "train_gain": (10000, 20000)}
]

# 功法加成系数与价值系统
CULTIVATION_BOOST = {
    "黄阶功法": {"boost": 1.1, "value": 500, "price": 750},
    "玄阶功法": {"boost": 1.2, "value": 1500, "price": 2250},
    "地阶功法": {"boost": 1.8, "value": 5000, "price": 7500},
    "天阶功法": {"boost": 2.5, "value": 15000, "price": 22500}
}

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

class DataPersistence:
    def __init__(self, storage_dir: str = "dpcq_data"):
        # 获取当前文件所在的目录
        self.storage_dir = Path(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_world(self, group_id: str, data: Dict[str, Any]):
        file_path = self.storage_dir / f"{group_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_world(self, group_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.storage_dir / f"{group_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None

    def delete_world(self, group_id: str):
        file_path = self.storage_dir / f"{group_id}.json"
        if file_path.exists():
            os.remove(file_path)

    def list_saved_worlds(self) -> List[str]:
        return [f.stem for f in self.storage_dir.glob("*.json")]

    def get_world_info(self, group_id: str) -> Optional[Dict[str, Any]]:
        data = self.load_world(group_id)
        if not data:
            return None
        return {
            "players": len(data.get("players", {})),
            "last_update": time.ctime(os.path.getmtime(self.storage_dir / f"{group_id}.json")),
            "game_started": data.get("game_started", False)
        }

class Player:
    def __init__(self, user_id: str, user_name: str, realm_index=0):
        self.user_id = user_id
        self.user_name = user_name
        self.realm_index = realm_index  # 当前境界索引
        self.level = 1  # 当前星级(1-10)
        self.current_qi = 0  # 当前境界积累的斗气
        self.required_qi = self._calculate_required_qi()  # 升级所需斗气
        self.max_health = self._calculate_max_health()
        self.health = self.max_health
        self.gold = 100
        self.inventory = []
        self.last_train_time = 0
        self.last_explore_time = 0
        self.last_duel_time = 0
        self.cooldowns = {
            "train": 60,  # 1分钟冷却
            "explore": 60,  # 1分钟冷却
            "duel": 60  # 1分钟冷却
        }
        self.zb=[] #准备栏
        self.training_progress = 0 #修炼增溢
        self.is_dying = False  # 濒死状态
        self.death_time = 0  # 死亡时间
        self.temp_boosts = {}  # 临时加成 {"attr": (value, expire_time)}
        self.lan_tiao = 100

        logger.info(f"DEBUG: Player {user_name} 初始化，realm_index={self.realm_index}")

    def _calculate_required_qi(self) -> int:
        base = REALMS[self.realm_index]["base_qi"]
        logger.info(f"{self.user_name} 当前境界 {self.realm_index}，基础斗气 {base}")
        return base + (self.level - 1) * int(base * 0.1)

    def _calculate_max_health(self):
        max_health = 100 + (self.realm_index**2)*10
        logger.info(f"{self.user_name} 当前境界 {self.realm_index}，当前最大生命值 {max_health}")
        return max_health

    @property
    def realm(self):
        return REALMS[self.realm_index]["name"]

    @property
    def title(self):
        titles = ["无名小卒", "初露锋芒", "小有名气", "一方强者", "威震四方",
                  "名动大陆", "绝世高手", "一代宗师", "巅峰强者", "超凡入圣", "万古至尊"]
        return titles[self.realm_index]

    @property
    def power(self):
        base_power = 0
        for i in range(0,self.realm_index):
            if i < self.realm_index:
                base_power += REALMS[i]['base_qi'] * 10
            base_power += REALMS[i]['base_qi'] * self.level

        # 功法加成
        for item in self.inventory:
            if item in CULTIVATION_BOOST:
                base_power *= CULTIVATION_BOOST[item]['boost']

        # 临时加成
        for boost, (value, expire) in self.temp_boosts.items():
            if time.time() < expire:
                if boost == "all":
                    base_power *= (1 + value / 100)
                elif boost == "strength":
                    base_power *= (1 + value / 100)


        return int(base_power)

    def can_train(self):
        return time.time() - self.last_train_time > self.cooldowns["train"]

    def can_explore(self):
        return time.time() - self.last_explore_time > self.cooldowns["explore"]

    def can_duel(self):
        return time.time() - self.last_duel_time > self.cooldowns["duel"]

    def gain_qi(self, amount: int):
        self.current_qi += amount
        if self.current_qi >= self.required_qi:
            self.level_up()

    def level_up(self):
        self.current_qi -= self.required_qi
        self.level += 1
        self.required_qi = self._calculate_required_qi()

        if self.level > REALMS[self.realm_index]["levels"]:
            return True  # 需要突破
        return False

    def take_damage(self, amount: int):
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            self.is_dying = True
            self.death_time = time.time()
            return True  # 触发濒死
        return False

    def apply_temp_boost(self, boost_type: str, value: float, duration: int) -> None:
        """应用临时加成"""
        expire_time = time.time() + duration
        self.temp_boosts[boost_type] = (value, expire_time)

    def heal(self, amount: int) -> None:
        """恢复生命值"""
        self.health = min(self.max_health, self.health + amount)

    def revive(self, full=False):
        if full:
            self.health = self.max_health
        else:
            self.health = max(1, int(self.max_health * 0.3))
        self.is_dying = False
        self.death_time = 0

    def check_status(self):
        if self.is_dying:
            return False, "你处于濒死状态，需要使用回魂丹复活！"
        return True, ""

    def add_item(self, item_name: str):
        if len(self.inventory) < 20 + sum(5 for item in self.inventory if "空间戒指" in item):
            self.inventory.append(item_name)
            return True
        return False

    def lose_item(self):
        if self.inventory:
            item_priority = {
                "一品": 1, "二品": 2, "三品": 3, "四品": 4, "五品": 5,
                "六品": 6, "七品": 7, "八品": 8, "九品": 9
            }
            items = sorted(self.inventory,
                           key=lambda x: item_priority.get(x[:2], 0))
            item = items[0]
            self.inventory.remove(item)
            return item
        return None

    def use_item(self, item_name: str):
        pill_result = PillSystem.use_pill(self, item_name)
        if pill_result[0] or pill_result[1] != "无效的丹药":
            return pill_result


        return False, "无效的物品"

    def train(self):
        if not self.can_train():
            remaining = int(self.cooldowns["train"] - (time.time() - self.last_train_time))
            return False, f"修炼需要冷却，还需等待{remaining}秒"

        status_ok, msg = self.check_status()
        if not status_ok:
            return False, msg

        min_gain, max_gain = REALMS[self.realm_index]["train_gain"]
        base_gain = random.randint(min_gain, max_gain)

        boost = 1.0
        boost = boost + self.training_progress

        qi_gain = int(base_gain * boost)
        self.current_qi += qi_gain
        self.health += 10
        if self.health>self.max_health:
            self.health = self.max_health
        self.last_train_time = time.time()

        if self.current_qi >= self.required_qi:
            need_breakthrough = self.level_up()
            if need_breakthrough:
                return True, "已达到突破条件！使用 /突破 尝试突破"
            return True, f"★ 突破至 {self.realm} {self.level}星！★"

        return True, f"修炼获得{qi_gain}斗气点（基础{base_gain} x{boost:.1f}），当前进度：{self.current_qi}/{self.required_qi}"

    def breakthrough(self):
        if self.level < REALMS[self.realm_index]["levels"]:
            return False, "尚未达到突破条件，需要当前境界满星"

        status_ok, msg = self.check_status()
        if not status_ok:
            return False, msg

        success_chance = REALMS[self.realm_index]["breakthrough_chance"]

        if "breakthrough" in self.temp_boosts and time.time() < self.temp_boosts["breakthrough"][1]:
            success_chance += self.temp_boosts["breakthrough"][0]
            del self.temp_boosts["breakthrough"]

        protected = any("护脉丹" in item for item in self.inventory)

        if random.random() < success_chance:
            self.realm_index += 1
            self.level = self.level - 9
            self.current_qi = 0
            self.health += (self.realm_index+1)**2 * 10/5
            if self.health>self.max_health:
                self.health = self.max_health
            self.required_qi = self._calculate_required_qi()

            for item in list(self.inventory):
                if "破障丹" in item or "破境丹" in item:
                    self.inventory.remove(item)

            return True, f"★ 惊天突破！晋升为 {self.realm}！★"
        else:
            if protected:
                protected_item = next((item for item in self.inventory if "护脉丹" in item), None)
                if protected_item:
                    self.inventory.remove(protected_item)
                return False, f"突破失败！但【{protected_item}】保护了你免受反噬"

            damage = random.randint(10, (self.realm_index+1)**2 * 10/2) * (self.realm_index + 1)
            self.health = max(1, self.health - damage)
            return False, f"突破失败！受到{damage}点反噬伤害"

    def explore(self, level="初级"):
        # 检查冷却和状态
        if not self.can_explore():
            remaining = int(self.cooldowns["explore"] - (time.time() - self.last_explore_time))
            return False, f"探索需要冷却，还需等待{remaining}秒"

        status_ok, msg = self.check_status()
        if not status_ok:
            return False, msg

        self.last_explore_time = time.time()

        # 获取探索等级信息
        level_info = EXPLORE_LEVELS[level]
        realm_index = self.realm_index

        # 计算境界差距（负数表示低于推荐境界）
        realm_diff = realm_index - level_info["min_realm"]

        # 动态调整系数
        danger_boost = max(0, -realm_diff) * 0.3  # 每低一个境界增加30%危险
        reward_penalty = max(0, -realm_diff) * 0.2  # 每低一个境界减少20%奖励
        protection = max(0, realm_diff) * 0.15  # 每高一个境界增加15%保护

        # 最终危险系数（基础危险 + 境界惩罚 - 境界保护）
        actual_danger = min(0.9, level_info["danger"] + danger_boost - protection)

        # 事件选择（考虑实际危险系数）
        event_data = random.choices(
            EXPLORE_EVENTS,
            weights=[e["weight"] * (1 + actual_danger if "妖兽" in e["name"] else 1)
                     for e in EXPLORE_EVENTS]
        )[0]

        # 执行事件效果
        results = []
        for effect in event_data["effects"]:
            res = effect(self, level)
            if res[1]:
                # 调整奖励（高境界加成/低境界惩罚）
                final_factor = 1.0 + max(0, realm_diff) * 0.1 - reward_penalty
                if "获得" in res[1] or "挖掘到" in res[1]:
                    res = (res[0], f"{res[1]}（境界修正：{final_factor:.1f}x）")
                results.append(res[1])

        # 额外危险判定（基于实际危险系数）
        if random.random() < actual_danger:
            base_dmg = random.randint(15, 40) * (1 + ["初级", "中级", "高级"].index(level))
            dmg = int(base_dmg * (1 + danger_boost))
            self.take_damage(dmg)
            results.append(f"遭遇致命危险！损失{dmg}点生命值！")

        # 添加境界差距提示
        if realm_diff < 0:
            results.append(f"⚠️境界警告：您比推荐境界低{-realm_diff}个层级，危险大幅增加！")
        elif realm_diff > 3:
            results.append(f"💤境界碾压：高级探索对您已无挑战性")

        return True, (
                f"【{event_data['name']}】{level}探索\n"
                f"{event_data['description']}\n\n"
                f"探索结果：\n" + "\n".join(results)
        )

    def to_dict(self) -> Dict[str, Any]:
        logger.info(f"Loading player {self.user_name}, realm_index={self.realm_index}")
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "realm_index": self.realm_index,
            "level": self.level,
            "current_qi": self.current_qi,
            "required_qi": self.required_qi,
            "health": self.health,
            "gold": self.gold,
            "inventory": self.inventory,
            "zb": self.zb,
            "training_progress": self.training_progress,
            "last_train_time": self.last_train_time,
            "last_explore_time": self.last_explore_time,
            "last_duel_time": self.last_duel_time,
            "is_dying": self.is_dying,
            "death_time": self.death_time,
            "temp_boosts": self.temp_boosts,
            "lan_tiao": self.lan_tiao
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        logger.info(f"Loading player {data['user_name']}, realm_index={data.get('realm_index')}")
        player = cls(data["user_id"], data["user_name"],data["realm_index"])
        player.realm_index = data["realm_index"]
        player.level = data["level"]
        player.current_qi = data["current_qi"]
        player.required_qi = data["required_qi"]
        player.health = data["health"]
        player.gold = data["gold"]
        player.inventory = data["inventory"]
        player.last_train_time = data["last_train_time"]
        player.zb = data["zb"]
        player.training_progress = data["training_progress"]
        player.last_explore_time = data["last_explore_time"]
        player.lan_tiao = data["lan_tiao"]
        player.last_duel_time = data["last_duel_time"]
        player.is_dying = data.get("is_dying", False)
        player.death_time = data.get("death_time", 0)
        player.temp_boosts = data.get("temp_boosts", {})
        return player

class GameWorld:
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.players: Dict[str, Player] = {}
        self.game_started = False
        self.market_items = []
        self.last_market_refresh = 0
        self.world_events = []
        self.last_event_update = 0
        self.duel_requests: Dict[str, str] = {}

    def generate_technique(self):
        """按概率生成功法"""
        technique = random.choices(
            ["黄阶功法", "玄阶功法", "地阶功法", "天阶功法"],
            weights=[65, 30, 4, 1]  # 黄阶65%，玄阶30%，地阶4%，天阶1%
        )[0]
        return {
            "name": technique,
            "effect": f"修炼效率+{int((CULTIVATION_BOOST[technique]['boost'] - 1) * 100)}%",
            "price": CULTIVATION_BOOST[technique]["price"],
            "value": CULTIVATION_BOOST[technique]["value"],
            "type": "technique"
        }

    def generate_market_items(self):
        self.market_items = []

        # 1. 生成2品以下丹药 (6个)
        low_grade_pills = PillSystem.get_pills_by_rank("一品") + PillSystem.get_pills_by_rank("二品")

        for _ in range(6):
            item = random.choice(low_grade_pills)
            self.market_items.append({
                "name": item["name"],
                "effect": item["description"],
                "price": item["price"],
                "value": item["value"],
                "type": item["type"]
            })

        # 2. 生成2-5品丹药 (3-4个)
        mid_grade_pills = (PillSystem.get_pills_by_rank("三品") +
                           PillSystem.get_pills_by_rank("四品") +
                           PillSystem.get_pills_by_rank("五品"))

        for _ in range(random.randint(3, 4)):
            item = random.choice(mid_grade_pills)
            self.market_items.append({
                "name": item["name"],
                "effect": item["description"],
                "price": item["price"],
                "value": item["value"],
                "type": item["type"]
            })

        # 3. 生成5品以上丹药 (概率生成，最多2个)
        high_grade_weights = {
            "六品": 50,
            "七品": 30,
            "八品": 15,
            "九品": 5
        }

        for _ in range(2):
            if random.random() < 0.6:  # 60%概率尝试生成
                grade = random.choices(
                    list(high_grade_weights.keys()),
                    weights=list(high_grade_weights.values())
                )[0]
                pills = PillSystem.get_pills_by_rank(grade)
                if pills:  # 确保该品阶有丹药
                    item = random.choice(pills)
                    self.market_items.append({
                        "name": item["name"],
                        "effect": item["description"],
                        "price": item["price"],
                        "value": item["value"],
                        "type": item["type"]
                    })

        # 4. 添加随机功法 (1-2个)
        for _ in range(random.randint(1, 2)):
            self.market_items.append(self.generate_technique())

        # 5. 随机打乱顺序并限制数量
        random.shuffle(self.market_items)

        # 6. 填充空缺位置（使用随机低品丹药）
        for i in range(0, 25 - len(self.market_items)):
            # 随机选择一种低品丹药类型来填充
            pill_types = ["healing", "recovery", "cultivation"]
            selected_type = random.choice(pill_types)
            low_pills = [p for p in low_grade_pills if p["type"] == selected_type]

            if low_pills:
                item = random.choice(low_pills)
                self.market_items.append({
                    "name": item["name"],
                    "effect": item["description"],
                    "price": item["price"],
                    "value": item["value"],
                    "type": item["type"]
                })
            else:
                # 如果没有找到指定类型的丹药，使用默认的2品回魂丹
                default_pill = PillSystem.get_pill_by_name("2品回魂丹")
                if default_pill:
                    self.market_items.append({
                        "name": default_pill["name"],
                        "effect": default_pill["description"],
                        "price": default_pill["price"],
                        "value": default_pill["value"],
                        "type": default_pill["type"]
                    })

        self.market_items = self.market_items[:20]  # 最多20个物品
        self.last_market_refresh = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "game_started": self.game_started,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "market_items": self.market_items,
            "last_market_refresh": self.last_market_refresh,
            "world_events": self.world_events,
            "last_event_update": self.last_event_update,
            "duel_requests": self.duel_requests
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameWorld":
        world = cls(data["group_id"])
        world.game_started = data["game_started"]
        world.players = {pid: Player.from_dict(pdata) for pid, pdata in data["players"].items()}
        world.market_items = data["market_items"]
        world.last_market_refresh = data["last_market_refresh"]
        world.world_events = data["world_events"]
        world.last_event_update = data["last_event_update"]
        world.duel_requests = data.get("duel_requests", {})
        return world

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

# ==================== 主插件类 ====================
@register("dpcq_final", "author", "斗破苍穹最终版", "1.0.0", "repo url")
class DouPoCangQiongFinal(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.worlds: Dict[str, GameWorld] = {}
        self.player_world_map: Dict[str, str] = {}
        self.persistence = DataPersistence()
        self._load_all_worlds()

    def _load_all_worlds(self):
        for group_id in self.persistence.list_saved_worlds():
            if data := self.persistence.load_world(group_id):
                try:
                    self.worlds[group_id] = GameWorld.from_dict(data)
                    for player_id in data.get("players", {}):
                        self.player_world_map[player_id] = group_id
                except Exception as e:
                    logger.error(f"加载世界数据失败: {group_id}, 错误: {e}")

    def _save_world(self, group_id: str):
        if group_id in self.worlds:
            try:
                self.persistence.save_world(group_id, self.worlds[group_id].to_dict())
            except Exception as e:
                logger.error(f"保存世界数据失败: {group_id}, 错误: {e}")

    def _get_world(self, group_id: str) -> GameWorld:
        if group_id not in self.worlds:
            self.worlds[group_id] = GameWorld(group_id)
            self._save_world(group_id)
        return self.worlds[group_id]

    async def terminate(self):
        for group_id in self.worlds:
            self._save_world(group_id)
        await super().terminate()

    async def _call_llm(self, event: AstrMessageEvent, prompt: str, system_prompt: str = "") -> str:
        func_tools_mgr = self.context.get_llm_tool_manager()
        llm_response = await self.context.get_using_provider().text_chat(
            prompt=prompt,
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )
        return llm_response.completion_text if llm_response.role == "assistant" else ""

    async def _generate_duel_description(self, player1: Player, player2: Player, winner: Player) -> str:
        prompt = f"""
        描述一场斗破苍穹风格的修炼者对战：
        对战双方：
        ▪ {player1.user_name}（{player1.realm} {player1.level}星）
        ▪ {player2.user_name}（{player2.realm} {player2.level}星）
        胜利者：{winner.user_name}

        要求：
        1. 若双方境界相差较小：详细描写双方使用的斗技和战术（各1-2种）、战斗转折点、胜利关键因素。
        2. 若境界差距悬殊（如高出两境或以上）：简要描述碾压过程，突出实力鸿沟，无需复杂战术与转折。
        3. 说明战败者的结局（轻伤/重伤/濒死等）。
        4. 全文约200字，语言热血激昂，体现玄幻战斗的壮观与气势。
        5. 注意你很熟悉斗破苍穹的境界划分

        注意：根据实力对比灵活调整描写详略，真实体现强者威压与战斗张力。
        """
        return await self._call_llm(
            None,
            prompt,
            system_prompt="你是斗破苍穹世界的战斗记录者，擅长用生动语言描述精彩对决"
        )

    async def _generate_world_event(self) -> str:
        prompt = """
        生成一个斗破苍穹风格的动态世界事件，包含：
        1. 事件名称（4-6字）
        2. 事件描述（50-70字）
        3. 对修炼者的影响（20-30字）
        输出格式：
        【事件名称】事件描述
        （影响说明）
        """
        return await self._call_llm(
            None,
            prompt,
            system_prompt="你是斗破苍穹世界的天道意志，掌控世界运行规律"
        )

    # ==================== 游戏命令 ====================
    @filter.command("dp_start")
    async def start_game(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        if world.game_started:
            yield event.plain_result("游戏已经开始了！")
            return

        world.game_started = True
        world.generate_market_items()
        world.world_events = [
            await self._generate_world_event(),
            await self._generate_world_event(),
            await self._generate_world_event()
        ]
        world.last_event_update = time.time()

        yield event.plain_result(
            "=== 斗破苍穹世界开启 ===\n"
            "修炼体系：斗之气→斗者→斗师→大斗师→斗灵→斗王→斗皇→斗宗→斗尊→斗圣→斗帝\n"
            "每个境界分为1-10星，积累足够斗气可升级\n"
            "探索分为初级/中级/高级，风险与奖励递增\n"
            "生命值为0会进入濒死状态，需要回魂丹复活\n"
            "输入 /dp_join 加入这个浩瀚的修炼世界！"
        )
        self._save_world(event.get_group_id())

    @filter.command("dp_join")
    async def join_game(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        if not world.game_started:
            yield event.plain_result("游戏尚未开始，请等待管理员开启游戏！")
            return

        if user_id in self.player_world_map:
            if self.player_world_map[user_id] == event.get_group_id():
                yield event.plain_result(f"{user_name} 已经在当前群聊的游戏中了！")
            else:
                yield event.plain_result(f"{user_name} 已经加入了其他群聊的游戏，每个玩家只能加入一个世界！")
            return

        world.players[user_id] = Player(user_id, user_name)
        self.player_world_map[user_id] = event.get_group_id()

        yield event.plain_result(
            f"=== {user_name} 踏入修炼之路 ===\n"
            f"初始境界：斗之气 1星\n"
            f"当前斗气：0/{REALMS[0]['base_qi']}\n"
            f"\n可用命令：\n"
            f"/状态 | /状态_s - 查看状态\n"
            f"/修炼 | 修炼_s(私聊)  - 修炼\n"
            f"/突破 - 突破境界\n"
            f"/探索 [初级/中级/高级] - 探索\n"
            f"/对战 - 挑战其他玩家\n"
            f"/商店 - 交易市场\n"
            f"/dp_world - 世界动态\n"
            f"/使用 - 使用物品\n"
            f"/复活 - 使用回魂丹复活"
        )
        self._save_world(event.get_group_id())

    @filter.command("状态")
    async def player_status(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]
        progress = int(player.current_qi / player.required_qi * 100)

        status_msg = (
            f"=== {player.user_name} 的状态 ===\n"
            f"【境界】{player.realm} {player.level}星\n"
            f"【斗气】{player.current_qi}/{player.required_qi} ({progress}%)\n"
            f"【称号】{player.title}\n"
            f"【金币】{player.gold}\n"
            f"【生命】{player.health}/{player.max_health} {'(濒死)' if player.is_dying else ''}\n"
            f"【战力】{player.power}\n"
            f"【装备】{player.zb}"
            f"【物品】{', '.join(player.inventory) if player.inventory else '无'}\n"
        )

        if player.temp_boosts:
            boosts = []
            for boost, (value, expire) in player.temp_boosts.items():
                if time.time() < expire:
                    remaining = int(expire - time.time())
                    boosts.append(f"{boost}+{value}%({remaining // 60}分)")
            if boosts:
                status_msg += f"【加成】{' '.join(boosts)}\n"

        status_msg += (
            f"\n修炼冷却：{'就绪' if player.can_train() else '冷却中'}\n"
            f"探索冷却：{'就绪' if player.can_explore() else '冷却中'}\n"
            f"对战冷却：{'就绪' if player.can_duel() else '冷却中'}"
        )

        yield event.plain_result(status_msg)

    @filter.command("状态_s", private=True)
    async def private_status(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()

        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return

        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]
        progress = int(player.current_qi / player.required_qi * 100)

        status_msg = (
            f"=== {player.user_name} 的状态 ===\n"
            f"【所属群聊】{group_id}\n"
            f"【境界】{player.realm} {player.level}星\n"
            f"【斗气】{player.current_qi}/{player.required_qi} ({progress}%)\n"
            f"【称号】{player.title}\n"
            f"【金币】{player.gold}\n"
            f"【生命】{player.health}/{player.max_health} {'(濒死)' if player.is_dying else ''}\n"
            f"【战力】{player.power}\n"
            f"【装备】{player.zb}"
            f"【物品】{', '.join(player.inventory) if player.inventory else '无'}\n"
        )

        if player.temp_boosts:
            boosts = []
            for boost, (value, expire) in player.temp_boosts.items():
                if time.time() < expire:
                    remaining = int(expire - time.time())
                    boosts.append(f"{boost}+{value}%({remaining // 60}分)")
            if boosts:
                status_msg += f"【加成】{' '.join(boosts)}\n"

        status_msg += (
            f"\n修炼冷却：{'就绪' if player.can_train() else '冷却中'}\n"
            f"探索冷却：{'就绪' if player.can_explore() else '冷却中'}\n"
            f"对战冷却：{'就绪' if player.can_duel() else '冷却中'}"
        )

        yield event.plain_result(status_msg)

    @filter.command("修炼")
    async def train(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]
        success, msg = player.train()

        if not success:
            yield event.plain_result(msg)
            return

        if "突破" in msg:
            yield event.plain_result(
                f"{msg}\n"
                f"当前境界：{player.realm} {player.level}星\n"
                f"斗气进度：{player.current_qi}/{player.required_qi}"
            )
        else:
            yield event.plain_result(msg)

    @filter.command("修炼_s", private=True)
    async def private_train(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()

        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return

        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]

        success, msg = player.train()

        if not success:
            yield event.plain_result(msg)
            return

        if "突破" in msg:
            yield event.plain_result(
                f"{msg}\n"
                f"当前境界：{player.realm} {player.level}星\n"
                f"斗气进度：{player.current_qi}/{player.required_qi}"
            )
        else:
            yield event.plain_result(msg)

    @filter.command("突破")
    async def breakthrough(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]
        success, msg = player.breakthrough()

        if success:
            yield event.plain_result(
                f"{msg}\n"
                f"新境界：{player.realm} 1星\n"
                f"所需斗气：0/{player.required_qi}"
            )
        else:
            yield event.plain_result(msg)

    @filter.command("探索")
    async def explore(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()
        level = "初级"

        if len(args) > 1:
            if args[1] in ["初级", "中级", "高级"]:
                level = args[1]
            else:
                yield event.plain_result("请指定有效的探索等级：初级/中级/高级")
                return

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]
        success, msg = player.explore(level)

        if not success:
            yield event.plain_result(msg)
            return

        yield event.plain_result(msg)

    @filter.command("探索_s", private=True)
    async def private_explore(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()
        level = "初级"

        if len(args) > 1:
            if args[1] in ["初级", "中级", "高级"]:
                level = args[1]
            else:
                yield event.plain_result("请指定有效的探索等级：初级/中级/高级")
                return

        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return

        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]

        success, msg = player.explore(level)

        if not success:
            yield event.plain_result(msg)
            return

        yield event.plain_result(msg)

    @filter.command("使用")
    async def use_item(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        if len(args) < 2:
            yield event.plain_result("请指定要使用的物品！")
            return

        player = world.players[user_id]
        item_name = " ".join(args[1:])
        success, msg = player.use_item(item_name)

        yield event.plain_result(msg)

    @filter.command("使用_s",private=True)
    async def private_use_item(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()

        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return
        args = event.message_str.strip().split()
        if len(args) < 2:
            yield event.plain_result("请指定要使用的物品！")
            return
        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]
        item_name = " ".join(args[1:])
        success, msg = player.use_item(item_name)
        yield event.plain_result(msg)

    @filter.command("复活")
    async def revive(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏！")
            return

        player = world.players[user_id]

        if not player.is_dying:
            yield event.plain_result("你并没有处于濒死状态！")
            return

        # 查找所有复活类丹药（使用新的丹药系统）
        revive_pills = []
        for item_name in player.inventory:
            pill = PillSystem.get_pill_by_name(item_name)
            if pill and pill["type"] == "revival":
                revive_pills.append(pill)

        if not revive_pills:
            yield event.plain_result("你没有可用的复活丹药！请等待其他玩家救助或使用金币购买")
            return

        # 使用品级最低的复活丹药（按品阶排序）
        used_pill = min(revive_pills, key=lambda x: int(x["rank"][0]))
        player.inventory.remove(used_pill["name"])

        # 根据丹药品级决定恢复效果（使用丹药的effect_value）
        pill_grade = int(used_pill["rank"][0])

        # 使用丹药的效果值来决定恢复效果
        if used_pill["effect"] == "revive":
            # 普通复活丹药
            if pill_grade >= 7:  # 七品及以上丹药完全复活
                player.revive(full=True)
                revive_msg = "完全复活！生命值和状态全部恢复"
            elif pill_grade >= 5:  # 五品六品丹药恢复70%
                player.health = min(player.max_health,
                                    player.health + int(player.max_health * used_pill["effect_value"]))
                revive_msg = f"恢复{int(used_pill['effect_value'] * 100)}%生命值"
            else:  # 低品丹药
                player.health = min(player.max_health,
                                    player.health + int(player.max_health * used_pill["effect_value"]))
                revive_msg = f"恢复{int(used_pill['effect_value'] * 100)}%生命值"

        elif used_pill["effect"] == "full_revive":
            # 完全复活丹药
            player.revive(full=True)
            revive_msg = "完全复活！生命值和状态全部恢复"

        elif used_pill["effect"] == "immortal":
            # 不朽复活丹药
            player.revive(full=True)
            # 应用无敌效果
            player.apply_temp_boost("immortal", used_pill["effect_value"], used_pill["effect_duration"])
            minutes = used_pill["effect_duration"] // 60
            revive_msg = f"完全复活并获得{minutes}分钟无敌状态"

        elif used_pill["effect"] == "auto_revive":
            # 自动复活丹药（应该是在死亡时自动触发，这里作为普通复活处理）
            player.revive(full=False if pill_grade < 5 else True)
            revive_msg = "复活成功"

        elif used_pill["effect"] == "reincarnate":
            # 转世丹药（应该是有特殊处理，这里作为普通复活）
            player.revive(full=True)
            revive_msg = "转世重生！完全恢复状态"

        player.is_dying = False
        player.death_time = 0
        yield event.plain_result(
            f"使用【{used_pill['name']}】成功复活！\n"
            f"{revive_msg}"
        )

    # 修改后的救助玩家逻辑
    @filter.command("救助")
    async def save_player(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏！")
            return

        player = world.players[user_id]

        # 查找所有复活类丹药（使用新的丹药系统）
        revive_pills = []
        for item_name in player.inventory:
            pill = PillSystem.get_pill_by_name(item_name)
            if pill and pill["type"] == "revival":
                revive_pills.append(pill)

        if not revive_pills:
            yield event.plain_result("你没有可用的复活丹药，无法救助他人！")
            return

        target_name = args[1].strip("@") if len(args) > 1 else None
        if not target_name:
            dying_players = [p for p in world.players.values() if p.is_dying and p.user_id != user_id]
            if not dying_players:
                yield event.plain_result("当前没有濒死玩家需要救助！")
                return

            yield event.plain_result(
                "需要救助的玩家：\n" +
                "\n".join([f"{i + 1}. {p.user_name}（死亡时间：{int(time.time() - p.death_time)}秒前）"
                           for i, p in enumerate(dying_players[:5])]) +
                "\n\n使用 /dp_save @玩家 进行救助"
            )
            return

        target = next((p for p in world.players.values() if p.user_name == target_name), None)
        if not target:
            yield event.plain_result("找不到该玩家！")
            return
        if not target.is_dying:
            yield event.plain_result(f"{target.user_name} 并没有濒死！")
            return

        # 使用品级最低的复活丹药
        used_pill = min(revive_pills, key=lambda x: int(x["rank"][0]))
        player.inventory.remove(used_pill["name"])

        # === 新增金币转移逻辑 ===
        gold_transfer = int(target.gold * 0.3)  # 转移30%金币
        player.gold += gold_transfer
        target.gold = max(0, target.gold - gold_transfer)

        # 根据丹药品级和效果类型决定恢复效果
        pill_grade = int(used_pill["rank"][0])

        # 使用丹药的效果值来决定恢复效果
        if used_pill["effect"] == "revive":
            # 普通复活丹药
            if pill_grade >= 7:  # 七品及以上丹药完全复活
                target.revive(full=True)
                revive_msg = "完全复活！生命值和状态全部恢复"
            elif pill_grade >= 5:  # 五品六品丹药
                target.health = min(target.max_health,
                                    target.health + int(target.max_health * used_pill["effect_value"]))
                revive_msg = f"恢复{int(used_pill['effect_value'] * 100)}%生命值"
            else:  # 低品丹药
                target.health = min(target.max_health,
                                    target.health + int(target.max_health * used_pill["effect_value"]))
                revive_msg = f"恢复{int(used_pill['effect_value'] * 100)}%生命值"

        elif used_pill["effect"] == "full_revive":
            # 完全复活丹药
            target.revive(full=True)
            revive_msg = "完全复活！生命值和状态全部恢复"

        elif used_pill["effect"] == "immortal":
            # 不朽复活丹药
            target.revive(full=True)
            # 应用无敌效果
            target.apply_temp_boost("immortal", used_pill["effect_value"], used_pill["effect_duration"])
            minutes = used_pill["effect_duration"] // 60
            revive_msg = f"完全复活并获得{minutes}分钟无敌状态"

        elif used_pill["effect"] == "auto_revive":
            # 自动复活丹药（这里作为普通复活处理）
            target.revive(full=False if pill_grade < 5 else True)
            revive_msg = "复活成功"

        elif used_pill["effect"] == "reincarnate":
            # 转世丹药
            target.revive(full=True)
            revive_msg = "转世重生！完全恢复状态"

        target.is_dying = False
        target.death_time = 0

        yield event.plain_result(
            f"你使用【{used_pill['name']}】成功救助了 {target.user_name}！\n"
            f"{target.user_name} {revive_msg}\n"
            f"获得对方30%金币作为报酬：{gold_transfer}枚（当前金币：{player.gold}）"
        )
        self._save_world(event.get_group_id())

    @filter.command("商店")
    async def market(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        if time.time() - world.last_market_refresh > 1800:
            world.generate_market_items()

        player = world.players[user_id]

        if len(args) == 1:
            if not world.market_items:
                yield event.plain_result("市场暂时没有商品！")
                return

            yield event.plain_result(
                "=== 交易市场 ===\n" +
                "\n".join([
                    f"{i + 1}. 【{item['name']}】{item['effect']} "
                    f"（价格：{item['price']}金币)"
                    for i, item in enumerate(world.market_items)
                ]) +
                "\n\n使用 /商店 buy 序号 购买物品\n"
                "/出售 -出售物品"
                "/出售_s -私聊出售物品"
            )
            return

        if args[1] == "buy" and len(args) > 2:
            try:
                index = int(args[2]) - 1
                if 0 <= index < len(world.market_items):
                    item = world.market_items[index]
                    if player.gold >= item["price"]:
                        if player.add_item(item["name"]):
                            player.gold -= item["price"]
                            world.market_items.pop(index)
                            yield event.plain_result(
                                f"成功购买 【{item['name']}】！\n"
                                f"花费：{item['price']}金币\n"
                                f"效果：{item['effect']}"
                            )
                        else:
                            yield event.plain_result("背包已满，无法购买更多物品！")
                    else:
                        yield event.plain_result("金币不足！")
                else:
                    yield event.plain_result("无效的商品序号！")
            except ValueError:
                yield event.plain_result("请输入正确的商品序号！")
            return

        if args[1] == "sell" and len(args) > 2:
            item_name = " ".join(args[1:])
            if item_name in player.inventory:
                if item_name in CULTIVATION_BOOST.keys():
                    price = CULTIVATION_BOOST[item_name]['price'] * random.uniform(0.8, 1.1)
                else:
                    price = random.randint(150, 300)

                player.gold += price
                player.inventory.remove(item_name)

                yield event.plain_result(
                    f"成功出售 【{item_name}】！\n"
                    f"获得：{price}金币"
                )
            else:
                yield event.plain_result("你没有这个物品！")
            return

        yield event.plain_result("无效的市场命令！")

    @filter.command("出售")
    async def sell(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return
        args = event.message_str.strip().split()
        player = world.players[user_id]
        item_name = " ".join(args[1:])
        if item_name in player.inventory:
            if item_name in CULTIVATION_BOOST.keys():
                price = CULTIVATION_BOOST[item_name]['price'] * random.uniform(0.8, 1.1)
            else:
                price = random.randint(150, 300)

            player.gold += price
            player.inventory.remove(item_name)

            yield event.plain_result(
                f"成功出售 【{item_name}】！\n"
                f"获得：{price}金币"
            )
        else:
            yield event.plain_result("你没有这个物品！")
        return

    @filter.command("出售_s")
    async def private_sell(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return
        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]
        args = event.message_str.strip().split()
        item_name = " ".join(args[1:])
        if item_name in player.inventory:
            if item_name in CULTIVATION_BOOST.keys():
                price = CULTIVATION_BOOST[item_name]['price'] * random.uniform(0.8, 1.1)
            else:
                price = random.randint(150, 300)
            player.gold += price
            player.inventory.remove(item_name)

            yield event.plain_result(
                f"成功出售 【{item_name}】！\n"
                f"获得：{price}金币"
            )
        else:
            yield event.plain_result("你没有这个物品！")
        return


    @filter.command("dp_world")
    async def world_news(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())

        if not world.game_started:
            yield event.plain_result("游戏尚未开始！")
            return

        if time.time() - world.last_event_update > 3600:
            world.world_events = [
                await self._generate_world_event(),
                await self._generate_world_event(),
                await self._generate_world_event()
            ]
            world.last_event_update = time.time()

        yield event.plain_result(
            "=== 斗破苍穹世界动态 ===\n" +
            "\n".join([f"· {event}" for event in world.world_events[:3]]) +
            "\n\n当前活跃修炼者：" + str(len(world.players)) + "人"
        )

    @filter.command("对战")
    async def duel(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]
        status_ok, msg = player.check_status()
        if not status_ok:
            yield event.plain_result(msg)
            return

        if not player.can_duel():
            remaining = int(player.cooldowns["duel"] - (time.time() - player.last_duel_time))
            yield event.plain_result(f"对战需要冷却，还需等待{remaining}秒")
            return

        if len(args) == 1:
            other_players = [
                p for p in world.players.values()
                if p.user_id != user_id and (time.time() - p.last_duel_time) > p.cooldowns["duel"]
            ]

            if not other_players:
                yield event.plain_result("当前没有可以挑战的玩家！")
                return

            yield event.plain_result(
                "可挑战的玩家：\n" +
                "\n".join([
                    f"{i + 1}. {p.user_name}（{p.realm} {p.level}星）"
                    for i, p in enumerate(other_players[:10])
                ]) +
                "\n\n使用 /对战 @玩家 发起挑战"
            )
            return

        target_name = args[1].strip("@")
        target = next((p for p in world.players.values() if p.user_name == target_name), None)

        if not target:
            yield event.plain_result("找不到该玩家！")
            return

        if target.user_id == user_id:
            yield event.plain_result("你不能挑战自己！")
            return

        if (time.time() - target.last_duel_time) < target.cooldowns["duel"]:
            yield event.plain_result(f"{target.user_name} 正在休息，暂时不能接受挑战！")
            return

        if target.is_dying:
            yield event.plain_result(f"{target.user_name} 处于濒死状态，无法接受挑战！")
            return

        world.duel_requests[user_id] = target.user_id
        yield event.plain_result(
            f"你向 {target.user_name} 发起了对战请求！\n"
            f"等待对方接受...\n"
            f"（对方有1分钟时间使用 /接受挑战 接受挑战）"
        )

    @filter.command("接受挑战")
    async def accept_duel(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        challenger_id = next((k for k, v in world.duel_requests.items() if v == user_id), None)

        if not challenger_id:
            yield event.plain_result("当前没有人挑战你！")
            return

        challenger = world.players[challenger_id]
        defender = world.players[user_id]
        status_ok, msg = defender.check_status()
        if not status_ok:
            yield event.plain_result(msg)
            return

        # 计算境界差和星级差
        # 计算战力比
        power_ratio = challenger.power / (defender.power + 1e-6)
        # 计算境界加成
        realm_diff = challenger.realm_index - defender.realm_index
        realm_bonus = 1 / (1 + math.exp(-realm_diff * 0.3))
        # 综合胜率
        base_chance = 0.7 * power_ratio + 0.3 * realm_bonus
        # 随机波动
        uncertainty = 0.15 * (1 - abs(realm_diff) * 0.1)
        final_chance = max(0.05, min(0.95, base_chance + random.uniform(-uncertainty, uncertainty)))
        # 胜负判定
        if random.random() < final_chance:
            winner, loser = challenger, defender
        else:
            winner, loser = defender, challenger
        # 战斗结果处理
        # 损失蓝条，看境界差异，境界差距越高，境界高的人损失蓝条越少
        # ===== 3. 蓝条消耗计算 =====
        def calculate_qi_cost(attacker, defender):
            base_cost = 10  # 基础消耗15点蓝条
            realm_diff = attacker.realm_index - defender.realm_index
            # 境界差每多1级，减少20%消耗 (最低30%)
            cost_multiplier = max(0.3, 1 - 0.2 * max(0, realm_diff))
            return int(base_cost * cost_multiplier)

        # 胜者消耗蓝条 (高境界消耗更少)
        qi_cost = calculate_qi_cost(winner, loser)
        winner.lan_tiao = max(0, winner.lan_tiao - qi_cost)
        # 败者额外消耗 (固定10点)
        loser.lan_tiao = max(0, loser.lan_tiao - 10)
        exp_gain = int(loser.level * (2 if winner == challenger else 1))
        gold_gain = int(loser.level * (5 if winner == challenger else 3))

        # 高境界打赢低境界时收益减少
        if winner.realm_index > loser.realm_index:
            exp_gain = int(exp_gain * 0.5)
            gold_gain = int(gold_gain * 0.6)

        winner.current_qi += exp_gain
        winner.gold += gold_gain

        # 伤害计算（低境界打高境界时伤害降低）
        damage = int(loser.health * (0.3 if winner == challenger else 0.2))
        if winner.realm_index - loser.realm_index >= 2:
            damage = loser.max_health
        if winner.realm_index < loser.realm_index:
            damage = int(damage * 0.3)  # 伤害减少70%

        loser_died = loser.take_damage(damage)
        loser.gold = max(0, loser.gold - int(gold_gain * 0.5))

        winner.last_duel_time = time.time()
        loser.last_duel_time = time.time()

        duel_desc = await self._generate_duel_description(challenger, defender, winner)

        if challenger_id in world.duel_requests:
            del world.duel_requests[challenger_id]

        result_msg = (
            f"=== 惊天对决 ===\n"
            f"{duel_desc}\n"
            f"\n★ 胜利者：{winner.user_name} ★\n"
            f"获得：{exp_gain}斗气点，{gold_gain}金币\n"
        )

        if loser_died:
            result_msg += f"\n{loser.user_name} 在战斗中重伤濒死！需要回魂丹复活\n"
        else:
            result_msg += f"\n{loser.user_name} 损失{gold_gain}金币和{damage}点生命值\n"

        result_msg += "双方进入休息状态，1分钟内不能对战"

        yield event.plain_result(result_msg)

    @filter.command("dp_save")
    async def save_world(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        world = self._get_world(group_id)

        try:
            self._save_world(group_id)
            yield event.plain_result("★ 游戏数据保存成功！ ★")
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            yield event.plain_result("⚠ 数据保存失败，请检查日志")

    @filter.command("dp_save_s")
    async def save_world_s(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)

        try:
            self._save_world(group_id)
            yield event.plain_result("★ 游戏数据保存成功！ ★")
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            yield event.plain_result("⚠ 数据保存失败，请检查日志")

    @filter.command("dp_load")
    async def load_world(self, event: AstrMessageEvent):
        group_id = event.get_group_id()
        args = event.message_str.strip().split()

        if len(args) == 1:
            saved_worlds = self.persistence.list_saved_worlds()
            if not saved_worlds:
                yield event.plain_result("没有找到已保存的游戏数据！")
                return

            world_info = []
            for world_id in saved_worlds[:10]:
                if info := self.persistence.get_world_info(world_id):
                    world_info.append(
                        f"{world_id} - 玩家数: {info['players']} 最后保存: {info['last_update']}"
                    )

            yield event.plain_result(
                "可加载的游戏数据：\n" +
                "\n".join(world_info) +
                "\n\n使用 /dp_load [世界ID] 加载指定数据"
            )
            return

        target_world = args[1]
        if target_world not in self.persistence.list_saved_worlds():
            yield event.plain_result("找不到指定的游戏数据！")
            return

        try:
            data = self.persistence.load_world(target_world)
            if not data:
                yield event.plain_result("数据加载失败，文件可能已损坏")
                return

            self.worlds[group_id] = GameWorld.from_dict(data)
            for player_id in data.get("players", {}):
                self.player_world_map[player_id] = group_id

            yield event.plain_result(
                f"★ 成功加载游戏数据！ ★\n"
                f"世界ID: {target_world}\n"
                f"玩家数: {len(data.get('players', {}))}\n"
                f"最后保存: {time.ctime(os.path.getmtime(self.persistence.storage_dir / f'{target_world}.json'))}"
            )
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            yield event.plain_result("⚠ 数据加载失败，请检查日志")

    @filter.command("dp_load_s")
    async def load_world_s(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return
        group_id = self.player_world_map[user_id]
        args = event.message_str.strip().split()

        if len(args) == 1:
            saved_worlds = self.persistence.list_saved_worlds()
            if not saved_worlds:
                yield event.plain_result("没有找到已保存的游戏数据！")
                return

            world_info = []
            for world_id in saved_worlds[:10]:
                if info := self.persistence.get_world_info(world_id):
                    world_info.append(
                        f"{world_id} - 玩家数: {info['players']} 最后保存: {info['last_update']}"
                    )

            yield event.plain_result(
                "可加载的游戏数据：\n" +
                "\n".join(world_info) +
                "\n\n使用 /dp_load [世界ID] 加载指定数据"
            )
            return

        target_world = args[1]
        if target_world not in self.persistence.list_saved_worlds():
            yield event.plain_result("找不到指定的游戏数据！")
            return

        try:
            data = self.persistence.load_world(target_world)
            if not data:
                yield event.plain_result("数据加载失败，文件可能已损坏")
                return

            self.worlds[group_id] = GameWorld.from_dict(data)
            for player_id in data.get("players", {}):
                self.player_world_map[player_id] = group_id

            yield event.plain_result(
                f"★ 成功加载游戏数据！ ★\n"
                f"世界ID: {target_world}\n"
                f"玩家数: {len(data.get('players', {}))}\n"
                f"最后保存: {time.ctime(os.path.getmtime(self.persistence.storage_dir / f'{target_world}.json'))}"
            )
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            yield event.plain_result("⚠ 数据加载失败，请检查日志")

    @filter.command("dp_help", private=True)
    async def show_help(self, event: AstrMessageEvent):
        help_text = """
        === 斗破苍穹游戏帮助 ===
        【基础命令】
        /dp_join - 加入游戏
        /状态 - 查看状态
        /状态_s - 私聊查看状态

        【修炼系统】
        /修炼 - 修炼增加斗气
        /修炼_s - 私聊修炼
        /突破 - 突破境界

        【探索系统】
        /探索 [初级/中级/高级] - 探索世界
        /探索_s [初级/中级/高级] - 私聊探索

        【战斗系统】
        /对战 @玩家 - 挑战其他玩家
        /接受挑战 - 接受对战请求

        【物品系统】
        /使用 物品名 - 使用物品
        /商店 - 查看交易市场
        /商店 buy 序号 - 购买物品
        /商店 sell 物品名 - 出售物品
        /出售 -出售物品
        /出售_s -私聊出售物品

        【世界系统】
        /dp_world - 查看世界动态
        /救助 - 救助濒死玩家
        /复活 - 使用回魂丹复活

        【管理命令】
        /dp_start - 管理员开启游戏
        /dp_save - 手动保存游戏数据
        /dp_load - 加载游戏数据

        【帮助命令】
        /dp_help - 显示本帮助信息

        === 玩法说明 ===
        1. 通过修炼积累斗气提升等级
        2. 探索世界获取资源和丹药
        3. 使用丹药增强修炼效果
        4. 与其他玩家对战提升实力
        5. 濒死状态需要回魂丹复活
        """
        yield event.plain_result(help_text)

    @filter.command("dp_clear", admin=True)
    async def clear_world(self, event: AstrMessageEvent):
        """管理员命令：清除当前群聊的游戏世界数据"""
        group_id = event.get_group_id()
        if group_id not in self.worlds:
            yield event.plain_result("当前群聊没有游戏数据！")
            return
        # 先移除所有玩家的映射关系
        for player_id in list(self.player_world_map.keys()):
            if self.player_world_map[player_id] == group_id:
                del self.player_world_map[player_id]
        # 删除世界数据
        del self.worlds[group_id]
        # 删除持久化文件
        self.persistence.delete_world(group_id)
        yield event.plain_result("★ 已成功清除当前群聊的游戏数据！ ★")

    @filter.command("dp_clear_all", admin=True)
    async def clear_all_worlds(self, event: AstrMessageEvent):
        """管理员命令：清除所有游戏世界数据"""
        confirm = event.message_str.strip().split()
        if len(confirm) < 2 or confirm[1] != "confirm":
            yield event.plain_result("⚠ 危险操作！这将删除所有游戏数据！\n如需继续，请使用 /dp_clear_all confirm")
            return
        # 清除内存中的数据
        self.worlds.clear()
        self.player_world_map.clear()
        # 删除所有持久化文件
        for world_id in self.persistence.list_saved_worlds():
            self.persistence.delete_world(world_id)
        yield event.plain_result("★ 已成功清除所有游戏世界数据！ ★")

    @filter.command("dp_cleanup", admin=True)
    async def cleanup_files(self, event: AstrMessageEvent):
        """管理员命令：清理无效数据文件"""
        saved_files = set(self.persistence.list_saved_worlds())
        active_worlds = set(self.worlds.keys())
        # 找出没有对应活跃世界的文件
        orphaned_files = saved_files - active_worlds
        count = 0
        for world_id in orphaned_files:
            self.persistence.delete_world(world_id)
            count += 1
        yield event.plain_result(
            f"★ 清理完成 ★\n"
            f"已删除 {count} 个无效数据文件\n"
            f"剩余有效文件: {len(saved_files) - count} 个"
        )
