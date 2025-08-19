from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from datetime import datetime

# 斗破苍穹等级体系
CULTIVATION_LEVELS = {
    1: ("斗之气", "一至九段"),
    2: ("斗者", "一至九星"),
    3: ("斗师", "一至九星"),
    4: ("大斗师", "一至九星"),
    5: ("斗灵", "一至九星"),
    6: ("斗王", "一至九星"),
    7: ("斗皇", "一至九星"),
    8: ("斗宗", "一至九星"),
    9: ("斗尊", "一至九星"),
    10: ("斗圣", "一至九星"),
    11: ("斗帝", "至高无上"),
}

# 游戏物品和消耗品
GAME_ITEMS = {
    "凝气散": {"description": "基础修炼丹药", "effect": "经验+50", "value": 100},
    "聚气丹": {"description": "中等修炼丹药", "effect": "经验+200", "value": 400},
    "筑基灵液": {"description": "高级修炼丹药", "effect": "经验+800", "value": 1500},
}


@register("DouPoWorld", "developer_name", "斗破苍穹文字游戏", "1.0.0", "repo_url")
class DouPoWorld(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.db = context.db  # 使用上下文提供的数据库接口

        # 初始化数据库表
        with self.db.connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS players ("
                "player_id TEXT PRIMARY KEY, "
                "player_name TEXT, "
                "level INTEGER DEFAULT 1, "
                "experience INTEGER DEFAULT 0, "
                "coins INTEGER DEFAULT 100, "
                "last_sign_date TEXT)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS player_inventory ("
                "player_id TEXT, "
                "item_name TEXT, "
                "quantity INTEGER DEFAULT 0, "
                "PRIMARY KEY (player_id, item_name))"
            )

    def _get_player(self, player_id: str, player_name: str):
        """获取或创建玩家数据"""
        with self.db.connect() as conn:
            player = conn.execute(
                "SELECT * FROM players WHERE player_id = ?",
                (player_id,)
            ).fetchone()

            if not player:
                # 新玩家初始化
                conn.execute(
                    "INSERT INTO players (player_id, player_name) VALUES (?, ?)",
                    (player_id, player_name)
                )
                # 为新玩家添加初始物品
                for item_name in ["凝气散", "聚气丹"]:
                    conn.execute(
                        "INSERT INTO player_inventory (player_id, item_name, quantity) VALUES (?, ?, ?)",
                        (player_id, item_name, 3 if item_name == "凝气散" else 1)
                    )
                # 重新获取玩家数据
                player = conn.execute(
                    "SELECT * FROM players WHERE player_id = ?",
                    (player_id,)
                ).fetchone()

            return player

    def _get_level_info(self, level: int, exp: int):
        """获取等级信息"""
        main_level = min((level - 1) // 10 + 1, 11)
        sub_level = (level - 1) % 10 + 1

        level_name, level_desc = CULTIVATION_LEVELS[main_level]
        next_level_exp = level * 100
        return {
            "main_level": main_level,
            "sub_level": sub_level,
            "level_name": level_name,
            "level_desc": level_desc,
            "exp_progress": f"{exp}/{next_level_exp}",
            "progress_percent": min(100, int(exp / next_level_exp * 100)) if next_level_exp > 0 else 100
        }

    # 签到指令
    @filter.command("签到")
    async def sign_in(self, event: AstrMessageEvent):
        """每日签到领取奖励"""
        player_id = event.get_sender_id()
        player_name = event.get_sender_name()
        today = datetime.now().strftime("%Y-%m-%d")

        with self.db.connect() as conn:
            player = self._get_player(player_id, player_name)

            # 检查今日是否已签到
            if player["last_sign_date"] == today:
                yield event.plain_result(f"{player_name} 今日已签到过了！")
                return

            # 更新签到日期
            conn.execute(
                "UPDATE players SET last_sign_date = ? WHERE player_id = ?",
                (today, player_id)
            )

            # 添加签到奖励
            reward_coins = player["level"] * 20
            reward_exp = player["level"] * 30
            conn.execute(
                "UPDATE players SET coins = coins + ?, experience = experience + ? WHERE player_id = ?",
                (reward_coins, reward_exp, player_id)
            )

            # 记录日志
            logger.info(f"玩家 {player_name} 签到成功，获得金币 {reward_coins}，经验 {reward_exp}")

            yield event.plain_result(
                f"✨ {player_name} 签到成功！\n"
                f"获得金币: {reward_coins} \n"
                f"获得经验: {reward_exp}"
            )

    # 查看个人信息
    @filter.command("我的信息")
    async def my_profile(self, event: AstrMessageEvent):
        """查看我的角色信息"""
        player_id = event.get_sender_id()
        player_name = event.get_sender_name()

        player = self._get_player(player_id, player_name)
        level_info = self._get_level_info(player["level"], player["experience"])

        # 组装响应消息
        response = (
            f"🏮【{player_name}的角色信息】🏮\n"
            f"境界: {level_info['level_name']} {level_info['sub_level']}{level_info['level_desc']}\n"
            f"等级: {player['level']}级\n"
            f"经验: {level_info['exp_progress']} "
            f"[{'▰' * (level_info['progress_percent'] // 5)}{'▱' * (20 - level_info['progress_percent'] // 5)}]\n"
            f"金币: {player['coins']}\n"
            f"签到状态: {'今日已签到' if player['last_sign_date'] == datetime.now().strftime('%Y-%m-%d') else '今日未签到'}"
        )

        yield event.plain_result(response)

    # 修炼指令
    @filter.command("修炼")
    async def cultivate(self, event: AstrMessageEvent):
        """通过修炼获取经验"""
        player_id = event.get_sender_id()
        player_name = event.get_sender_name()

        with self.db.connect() as conn:
            player = self._get_player(player_id, player_name)

            # 计算修炼收益 (1-3小时收益)
            hours = min(3, player["level"] // 5 + 1)
            exp_gain = player["level"] * 10 * hours

            # 更新经验和金币
            conn.execute(
                "UPDATE players SET experience = experience + ? WHERE player_id = ?",
                (exp_gain, player_id)
            )

            # 获取更新后的玩家数据
            player = self._get_player(player_id, player_name)
            level_info = self._get_level_info(player["level"], player["experience"])

            logger.info(f"玩家 {player_name} 修炼了{hours}小时，获得经验 {exp_gain}")

            response = (
                f"🧘 {player_name} 潜心修炼了{hours}小时\n"
                f"获得经验: +{exp_gain}\n\n"
                f"当前境界: {level_info['level_name']} {level_info['sub_level']}段\n"
                f"经验进度: {level_info['exp_progress']} "
                f"[{'▰' * (level_info['progress_percent'] // 5)}{'▱' * (20 - level_info['progress_percent'] // 5)}]"
            )

            yield event.plain_result(response)

    async def terminate(self):
        '''插件终止时执行'''
        logger.info("斗破苍穹游戏插件已安全终止")
