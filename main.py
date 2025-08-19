from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import random
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any

# ================= 游戏常量设置 =================
CULTIVATION_LEVELS = [
    "斗之气一段", "斗之气二段", "斗之气三段", "斗之气四段", "斗之气五段",
    "斗之气六段", "斗之气七段", "斗之气八段", "斗之气九段",
    "斗者", "斗师", "大斗师", "斗灵", "斗王",
    "斗皇", "斗宗", "斗尊", "斗圣", "斗帝"
]


# ================= 游戏核心类 =================
class Player:
    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
        self.level = 0  # 初始为斗之气一段
        self.qi = 100  # 当前斗气值
        self.max_qi = 100  # 最大斗气值
        self.exp = 0  # 经验值
        self.talent = random.randint(80, 120)  # 修炼天赋(80-120%)
        self.sect: Optional[str] = None  # 所属门派
        self.techniques: Dict[str, Dict] = {}  # 掌握的功法
        self.items: Dict[str, int] = {}  # 物品
        self.money = 50  # 初始灵石
        self.last_cultivate_time: float = 0
        self.last_event_time: float = 0
        self.status: Dict[str, Any] = {}  # 状态效果
        self.meridian_progress = 0  # 经脉修炼进度
        self.combat_log = []  # 战斗记录
        self.achievements = set()  # 成就
        self.treasure_map: Optional[str] = None  # 藏宝图
        self.daily_quest_completed = 0  # 每日任务完成数量

    def next_level_exp(self) -> int:
        """升级所需经验"""
        return (self.level + 1) * 10

    def can_level_up(self) -> bool:
        """检查是否可以升级"""
        return self.exp >= self.next_level_exp() and self.level < len(CULTIVATION_LEVELS) - 1

    def level_up(self):
        """升级"""
        old_level = self.level
        self.level += 1
        self.exp = 0
        self.max_qi = 100 + (self.level * 20)
        self.qi = self.max_qi

        # 大境界突破加成
        level_name = CULTIVATION_LEVELS[self.level]
        if level_name in ["斗者", "斗师", "大斗师", "斗灵", "斗王", "斗皇", "斗宗", "斗尊", "斗圣", "斗帝"]:
            self.max_qi += 50 * (self.level // 10 + 1)
            self.qi = self.max_qi


class NPC:
    """NPC类，代表游戏中的非玩家角色"""

    def __init__(self, name: str, role: str, background: str, location: str):
        self.name = name
        self.role = role
        self.background = background
        self.location = location
        self.dialogue_history = []
        self.quests = []  # NPC提供的任务
        self.items_for_sale = []  # NPC出售的物品


class Sect:
    def __init__(self, name: str, desc: str):
        self.name = name
        self.desc = desc
        self.members: Dict[str, str] = {}  # {user_id: 职位}
        self.leader: Optional[str] = None  # 掌门ID
        self.funds = 0  # 门派资金
        self.techniques: Dict[str, Dict] = {}  # 门派功法
        self.level = 1  # 门派等级
        self.storage: Dict[str, int] = {}  # 门派仓库
        self.quests: List[Dict] = []  # 门派任务
        self.created_time = datetime.now()


# ================= 游戏核心插件 =================
@register("doupo_game", "author", "斗破苍穹文字游戏", "4.0.0", "repo url")
class DouPoGame(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.players: Dict[str, Player] = {}
        self.sects: Dict[str, Sect] = {}
        self.npcs: Dict[str, NPC] = {}  # NPC字典
        self.world_setting: str = ""  # 世界观描述
        self.last_reset_time = time.time()

        # 启动后台任务
        self.context.register_task(self._daily_reset_task())
        self.context.register_task(self._world_init_task())

    async def _world_init_task(self):
        """世界初始化任务"""
        # 生成世界观设定
        self.world_setting = await self.generate_world_setting()
        logger.info(f"世界观设定生成: {self.world_setting[:50]}...")

        # 生成初始NPC
        await self.generate_initial_npcs()
        logger.info(f"生成 {len(self.npcs)} 个初始NPC")

        # 生成初始门派
        await self.generate_initial_sects()
        logger.info(f"生成 {len(self.sects)} 个初始门派")

    async def _daily_reset_task(self):
        """每日重置任务"""
        while True:
            now = time.time()
            # 计算下一个凌晨4点
            today = datetime.now().date()
            next_reset = datetime.combine(today + timedelta(days=1), datetime.min.time()) + timedelta(hours=4)
            wait_seconds = (next_reset - datetime.now()).total_seconds()

            await asyncio.sleep(wait_seconds)

            # 执行每日重置
            self._daily_reset()
            logger.info("完成每日重置")

    def _daily_reset(self):
        """每日重置逻辑"""
        # 重置玩家状态
        for player in self.players.values():
            player.daily_quest_completed = 0
            player.last_cultivate_time = 0
            player.last_event_time = 0
            player.money += 10  # 每日登录奖励

    def _get_player(self, event: AstrMessageEvent) -> Player:
        """获取玩家对象，如果不存在则创建"""
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        if user_id not in self.players:
            self.players[user_id] = Player(user_id, user_name)
            logger.info(f"新玩家注册: {user_name}({user_id})")

        return self.players[user_id]

    # ============== LLM世界生成功能 ==============
    async def generate_world_setting(self) -> str:
        """使用LLM生成世界观设定"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            "你是一个斗破苍穹风格的游戏世界构建者。请生成一段详细的游戏世界观背景设定（300-500字），"
            "包括世界的基本结构、力量体系、主要势力和历史背景。"
            "风格要符合斗破苍穹的玄幻修真世界观。"
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            return llm_response.completion_text
        else:
            return "斗气大陆，一个以斗气为尊的世界。强者可移山填海，弱者只能任人宰割。"

    async def generate_initial_npcs(self):
        """使用LLM生成初始NPC"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            "你是一个斗破苍穹风格的游戏世界构建者。请生成5个初始NPC，包括他们的名字、角色、背景故事和所在位置。"
            "以JSON格式返回，格式如下："
            '{"npcs": [{"name": "药老", "role": "灵魂体炼药师", "background": "曾经是斗尊强者，现在是玩家的老师", "location": "戒指中"}, ...]}'
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            try:
                npc_data = json.loads(llm_response.completion_text)
                for npc_info in npc_data.get("npcs", []):
                    npc = NPC(
                        npc_info["name"],
                        npc_info["role"],
                        npc_info["background"],
                        npc_info["location"]
                    )
                    self.npcs[npc.name] = npc
            except json.JSONDecodeError:
                logger.error("NPC生成失败，使用默认NPC")
                self._create_default_npcs()
        else:
            logger.error("NPC生成失败，使用默认NPC")
            self._create_default_npcs()

    async def generate_initial_sects(self):
        """使用LLM生成初始门派"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            "你是一个斗破苍穹风格的游戏世界构建者。请生成3个初始门派，包括门派名称、描述和特色功法。"
            "以JSON格式返回，格式如下："
            '{"sects": [{"name": "云岚宗", "desc": "加玛帝国第一大宗门", "techniques": ["云岚剑法", "风之极"]}, ...]}'
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            try:
                sect_data = json.loads(llm_response.completion_text)
                for sect_info in sect_data.get("sects", []):
                    sect = Sect(sect_info["name"], sect_info["desc"])
                    for tech_name in sect_info.get("techniques", []):
                        tech_info = await self.generate_technique_info(tech_name)
                        sect.techniques[tech_name] = tech_info
                    self.sects[sect.name] = sect
            except json.JSONDecodeError:
                logger.error("门派生成失败，使用默认门派")
                self._create_default_sects()
        else:
            logger.error("门派生成失败，使用默认门派")
            self._create_default_sects()

    async def generate_technique_info(self, name: str) -> Dict:
        """使用LLM生成功法信息"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            f"你是一个斗破苍穹风格的游戏世界构建者。请为功法'{name}'生成详细信息，包括等级、效果和描述。"
            "以JSON格式返回，格式如下："
            '{"grade": "玄阶高级", "effect": "提升攻击力", "description": "一种强大的攻击功法"}'
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            try:
                return json.loads(llm_response.completion_text)
            except json.JSONDecodeError:
                return {"grade": "黄阶中级", "effect": "基础攻击", "description": "一种基础功法"}
        else:
            return {"grade": "黄阶中级", "effect": "基础攻击", "description": "一种基础功法"}

    async def generate_item_info(self, name: str) -> Dict:
        """使用LLM生成物品信息"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            f"你是一个斗破苍穹风格的游戏世界构建者。请为物品'{name}'生成详细信息，包括类型、效果和描述。"
            "以JSON格式返回，格式如下："
            '{"type": "丹药", "effect": "恢复斗气", "description": "能够快速恢复斗气的丹药"}'
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            try:
                return json.loads(llm_response.completion_text)
            except json.JSONDecodeError:
                return {"type": "消耗品", "effect": "未知效果", "description": "一种神秘物品"}
        else:
            return {"type": "消耗品", "effect": "未知效果", "description": "一种神秘物品"}

    def _create_default_npcs(self):
        """创建默认NPC"""
        default_npcs = [
            NPC("药老", "灵魂体炼药师", "曾经是斗尊强者，现在是玩家的老师", "戒指中"),
            NPC("萧薰儿", "古族大小姐", "与玩家青梅竹马，天赋极高", "迦南学院"),
            NPC("海波东", "冰皇", "加玛帝国十大强者之一，经营地图店", "漠城地图店")
        ]
        for npc in default_npcs:
            self.npcs[npc.name] = npc

    def _create_default_sects(self):
        """创建默认门派"""
        default_sects = [
            ("云岚宗", "加玛帝国第一大宗门"),
            ("魂殿", "神秘强大的黑暗势力"),
            ("迦南学院", "培养强者的学院")
        ]
        for name, desc in default_sects:
            self.sects[name] = Sect(name, desc)

    # ============== LLM游戏功能 ==============
    async def generate_npc_response(self, npc: NPC, player: Player, message: str) -> str:
        """使用LLM生成NPC的回应"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            f"你扮演{npc.name}，一个{npc.role}。{npc.background}。"
            f"当前游戏世界是斗破苍穹的修真世界。玩家{player.name}当前境界是{CULTIVATION_LEVELS[player.level]}。"
            "请用符合角色设定的语言风格回复，回复要简短（50字以内）。"
        )

        # 构建对话上下文
        contexts = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{player.name}说：{message}"}
        ]

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=contexts,
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            return llm_response.completion_text
        else:
            return "（NPC陷入沉思，没有回应）"

    async def generate_dynamic_event(self, player: Player) -> Tuple[str, Dict]:
        """使用LLM生成动态事件"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            f"你是一个斗破苍穹游戏的事件生成器。玩家{player.name}当前境界是{CULTIVATION_LEVELS[player.level]}，"
            f"位于{player.sect if player.sect else '野外'}。请生成一个简短的随机事件（50字以内），"
            "并指定事件类型（发现物品、遭遇敌人、特殊事件）和可能的奖励。"
            "以JSON格式返回，格式如下："
            '{"description": "事件描述", "type": "事件类型", "reward": {"item": "物品名", "effect": "效果描述"}}'
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            try:
                event_data = json.loads(llm_response.completion_text)
                return event_data.get("description", "你遇到了一件神秘的事情..."), event_data
            except json.JSONDecodeError:
                return "你遇到了一件神秘的事情...", {}
        else:
            return "你遇到了一件神秘的事情...", {}

    async def generate_battle_description(self, player: Player, target: Player, result: str) -> str:
        """使用LLM生成战斗描述"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            f"你是一个斗破苍穹游戏的战斗解说员。玩家{player.name}（境界：{CULTIVATION_LEVELS[player.level]}）"
            f"向{target.name}（境界：{CULTIVATION_LEVELS[target.level]}）发起挑战，战斗结果是：{result}。"
            "请生成一段50字左右的战斗过程描述，要求符合斗破苍穹的风格。"
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            return llm_response.completion_text
        else:
            return f"{player.name}与{target.name}展开了一场激烈的战斗！"

    async def interpret_natural_command(self, event: AstrMessageEvent, player: Player) -> str:
        """使用LLM解析自然语言命令"""
        # 获取当前对话ID
        curr_cid = await self.context.conversation_manager.get_curr_conversation_id(event.unified_msg_origin)
        conversation = None
        context = []
        if curr_cid:
            conversation = await self.context.conversation_manager.get_conversation(event.unified_msg_origin, curr_cid)
            context = json.loads(conversation.history)

        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            "你是斗破苍穹游戏的指令解析器。请将玩家的自然语言指令转换为游戏命令。"
            "可用命令：修炼、战斗[玩家名]、使用[物品名]、加入[门派]、探索、查看信息等。"
            "只需返回命令，不要解释。例如：玩家说'我想修炼'，你回复'修炼'；玩家说'我要挑战张三'，你回复'战斗 张三'。"
        )

        # 构建对话上下文
        contexts = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": event.message_str.strip()}
        ]

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=contexts,
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            return llm_response.completion_text.strip()
        else:
            return ""

    # ============== 游戏指令系统 ==============
    @filter.command("doupo start")
    async def start_game(self, event: AstrMessageEvent):
        '''开始游戏'''
        player = self._get_player(event)

        # 生成初始功法
        technique_name = await self.generate_random_technique_name()
        technique_info = await self.generate_technique_info(technique_name)
        player.techniques[technique_name] = technique_info

        # 生成初始物品
        item_name = await self.generate_random_item_name()
        item_info = await self.generate_item_info(item_name)
        player.items[item_name] = 1

        response = (
            f"欢迎来到斗气大陆！\n"
            f"{self.world_setting[:200]}...\n\n"
            f"你已获得初始境界：{CULTIVATION_LEVELS[player.level]}\n"
            f"你领悟了功法：{technique_name}({technique_info.get('grade', '黄阶低级')})\n"
            f"{technique_info.get('description', '一种基础功法')}\n\n"
            f"你获得了物品：{item_name}\n"
            f"{item_info.get('description', '一种神秘物品')}\n\n"
            f"使用 /doupo help 查看游戏帮助"
        )

        yield event.plain_result(response)

    @filter.command("doupo info")
    async def player_info(self, event: AstrMessageEvent):
        '''查看玩家信息'''
        player = self._get_player(event)

        sect_info = f"门派：{player.sect}" if player.sect else "无门无派"
        money_info = f"灵石：{player.money}块"

        # 获取功法列表
        techniques = []
        for tech, data in player.techniques.items():
            techniques.append(f"{tech}({data.get('grade', '未知等级')})")
        tech_info = f"功法：{', '.join(techniques)}" if techniques else "无功法"

        # 物品列表
        items_info = f"物品：{', '.join([f'{name}x{count}' for name, count in player.items.items()])}" if player.items else "无物品"

        info = (
            f"【{player.name}】\n"
            f"境界：{CULTIVATION_LEVELS[player.level]}\n"
            f"斗气：{player.qi}/{player.max_qi}\n"
            f"经验：{player.exp}/{player.next_level_exp()}\n"
            f"{sect_info}\n{money_info}\n"
            f"{tech_info}\n"
            f"{items_info}"
        )

        yield event.plain_result(info)

    @filter.command("doupo cultivate")
    async def cultivate(self, event: AstrMessageEvent):
        '''修炼提升斗气'''
        player = self._get_player(event)

        now = time.time()

        # 检查修炼冷却时间（现实时间30分钟）
        if now - player.last_cultivate_time < 1800:
            remaining = int(1800 - (now - player.last_cultivate_time))
            yield event.plain_result(f"修炼过度会导致根基不稳，请等待{remaining // 60}分钟后再试")
            return

        # 基础获得量
        base_gain = random.randint(5, 15) * (player.talent / 100)

        # 功法加成
        technique_bonus = 0
        for tech, data in player.techniques.items():
            if "修炼" in tech or "心法" in tech:
                # 根据功法等级计算加成
                grade = data.get("grade", "黄阶低级")
                if "玄阶" in grade:
                    technique_bonus += random.randint(5, 10)
                elif "黄阶" in grade:
                    technique_bonus += random.randint(2, 5)

        total_gain = int(base_gain + technique_bonus)
        player.qi = min(player.qi + total_gain, player.max_qi)

        # 获得经验
        player.exp += 1

        # 更新状态
        player.last_cultivate_time = now

        # 结果消息
        result_msg = f"你静坐修炼，运转周天，获得了{total_gain}点斗气，经验+1"

        # 功法加成提示
        if technique_bonus > 0:
            result_msg += f"（功法加成{technique_bonus}点）"
        result_msg += f"\n当前斗气：{player.qi}/{player.max_qi}"

        # 检查升级
        if player.can_level_up():
            player.level_up()
            level_name = CULTIVATION_LEVELS[player.level]
            result_msg += f"\n✨ 恭喜！你突破到了{level_name}！最大斗气值提升至{player.max_qi}"

        # 发送修炼结果
        yield event.plain_result(result_msg)

        # 有几率触发随机事件
        if random.random() < 0.3:
            event_desc, event_data = await self.generate_dynamic_event(player)
            if event_desc:
                yield event.plain_result(event_desc)

    @filter.command("doupo battle")
    async def battle(self, event: AstrMessageEvent):
        '''挑战其他玩家'''
        player = self._get_player(event)

        # 解析目标玩家
        target_name = event.message_str.strip().split()[-1] if event.message_str.strip() else None
        if not target_name:
            yield event.plain_result("请指定挑战的玩家，例如: /doupo battle 玩家名")
            return

        # 查找目标玩家
        target_player = None
        for pid, p in self.players.items():
            if p.name == target_name and pid != player.user_id:
                target_player = p
                break

        if not target_player:
            yield event.plain_result("找不到指定的玩家")
            return

        # 检查斗气是否足够
        if player.qi < 30:
            yield event.plain_result("斗气不足30点，无法发起挑战")
            return

        # 更新状态
        player.qi -= 30

        # 战斗过程描述（使用LLM生成）
        battle_desc = await self.generate_battle_description(player, target_player, "")
        battle_log = [battle_desc]

        # 战斗结果计算
        player_power = player.qi + player.exp * 10
        target_power = target_player.qi + target_player.exp * 10
        power_diff = player_power - target_power

        if power_diff > 50:
            # 轻松胜利
            exp_gain = max(1, int(target_power * 0.05))
            money_gain = random.randint(5, 15)

            player.exp += exp_gain
            player.money += money_gain
            target_player.qi = max(1, target_player.qi - int(target_player.max_qi * 0.1))

            battle_log.append(f"经过激烈战斗，{player.name} 轻松战胜了对手！")
            result = f"你获得 {exp_gain} 经验和 {money_gain} 灵石"

        elif power_diff > 0:
            # 艰难胜利
            exp_gain = max(1, int(target_power * 0.03))
            money_gain = random.randint(3, 8)

            player.exp += exp_gain
            player.money += money_gain
            player.qi = max(1, player.qi - int(player.max_qi * 0.2))
            target_player.qi = max(1, target_player.qi - int(target_player.max_qi * 0.2))

            battle_log.append(f"经过一番苦战，{player.name} 勉强获胜！")
            result = f"你获得 {exp_gain} 经验和 {money_gain} 灵石"

        else:
            # 失败
            money_loss = min(player.money, random.randint(5, int(player.money * 0.2)))
            player.money -= money_loss
            player.qi = max(1, player.qi - int(player.max_qi * 0.4))
            target_player.money += int(money_loss * 0.5)

            # 有几率获得少量经验
            if random.random() < 0.5:
                exp_gain = max(1, int(player_power * 0.01))
                player.exp += exp_gain
                exp_text = f"和 {exp_gain} 经验"
            else:
                exp_text = ""

            battle_log.append(f"经过激烈战斗，{player.name} 不敌对手，最终落败！")
            result = f"你失去了 {money_loss} 灵石{exp_text}"

        battle_log.append(result)

        # 检查升级
        if player.can_level_up():
            player.level_up()
            level_name = CULTIVATION_LEVELS[player.level]
            battle_log.append(f"\n✨ 战斗中突破！你晋升为 {level_name}！")

        yield event.plain_result("\n".join(battle_log))

    @filter.command("doupo talk")
    async def talk_to_npc(self, event: AstrMessageEvent):
        '''与NPC对话'''
        player = self._get_player(event)
        args = event.message_str.strip().split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("用法: /doupo talk <NPC名字> <对话内容>")
            return

        npc_name, message = args
        if npc_name not in self.npcs:
            yield event.plain_result(f"找不到名为{npc_name}的NPC")
            return

        npc = self.npcs[npc_name]
        response = await self.generate_npc_response(npc, player, message)

        yield event.plain_result(f"{npc_name}：{response}")

    @filter.command("doupo explore")
    async def explore(self, event: AstrMessageEvent):
        '''探索世界'''
        player = self._get_player(event)

        # 消耗斗气
        if player.qi < 20:
            yield event.plain_result("斗气不足20点，无法探索")
            return

        player.qi -= 20

        # 生成随机事件
        event_desc, event_data = await self.generate_dynamic_event(player)

        # 处理事件奖励
        reward_msg = ""
        if "reward" in event_data:
            reward = event_data["reward"]
            item_name = reward.get("item", "")
            if item_name:
                # 生成物品信息
                item_info = await self.generate_item_info(item_name)
                player.items[item_name] = player.items.get(item_name, 0) + 1
                reward_msg = f"\n你获得了{item_name}！"

        yield event.plain_result(f"{event_desc}{reward_msg}")

    @filter.command("doupo join")
    async def join_sect(self, event: AstrMessageEvent):
        '''加入门派'''
        player = self._get_player(event)
        sect_name = event.message_str.strip()

        if not sect_name:
            yield event.plain_result("请指定要加入的门派，例如: /doupo join 云岚宗")
            return

        if sect_name not in self.sects:
            yield event.plain_result("该门派不存在")
            return

        if player.sect:
            yield event.plain_result(f"你已经是{player.sect}的成员，请先退出当前门派")
            return

        sect = self.sects[sect_name]
        sect.members[player.user_id] = "弟子"
        player.sect = sect_name

        # 加入门派奖励
        if sect.techniques:
            tech_name = random.choice(list(sect.techniques.keys()))
            player.techniques[tech_name] = sect.techniques[tech_name]
            reward_msg = f"并获得了门派功法《{tech_name}》"
        else:
            reward_msg = ""

        yield event.plain_result(
            f"恭喜你加入{sect_name}！{reward_msg}"
        )

    @filter.command("doupo world")
    async def world_info(self, event: AstrMessageEvent):
        '''查看世界信息'''
        # NPC列表
        npc_list = "\n".join([f"{npc.name} - {npc.role} ({npc.location})" for npc in self.npcs.values()])

        # 门派列表
        sect_list = "\n".join([f"{name}: {sect.desc}" for name, sect in self.sects.items()])

        response = (
            f"【斗气大陆世界设定】\n{self.world_setting[:500]}...\n\n"
            f"【重要NPC】\n{npc_list}\n\n"
            f"【门派列表】\n{sect_list}"
        )

        yield event.plain_result(response)

    @filter.command("doupo")
    async def natural_language_command(self, event: AstrMessageEvent):
        '''自然语言命令接口'''
        player = self._get_player(event)
        command = await self.interpret_natural_command(event, player)

        if not command:
            yield event.plain_result("无法理解你的指令，请尝试使用标准命令")
            return

        # 根据解析的命令执行相应操作
        if command == "修炼":
            yield self.cultivate(event)
        elif command.startswith("战斗"):
            target = command[2:].strip()
            # 设置事件消息为战斗目标
            event.message_str = f"battle {target}"
            yield self.battle(event)
        elif command.startswith("使用"):
            item = command[2:].strip()
            # TODO: 实现物品使用
            yield event.plain_result(f"使用了{item}")
        elif command == "探索":
            yield self.explore(event)
        elif command in ["查看信息", "信息"]:
            yield self.player_info(event)
        elif command.startswith("对话"):
            npc = command[2:].strip()
            event.message_str = f"talk {npc} 你好"
            yield self.talk_to_npc(event)
        elif command.startswith("加入"):
            sect = command[2:].strip()
            event.message_str = f"join {sect}"
            yield self.join_sect(event)
        else:
            yield event.plain_result(f"无法执行命令: {command}")

    async def generate_random_technique_name(self) -> str:
        """生成随机功法名称"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            "你是一个斗破苍穹风格的游戏世界构建者。请生成一个随机的功法名称，符合修真世界的风格。"
            "只需返回名称，不要解释。"
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            return llm_response.completion_text.strip()
        else:
            return "碎石掌"

    async def generate_random_item_name(self) -> str:
        """生成随机物品名称"""
        # 获取LLM工具管理器
        func_tools_mgr = self.context.get_llm_tool_manager()

        # 构建系统提示
        system_prompt = (
            "你是一个斗破苍穹风格的游戏世界构建者。请生成一个随机的物品名称，符合修真世界的风格。"
            "只需返回名称，不要解释。"
        )

        # 调用LLM
        llm_response = await self.context.get_using_provider().text_chat(
            prompt="",
            contexts=[{"role": "system", "content": system_prompt}],
            func_tool=func_tools_mgr,
            system_prompt=system_prompt
        )

        if llm_response.role == "assistant":
            return llm_response.completion_text.strip()
        else:
            return "聚气散"

    async def terminate(self):
        '''插件终止时保存数据'''
        logger.info("斗破苍穹游戏插件正在关闭...")
        # 在实际应用中，这里应该将玩家数据保存到数据库或文件
        logger.info(f"保存了 {len(self.players)} 名玩家数据")
