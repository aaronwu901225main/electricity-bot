import base64
import hashlib
import hmac
import logging
import os
import re
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, abort, request
from waitress import serve

import config
from daily import TIMEZONE, send_daily_notifications
from database import (
    create_user,
    get_user,
    init_db,
    set_enabled,
    update_phone,
    update_room,
    update_state,
)
from electricity import get_electricity_balance
from line_api import reply_line_message


logger = logging.getLogger(__name__)
app = Flask(__name__)
_scheduler = None


def _verify_signature(body, signature):
    channel_secret = config.require_env("LINE_CHANNEL_SECRET")
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(signature or "", expected_signature)


def _masked_phone(phone_number):
    return f"{phone_number[:4]}***{phone_number[-3:]}"


def handle_message(user_id, reply_token, text):
    user = get_user(user_id)
    if user is None:
        create_user(user_id)
        user = get_user(user_id)
    if user is None:
        raise RuntimeError("Failed to create LINE user record.")

    if text in ("設定", "修改設定", "重新設定"):
        update_state(user_id, "waiting_room")
        reply_line_message(reply_token, "請輸入你的房號：")
        return

    if text == "取消":
        update_state(
            user_id,
            "ready" if user["room_number"] and user["phone_number"] else "new"
        )
        reply_line_message(reply_token, "已取消設定流程。")
        return

    if text == "關閉通知":
        if user["state"] != "ready":
            reply_line_message(reply_token, "請先輸入「設定」完成資料設定。")
            return
        set_enabled(user_id, False)
        reply_line_message(reply_token, "每日電費通知已關閉。")
        return

    if text == "開啟通知":
        if user["state"] != "ready":
            reply_line_message(reply_token, "請先輸入「設定」完成資料設定。")
            return
        set_enabled(user_id, True)
        reply_line_message(reply_token, "每日電費通知已開啟，每天中午 12:00 通知。")
        return

    if text == "我的資料":
        if user["state"] != "ready":
            reply_line_message(reply_token, "尚未完成設定，請輸入「設定」開始。")
            return
        notification_status = "✅ 開啟" if user["enabled"] else "⏸️ 關閉"
        reply_line_message(
            reply_token,
            (
                "⚙️ 目前設定\n\n"
                f"房號：{user['room_number']}\n"
                f"電話：{_masked_phone(user['phone_number'])}\n"
                f"每日通知：{notification_status}\n"
                "通知時間：12:00\n\n"
                "如需變更請輸入「修改設定」"
            )
        )
        return

    if text == "查詢":
        if user["state"] != "ready":
            reply_line_message(reply_token, "尚未完成設定，請輸入「設定」開始。")
            return
        try:
            balance = get_electricity_balance(
                user["room_number"],
                user["phone_number"]
            )
        except Exception:
            logger.exception("Electricity balance lookup failed for user %s", user_id)
            reply_line_message(
                reply_token,
                "⚠️ 電費查詢失敗，請確認房號及手機號碼，或輸入「修改設定」。"
            )
            return

        reply_line_message(reply_token, f"⚡ 目前電費餘額：{balance} 元")
        return

    if user["state"] == "waiting_room":
        room_number = text.strip().upper()
        if not room_number:
            reply_line_message(reply_token, "房號不可空白，請重新輸入：")
            return
        update_room(user_id, room_number)
        update_state(user_id, "waiting_phone")
        reply_line_message(reply_token, "請輸入你的手機號碼（09 開頭，共 10 碼）：")
        return

    if user["state"] == "waiting_phone":
        phone_number = re.sub(r"[\s-]", "", text)
        if re.fullmatch(r"09\d{8}", phone_number) is None:
            reply_line_message(
                reply_token,
                "手機號碼格式不正確，請輸入 09 開頭的 10 碼手機號碼："
            )
            return
        update_phone(user_id, phone_number)
        reply_line_message(
            reply_token,
            (
                "✅ 設定完成\n\n"
                f"房號：{user['room_number'] or ''}\n\n"
                "每天中午 12:00 會自動查詢電費餘額並通知你。\n\n"
                "你也可以輸入「查詢」立即查詢目前餘額。"
            )
        )
        return

    reply_line_message(
        reply_token,
        "請輸入「設定」、「查詢」、「我的資料」、「開啟通知」或「關閉通知」。"
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
def webhook():
    body = request.get_data()
    if not _verify_signature(body, request.headers.get("X-Line-Signature")):
        abort(400)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        abort(400)

    for event in payload["events"]:
        if not isinstance(event, dict) or event.get("type") != "message":
            continue

        message = event.get("message", {})
        if not isinstance(message, dict) or message.get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        if not reply_token:
            continue

        source = event.get("source", {})
        user_id = source.get("userId") if isinstance(source, dict) else None
        if not user_id:
            reply_line_message(
                reply_token,
                "請在與 Bot 的一對一聊天室設定電費通知。"
            )
            continue

        text = message.get("text")
        if isinstance(text, str):
            handle_message(user_id, reply_token, text.strip())

    return "OK"


def start_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=ZoneInfo(TIMEZONE))
        _scheduler.add_job(
            send_daily_notifications,
            trigger="cron",
            hour=12,
            minute=0,
            id="daily-electricity-notifications",
            replace_existing=True,
        )
        _scheduler.start()
    return _scheduler


def main():
    init_db()
    start_scheduler()
    serve(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000"))
    )


if __name__ == "__main__":
    main()
