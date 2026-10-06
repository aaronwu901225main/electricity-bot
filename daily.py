import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from database import get_enabled_users
from electricity import get_electricity_balance
from line_api import send_line_message


logger = logging.getLogger(__name__)
TIMEZONE = config.TIMEZONE


def send_daily_notifications():
    today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y/%m/%d")

    for user in get_enabled_users():
        try:
            balance = get_electricity_balance(
                user["room_number"],
                user["phone_number"]
            )
            message = (
                f"⚡ 電費每日通知\n"
                f"日期：{today}\n"
                f"目前餘額：{balance} 元"
            )
        except Exception:
            logger.exception(
                "Electricity balance lookup failed for LINE user %s",
                user["user_id"]
            )
            message = (
                "⚠️ 今日電費查詢失敗\n"
                "請輸入「修改設定」確認房號及手機號碼。"
            )

        try:
            send_line_message(user["user_id"], message)
        except Exception:
            logger.exception(
                "Daily LINE notification failed for user %s",
                user["user_id"]
            )
