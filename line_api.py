import requests

import config


LINE_API_BASE_URL = "https://api.line.me/v2/bot/message"


def _send_line_message(endpoint, payload):
    response = requests.post(
        f"{LINE_API_BASE_URL}/{endpoint}",
        headers={
            "Authorization": (
                f"Bearer {config.require_env('LINE_CHANNEL_ACCESS_TOKEN')}"
            ),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20
    )
    response.raise_for_status()


def reply_line_message(reply_token, message):
    _send_line_message(
        "reply",
        {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }
    )


def send_line_message(user_id, message):
    _send_line_message(
        "push",
        {
            "to": user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }
    )
