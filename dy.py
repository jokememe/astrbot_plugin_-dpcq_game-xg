# 标准化的丹药数据结构
from typing import Optional, Dict, List, Tuple

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
