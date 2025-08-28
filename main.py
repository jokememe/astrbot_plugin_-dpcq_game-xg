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
from dy import *


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
