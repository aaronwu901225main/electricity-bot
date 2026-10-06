import requests
from bs4 import BeautifulSoup

import config


ELECTRICITY_URL = config.ELECTRICITY_URL


def get_electricity_balance(room_number, phone_number):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        )
    }

    with requests.Session() as session:
        response = session.get(
            ELECTRICITY_URL,
            headers=headers,
            timeout=20
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form", id="ctl01")
        if form is None:
            raise RuntimeError("找不到查詢表單")

        payload = {}
        for input_tag in form.find_all("input"):
            name = input_tag.get("name")
            if not name:
                continue

            input_type = input_tag.get("type", "text").lower()
            if input_type in ("submit", "button", "image", "file"):
                continue

            payload[name] = input_tag.get("value", "")

        payload[
            "ctl00$Content$BootstrapFormLayout1$edRoomNo"
        ] = room_number
        payload[
            "ctl00$Content$BootstrapFormLayout1$edPhone"
        ] = phone_number
        payload[
            "ctl00$Content$BootstrapFormLayout1$btnQuery"
        ] = "查詢"

        response = session.post(
            ELECTRICITY_URL,
            data=payload,
            headers={
                **headers,
                "Referer": ELECTRICITY_URL
            },
            timeout=20
        )
        response.raise_for_status()

        result = BeautifulSoup(response.text, "html.parser")
        balance_input = result.find(
            "input",
            id="Content_BootstrapFormLayout1_edBalance_I"
        )
        if balance_input is None:
            raise RuntimeError("找不到儲值餘額")

        balance = balance_input.get("value", "").strip()
        if not balance:
            raise RuntimeError("查詢失敗，請確認房號及電話。")

        return balance
