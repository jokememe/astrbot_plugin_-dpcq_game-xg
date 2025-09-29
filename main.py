import asyncio
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
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

DUNGEON_LEVELS = {
    # 普通副本
    "初级": {
        "min_realm": 0,  # 斗之气
        "max_realm": 13,  # 大斗师
        "boss_power": 1000,
        "reward_factor": 1.0,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.2, "quantity": (1,2)},
            {"name": "1品聚气丹", "probability": 0.6, "quantity": (1, 3)},
            {"name": "2品聚气散", "probability": 0.4, "quantity": (1, 2)},
            {"name": "3品破障丹", "probability": 0.3, "quantity": 1},
            {"name": "1品凝神丹", "probability": 0.5, "quantity": (1, 2)},
            {"name": "3品玄灵丹", "probability": 0.2, "quantity": 1},
            {"name": "1品回复丹", "probability": 0.7, "quantity": (1, 3)},
            {"name": "1品疗伤丹", "probability": 0.7, "quantity": (1, 3)}
        ],
        "gold_range": (100, 300),
        "description": "新手修炼者的试炼场，适合初入修炼之路的修士"
    },
    "中级": {
        "min_realm": 3,  # 大斗师
        "max_realm": 13,  # 斗皇
        "boss_power": 200000,
        "reward_factor": 1.5,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.4, "quantity": (1,2)},
            {"name": "3品破障丹", "probability": 0.5, "quantity": (1, 2)},
            {"name": "3品玄灵丹", "probability": 0.4, "quantity": (1, 2)},
            {"name": "3品龙力丹", "probability": 0.3, "quantity": 1},
            {"name": "玄阶功法", "probability": 0.2, "quantity": 1}
        ],
        "gold_range": (300, 800),
        "description": "中阶修士的晋升之地，危险与机遇并存"
    },
    "高级": {
        "min_realm": 6,  # 斗皇
        "max_realm": 13,  # 斗圣
        "boss_power": 5000000,
        "reward_factor": 2.0,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.6, "quantity": (1,2)},
            {"name": "6品造化丹", "probability": 0.4, "quantity": 1},
            {"name": "6品玄灵丹", "probability": 0.4, "quantity": 1},
            {"name": "6品风行丹", "probability": 0.3, "quantity": 1},
            {"name": "地阶功法", "probability": 0.3, "quantity": 1},
            # 新增严格匹配的8/9品丹药
            {"name": "8品混沌丹", "probability": 0.1, "quantity": 1},
            {"name": "9品洗髓丹", "probability": 0.1, "quantity": 1},
            {"name": "天阶功法", "probability": 0.1, "quantity": 1}
        ],
        "gold_range": (800, 2000),
        "description": "强者云集的危险区域，只有真正的强者才能生存"
    },
    "顶级": {
        "min_realm": 9,  # 斗圣
        "max_realm": 13,  # 主宰
        "boss_power": 50000000,
        "reward_factor": 3.0,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.8, "quantity": (1,2)},
            {"name": "9品至尊丹", "probability": 0.4, "quantity": 1},
            {"name": "9品涅槃丹", "probability": 0.3, "quantity": 1},
            {"name": "9品洗髓丹", "probability": 0.5, "quantity": 1},
            # 新增严格匹配的8品丹药
            {"name": "8品不朽丹", "probability": 0.3, "quantity": 1},
            {"name": "9品永生丹", "probability": 0.3, "quantity": 1},
            {"name": "9品玄灵丹", "probability": 0.5, "quantity": 1}
        ],
        "gold_range": (2000, 5000),
        "description": "巅峰强者的终极试炼，距离主宰仅一步之遥"
    },

    # 混沌级副本
    "混沌初境": {
        "min_realm": 12,  # 主宰
        "max_realm": 13,  # 混沌主宰
        "boss_power": 150000000,
        "reward_factor": 4.0,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.9, "quantity": (2,4)},
            {"name": "混沌结晶", "probability": 0.5, "quantity": (1, 2)},
            {"name": "7品阴阳丹", "probability": 0.8, "quantity": 1},
            {"name": "8品混沌丹", "probability": 0.8, "quantity": 1},
            {"name": "天阶功法", "probability": 0.6, "quantity": 1},
            {"name": "神阶功法", "probability": 0.2, "quantity": 1},
            {"name": "圣阶功法", "probability": 0.1, "quantity": 1},
            {"name": "仙阶功法", "probability": 0.02, "quantity": 1},
            {"name": "9品轮回丹", "probability": 0.6, "quantity": 1},
            {"name": "9品玄灵丹", "probability": 0.5, "quantity": 1}
        ],
        "gold_range": (50000, 80000),
        "description": "混沌初开之地，空间裂缝中诞生的初级混沌生物"
    },
    "混沌秘境": {
        "min_realm": 12,
        "max_realm": 13,
        "boss_power": 500000000,
        "reward_factor": 5.0,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.95, "quantity": (3,6)},
            {"name": "混沌结晶", "probability": 0.8, "quantity": (2, 3)},
            {"name": "混沌核心", "probability": 0.1, "quantity": 1},
            {"name": "8品不朽丹", "probability": 0.5, "quantity": 1},
            {"name": "9品轮回丹", "probability": 0.5, "quantity": 1},
            {"name": "天阶功法", "probability": 0.9, "quantity": 1},
            {"name": "神阶功法", "probability": 0.4, "quantity": 1},
            {"name": "圣阶功法", "probability": 0.2, "quantity": 1},
            {"name": "仙阶功法", "probability": 0.1, "quantity": 1},
            {"name": "仙阶功法", "probability": 0.05, "quantity": 1},
            {"name": "9品永生丹", "probability": 0.2, "quantity": 1}
        ],
        "gold_range": (80000, 120000),
        "description": "混沌能量汇聚的中级区域，时空扭曲严重"
    },
    "混沌核心": {
        "min_realm": 12,
        "max_realm": 13,
        "boss_power": 10000000000,
        "reward_factor": 6.0,
        "drop_items": [
            {"name": "魔兽内丹", "probability": 0.95, "quantity": (5,10)},
            {"name": "混沌结晶", "probability": 0.99, "quantity": (3, 5)},
            {"name": "混沌核心", "probability": 0.4, "quantity": (1, 2)},
            {"name": "9品永生丹", "probability": 0.6, "quantity": 1},
            {"name": "天阶功法", "probability": 0.9, "quantity": 1},
            {"name": "神阶功法", "probability": 0.6, "quantity": 1},
            {"name": "圣阶功法", "probability": 0.4, "quantity": 1},
            {"name": "仙阶功法", "probability": 0.2, "quantity": 1},
            {"name": "仙阶功法", "probability": 0.1, "quantity": 1},
            {"name": "无上功法", "probability": 0.05, "quantity": 1},
            {"name": "9品洗髓丹", "probability": 0.5, "quantity": 1},
            {"name": "8品混沌丹", "probability": 0.7, "quantity": 1}
        ],
        "gold_range": (120000, 200000),
        "description": "混沌本源所在，只有最强者才能涉足的终极区域"
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
                    weights=[
                        45 - ["初级", "中级", "高级"].index(level)*10,  # 黄阶概率随等级降低
                        35 - ["初级", "中级", "高级"].index(level)*5,   # 玄阶概率随等级降低
                        1 + ["初级", "中级", "高级"].index(level)*8,    # 地阶概率随等级提高
                        0.1 + ["初级", "中级", "高级"].index(level)*2   # 天阶概率随等级提高
                    ]
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
                p.take_damage(dmg := min(120, random.randint(30, 80)*(p.realm_index**2))),
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
                        60 - ["初级", "中级", "高级"].index(level)*20,  # 黄阶概率随等级降低
                        30 - ["初级", "中级", "高级"].index(level)*5,   # 玄阶概率随等级降低
                        0 + ["初级", "中级", "高级"].index(level)*8,    # 地阶概率随等级提高
                        0 + ["初级", "中级", "高级"].index(level)*2     # 天阶概率随等级提高
                    ]
                )[0]),
                f"顿悟石碑奥义，领悟【{tech}】"
            ) if random.random() < (0.6 + ["初级", "中级", "高级"].index(level)*0.2) else (None, ""),
            lambda p, level: (
                p.take_damage(min(120, int(p.health * (0.5 - ["初级", "中级", "高级"].index(level)*0.1)))),
                "参悟时走火入魔，气血逆冲！"
            ) if random.random() < (0.3 - ["初级", "中级", "高级"].index(level)*0.1) else (None, "")
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
                p.take_damage(dmg := min(120, int(random.randint(5, 10)*(["初级", "中级", "高级"].index(level)**3)*p.realm_index/2))),
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
            ) if random.random() < 0.8 else (
                p.take_damage(
                    dmg := min(120, int(random.randint(5, 10) * (["初级", "中级", "高级"].index(level) ** 3) * p.realm_index / 2))),
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
            lambda p, level: (p.gain_qi(qi := int(p.required_qi * (0.2 + 0.1 * ["初级", "中级", "高级"].index(level)**2))),
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
            lambda p, level: (p.take_damage(dmg := min(120, random.randint(5, 20) * (1 + ["初级", "中级", "高级"].index(level)**2))),
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
    "battle_strength": lambda player, pill: player.apply_temp_boost("battle_strength", pill["effect_value"],
                                                                    pill["effect_duration"]),
    "battle_defense": lambda player, pill: player.apply_temp_boost("battle_defense", pill["effect_value"],
                                                                   pill["effect_duration"]),
    "battle_all": lambda player, pill: player.apply_temp_boost("battle_all", pill["effect_value"], pill["effect_duration"]),
    "battle_desperate": lambda player, pill: player.apply_temp_boost("battle_desperate", pill["effect_value"],
                                                                     pill["effect_duration"]),
    "battle_invincible": lambda player, pill: player.apply_temp_boost("battle_invincible", pill["effect_value"],
                                                                      pill["effect_duration"]),

    # 恢复类
    "restore_qi": lambda player, pill: (
        player.heal(int(player.max_health * pill["effect_value"])),
        player.gain_qi(int(player.required_qi + 10))
    ),
    "heal": lambda player, pill: player.heal(int(player.max_health * pill["effect_value"])),

    # 复活类
    "revive": lambda player, pill: player.revive(full=False,args=pill["effect_value"]),
    "auto_revive": lambda player, pill: player.apply_temp_boost("auto_revive", pill["effect_value"],
                                                                pill["effect_duration"]),
    "reincarnate": lambda player, pill: player.apply_temp_boost("reincarnate", pill["effect_value"],
                                                                pill["effect_duration"]),
    "full_revive": lambda player, pill: player.revive(full=True),
    "immortal": lambda player, pill: player.apply_temp_boost("immortal", pill["effect_value"],
                                                                pill["effect_duration"]),
    # 升级
    "level_up": lambda player, pill: (
        setattr(player, 'level', player.level + pill["effect_value"]),
        setattr(player, 'current_qi', 0),
        setattr(player, 'required_qi', player._calculate_required_qi())
    ),
    "realm_up": lambda player, pill: player.realm_up(pill),

    # 探索辅助类
    "explore_cd": lambda player, pill: player.apply_temp_boost("explore_cd", pill["effect_value"],
                                                               pill["effect_duration"]),

    # 永久增益类
    "perm_health": lambda player, pill: player.apply_temp_boost("perm_health", pill["effect_value"], 2147483647),
}

REALMS = [
    {"name": "斗之气", "levels": 10, "breakthrough_chance": 0.9, "base_qi": 50, "train_gain": (5, 10)},
    {"name": "斗者", "levels": 10, "breakthrough_chance": 0.7, "base_qi": 200, "train_gain": (8, 15)},
    {"name": "斗师", "levels": 10, "breakthrough_chance": 0.6, "base_qi": 300, "train_gain": (12, 20)},
    {"name": "大斗师", "levels": 10, "breakthrough_chance": 0.5, "base_qi": 500, "train_gain": (15, 25)},
    {"name": "斗灵", "levels": 10, "breakthrough_chance": 0.4, "base_qi": 800, "train_gain": (20, 30)},
    {"name": "斗王", "levels": 10, "breakthrough_chance": 0.3, "base_qi": 1000, "train_gain": (25, 35)},
    {"name": "斗皇", "levels": 10, "breakthrough_chance": 0.25, "base_qi": 1200, "train_gain": (30, 40)},
    {"name": "斗宗", "levels": 10, "breakthrough_chance": 0.2, "base_qi": 3000, "train_gain": (50, 80)},
    {"name": "斗尊", "levels": 10, "breakthrough_chance": 0.15, "base_qi": 7000, "train_gain": (100, 150)},
    {"name": "斗圣", "levels": 10, "breakthrough_chance": 0.1, "base_qi": 30000, "train_gain": (200, 300)},
    {"name": "斗帝", "levels": 10, "breakthrough_chance": 0.05, "base_qi": 100000, "train_gain": (500, 800)},
    {"name": "天至尊", "levels": 3, "breakthrough_chance": 0.01, "base_qi": 1000000, "train_gain": (2000, 5000)},
    {"name": "主宰", "levels": 100, "breakthrough_chance": 0.05, "base_qi": 100000000, "train_gain": (10000, 20000)},
    {"name": "混沌主宰", "levels": 2147483647, "breakthrough_chance": 0.01, "base_qi": 2147483647, "train_gain": (50000, 100000)}
]

# 功法加成系数与价值系统
CULTIVATION_BOOST = {
    "黄阶功法":   {"boost": 0.1,  "value": 500,       "price": 750},
    "玄阶功法":   {"boost": 0.3,  "value": 1500,     "price": 2250},
    "地阶功法":   {"boost": 0.8,  "value": 5000,     "price": 7500},
    "天阶功法":   {"boost": 1.8,  "value": 15000,    "price": 225500},
    "神阶功法":   {"boost": 4.0,  "value": 50000,    "price": 7500000},
    "圣阶功法":   {"boost": 8.0,  "value": 150000,   "price": 22500000},
    "仙阶功法":   {"boost": 12.0, "value": 3500000,   "price": 52500000},
    "帝阶功法":   {"boost": 16.0, "value": 7000000,   "price": 105000000},
    "无上功法":   {"boost": 20.0, "value": 120000000, "price": 900000000},
}

OTHER_DATA = [
    "魔兽内丹",
    "空间戒指",
    "混沌结晶"
]

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
        "effect": "train_extra",
        "effect_value": 0.2,
        "effect_duration": 7200,
        "price": 2250,
        "value": 1500,
        "description": "修炼时额外获得20%斗气"
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
        "description": "战力+30%持续1小时"
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
        "description": "战力+50%持续1小时"
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
        "description": "1小时内战力+80%"
    },

    # ===== 恢复类丹药 =====
    {
        "id": "restore_qi_1",
        "name": "1品回复丹",
        "type": "recovery",
        "rank": "一品",
        "effect": "restore_qi",
        "effect_value": 0.1,
        "effect_duration": 0,
        "price": 120,
        "value": 80,
        "description": "恢复10%生命并加10点斗气"
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
        "type": "revival",
        "rank": "三品",
        "effect": "revive",
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
        "description": "死亡后自动复活(使用后死亡时自动触发)"
    },
    {
        "id": "reincarnate_6",
        "name": "9品轮回丹",
        "type": "revival",
        "rank": "九品",
        "effect": "reincarnate",
        "effect_value": 1.0,
        "effect_duration": 259200,
        "price": 105000,
        "value": 10000,
        "description": "死亡后保留记忆转世(使用后死亡时自动触发)"
    },
    {
        "id": "full_revive_7",
        "name": "9品涅槃丹",
        "type": "revival",
        "rank": "九品",
        "effect": "full_revive",
        "effect_value": 1.0,
        "effect_duration": 0,
        "price": 80000,
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
        "description": "死亡后立即满状态复活(使用后死亡时自动触发)"
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
        "price": 1200000,
        "value": 80000,
        "description": "提示一定境界（概率，有可能提升一个大境界，有可能无提升）"
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
        backup_path = self.storage_dir / f"{group_id}.json.bak"

        # 如果主文件已存在，先备份它（保留旧版本）
        if file_path.exists():
            file_path.rename(backup_path)
        # 写入新数据到主文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_world(self, group_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.storage_dir / f"{group_id}.json"
        logger.info(f"从 {file_path} 加载数据")
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
        self.temp_boosts = {}  # 临时加成 {"attr": (value, expire_time)}
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
            "explore": 5,  # 1分钟冷却
            "duel": 60  # 1分钟冷却
        }
        self.zb=[] #准备栏
        self.training_progress = 0 #修炼增溢
        self.is_dying = False  # 濒死状态
        self.death_time = 0  # 死亡时间
        self.is_supreme_ruler = False
        self.is_auto_training = False

        logger.info(f"DEBUG: Player {user_name} 初始化，realm_index={self.realm_index}")

    def _calculate_required_qi(self) -> int:
        base = REALMS[self.realm_index]["base_qi"]
        logger.info(f"{self.user_name} 当前境界 {self.realm_index}，基础斗气 {base}")
        return base + (self.level - 1) * int(base * 0.1)

    def _calculate_max_health(self,effect_value=None):
        max_health = 100 + (self.realm_index**2)*(10)
        now = time.time()
        for boost_type, (value, expire) in self.temp_boosts.items():
            if now < expire:
                if boost_type == 'perm_health':
                    max_health += value
        logger.info(f"{self.user_name} 当前境界 {self.realm_index}，当前最大生命值 {max_health}")
        return max_health

    @property
    def realm(self):
        return REALMS[self.realm_index]["name"]

    def get_inventory_display(self) -> str:
        """获取格式化后的背包显示内容（物品×数量）"""
        if not self.inventory:
            return "无"
        # 统计物品数量
        item_counts = {}
        for item in self.inventory:
            if item in item_counts:
                item_counts[item] += 1
            else:
                item_counts[item] = 1

        # 格式化显示
        return ", ".join([f"{name}×{count}" for name, count in item_counts.items()])

    @property
    def title(self):
        titles = ["无名小卒", "初露锋芒", "小有名气", "一方强者", "威震四方",
                  "名动大陆", "绝世高手", "一代宗师", "巅峰强者", "超凡入圣",
                  "位面强者", "万古至尊", "世界主宰", "混沌主宰"]
        title = titles[self.realm_index]
        if self.is_supreme_ruler:
            title = '''
            　　✦˖* ～～～ 至 · 高 · 主 · 宰 ～～～ *˖✦\n
　　              ✨ 星河寂灭我独行，天地唯吾敕令鸣 ✨
            '''
        return title

    @property
    def power(self):
        base_power = 0

        # 境界基础灵气加成
        for i in range(self.realm_index):
            base_power += REALMS[i]['base_qi'] * (10 + self.level)

        # 功法加成（乘数）
        cultivation_multiplier = 1.0
        for item in self.zb:
            if item in CULTIVATION_BOOST:
                boost_value = CULTIVATION_BOOST[item]['boost']
                cultivation_multiplier *= (1+boost_value)
        base_power *= cultivation_multiplier

        # 临时加成
        temp_multiplier = 1.0
        now = time.time()
        for boost_type, (value, expire) in self.temp_boosts.items():
            if now < expire:
                if boost_type in ("battle_all","battle_desperate","battle_invincible"):
                    temp_multiplier *= (1 + value / 10)
                if boost_type in ("battle_strength","battle_defense"):
                    temp_multiplier *= (1 + value / 10 / 4)

        base_power *= temp_multiplier
        if self.is_supreme_ruler:
            base_power *= 1.3
        return base_power

    def can_train(self):
        return time.time() - self.last_train_time > self.cooldowns["train"]

    def can_explore(self):
        base_time = self.cooldowns["explore"]
        now = time.time()
        for boost_type, (value, expire) in self.temp_boosts.items():
            if now < expire:
                if boost_type == "explore_cd":
                    base_time = base_time * (1 - value)
        return time.time() - self.last_explore_time > base_time , base_time

    def can_duel(self):
        return time.time() - self.last_duel_time > self.cooldowns["duel"]

    def gain_qi(self, amount: int):
        self.current_qi += amount
        if self.current_qi >= self.required_qi:
            self.level_up()

    def level_up(self):
        """升级逻辑"""
        self.current_qi -= self.required_qi
        self.level += 1
        self.required_qi = self._calculate_required_qi()

        # 主宰境界需要混沌结晶才能突破
        if self.realm_index == 12 and self.level > 1 and "混沌结晶" not in self.inventory:
            self.level -= 1
            self.current_qi = self.required_qi - 1
            return False
        # 主宰境界突破时消耗混沌结晶
        if self.realm_index == 12 and self.level > 1 and "混沌结晶" in self.inventory:
            self.inventory.remove("混沌结晶")
        # 突破到混沌主宰需要100混沌结晶和1混沌核心
        if self.realm_index == 12 and self.level > REALMS[self.realm_index]["levels"]:
            if ("混沌结晶" not in self.inventory or self.inventory.count(
                    "混沌结晶") < 100) or "混沌核心" not in self.inventory:
                self.level -= 1
                self.current_qi = self.required_qi - 1
                return False
            # 消耗材料
            for _ in range(100):
                self.inventory.remove("混沌结晶")
            self.inventory.remove("混沌核心")
            return True
        if self.level > REALMS[self.realm_index]["levels"]:
            return True
        return False


    def take_damage(self, amount: int):
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            self.is_dying = True
            self.death_time = time.time()
            for boost_type, (value, expire) in self.temp_boosts.items():
                if boost_type == "auto_revive" or boost_type == "reincarnate" or boost_type == "immortal":
                    self.revive(full=True,args=value)
                    return False
            return True  # 触发濒死
        return False

    def apply_temp_boost(self, boost_type: str, value: float, duration: int) -> None:
        """应用临时加成"""
        expire_time = time.time() + duration
        self.temp_boosts[boost_type] = (value, expire_time)

    def heal(self, amount: int) -> None:
        """恢复生命值"""
        self.health = min(self.max_health, self.health + amount)

    def revive(self, full=False,args=None):
        if full:
            self.health = self.max_health
        else:
            if args is None:
                args = 0.3
            self.health = max(1, int(self.max_health * args))
        self.is_dying = False
        self.death_time = 0

    def check_status(self):
        if self.is_dying:
            return False, "你处于濒死状态，需要使用回魂丹复活！"
        return True, ""

    def add_item(self, item_name: str):
        if len(self.inventory) < 200 + sum(10 for item in self.inventory if "空间戒指" in item):
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
        """
        使用一个物品。
        支持：丹药系统、修炼增益类物品（CULTIVATION_BOOST）
        """
        # 1. 尝试使用丹药
        pill_result = PillSystem.use_pill(self, item_name)
        if pill_result[0] or pill_result[1] != "无效的丹药":
            return pill_result
        # 2. 检查是否为修炼增益类物品
        if item_name not in CULTIVATION_BOOST:
            return False, "无效的物品"
        boost_data = CULTIVATION_BOOST[item_name]
        boost_value = boost_data['boost']
        # 3. 查找当前装备中同类增益物品（用于替换）
        old_item = None
        for item in self.zb:
            if item in CULTIVATION_BOOST:
                old_item = item
                break
        # 4. 如果已有同类增益物品，先移除其效果
        if old_item:
            old_boost = CULTIVATION_BOOST[old_item]['boost']
            self.training_progress -= old_boost
            # 从装备栏移除，并放回背包
            self.zb.remove(old_item)
            self.inventory.append(old_item)
        # 5. 检查背包中是否有该物品
        if item_name not in self.inventory:
            return False, f"背包中没有 {item_name}，无法使用。"
        # 6. 从背包移除，加入装备栏
        self.inventory.remove(item_name)
        self.zb.append(item_name)
        self.training_progress += boost_value
        return True, f"已使用 {item_name}，效果已生效。"

    def train(self, continuous=False):
        # 冷却检查
        if not continuous and not self.can_train():
            remaining = int(self.cooldowns["train"] - (time.time() - self.last_train_time))
            return False, f"修炼需要冷却，还需等待{remaining}秒"

        # 状态检查（健康值、走火入魔等）
        status_ok, msg = self.check_status()
        if not status_ok:
            return False, msg

        # 基础增益计算（基于境界和等级）
        min_gain, max_gain = REALMS[self.realm_index]["train_gain"]
        base_multiplier = 1 + (self.level - 1) * 0.05  # 每级+5%增益（非指数增长）
        base_gain = random.randint(min_gain, max_gain) * base_multiplier

        # 混沌主宰特殊限制
        if self.realm_index == 12 and "混沌结晶" not in self.inventory:
            return False, "主宰境界修炼需要混沌结晶引导，否则无法吸收斗气！"

        # 走火入魔判定（连续修炼降低风险）
        now = time.time()
        addicted = 0.5
        for boost_type, (value, expire) in self.temp_boosts.items():
            if now >= expire:
                continue
            if boost_type == "train_safe":
                addicted -= value
                if addicted < 0:
                    addicted = 0
            if boost_type == "train_immune":
                addicted = 0
            if boost_type == "train_perfect":
                addicted = 0
        if continuous:
            addicted *= 0.7  # 连续修炼风险降低30%
        if addicted > 0 and random.random() < addicted:
            return False, "修炼时气息紊乱，险些走火入魔！"

        # 增益计算体系（乘法叠加）
        boost = 1.0
        # 装备增益
        for key in CULTIVATION_BOOST.keys():
            if key in self.zb:
                boost *= (1 + CULTIVATION_BOOST[key]['boost'])
        # 临时增益
        for boost_type, (value, expire) in self.temp_boosts.items():
            if now < expire:
                if boost_type in ["train_boost", "train_perfect"]:
                    boost *= (1 + value)
                elif boost_type == "train_extra":
                    base_gain *= (1 + value)

        # 境界压制（高境界修炼效率衰减）
        realm_suppression = 1 - (self.realm_index * 0.02)  # 每境界衰减2%
        # 最终斗气增益
        qi_gain = int(base_gain * boost * realm_suppression * (1.3 if continuous else 1.0))

        # 更新角色状态
        self.current_qi += qi_gain
        self.health = min(self.health + 10, self.max_health)
        if not continuous:
            self.last_train_time = time.time()

        # 突破检查
        if self.current_qi >= self.required_qi:
            need_breakthrough = self.level_up()
            if need_breakthrough:
                return True, "已达到突破条件！使用 /突破 尝试突破"
            return True, f"★ 突破至 {self.realm} {self.level}星！★"
        return True, f"修炼获得 {qi_gain} 斗气（基础 {int(base_gain)} ×{boost:.1f}），进度：{self.current_qi}/{self.required_qi}"


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

        # protected = any("护脉丹" in item for item in self.inventory)
        if 'breakthrough_protect' in self.temp_boosts or '2品护脉丹' in self.inventory:
            protected = True
        else:
            protected = False


        if random.random() < success_chance:
            if self.realm_index == 12 and self.level > REALMS[self.realm_index]["levels"]:
                if ("混沌结晶" not in self.inventory or self.inventory.count(
                        "混沌结晶") < 100) or "混沌核心" not in self.inventory:
                    self.level -= 1
                    self.current_qi = self.required_qi - 1
                    return False, f"缺少核心突破材料，无法进行突破"
                for _ in range(100):
                    self.inventory.remove("混沌结晶")
                self.inventory.remove("混沌核心")
            self.realm_index += 1
            if self.realm_index == 13:
                self.level = 1
            else:
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
                protected_item = "2品护脉丹"
                if protected_item:
                    self.inventory.remove(protected_item)
                return False, f"突破失败！但【{protected_item}】保护了你免受反噬"

            damage = random.randint(10, (self.realm_index+1)**2 * 10/2) * (self.realm_index + 1)
            self.health = max(1, self.health - damage)
            return False, f"突破失败！受到{damage}点反噬伤害"

    def explore(self, level="初级"):
        # 检查冷却和状态
        status_ok, base_time = self.can_explore()
        if not status_ok:
            remaining = int(base_time - (time.time() - self.last_explore_time))
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
            dmg = min(120, int(base_dmg * (1 + danger_boost)))
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

    def add_gold(self, amount: int) -> None:
        """增加金币"""
        self.gold += amount

    def deduct_gold(self, amount: int) -> bool:
        """扣除金币，如果不足返回False"""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def realm_up(self, pill):
        effect_value = pill.get("effect_value", 1)  # 防止 key 不存在

        if self.realm_index == 12:
            # 特殊情况：境界为 12，只增加灵气
            self.current_qi += 1000000000
            print("已达至高境界，只吸收海量灵气！")
            return
        # 根据当前境界决定突破概率
        if self.realm_index < 5:
            success_chance = 0.3  # 30% 大境界突破
        elif self.realm_index < 12:
            success_chance = 0.05  # 5% 大境界突破
        else:
            success_chance = 0  # 境界 >=12 不可能突破

        if random.random() < success_chance:
            # 成功突破大境界
            self.realm_index += effect_value
            self.level = 1
            self.current_qi = 0
            self.required_qi = self._calculate_required_qi()
            print(f"恭喜突破至大境界 {self.realm_index}！")
        else:
            # 未突破，随机增加若干等级
            level_up = random.randint(1, 5)  # 假设随机升 1~5 级
            self.level += level_up
            # 可选：升级后调整 current_qi，比如清空或按比例保留
            self.current_qi = 0  # 通常突破失败不涨大境界，但这里只升小等级
            print(f"突破失败，但小有进益，提升了 {level_up} 个小等级！")
        # 更新所需灵气（无论是否突破）
        if self.realm_index != 12:
            self.required_qi = self._calculate_required_qi()

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
            "is_supreme_ruler": self.is_supreme_ruler,  # 新增持久化字段
            "is_auto_training": self.is_auto_training,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        logger.info(f"Loading player {data['user_name']}, realm_index={data.get('realm_index')}")
        player = cls(data["user_id"], data["user_name"], data["realm_index"])
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
        player.last_duel_time = data["last_duel_time"]
        player.is_dying = data.get("is_dying", False)
        player.death_time = data.get("death_time", 0)
        player.temp_boosts = data.get("temp_boosts", {})
        player.is_supreme_ruler = data.get("is_supreme_ruler", False)  # 新增持久化字段
        player.is_auto_training = data.get("is_auto_training", False)
        return player

    # def to_dict(self) -> Dict[str, Any]:
    #     logger.info(f"Loading player {self.user_name}, realm_index={self.realm_index}")
    #     return {
    #         "user_id": self.user_id,
    #         "user_name": self.user_name,
    #         "realm_index": self.realm_index,
    #         "level": self.level,
    #         "current_qi": self.current_qi,
    #         "required_qi": self.required_qi,
    #         "health": self.health,
    #         "gold": self.gold,
    #         "inventory": self.inventory,
    #         "zb": self.zb,
    #         "training_progress": self.training_progress,
    #         "last_train_time": self.last_train_time,
    #         "last_explore_time": self.last_explore_time,
    #         "last_duel_time": self.last_duel_time,
    #         "is_dying": self.is_dying,
    #         "death_time": self.death_time,
    #         "temp_boosts": self.temp_boosts,
    #     }

    # @classmethod
    # def from_dict(cls, data: Dict[str, Any]) -> "Player":
    #     logger.info(f"Loading player {data['user_name']}, realm_index={data.get('realm_index')}")
    #     player = cls(data["user_id"], data["user_name"],data["realm_index"])
    #     player.realm_index = data["realm_index"]
    #     player.level = data["level"]
    #     player.current_qi = data["current_qi"]
    #     player.required_qi = data["required_qi"]
    #     player.health = data["health"]
    #     player.gold = data["gold"]
    #     player.inventory = data["inventory"]
    #     player.last_train_time = data["last_train_time"]
    #     player.zb = data["zb"]
    #     player.training_progress = data["training_progress"]
    #     player.last_explore_time = data["last_explore_time"]
    #     player.last_duel_time = data["last_duel_time"]
    #     player.is_dying = data.get("is_dying", False)
    #     player.death_time = data.get("death_time", 0)
    #     player.temp_boosts = data.get("temp_boosts", {})
    #     return player





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

        self.auction_items = []
        self.last_auction_refresh = 0
        self.auction_bids = {}  # {index: {'bid': amount, 'bidder': user_id, 'bidder_name': name, 'bid_time': timestamp}}
        self.auction_end_time = 0
        self.auction_quick_win_tasks: Dict[int, asyncio.Task] = {}

        self.lottery_pool = 5000000 + 213616  # 奖池累计
        self.last_lottery_draw = 0  # 上次开奖时间
        self.lottery_tickets = {}  # 玩家购买的彩票 {user_id: [ticket_numbers]}
        self.lottery_history = []  # 历史开奖记录
        self.lottery_end_time = self.last_lottery_draw  #
        self.lottery_task = []

        self.supreme_ruler = None  # 当前至高主宰玩家ID
        self.world_boss_alive = True  # 世界boss状态
        self.world_boss_hp = 1000000000  # 世界boss血量
        self.world_boss_max_hp = 1000000000  # 世界boss最大血量
        self.supreme_ruler_title = "至高主宰"  # 称号名称
        self.supreme_ruler_bonus = 1.5  # 至高主宰加成系数

        # 新增交易系统
        self.trade_requests: Dict[str, Dict] = {}  # {trade_id: trade_data}
        self.next_trade_id = 1


    def reset_world_boss(self):
        """重置世界boss"""
        self.world_boss_alive = True
        self.world_boss_hp = self.world_boss_max_hp

    def get_dominator_players(self):
        """获取当前世界中的所有主宰玩家"""
        return [p for p in self.players.values() if p.realm_index == 12]

    def get_dominator_ranking(self, top_n=10):
        """获取主宰玩家战力排行榜"""
        dominators = self.get_dominator_players()
        sorted_doms = sorted(dominators, key=lambda x: x.power, reverse=True)
        return sorted_doms[:top_n]

    def generate_technique(self):
        """按概率生成功法"""
        technique = random.choices(
            ["黄阶功法", "玄阶功法", "地阶功法", "天阶功法","神阶功法","圣阶功法","仙阶功法"],
            weights=[65, 30, 10, 5, 1, 0.5, 0.1]  # 黄阶65%，玄阶30%，地阶4%，天阶1%
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

        default_pill = PillSystem.get_pill_by_name("2品回魂丹")
        if default_pill:
            for i in range(0,2):
                self.market_items.append({
                    "name": default_pill["name"],
                    "effect": default_pill["description"],
                    "price": default_pill["price"],
                    "value": default_pill["value"],
                    "type": default_pill["type"]
                })

        jz_random = random.randint(1, 10)
        if jz_random >=8 :
            self.market_items.append({
                "name": "空间戒指",
                "effect": "",
                "price": random.randint(8000, 30000),
                "value": "",
                "type": ""
            })

        # 6. 填充空缺位置（使用随机低品丹药）
        for i in range(0, 25 - len(self.market_items)):
            # 随机选择一种低品丹药类型来填充
            pill_types = ["healing", "recovery"]
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

    def generate_auction_items(self):
        # 从高级物品中随机选择
        rare_items = []

        # 添加高级功法
        ranks = list(CULTIVATION_BOOST.keys())
        probabilities = [0, 0, 0, 70.0, 20.0, 5.0, 3.0, 1.4, 0.6]  # 总和 100%
        # 验证总和
        assert abs(sum(probabilities) - 100.0) < 1e-6, "概率总和必须为100%"

        # 生成5个功法（可重复）
        selected_names = random.choices(ranks, weights=probabilities, k=5)

        # 构建结果列表（和你原来的结构一致）
        rare_items = []
        for name in selected_names:
            data = CULTIVATION_BOOST[name]
            rare_items.append({
                "name": name,
                "description": f"修炼速度+{int(data['boost'] * 100)}%",
                "base_price": int(data['price'] * random.uniform(1.5, 2.5)),
                "rank": "高级" if name in ["天阶功法", "神阶功法"] else "普通",  # 可扩展
                "type": "功法"
            })
        # for name, data in CULTIVATION_BOOST.items():
        #     if name in ["天阶功法","神阶功法"]:
        #         rare_items.append({
        #             "name": name,
        #             "description": f"修炼速度+{int(data['boost'] * 100)}%",
        #             "base_price": int(data['price'] * random.uniform(1.5, 2.5)),
        #             "rank": "高级",
        #             "type": "功法"
        #         })

        # 添加高级丹药（从PILLS_DATA中筛选6品及以上）
        for pill in PILLS_DATA:
            rank_str = pill.get('rank', '')
            if '六品' in rank_str or '七品' in rank_str or '八品' in rank_str or '九品' in rank_str:
                rare_items.append({
                    "name": pill['name'],
                    "description": pill['description'],
                    "base_price": int(pill['price'] * random.uniform(1.2, 2.0)),
                    "rank": pill['rank'],
                    "type": pill['type']
                })
        # 随机选择3-5件商品
        num_items = min(random.randint(3, 5), len(rare_items))
        self.auction_items = random.sample(rare_items, num_items)

    def process_auction_results(self):
        """处理拍卖结果，在拍卖结束后调用"""
        results = []
        for index, item in enumerate(self.auction_items):
            bid_info = self.auction_bids.get(str(index))
            if bid_info:
                # 找到最高出价者
                winner_id = bid_info['bidder']
                bid_amount = bid_info['bid']

                if winner_id in self.players:
                    winner = self.players[winner_id]
                    if winner.gold >= bid_amount:
                        winner.gold -= bid_amount
                        if winner.add_item(item['name']):
                            results.append(f"🎉 【{winner.user_name}】以 {bid_amount}金币 拍得 【{item['name']}】")
                        else:
                            results.append(f"❌ 【{winner.user_name}】拍得 【{item['name']}】但背包已满，交易取消")
                            winner.gold += bid_amount  # 返还金币
                    else:
                        results.append(f"❌ 【{winner.user_name}】金币不足，【{item['name']}】流拍")
                else:
                    results.append(f"❌ 【{item['name']}】流拍（出价者已退出游戏）")
            else:
                results.append(f"❌ 【{item['name']}】无人出价，流拍")
        # 清空拍卖物品
        self.auction_items = []
        return results

    def generate_lottery_numbers(self) -> List[int]:
        """生成5个1-35的主号码和2个1-12的特别号码"""
        main_numbers = sorted(random.sample(range(1, 36), 5))
        special_numbers = sorted(random.sample(range(1, 13), 2))
        return main_numbers + special_numbers

    def buy_lottery_ticket(self, user_id: str, numbers: List[int] = None) -> Tuple[bool, str]:
        """购买彩票"""
        if numbers and len(numbers) != 7:
            return False, "请输入7个数字(前5个1-35，后2个1-12)"

        if not numbers:
            numbers = self.generate_lottery_numbers()
        else:
            # 验证数字范围
            for i in range(5):
                if not 1 <= numbers[i] <= 35:
                    return False, "前5个数字必须在1-35范围内"
            for i in range(5, 7):
                if not 1 <= numbers[i] <= 12:
                    return False, "后2个数字必须在1-12范围内"

        if user_id not in self.lottery_tickets:
            self.lottery_tickets[user_id] = []

        self.lottery_tickets[user_id].append(numbers)
        self.lottery_pool += 100  # 每注100金币加入奖池
        return True, f"购买成功！你的号码是：{numbers[:5]} + {numbers[5:]}"

    def draw_lottery(self) -> Dict[str, Any]:
        """开奖并计算中奖结果"""
        if self.lottery_pool <= 0:
            self.lottery_pool = 100000
        winning_numbers = self.generate_lottery_numbers()
        winners = {
            "一等奖": [],  # 5+2
            "二等奖": [],  # 5+1
            "三等奖": [],  # 5+0
            "四等奖": [],  # 4+2
            "五等奖": [],  # 4+1
            "六等奖": [],  # 3+2 or 2+2
            "七等奖": [],  # 4+0
            "八等奖": [],  # 3+1 or 1+2
            "九等奖": []  # 3+0 or 2+1 or 0+2
        }

        # 更合理的奖池分配方案，提高中低奖项比例
        prize_distribution = {
            "一等奖": 0.4,  # 40% 奖池 - 头奖，占大头
            "二等奖": 0.25,  # 25% 奖池 - 次大奖
            "三等奖": 0.15,  # 15% 奖池 - 中等奖
            "四等奖": 0.08,  # 8% 奖池 - 小奖，递减
            "五等奖": 0.05,  # 5% 奖池
            "六等奖": 0.03,  # 3% 奖池
            "七等奖": 0.02,  # 2% 奖池
            "八等奖": 0.015,  # 1.5% 奖池
            "九等奖": 0.005  # 0.5% 奖池 - 安慰奖，比例最小
        }

        # 计算每个奖项的奖金
        total_prize = self.lottery_pool
        prize_amounts = {
            level: int(total_prize * percentage)
            for level, percentage in prize_distribution.items()
        }

        # 检查所有彩票
        for user_id, tickets in self.lottery_tickets.items():
            for ticket in tickets:
                main_match = len(set(ticket[:5]) & set(winning_numbers[:5]))
                special_match = len(set(ticket[5:]) & set(winning_numbers[5:]))

                if main_match == 5 and special_match == 2:
                    winners["一等奖"].append((user_id, ticket))
                elif main_match == 5 and special_match == 1:
                    winners["二等奖"].append((user_id, ticket))
                elif main_match == 5:
                    winners["三等奖"].append((user_id, ticket))
                elif main_match == 4 and special_match == 2:
                    winners["四等奖"].append((user_id, ticket))
                elif main_match == 4 and special_match == 1:
                    winners["五等奖"].append((user_id, ticket))
                elif (main_match == 3 and special_match == 2) or (main_match == 2 and special_match == 2):
                    winners["六等奖"].append((user_id, ticket))
                elif main_match == 4:
                    winners["七等奖"].append((user_id, ticket))
                elif (main_match == 3 and special_match == 1) or (main_match == 1 and special_match == 2):
                    winners["八等奖"].append((user_id, ticket))
                elif main_match == 3 or (main_match == 2 and special_match == 1) or (
                        main_match == 0 and special_match == 2):
                    winners["九等奖"].append((user_id, ticket))

        # 计算实际发放的总奖金
        total_payout = 0
        for level in prize_amounts:
            if winners[level]:  # 如果有中奖者
                # 奖金按中奖人数平分
                per_winner_prize = prize_amounts[level] // len(winners[level])
                total_payout += per_winner_prize * len(winners[level])

        # 记录开奖结果
        self.lottery_history.append({
            "draw_time": time.time(),
            "numbers": winning_numbers,
            "winners": {k: len(v) for k, v in winners.items()},
            "total_payout": total_payout
        })

        # 重置奖池和彩票
        # 全额保留奖池，扣除已发放奖金，并添加基础奖金
        self.lottery_pool = self.lottery_pool - total_payout + 1000
        self.lottery_tickets = {}
        self.last_lottery_draw = time.time()

        return {
            "numbers": winning_numbers,
            "winners": winners,
            "prizes": prize_amounts,
            "total_payout": total_payout
        }

    def _send_lottery_result(self, event: AstrMessageEvent, result: dict):
        """发送开奖结果通知"""
        logger.info("正在发送开奖结果...")
        logger.info(result)

        # 格式化中奖号码
        main_numbers = " ".join(map(str, result['numbers'][:5]))
        special_numbers = " ".join(map(str, result['numbers'][5:]))
        winning_numbers = f"主区: {main_numbers} | 特码: {special_numbers}"

        # 构建中奖信息
        winner_info = []
        prize_levels = ["一等奖", "二等奖", "三等奖", "四等奖", "五等奖",
                        "六等奖", "七等奖", "八等奖", "九等奖"]

        # 用于存储五等奖以上的详细票信息
        high_prize_tickets = []

        for level in prize_levels:
            if result["winners"][level]:
                winners = []
                for user_id, ticket in result["winners"][level]:
                    player = self.players.get(user_id)
                    if player:
                        # 计算个人奖金（平分该奖项总奖金）
                        prize = result["prizes"][level] // len(result["winners"][level])
                        player.add_gold(prize)

                        # 格式化号码
                        ticket_main = " ".join(map(str, ticket[:5]))
                        ticket_special = " ".join(map(str, ticket[5:]))
                        ticket_str = f"{ticket_main} + {ticket_special}"

                        winners.append(f"{player.user_name} [{ticket_str}] (+{prize}金币)")

                        # 如果是五等奖及以上，记录详细信息
                        if level in ["一等奖", "二等奖", "三等奖", "四等奖", "五等奖"]:
                            high_prize_tickets.append(
                                f"{player.user_name} [{ticket_str}] - {level} (+{prize}金币)"
                            )

                if winners:
                    # 添加奖项标题和获奖者
                    winner_info.append(f"★{level}★")
                    winner_info.extend(winners)
                    winner_info.append("")  # 空行分隔

        if not any(result["winners"].values()):
            winner_info.append("本期无人中奖，奖池将累积至下期")

        # 构建最终消息
        message = (
                "══════ 斗气彩开奖结果 ══════\n"
                f"🎯 中奖号码: {winning_numbers}\n"
                f"💰 奖池总额: {sum(result['prizes'].values()):,}金币\n"
                "\n"
        )

        # 如果有五等奖以上的中奖票，添加详细信息
        if high_prize_tickets:
            message += (
                    "\n\n🎫 五等奖及以上详细票信息:\n" +
                    "\n".join(high_prize_tickets) +
                    "\n"
            )

        message += (
            "\n══════════════════════════\n"
            "感谢参与，下期再见！"
        )

        logger.info(message)
        return message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "game_started": self.game_started,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "market_items": self.market_items,
            "last_market_refresh": self.last_market_refresh,
            "world_events": self.world_events,
            "last_event_update": self.last_event_update,
            "duel_requests": self.duel_requests,
            "auction_items": self.auction_items,
            "last_auction_refresh": self.last_auction_refresh,
            "auction_bids": self.auction_bids,
            "auction_end_time": self.auction_end_time,
            "lottery_pool": self.lottery_pool,
            "last_lottery_draw": self.last_lottery_draw,
            "lottery_tickets": self.lottery_tickets,
            "lottery_history": self.lottery_history,
            "lottery_end_time": self.lottery_end_time,
            "supreme_ruler": self.supreme_ruler,
            "world_boss_alive": self.world_boss_alive,
            "world_boss_hp": self.world_boss_hp,
            "world_boss_max_hp": self.world_boss_max_hp,
            "trade_requests": self.trade_requests,
            "next_trade_id": self.next_trade_id,
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

        # 恢复拍卖系统数据
        world.auction_items = data.get("auction_items", [])
        world.last_auction_refresh = data.get("last_auction_refresh", 0)
        world.auction_bids = data.get("auction_bids", {})
        world.auction_end_time = data.get("auction_end_time", 0)

        # 恢复彩票系统数据
        world.lottery_pool = data.get("lottery_pool", 5000000 + 213616)
        world.last_lottery_draw = data.get("last_lottery_draw", 0)
        world.lottery_tickets = data.get("lottery_tickets", {})
        world.lottery_history = data.get("lottery_history", [])
        world.lottery_end_time = data.get("lottery_end_time", 0)

        # 恢复至高主宰数据
        world.supreme_ruler = data.get("supreme_ruler")

        # 恢复世界boss数据
        world.world_boss_alive = data.get("world_boss_alive", True)
        world.world_boss_hp = data.get("world_boss_hp", 1000000000)
        world.world_boss_max_hp = data.get("world_boss_max_hp", 1000000000)

        # 恢复交易系统数据
        world.trade_requests = data.get("trade_requests", {})
        world.next_trade_id = data.get("next_trade_id", 1)

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
            logger.error(e)
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

    @staticmethod
    def search_pill_by_name(query: str) -> List[Dict]:
        """
        搜索丹药：支持模糊匹配名称或ID
        返回匹配的丹药列表
        """
        if not query.strip():
            return []

        query = query.lower().strip()
        results = []

        for pill in PILLS_DATA:
            if (query in pill["name"].lower() or
                    query in pill["id"].lower() or
                    query in pill["rank"].lower()):
                results.append(pill)

        return results

    @staticmethod
    def display_pill_detail(pill: Dict) -> str:
        """
        格式化输出单个丹药的详细信息
        """
        duration = pill["effect_duration"]
        duration_str = "立即生效" if duration == 0 else (
            f"{duration // 60}分钟" if duration < 3600 else
            f"{duration // 3600}小时"
        )

        detail = (
            f"【{pill['name']}】({pill['rank']} | {pill['type']})\n"
            f"  ID: {pill['id']}\n"
            f"  效果: {pill['description']}\n"
            f"  持续时间: {duration_str}\n"
            f"  价值: {pill['value']} | 售价: {pill['price']} 金币"
        )
        return detail

    @staticmethod
    def list_all_pills(page: int = 1, page_size: int = 10) -> str:
        """
        分页列出所有丹药的简要信息
        """
        total_pills = len(PILLS_DATA)
        total_pages = math.ceil(total_pills / page_size)

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_pills = PILLS_DATA[start_idx:end_idx]

        if not paginated_pills:
            return "暂无丹药数据。"

        output = [f"===== 丹药列表 (第 {page}/{total_pages} 页) ====="]
        for pill in paginated_pills:
            duration = pill["effect_duration"]
            duration_hint = "" if duration == 0 else (
                f"({duration // 60}分钟)" if duration < 3600 else f"({duration // 3600}h)"
            )
            output.append(
                f"• {pill['name']} [{pill['rank']}] "
                f"({pill['type']}) {duration_hint}"
            )

        output.append(f"\n共 {total_pills} 种丹药，输入 '/丹药 页码' 查看其他页")
        return "\n".join(output)

    @staticmethod
    def handle_query_command(query: str = "", page_str: str = "") -> str:
        """
        处理用户查询命令的统一接口
        示例：
            handle_query_command("聚气") -> 搜索含“聚气”的丹药
            handle_query_command("", "2") -> 显示第2页所有丹药
            handle_query_command() -> 显示第1页
        """
        # 如果提供了页码，则显示所有丹药的对应页
        if page_str.isdigit():
            page = int(page_str)
            return PillSystem.list_all_pills(page=page)
        # 如果有搜索关键词
        if query.strip():
            results = PillSystem.search_pill_by_name(query)
            if not results:
                return f"未找到与 '{query}' 相关的丹药。"

            if len(results) == 1:
                return PillSystem.display_pill_detail(results[0])
            else:
                output = [f"找到 {len(results)} 个匹配结果："]
                for pill in results:
                    output.append(f"• {pill['name']} [{pill['rank']}] - {pill['type']}")
                output.append("输入完整名称查看详情。")
                return "\n".join(output)
        # 默认显示第1页
        return PillSystem.list_all_pills(page=1)


class DungeonManager:
    def __init__(self):
        self.active_dungeons = {}  # {dungeon_id: DungeonInstance}
        self.next_dungeon_id = 1
        self.pending_confirmations = {}  # {dungeon_id: set(player_ids)}

    def create_dungeon(self, world: GameWorld, level: str, player_ids: List[str]) -> str:
        """创建新副本"""
        if level not in DUNGEON_LEVELS:
            return f"无效的副本等级: {level}"

        players = [world.players[pid] for pid in player_ids if pid in world.players]
        if not players:
            return "没有有效的玩家参与副本"

        if len(players) > 5:
            return "副本最多支持5名玩家"

        dungeon_id = f"dungeon-{self.next_dungeon_id}"
        self.next_dungeon_id += 1

        dungeon = DungeonInstance(
            dungeon_id=dungeon_id,
            level=level,
            players=players,
            boss_power=DUNGEON_LEVELS[level]["boss_power"],
            creator_id=player_ids[0]  # 第一个玩家是发起者
        )
        self.active_dungeons[dungeon_id] = dungeon
        # 初始化确认集合，包含所有玩家ID
        self.pending_confirmations[dungeon_id] = set(player_ids)

        # 生成奖励预览
        dungeon_info = DUNGEON_LEVELS[level]
        reward_preview = []
        for item in dungeon_info["drop_items"]:
            prob_percent = int(item["probability"] * 100)
            quantity = f"{item['quantity'][0]}-{item['quantity'][1]}" if isinstance(item["quantity"], tuple) else item[
                "quantity"]
            reward_preview.append(f"- {item['name']} ({prob_percent}%几率, 数量: {quantity})")

        player_names = ", ".join(p.user_name for p in players)
        return (
            f"=== 副本组队成功 ===\n"
            f"副本等级: {level}\n"
            f"参与玩家: {player_names}\n"
            f"BOSS战力: {dungeon.boss_power:,}\n"
            f"队伍总战力: {dungeon.total_power:,}\n\n"
            f"=== 可能获得的奖励 ===\n"
            f"{reward_preview}\n\n"
            f"金币范围: {dungeon_info['gold_range'][0]:,}-{dungeon_info['gold_range'][1]:,}\n"
            f"奖励倍率: {dungeon_info['reward_factor']}x\n\n"
            f"副本ID: {dungeon_id}\n"
            f"所有队员需输入 /接受副本 {dungeon_id} 确认准备就绪\n"
            f"当所有队员确认后，发起者可输入 /开始副本 {dungeon_id} 开始挑战"
        )

    def confirm_dungeon(self, dungeon_id: str, player_id: str) -> str:
        """玩家确认准备就绪"""
        if dungeon_id not in self.active_dungeons:
            return "无效的副本ID"

        if dungeon_id not in self.pending_confirmations:
            return "该副本已准备好，等待发起者开始"

        if player_id not in self.pending_confirmations[dungeon_id]:
            return "你不是该副本的参与者"

        self.pending_confirmations[dungeon_id].remove(player_id)
        remaining = len(self.pending_confirmations[dungeon_id])

        if remaining == 0:
            del self.pending_confirmations[dungeon_id]
            return f"所有队员已确认！发起者现在可以输入 /开始副本 {dungeon_id} 开始挑战"
        else:
            return f"已确认准备就绪，还剩下 {remaining} 位队员需要确认"

    def start_dungeon(self, dungeon_id: str, player_id: str) -> Tuple[bool, str]:
        """开始副本挑战并返回结果"""
        if dungeon_id not in self.active_dungeons:
            return False, "无效的副本ID"

        dungeon = self.active_dungeons[dungeon_id]

        # 检查是否是发起者
        if player_id != dungeon.creator_id:
            return False, "只有副本发起者可以开始挑战"

        # 检查是否所有玩家都已确认
        if dungeon_id in self.pending_confirmations:
            remaining = len(self.pending_confirmations[dungeon_id])
            return False, f"还有 {remaining} 位队员未确认，无法开始挑战"

        dungeon = self.active_dungeons.pop(dungeon_id)
        return dungeon.run_battle()


class DungeonInstance:
    def __init__(self, dungeon_id: str, level: str, players: List[Player], boss_power: int, creator_id: str):
        self.dungeon_id = dungeon_id
        self.level = level
        self.players = players
        self.boss_power = boss_power
        self.creator_id = creator_id  # 副本发起者ID
        self.start_time = time.time()

    @property
    def total_power(self) -> int:
        """计算队伍总战力"""
        return sum(p.power for p in self.players)

    def run_battle(self) -> Tuple[bool, str]:
        """执行副本战斗逻辑"""
        # 计算胜率 (队伍战力/(队伍战力+boss战力))
        power_ratio = self.total_power / self.boss_power
        # ✅ 核心改动：平移 Sigmoid，让 ratio=0.7 时胜率=50%
        # 目标：ratio=1.0 时胜率≈80%
        center_point = 0.7  # 在这里，胜率是50%
        steepness = 5.0  # 控制曲线陡峭度
        base_probability = 1 / (1 + math.exp(-steepness * (power_ratio - center_point)))
        # 小幅随机扰动 ±5%
        random_effect = random.uniform(-0.05, 0.05)
        final_probability = max(0.0, min(1.0, base_probability + random_effect))
        victory = random.random() < final_probability
        if victory:
            gold_reward, dropped_items = self._distribute_rewards()
        else:
            gold_reward, dropped_items = None, None
        result_msg = self._generate_result_message(victory,gold_reward,dropped_items)

        return victory, result_msg

    def _generate_result_message(self, victory: bool,gold_reward=None,dropped_items=None) -> str:
        """生成战斗结果消息"""
        dungeon_info = DUNGEON_LEVELS[self.level]
        player_names = ", ".join(p.user_name for p in self.players)

        if victory:
            # 生成奖励详情
            reward_details = [f"金币: {int(gold_reward):,}"]
            if dropped_items:
                reward_details.append("\n掉落物品:")
                for item_name, quantity in dropped_items.items():
                    reward_details.append(f"- {item_name} ×{quantity}")
            else:
                reward_details.append("\n(本次未掉落物品)")

            reward_info = "\n".join(reward_details)

            return (
                f"=== 副本挑战成功 ===\n"
                f"副本等级: {self.level}\n"
                f"参与玩家: {player_names}\n"
                f"BOSS战力: {self.boss_power:,}\n"
                f"队伍总战力: {self.total_power:,}\n"
                f"经过激烈战斗，你们成功击败了BOSS！\n\n"
                f"=== 获得奖励 ===\n"
                f"{reward_info}"
            )
        else:
            # 失败惩罚
            damage_per_player = int(self.boss_power * 0.2 / len(self.players))
            for player in self.players:
                player.take_damage(damage_per_player)
            return (
                f"=== 副本挑战失败 ===\n"
                f"副本等级: {self.level}\n"
                f"参与玩家: {player_names}\n"
                f"BOSS战力: {self.boss_power:,}\n"
                f"队伍总战力: {self.total_power:,}\n"
                f"BOSS的实力远超想象，队伍不敌败退！\n"
                f"每位玩家损失了{damage_per_player}点生命值"
            )

    def _distribute_rewards(self):
        """分配副本奖励并返回实际掉落的物品"""
        dungeon_info = DUNGEON_LEVELS[self.level]

        # 基础金币奖励
        gold_min, gold_max = dungeon_info["gold_range"]
        gold_reward = random.randint(gold_min, gold_max) * dungeon_info["reward_factor"]

        # 收集实际掉落的物品
        dropped_items = {}
        for item in dungeon_info["drop_items"]:
            if random.random() < item["probability"]:
                quantity = item["quantity"] if isinstance(item["quantity"], int) else random.randint(*item["quantity"])
                if item["name"] in dropped_items:
                    dropped_items[item["name"]] += quantity
                else:
                    dropped_items[item["name"]] = quantity
        # 分配奖励给玩家
        for player in self.players:
            # 金币奖励
            player.gold += int(gold_reward)

            # 物品奖励
            for item_name, quantity in dropped_items.items():
                for _ in range(quantity):
                    player.add_item(item_name)
        return gold_reward, dropped_items

# ==================== 主插件类 ====================
@register("dpcq_final", "author", "斗破苍穹最终版", "1.0.0", "repo url")
class DouPoCangQiongFinal(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.worlds: Dict[str, GameWorld] = {}
        self.player_world_map: Dict[str, str] = {}
        self.persistence = DataPersistence()
        self.dungeon_manager = DungeonManager()
        self.auto_train_tasks = {}
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

    def send_scheduled_messages(self, event: AstrMessageEvent, group_id: str, message: str, seconds):
        """发送定时消息"""
        world = self._get_world(group_id)






    async def terminate(self):
        for task in self.auto_train_tasks.values():
            task.cancel()
        for group_id in self.worlds:
            self._save_world(group_id)
        await super().terminate()

    async def _process_quick_win(self, event: AstrMessageEvent, group_id: str, item_index: int):
        try:
            await asyncio.sleep(30)
            world = self._get_world(group_id)

            # Check if the item is still up for auction and has a bid
            if item_index >= len(world.auction_items) or world.auction_items[item_index] is None:
                if item_index in world.auction_quick_win_tasks:
                    del world.auction_quick_win_tasks[item_index]
                return  # Item already sold or auction ended

            bid_info = world.auction_bids.get(str(item_index))
            if not bid_info:
                if item_index in world.auction_quick_win_tasks:
                    del world.auction_quick_win_tasks[item_index]
                return # No bid, should not happen if task was created

            item = world.auction_items[item_index]
            winner_id = bid_info['bidder']
            winner_name = bid_info['bidder_name']
            bid_amount = bid_info['bid']
            winner = world.players.get(winner_id)

            if winner and winner.deduct_gold(bid_amount):
                winner.add_item(item['name'])
                
                win_message = f"⚡️快速成交！⚡️\n30秒内无人出价，【{item['name']}】以 {bid_amount} 金币的价格成交给【{winner_name}】！"
                message_chain = MessageChain().message(win_message)
                await self.context.send_message(event.unified_msg_origin, message_chain)

                # Clean up
                world.auction_items[item_index] = None
                if str(item_index) in world.auction_bids:
                    del world.auction_bids[str(item_index)]
                if item_index in world.auction_quick_win_tasks:
                    del world.auction_quick_win_tasks[item_index]
                
                self._save_world(group_id)
            else:
                if winner:
                    # Not enough gold, refund. But this is checked on bid.
                    pass
                # Announce failure to quick-win if needed, or just let it go to normal auction.
                if item_index in world.auction_quick_win_tasks:
                    del world.auction_quick_win_tasks[item_index]


        except asyncio.CancelledError:
            # Task was cancelled, which is normal.
            return
        except Exception as e:
            logger.error(f"Error in _process_quick_win for item {item_index}: {e}")

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
            f"【斗气】{int(player.current_qi)}/{player.required_qi} ({progress}%)\n"
            f"【称号】{player.title}\n"
            f"【金币】{int(player.gold)}\n"
            f"【生命】{player.health}/{player.max_health} {'(濒死)' if player.is_dying else ''}\n"
            f"【战力】{int(player.power)}\n"
            f"【装备】{player.zb}\n"
            f"【物品】{player.get_inventory_display()}\n"
        )

        if player.temp_boosts:
            boosts = []
            for boost, (value, expire) in player.temp_boosts.items():
                if time.time() < expire:
                    remaining = int(expire - time.time())
                    boosts.append(f"{boost}+{value}%({remaining // 60}分)")
            if boosts:
                status_msg += f"【加成】{' '.join(boosts)}\n"

        status_ok, base_time = player.can_explore()
        status_msg += (
            f"\n修炼冷却：{'就绪' if player.can_train() else '冷却中'}\n"
            f"探索冷却：{'就绪' if status_ok else '冷却中'}\n"
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
            f"【斗气】{int(player.current_qi)}/{player.required_qi} ({progress}%)\n"
            f"【称号】{player.title}\n"
            f"【金币】{int(player.gold)}\n"
            f"【生命】{player.health}/{player.max_health} {'(濒死)' if player.is_dying else ''}\n"
            f"【战力】{int(player.power)}\n"
            f"【装备】{player.zb}\n"
            f"【物品】{player.get_inventory_display()}\n"
        )

        if player.temp_boosts:
            boosts = []
            for boost, (value, expire) in player.temp_boosts.items():
                if time.time() < expire:
                    remaining = int(expire - time.time())
                    boosts.append(f"{boost}+{value}%({remaining // 60}分)")
            if boosts:
                status_msg += f"【加成】{' '.join(boosts)}\n"

        status_ok, base_time = player.can_explore()
        status_msg += (
            f"\n修炼冷却：{'就绪' if player.can_train() else '冷却中'}\n"
            f"探索冷却：{'就绪' if status_ok else '冷却中'}\n"
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
            player.health-=1
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


    @filter.command("突破_s")
    async def breakthrough_s(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return
        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
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

    @filter.command("炼丹_s", private=True)
    async def private_have_dy(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return
        args = event.message_str.strip().split()
        if len(args) < 2:
            yield event.plain_result("请指定炼丹品阶，如炼丹_s 五品！")
            return
        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]
        item_name = " ".join(args[1:])
        if int(self.extract_simple_chinese_digits(item_name)) > player.realm_index+1:
            yield event.plain_result("你的境界不能炼制该品级丹药！")
            return
        if "魔兽内丹" not in player.inventory:
            yield event.plain_result("你没有魔兽内丹！")
            return
        dy_list = PillSystem.get_pills_by_rank(item_name)
        if dy_list:  # 确保该品阶有丹药
            item = random.choice(dy_list)
            base_gl = 1.0
            base_gl = base_gl - int(self.extract_simple_chinese_digits(item_name))*0.1*0.5
            if random.random() < base_gl:
                player.inventory.remove("魔兽内丹")
                player.inventory.append(item['name'])
                player.gold = player.gold - int(self.extract_simple_chinese_digits(item_name))**2*80
                yield event.plain_result(f"你成功炼制了{item['name']}！")
            else:
                player.inventory.remove("魔兽内丹")
                yield event.plain_result(f"你炼制失败了！")
                return


    def extract_simple_chinese_digits(self,text):
        """提取简单的中文数字并转换"""
        digit_map = {'零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
                     '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'}

        result = []
        for char in text:
            if char in digit_map:
                result.append(digit_map[char])
            elif char.isdigit():  # 如果已经是阿拉伯数字
                result.append(char)
        return ''.join(result)

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
        used_pill = min(revive_pills, key=lambda x: int(self.extract_simple_chinese_digits(x["rank"])))
        player.inventory.remove(used_pill["name"])

        # 根据丹药品级决定恢复效果（使用丹药的effect_value）
        pill_grade = int(self.extract_simple_chinese_digits(used_pill["rank"][0]))

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
            revive_msg = "转世重生！完全恢复状态并保留境界"

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

        revive_pills = []
        if player.realm_index == 12:
            revive_pills.append(PillSystem.get_pill_by_name("2品回魂丹"))
            player.inventory.append("2品回魂丹")

        # 查找所有复活类丹药（使用新的丹药系统）

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

        target = next((p for p in world.players.values() if p.user_name == target_name), None) or next((p for p in world.players.values() if p.user_id == target_name), None)
        if not target:
            yield event.plain_result("找不到该玩家！")
            return
        if not target.is_dying:
            yield event.plain_result(f"{target.user_name} 并没有濒死！")
            return

        # 使用品级最低的复活丹药
        used_pill = min(revive_pills, key=lambda x: int(self.extract_simple_chinese_digits(x["rank"])))
        player.inventory.remove(used_pill["name"])

        # === 新增金币转移逻辑 ===
        gold_transfer = int(target.gold * 0.3)  # 转移30%金币
        player.gold += gold_transfer
        target.gold = max(0, target.gold - gold_transfer)

        # 根据丹药品级和效果类型决定恢复效果
        pill_grade = int(self.extract_simple_chinese_digits(used_pill["rank"][0]))

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

    @filter.command("拍卖会")
    async def auction(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        # 检查是否需要刷新拍卖会物品
        current_time = time.time()

        if current_time - world.last_auction_refresh > 7200:  # 2小时刷新一次
            # Cancel all running quick-win tasks before refreshing
            for task in world.auction_quick_win_tasks.values():
                task.cancel()
            world.auction_quick_win_tasks.clear()

            world.generate_auction_items()
            world.last_auction_refresh = current_time
            world.auction_bids = {}  # 清空竞拍记录
            world.auction_end_time = current_time + 7200  # 拍卖持续2小时
            if hasattr(world, 'auction_task'):
                world.auction_task.cancel()
            # 设置新的定时任务，在拍卖结束时发送通知
            world.auction_task = asyncio.create_task(
                self._send_auction_end_message(event, event.get_group_id(), world.auction_end_time)
            )
        player = world.players[user_id]

        if len(args) == 1:
            if not world.auction_items:
                yield event.plain_result("拍卖会暂时没有商品，请稍后再来！")
                return

            # 计算剩余时间
            remaining_time = int(world.auction_end_time - current_time)
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            seconds = remaining_time % 60

            # 显示拍卖会商品列表
            auction_list = f"=== 拍卖会 === (剩余时间: {hours:02d}:{minutes:02d}:{seconds:02d})\n"
            for i, item in enumerate(world.auction_items):
                current_bid_info = world.auction_bids.get(str(i), {})
                current_bid = current_bid_info.get('bid', item['base_price'])
                bidder_name = current_bid_info.get('bidder_name', '无人出价')

                auction_list += f"{i + 1}. 【{item['name']}】{item['description']}\n"
                auction_list += f"   当前最高价：{current_bid}金币，出价者：{bidder_name}\n"
                auction_list += f"   起拍价：{item['base_price']}金币\n"

            auction_list += "\n使用 /拍卖会 bid 序号 价格 参与竞拍"
            auction_list += "\n使用 /拍卖会 info 序号 查看物品详细信息"
            auction_list += "\n拍卖会每2小时刷新一次，结束后价高者得"

            yield event.plain_result(auction_list)
            return

        if args[1] == "bid" and len(args) > 3:
            try:
                index = int(args[2]) - 1
                bid_amount = int(args[3])

                if current_time >= world.auction_end_time:
                    yield event.plain_result("拍卖会已结束，无法出价！")
                    return

                if 0 <= index < len(world.auction_items):
                    item = world.auction_items[index]
                    current_bid = world.auction_bids.get(str(index), {}).get('bid', item['base_price'])

                    if bid_amount <= current_bid:
                        yield event.plain_result(f"你的出价必须高于当前最高价 {current_bid} 金币！")
                        return

                    if bid_amount < item['base_price']:
                        yield event.plain_result(f"出价不能低于起拍价 {item['base_price']} 金币！")
                        return

                    if player.gold < bid_amount:
                        yield event.plain_result("你的金币不足！")
                        return

                    # 记录竞拍
                    # Cancel previous quick-win task for this item
                    if index in world.auction_quick_win_tasks:
                        old_task = world.auction_quick_win_tasks.get(index)
                        if old_task:
                            old_task.cancel()

                    world.auction_bids[str(index)] = {
                        'bid': bid_amount,
                        'bidder': user_id,
                        'bidder_name': player.user_name,
                        'bid_time': current_time
                    }

                    # Start a new quick-win task
                    new_task = asyncio.create_task(self._process_quick_win(event, event.get_group_id(), index))
                    world.auction_quick_win_tasks[index] = new_task

                    # 通知所有玩家有新出价
                    yield event.plain_result(
                        f"🎉 【{player.user_name}】对 【{item['name']}】 出价 {bid_amount} 金币！\n"
                        f"📈 当前最高价：{bid_amount}金币\n"
                        f"⏰ 拍卖剩余时间：{int((world.auction_end_time - current_time) // 60)}分钟\n"
                        f"⚡️ 若30秒内无人出更高价，此物品将快速成交！"
                    )
                else:
                    yield event.plain_result("无效的商品序号！")
            except ValueError:
                yield event.plain_result("请输入正确的商品序号和价格！")
            return

        if args[1] == "info" and len(args) > 2:
            try:
                index = int(args[2]) - 1
                if 0 <= index < len(world.auction_items):
                    item = world.auction_items[index]
                    info_text = f"=== {item['name']} 详细信息 ===\n"
                    info_text += f"描述：{item['description']}\n"
                    info_text += f"品阶：{item.get('rank', '未知')}\n"
                    info_text += f"类型：{item.get('type', '未知')}\n"
                    info_text += f"起拍价：{item['base_price']}金币\n"

                    current_bid_info = world.auction_bids.get(str(index), {})
                    if current_bid_info:
                        info_text += f"当前最高价：{current_bid_info.get('bid')}金币\n"
                        info_text += f"出价者：{current_bid_info.get('bidder_name')}\n"
                    else:
                        info_text += "当前最高价：无人出价\n"

                    yield event.plain_result(info_text)
                else:
                    yield event.plain_result("无效的商品序号！")
            except ValueError:
                yield event.plain_result("请输入正确的商品序号！")
            return
        yield event.plain_result("无效的拍卖会命令！可用命令：/拍卖会, /拍卖会 bid 序号 价格, /拍卖会 info 序号")

    @filter.command("出售")
    async def sell(self, event: AstrMessageEvent):
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        args = event.message_str.strip().split()
        player = world.players[user_id]

        if len(args) < 2:
            yield event.plain_result("请指定要出售的物品。格式：/出售 物品名称 [数量]")
            return

        # 解析数量和物品名称
        quantity = 1
        item_name_parts = args[1:]
        if args[-1].isdigit():
            quantity = int(args[-1])
            item_name_parts = args[1:-1]

        item_name = " ".join(item_name_parts)

        if not item_name:
            yield event.plain_result("无效的物品名称。")
            return

        # 检查物品数量
        current_quantity = player.inventory.count(item_name)
        if current_quantity < quantity:
            yield event.plain_result(f"物品【{item_name}】数量不足，你只有 {current_quantity} 个。")
            return

        # 计算总售价并出售
        total_price = 0
        for _ in range(quantity):
            # 计算单个物品价格
            price = 0
            if item_name in CULTIVATION_BOOST:
                price = CULTIVATION_BOOST[item_name].get('value', 0) * random.uniform(0.8, 1.1)
            else:
                pill = PillSystem.get_pill_by_name(item_name)
                if pill:
                    price = pill.get('value', 0) * random.uniform(0.8, 1.2)
                else:
                    # 为其他杂项物品设置一个默认价值
                    price = random.randint(50, 200)
            
            total_price += price
            player.inventory.remove(item_name)

        player.add_gold(total_price)

        yield event.plain_result(
            f"成功出售【{item_name}】×{quantity}！\n"
            f"获得金币：{int(total_price)}"
        )
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

        if len(args) < 2:
            yield event.plain_result("请指定要出售的物品。格式：/出售_s 物品名称 [数量]")
            return

        # 解析数量和物品名称
        quantity = 1
        item_name_parts = args[1:]
        if args[-1].isdigit():
            quantity = int(args[-1])
            item_name_parts = args[1:-1]

        item_name = " ".join(item_name_parts)

        if not item_name:
            yield event.plain_result("无效的物品名称。")
            return

        # 检查物品数量
        current_quantity = player.inventory.count(item_name)
        if current_quantity < quantity:
            yield event.plain_result(f"物品【{item_name}】数量不足，你只有 {current_quantity} 个。")
            return

        # 计算总售价并出售
        total_price = 0
        for _ in range(quantity):
            # 计算单个物品价格
            price = 0
            if item_name in CULTIVATION_BOOST:
                price = CULTIVATION_BOOST[item_name].get('value', 0) * random.uniform(0.8, 1.1)
            else:
                pill = PillSystem.get_pill_by_name(item_name)
                if pill:
                    price = pill.get('value', 0) * random.uniform(0.8, 1.2)
                else:
                    # 为其他杂项物品设置一个默认价值
                    price = random.randint(50, 200)
            
            total_price += price
            player.inventory.remove(item_name)

        player.add_gold(total_price)

        yield event.plain_result(
            f"成功出售【{item_name}】×{quantity}！\n"
            f"获得金币：{int(total_price)}"
        )
    # async def private_sell(self, event: AstrMessageEvent):
    #     user_id = event.get_sender_id()
    #     if user_id not in self.player_world_map:
    #         yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
    #         return
    #     group_id = self.player_world_map[user_id]
    #     world = self._get_world(group_id)
    #     player = world.players[user_id]
    #     args = event.message_str.strip().split()
    #     item_name = " ".join(args[1:])
    #     if item_name in player.inventory:
    #         if item_name in CULTIVATION_BOOST.keys():
    #             price = CULTIVATION_BOOST[item_name]['price'] * random.uniform(0.8, 1.1)
    #         else:
    #             pill = PillSystem.get_pill_by_name(item_name)
    #             if pill:
    #                 price = pill.get('price',401)* random.uniform(0.8, 1.2)
    #             else:
    #                 price = random.randint(150, 1000)
    #         player.gold += price
    #         player.inventory.remove(item_name)
    #
    #         yield event.plain_result(
    #             f"成功出售 【{item_name}】！\n"
    #             f"获得：{price}金币"
    #         )
    #     else:
    #         yield event.plain_result("你没有这个物品！")
    #     return






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
        target = next((p for p in world.players.values() if p.user_name == target_name), None) or next(
            (p for p in world.players.values() if p.user_id == target_name), None)

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
        realm_mult = 1.3 ** (challenger.realm_index - defender.realm_index)
        att_power = challenger.power * realm_mult
        def_power = defender.power * 1.2  # 防守加成

        ratio = att_power / def_power
        ratio += random.uniform(-0.02, 0.02)  # 极小扰动

        if ratio > 1.0:
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
                logger.info(f"已加载玩家数据：{player_id}")
            logger.info(f"已加载游戏数据：{data}")
            logger.info(f"已加载玩家数据：{self.player_world_map}")

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
        # if user_id not in self.player_world_map:
        #     yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
        #     return
        # group_id = self.player_world_map[user_id]
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

            self.worlds[target_world] = GameWorld.from_dict(data)
            for player_id in data.get("players", {}):
                self.player_world_map[player_id] = target_world
            logger.info(f"已加载玩家数据：{self.player_world_map}")

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
        help_text = (
            "╔════════════════════════════════════════╗\n"
            "║          🌟 斗破苍穹·终极版 🌟          ║\n"
            "║        修炼之路·一入斗气万劫不复        ║\n"
            "╚════════════════════════════════════════╝\n\n"

            "🔥━━━━━━━━━━ 基础指令 ━━━━━━━━━━━🔥\n"
            "🔹 /dp_join - 加入游戏(群聊)\n"
            "🔹 /状态 - 查看角色状态\n"
            "🔹 /状态_s - 私聊查看状态(含群ID)\n"
            "🔹 /复活 - 濒死时使用复活丹\n\n"

            "⚡━━━━━━━━━━ 修炼系统 ━━━━━━━━━━━⚡\n"
            "🔹 /修炼 - 修炼斗气(1分钟冷却)\n"
            "🔹 /修炼_s - 私聊修炼\n"
            "🔹 /突破 - 冲击新境界(需斗气满)\n"
            "🔹 /丹药 - 查看丹药系统\n"
            "🔹 /丹药_s - 私聊查询丹药\n\n"

            "🌍━━━━━━━━━━ 探索冒险 ━━━━━━━━━━━🌍\n"
            "🔹 /探索 初级/中级/高级 - 探索世界\n"
            "🔹 /探索_s - 私聊探索\n"
            "🔹 /挑战副本 - 组队挑战副本\n"
            "🔹 /开始副本 [ID] - 开始副本战斗\n\n"

            "⚔━━━━━━━━━━ 战斗系统 ━━━━━━━━━━━⚔\n"
            "🔹 /对战 @玩家 - 发起对战\n"
            "🔹 /接受挑战 - 接受对战请求\n"
            "🔹 /救助 @玩家 - 救助濒死玩家\n"
            "🔹 /挑战至高主宰 - 混沌主宰专属挑战\n\n"

            "💰━━━━━━━━━━ 经济系统 ━━━━━━━━━━━💰\n"
            "🔹 /商店 - 交易市场\n"
            "🔹 /出售 - 出售物品\n"
            "🔹 /出售_s - 私聊出售\n"
            "🔹 /拍卖会 - 参与珍品拍卖\n"
            "🔹 /斗破彩 - 斗气彩票系统\n\n"
            
            "💱━━━━━━━━━━ 交易系统 ━━━━━━━━━━━━💱\n"
            "🔹🔹 /交易 @玩家 物品 金额 - 发起交易\n"
            "🔹🔹 /接受交易 交易号 - 接受交易请求\n"
            "🔹🔹 /拒绝交易 交易号 - 拒绝交易请求\n"

            "🔮━━━━━━━━━━ 特殊系统 ━━━━━━━━━━━🔮\n"
            "🔹 /炼丹_s [品阶] - 炼制丹药(需内丹)\n"
            "🔹 /dp_world - 查看世界动态\n"
            "🔹 /dp_save - 保存游戏数据(管理员)\n"
            "🔹 /dp_load - 加载游戏数据(管理员)\n\n"
            
            "🎯━━━━━━━━━━ 帮助 ━━━━━━━━━━━🎯\n"
            " 输入 更新公告 查看最新更新内容\n"
            " 输入 dp_help 查看帮助\n"

            "📜━━━━━━━━━━ 游戏说明 ━━━━━━━━━━━📜\n"
            "• 境界体系: 斗之气→斗者→...→混沌主宰\n"
            "• 每个境界10星,满星后可突破\n"
            "• 濒死状态需5分钟内复活\n"
            "• 私聊指令需先在群聊绑定\n"
            "• 所有冷却在群聊与私聊间共享\n\n"

            "🎯━━━━━━━━━━ 新增内容 ━━━━━━━━━━━🎯\n"
            " 输入 更新公告 查看最新更新内容\n"
            "💡 提示: 输入具体指令查看详细用法\n"
            "✨ 愿你一掌碎星河，成就斗帝之路！"
        )

        yield event.plain_result(help_text)

    @filter.command("更新公告", private=True)
    async def show_changelog(self, event: AstrMessageEvent):
        changelog_text = (
            "╔════════════════════════════════════════╗\n"
            "║        📢 斗破苍穹·版本更新日志 📢       ║\n"
            "║        最近更新：2025年9月25日          ║\n"
            "╚════════════════════════════════════════╝\n\n"

            "🆕━━━━━━━━━━ 新增内容 ━━━━━━━━━━━🆕\n"
            "• 🎰 **斗破彩定时开奖**：每2小时自动开奖一次，无需手动触发！\n"
            "• 📜 **全新功法体系上线**：修炼效率飞跃提升，共9阶功法：\n"
            "• 📜 **自由交易系统上线**: 新增自由交易系统"
            "   └ 黄阶 → 玄阶 → 地阶 → 天阶 → 神阶 → 圣阶 → 仙阶 → 帝阶 → 无上功法\n"
            "   └ 功法可大幅提升修炼收益（最高20倍！）\n"
            "   └ 获取途径：**高级副本掉落** 或 **拍卖会竞拍**\n\n"
            

            "💰━━━━━━━━━━ 功法详情（节选）━━━━━━━━━💰\n"
            "• 黄阶功法：+10% 修炼效率｜售价 750\n"
            "• 地阶功法：+80% 修炼效率｜售价 7,500\n"
            "• 天阶功法：+180% 修炼效率｜售价 225,500\n"
            "• 无上功法：+2000% 修炼效率｜售价 900,000,000\n"
            "（完整属性可在游戏内通过 /商店 或 拍卖会 查看）\n\n"

            "✨━━━━━━━━━━ 系统优化 ━━━━━━━━━━━✨\n"
            "• 自动化斗破彩流程，提升玩家参与体验\n"
            "• 功法系统与修炼、突破深度联动，策略性更强\n\n"

            "🔮 下版本预告：宗门创建 & 自由交易！\n"
            "💡 提示：输入 /dp_help 查看全部指令，/商店 查看功法详情"
        )
        yield event.plain_result(changelog_text)

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

    @filter.command("斗破彩")
    async def lottery(self, event: AstrMessageEvent):
        """斗气彩彩票系统"""
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return
        player = world.players[user_id]

        current_time = time.time()
        logger.info(f"剩余时间：{current_time}")
        if not hasattr(world, 'lottery_task'):
            world.last_lottery_draw = current_time
            world.lottery_end_time = current_time + 7200  # 2小时后开奖
            world.lottery_task = asyncio.create_task(
                self._send_lottery_end_message(event, event.get_group_id(), world.lottery_end_time)
            )

        if len(args) == 1:
            # 显示彩票信息（修改剩余时间计算方式）
            remaining_time = max(0, int(world.lottery_end_time - current_time))
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)

            info = (
                "=== 斗破彩彩票 ===\n"
                f"当前奖池：{world.lottery_pool}金币\n"
                f"下次开奖：{hours}小时{minutes}分钟后\n"
                "玩法说明：\n"
                "1. 从1-35选5个主号码，1-12选2个特别号码\n"
                "2. 每注100金币，奖金来自奖池\n"
                "3. 每2小时开奖一次\n"
                "4. 中奖规则：\n"
                "   一等奖：5+2（40%奖池）\n"
                "   二等奖：5+1（25%奖池）\n"
                "   三等奖：5+0（15%奖池）\n"
                "   四等奖：4+2（8%奖池）\n"
                "   五等奖：4+1（5%奖池）\n"
                "   六等奖：3+2（3%奖池）\n"
                "   七等奖：4+0（2%奖池）\n"
                "   八等奖：3+1或2+2（1.5%奖池）\n"
                "   九等奖：3+0或1+2或0+2（0.5%奖池）\n"
                "\n使用命令：\n"
                "/斗破彩 buy - 随机购买一注\n"
                "/斗破彩 buy [数量] - 随机购买多注\n"
                "/斗破彩 buy 1 2 3 4 5 6 7 - 自选号码\n"
                "/斗破彩 my - 查看我的彩票\n"
                "/斗破彩 history - 查看历史开奖\n"
            )
            yield event.plain_result(info)
            return

        if args[1] == "buy":
            # 辅助函数：尝试从字符串中提取整数（支持 [123] 这样的格式）
            def try_extract_number(s):
                try:
                    # 去除首尾可能的方括号和其他空白字符
                    cleaned = s.strip().lstrip('[').rstrip(']')
                    if cleaned.isdigit():
                        return int(cleaned)
                    else:
                        return None
                except:
                    return None
            # 情况1：购买多注（支持 /buy 100 或 /buy [100]）
            if len(args) >= 3:
                # 尝试解析第二项是否为数量
                count_candidate = try_extract_number(args[2])
                if count_candidate is not None:
                    count = count_candidate
                    if count <= 0:
                        yield event.plain_result("购买数量必须大于0！")
                        return

                    total_cost = count * 100
                    if not player.deduct_gold(total_cost):
                        yield event.plain_result(f"金币不足，购买{count}注需要{total_cost}金币！")
                        return

                    success_count = 0
                    for _ in range(count):
                        success, msg = world.buy_lottery_ticket(user_id)
                        if success:
                            success_count += 1

                    if success_count > 0:
                        self._save_world(event.get_group_id())
                    yield event.plain_result(f"成功购买{success_count}注彩票，花费{success_count * 100}金币")
                    return

                # 如果不是数量，检查是否为自选号码（至少7个数字）
                elif len(args) >= 9:  # buy + 7个号码 = 至少9个参数
                    try:
                        numbers = [int(num) for num in args[2:9]]
                        # 验证是否是7个有效数字（假设彩票是7个号码）
                        if len(numbers) != 7 or any(n < 1 or n > 35 for n in numbers):  # 示例范围1-35
                            yield event.plain_result("请提供7个有效的号码（例如1-35）！")
                            return
                        if not player.deduct_gold(100):
                            yield event.plain_result("金币不足，每注需要100金币！")
                            return
                        success, msg = world.buy_lottery_ticket(user_id, numbers)
                        if success:
                            self._save_world(event.get_group_id())
                        yield event.plain_result(msg)
                        return
                    except ValueError:
                        yield event.plain_result("请输入有效的数字！")
                        return
                else:
                    yield event.plain_result("参数格式错误，请检查输入！")
                    return
            # 情况2：购买单注（/buy）
            elif len(args) == 2:
                if not player.deduct_gold(100):
                    yield event.plain_result("金币不足，每注需要100金币！")
                    return
                success, msg = world.buy_lottery_ticket(user_id)
                if success:
                    self._save_world(event.get_group_id())
                yield event.plain_result(msg)
                return
            else:
                yield event.plain_result("参数不足或格式错误！用法：/斗破彩 buy [数量] 或 /斗破彩 buy [号码1-7]")
                return

        if args[1] == "my":
            if user_id not in world.lottery_tickets or not world.lottery_tickets[user_id]:
                yield event.plain_result("你还没有购买任何彩票！")
                return

            tickets = [
                f"{i + 1}. 主:{ticket[:5]} 特:{ticket[5:]}"
                for i, ticket in enumerate(world.lottery_tickets[user_id])
            ]
            yield event.plain_result(
                f"=== 你的彩票 ===\n" +
                "\n".join(tickets) +
                f"\n\n共{len(tickets)}注，总价值{len(tickets) * 100}金币"
            )
            return
        if args[1] == "history":
            if not world.lottery_history:
                yield event.plain_result("暂无开奖历史！")
                return
            history = []
            for i, record in enumerate(world.lottery_history[-5:]):  # 显示最近5期
                draw_time = time.strftime("%m-%d %H:%M", time.localtime(record["draw_time"]))
                numbers = f"主:{record['numbers'][:5]} 特:{record['numbers'][5:]}"
                winners = " ".join([f"{k}:{v}" for k, v in record["winners"].items() if v > 0])
                history.append(f"{i + 1}. {draw_time} {numbers} 中奖: {winners}")

            yield event.plain_result(
                "=== 最近5期开奖 ===\n" +
                "\n".join(history)
            )
            return

        yield event.plain_result("无效的命令，请输入 /斗气彩 查看帮助")

    @filter.command("丹药")
    async def query_pill(self, event: AstrMessageEvent):
        """
        丹药查询系统（群聊版）
        支持：
            /丹药                 -> 显示帮助和第1页丹药
            /丹药 2               -> 查看第2页
            /丹药 聚气             -> 搜索含“聚气”的丹药
            /丹药 8品混沌丹         -> 查看具体丹药详情
            /丹药 分类 修炼         -> 按类型筛选（可选扩展）
        """
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        # 玩家必须加入游戏
        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]

        # 无参数：显示帮助 + 第1页丹药
        if len(args) == 1:
            result = PillSystem.handle_query_command(query="", page_str="1")
            yield event.plain_result(result)
            return

        # 第二个参数为页码（如 /斗破丹 2）
        if len(args) == 2 and args[1].isdigit():
            page = args[1]
            result = PillSystem.handle_query_command(query="", page_str=page)
            yield event.plain_result(result)
            return

        # 第二个参数为“分类”，第三个为类型（如 /斗破丹 分类 修炼）
        if len(args) >= 3 and args[1] == "分类":
            pill_type = args[2]
            valid_types = ["修炼", "突破", "战斗", "恢复", "cultivation", "breakthrough", "battle", "heal"]
            if pill_type not in valid_types:
                yield event.plain_result(f"不支持的丹药类型！支持：{'、'.join(valid_types)}")
                return
            result = PillSystem.handle_query_command(query=pill_type, page_str="")
            yield event.plain_result(result)
            return

        # 否则视为搜索或精确查询
        search_query = " ".join(args[1:])  # 允许多词搜索
        result = PillSystem.handle_query_command(query=search_query, page_str="")

        # 如果返回的是“未找到”，可以提示用户尝试其他关键词
        if "未找到" in result or "没有匹配" in result:
            help_msg = (
                f"{result}\n\n"
                "你可以尝试：\n"
                "• /丹药 2  查看第2页\n"
                "• /丹药 聚气  搜索关键词\n"
                "• /丹药 分类 修炼  查看修炼类丹药"
            )
            yield event.plain_result(help_msg)
        else:
            yield event.plain_result(result)

    @filter.command("丹药_s", private=True)
    async def private_query_pill(self, event: AstrMessageEvent):
        """
        丹药查询系统（私聊版）
        功能与群聊一致，但需先加入游戏
        """
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        # 检查是否已加入任何群的世界
        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return

        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)

        if user_id not in world.players:
            yield event.plain_result("你在该群的世界中不存在，请重新加入。")
            return

        player = world.players[user_id]

        # 无参数：第1页
        if len(args) == 1:
            result = PillSystem.handle_query_command(query="", page_str="1")
            yield event.plain_result(result)
            return

        # 页码查询
        if len(args) == 2 and args[1].isdigit():
            result = PillSystem.handle_query_command(query="", page_str=args[1])
            yield event.plain_result(result)
            return

        # 分类查询（可选）
        if len(args) >= 3 and args[1] == "分类":
            pill_type = args[2]
            valid_types = ["修炼", "突破", "战斗", "恢复", "cultivation", "breakthrough", "battle", "heal"]
            if pill_type not in valid_types:
                yield event.plain_result(f"不支持的丹药类型！支持：{'、'.join(valid_types)}")
                return
            result = PillSystem.handle_query_command(query=pill_type, page_str="")
            yield event.plain_result(result)
            return

        # 搜索
        search_query = " ".join(args[1:])
        result = PillSystem.handle_query_command(query=search_query, page_str="")

        if "未找到" in result:
            help_msg = (
                f"{result}\n\n"
                "你可以尝试：\n"
                "• /丹药_s 2  查看第2页\n"
                "• /丹药_s 聚气  搜索关键词\n"
                "• /丹药_s 分类 修炼  查看修炼类丹药"
            )
            yield event.plain_result(help_msg)
        else:
            yield event.plain_result(result)

    @filter.command("挑战至高主宰", private=True)
    async def challenge_supreme_ruler(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()

        # 1. 检查玩家是否已加入游戏
        if user_id not in self.player_world_map:
            yield event.plain_result("你还没有加入任何游戏，请先在群聊中使用 /dp_join 加入游戏！")
            return

        group_id = self.player_world_map[user_id]
        world = self._get_world(group_id)
        player = world.players[user_id]

        # 2. 检查是否为混沌主宰
        if player.realm_index != 13:  # 混沌主宰的境界索引为13
            yield event.plain_result("你必须先达到混沌主宰境界才能挑战至高主宰！")
            return

        # 4. 检查当前是否有至高主宰
        if world.supreme_ruler is None:
            # 没有现任至高主宰，直接与系统设定的100亿战力对战
            supreme_power = 10000000000  # 100亿战力
            player_power = player.power
            # 战斗结果计算（加入随机因素）
            win_chance = min(0.95, player_power / (player_power + supreme_power))
            if random.random() < win_chance:
                # 挑战成功
                world.supreme_ruler = player.user_id
                player.is_supreme_ruler = True
                # 战力提升奖励
                power_bonus = int(supreme_power * 0.1)  # 获得10%至高主宰战力
                player.apply_temp_boost("supreme_ruler", 0.5, 86400)  # 50%加成，持续24小时
                yield event.plain_result(
                    f"★ 惊天动地！你成功击败了世界意志：混沌至尊！ ★\n"
                    f"【{player.user_name}】正式成为新的至高主宰！\n"
                    f"获得天道战力加成：+30%（永久）\n"
                    f"当前战力：{player.power}"
                )
            else:
                # 挑战失败惩罚
                damage = int(player.max_health * 0.3)  # 损失30%生命值
                player.take_damage(damage)
                dl = random.randint(5, 10)
                if player.level - dl <= 0:
                    player.realm_index = player.realm_index - 1
                    player.level = REALMS[player.realm_index]["level"] - 1
                yield event.plain_result(
                    f"★ 挑战失败！至高主宰的威压让你难以承受！ ★\n"
                    f"你损失了{damage}点生命值\n"
                    f"受到天道反噬，掉落{dl}等级"
                    f"当前生命：{player.health}/{player.max_health}\n"
                    f"不要气馁，提升实力后可以再次挑战！"
                )
        else:
            # 5. 挑战现任至高主宰玩家
            if world.supreme_ruler == player.user_id:
                yield event.plain_result("你已经是至高主宰了，无需挑战自己！")
                return

            target_player = world.players.get(world.supreme_ruler)
            if not target_player:
                yield event.plain_result("至高主宰玩家数据异常，请联系管理员")
                return

            # 战斗逻辑（基于双方战力）
            attacker_power = player.power
            defender_power = target_player.power
            # 计算胜率（加入随机因素）
            base_ratio = attacker_power / (defender_power * 1.2)
            random_factor = random.uniform(-0.1, 0.1)  # -5% ~ +5%
            final_ratio = base_ratio + random_factor

            if final_ratio > 1:
                # 挑战成功
                old_ruler_name = target_player.user_name
                target_player.is_supreme_ruler = False

                # 转移至高主宰称号
                world.supreme_ruler = player.user_id
                player.is_supreme_ruler = True

                # 战力提升奖励
                power_bonus = int(defender_power * 0.1)  # 获得前任10%战力
                player.apply_temp_boost("supreme_victory", 0.3, 86400)  # 30%加成，持续24小时

                # 失败者惩罚
                target_damage = int(target_player.max_health * 0.2)  # 损失20%生命值
                target_player.take_damage(target_damage)

                yield event.plain_result(
                    f"★ 惊天一战！{player.user_name}击败了{old_ruler_name}！ ★\n"
                    f"【{player.user_name}】成为新的至高主宰！\n"
                    f"获得战力加成：+30%（持续24小时）\n"
                    f"前任至高主宰损失{target_damage}点生命值\n"
                    f"当前战力对比：\n"
                    f"挑战者：{attacker_power:,}\n"
                    f"前任主宰：{defender_power:,}"
                )
            else:
                # 挑战失败惩罚
                damage = int(player.max_health * 0.3)  # 损失30%生命值
                player.take_damage(damage)

                yield event.plain_result(
                    f"★ 挑战失败！{target_player.user_name}的威压让你难以承受！ ★\n"
                    f"你损失了{damage}点生命值\n"
                    f"当前生命：{player.health}/{player.max_health}\n"
                    f"战力对比：\n"
                    f"你：{attacker_power:,}\n"
                    f"至高主宰：{defender_power:,}\n"
                    f"不要气馁，提升实力后可以再次挑战！"
                )

        # 保存游戏状态
        self._save_world(group_id)

    @filter.command("挑战副本")
    async def create_dungeon(self, event: AstrMessageEvent):
        """创建副本队伍"""
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        if len(args) < 2:
            yield event.plain_result(
                "请指定副本等级和队友QQ号！\n"
                "可用副本等级: 初级、中级、高级、顶级、混沌初境、混沌秘境、混沌核心\n"
                "示例: /挑战副本 高级 123456 123457 123458"
            )
            return

        level = args[1]
        teammate_qqs = args[2:]
        all_player_ids = [user_id] + teammate_qqs
        # all_player_ids = list(set(all_player_ids))
        seen = set()
        deduped = []
        for pid in [user_id] + teammate_qqs:
            if pid not in seen:
                seen.add(pid)
                deduped.append(pid)
        all_player_ids = deduped

        result = self.dungeon_manager.create_dungeon(world, level, all_player_ids)
        yield event.plain_result(result)

    @filter.command("接受副本")
    async def confirm_dungeon(self, event: AstrMessageEvent):
        """确认准备就绪"""
        args = event.message_str.strip().split()
        if len(args) < 2:
            yield event.plain_result("请指定要接受的副本ID！")
            return

        dungeon_id = args[1]
        user_id = event.get_sender_id()
        result = self.dungeon_manager.confirm_dungeon(dungeon_id, user_id)
        yield event.plain_result(result)

    @filter.command("开始副本")
    async def start_dungeon(self, event: AstrMessageEvent):
        """开始副本挑战"""
        args = event.message_str.strip().split()
        if len(args) < 2:
            yield event.plain_result("请指定要开始的副本ID！")
            return

        dungeon_id = args[1]
        user_id = event.get_sender_id()
        success, result = self.dungeon_manager.start_dungeon(dungeon_id, user_id)

        if success:
            # 保存世界状态
            self._save_world(event.get_group_id())
        yield event.plain_result(result)




    async def _send_auction_end_message(self,event: AstrMessageEvent, group_id: str, end_time: float):
        try:
            # 计算需要等待的时间
            wait_time = end_time - time.time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            # 获取当前世界状态
            world = self._get_world(group_id)
            # 检查拍卖是否真的结束了（防止提前刷新）
            if time.time() < world.auction_end_time:
                return

            # At the end of the auction, cancel all pending quick-win tasks.
            for task in world.auction_quick_win_tasks.values():
                task.cancel()
            world.auction_quick_win_tasks.clear()

            # 处理拍卖结果
            result_message = "🎉 拍卖会已结束！以下是竞拍结果：\n"
            any_success = False
            for index, item in enumerate(world.auction_items):
                if item is None:  # Item might have been sold via quick-win
                    continue
                bid_info = world.auction_bids.get(str(index))
                if bid_info:
                    bidder_id = bid_info['bidder']
                    bid_amount = bid_info['bid']

                    # 检查玩家是否还在游戏中
                    if bidder_id in world.players:
                        player = world.players[bidder_id]
                        if player.gold >= bid_amount:
                            # 扣除金币并给予物品
                            player.gold -= bid_amount
                            player.add_item(item['name'])
                            result_message += (
                                f"【{item['name']}】由 {bid_info['bidder_name']} "
                                f"以 {bid_amount}金币 成功拍得！\n"
                            )
                            any_success = True
                            continue

                # 如果没有人成功竞拍
                result_message += f"【{item['name']}】流拍，无人获得。\n"

            if not any_success:
               logger.info("本轮没有玩家成功竞拍")
            else:
                # 发送结果消息
                message_chain = MessageChain().message(result_message)
                await self.context.send_message(event.unified_msg_origin, message_chain)
            # 立即刷新拍卖会
            world.generate_auction_items()
            world.last_auction_refresh = time.time()
            world.auction_bids = {}
            world.auction_end_time = world.last_auction_refresh + 3600
            # 设置新的定时任务
            world.auction_task = asyncio.create_task(
                self._send_auction_end_message(event, group_id, world.auction_end_time)
            )
        except Exception as e:
            logger.error(f"拍卖会结束消息发送失败: {e}")

    async def _send_lottery_end_message(self, event: AstrMessageEvent, group_id: str, end_time: float):
        try:
            # 计算需要等待的时间
            wait_time = end_time - time.time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            # 获取当前世界状态
            world = self._get_world(group_id)
            # 检查彩票是否真的该开奖了（防止提前刷新）
            if time.time() < world.lottery_end_time:
                return
            # 执行开奖逻辑
            if world.lottery_tickets:
                result = world.draw_lottery()
                message = world._send_lottery_result(event, result)
                # 发送开奖结果
                message_chain = MessageChain().message(message)
                await self.context.send_message(event.unified_msg_origin, message_chain)
            # 重置开奖时间
            world.last_lottery_draw = time.time()
            world.lottery_end_time = world.last_lottery_draw + 7200
            # 设置新的定时任务
            world.lottery_task = asyncio.create_task(
                self._send_lottery_end_message(event, group_id, world.lottery_end_time)
            )
        except Exception as e:
            logger.error(f"彩票开奖消息发送失败: {e}")

    @filter.command("交易")
    async def trade_item(self, event: AstrMessageEvent):
        """发起交易请求"""
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return
        player = world.players[user_id]
        # 检查参数格式
        if len(args) < 4:
            yield event.plain_result(
                "交易命令格式：/交易 @对方玩家 物品名称 金额\n"
                "示例：/交易 @张三 1品聚气丹 100"
            )
            return
        # 解析参数
        target_name = args[1].strip("@")
        item_name = " ".join(args[2:-1])
        try:
            amount = int(args[-1])
        except ValueError:
            yield event.plain_result("金额必须是整数！")
            return
        # 检查金额有效性
        if amount <= 0:
            yield event.plain_result("交易金额必须大于0！")
            return
        # 检查物品是否存在
        if item_name not in player.inventory:
            yield event.plain_result(f"你没有【{item_name}】这个物品！")
            return
        # 查找目标玩家
        target = None
        for p in world.players.values():
            if p.user_name == target_name or p.user_id == target_name:
                target = p
                break
        if not target:
            yield event.plain_result(f"找不到玩家【{target_name}】！")
            return

        if target.user_id == user_id:
            yield event.plain_result("你不能和自己交易！")
            return

        # 检查目标玩家是否在线
        if target.is_dying:
            yield event.plain_result(f"{target.user_name} 处于濒死状态，无法交易！")
            return

        # 生成交易ID
        trade_id = f"trade-{world.next_trade_id}"
        world.next_trade_id += 1

        # 创建交易请求
        trade_data = {
            "trade_id": trade_id,
            "sender_id": user_id,
            "sender_name": player.user_name,
            "target_id": target.user_id,
            "target_name": target.user_name,
            "item_name": item_name,
            "amount": amount,
            "create_time": time.time(),
            "status": "pending"
        }
        world.trade_requests[trade_id] = trade_data

        yield event.plain_result(
            f"✅ 交易请求已发送！\n"
            f"📦 物品：{item_name}\n"
            f"💰 金额：{amount}金币\n"
            f"👤 对方：{target.user_name}\n"
            f"🔢 交易号：{trade_id}\n"
            f"请让对方使用以下命令处理：\n"
            f"• /接受交易 {trade_id} - 接受交易\n"
            f"• /拒绝交易 {trade_id} - 拒绝交易"
        )

    @filter.command("接受交易")
    async def accept_trade(self, event: AstrMessageEvent):
        """接受交易请求"""
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        if len(args) < 2:
            yield event.plain_result("请指定交易号！格式：/接受交易 交易号")
            return

        trade_id = args[1]

        # 查找交易请求
        if trade_id not in world.trade_requests:
            yield event.plain_result("交易号无效或交易已过期！")
            return

        trade_data = world.trade_requests[trade_id]
        # 检查交易是否指向当前玩家
        if trade_data["target_id"] != user_id:
            yield event.plain_result("这个交易不是发给你的！")
            return
        target_player = world.players[user_id]
        requester_id = trade_data["sender_id"]
        requester = world.players[requester_id]
        item_name = trade_data["item_name"]
        amount = trade_data["amount"]
        # 检查请求者是否还有该物品
        if item_name not in requester.inventory:
            del world.trade_requests[trade_id]
            yield event.plain_result(f"{requester.user_name} 已经没有【{item_name}】这个物品了！")
            return
        # 检查目标玩家是否有足够的金币
        if target_player.gold < amount:
            del world.trade_requests[trade_id]
            yield event.plain_result(f"你的金币不足！需要{amount}金币，你只有{target_player.gold}金币")
            return
        # 检查目标玩家背包是否已满
        if len(target_player.inventory) >= 200 + sum(10 for item in target_player.inventory if "空间戒指" in item):
            del world.trade_requests[trade_id]
            yield event.plain_result("你的背包已满，无法接收物品！")
            return
        # 执行交易
        try:
            # 从请求者移除物品
            requester.inventory.remove(item_name)
            # 向目标玩家添加物品
            target_player.inventory.append(item_name)
            # 金币转移
            target_player.gold -= amount
            requester.gold += amount
            # 移除交易请求
            del world.trade_requests[trade_id]
            yield event.plain_result(
                f"✅ 交易成功完成！\n"
                f"🔢 交易号：{trade_id}\n"
                f"📦 {requester.user_name} → {target_player.user_name}：{item_name}\n"
                f"💰 {target_player.user_name} → {requester.user_name}：{amount}金币\n"
                f"🏦 {requester.user_name} 现有金币：{requester.gold}\n"
                f"🏦 {target_player.user_name} 现有金币：{target_player.gold}"
            )
        except Exception as e:
            logger.error(f"交易执行失败: {e}")
            yield event.plain_result("交易执行失败，请稍后重试！")

    @filter.command("拒绝交易")
    async def reject_trade(self, event: AstrMessageEvent):
        """拒绝交易请求"""
        world = self._get_world(event.get_group_id())
        user_id = event.get_sender_id()
        args = event.message_str.strip().split()

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        if len(args) < 2:
            yield event.plain_result("请指定交易号！格式：/拒绝交易 交易号")
            return

        trade_id = args[1]

        # 查找交易请求
        if trade_id not in world.trade_requests:
            yield event.plain_result("交易号无效或交易已过期！")
            return

        trade_data = world.trade_requests[trade_id]

        # 检查交易是否指向当前玩家
        if trade_data["target_id"] != user_id:
            yield event.plain_result("这个交易不是发给你的！")
            return

        # 获取请求者信息
        requester_name = trade_data["sender_name"]
        item_name = trade_data["item_name"]
        amount = trade_data["amount"]

        # 移除交易请求
        del world.trade_requests[trade_id]

        yield event.plain_result(
            f"❌ 已拒绝交易请求！\n"
            f"🔢 交易号：{trade_id}\n"
            f"📦 物品：{item_name}\n"
            f"💰 金额：{amount}金币\n"
            f"👤 请求者：{requester_name}\n"
            f"交易已取消"
        )

    async def _auto_train_loop(self, event: AstrMessageEvent, group_id: str, user_id: str):
        """后台自动修炼循环"""
        world = self._get_world(group_id)
        player = world.players.get(user_id)

        try:
            while True:
                player = self._get_world(group_id).players.get(user_id)
                if not player or not player.is_auto_training:
                    break

                success, msg = player.train(continuous=True)

                if not success:
                    await self.context.send_private_message(user_id, f"自动修炼已停止：{msg}")
                    break

                if "突破" in msg or "晋升" in msg:
                    await self.context.send_private_message(user_id, f"自动修炼通知：{msg}")

                await asyncio.sleep(player.cooldowns["train"])
        finally:
            if player:
                player.is_auto_training = False
            if user_id in self.auto_train_tasks:
                del self.auto_train_tasks[user_id]
            self._save_world(group_id)

    @filter.command("自动修炼")
    async def auto_train(self, event: AstrMessageEvent):
        """开启或关闭自动修炼"""
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        world = self._get_world(group_id)

        if user_id not in world.players:
            yield event.plain_result("你还没有加入游戏，请输入 /dp_join 加入游戏！")
            return

        player = world.players[user_id]

        if user_id in self.auto_train_tasks:
            # 停止自动修炼
            self.auto_train_tasks[user_id].cancel()
            player.is_auto_training = False
            del self.auto_train_tasks[user_id]
            self._save_world(group_id)
            yield event.plain_result("自动修炼已停止。")
        else:
            # 开启自动修炼
            status_ok, msg = player.check_status()
            if not status_ok:
                yield event.plain_result(f"无法开启自动修炼：{msg}")
                return

            player.is_auto_training = True
            task = asyncio.create_task(self._auto_train_loop(event, group_id, user_id))
            self.auto_train_tasks[user_id] = task
            self._save_world(group_id)
            yield event.plain_result("自动修炼已开启！系统将在后台为您持续修炼。当遇到濒死、需要突破等情况时将自动停止。")











