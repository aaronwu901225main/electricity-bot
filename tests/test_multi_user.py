import base64
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
import daily
import database
import line_api


class MultiUserBotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(Path(self.temp_dir.name) / "test.db")
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_setup_persists_and_masks_phone_number(self):
        with patch.object(app_module, "reply_line_message") as reply:
            app_module.handle_message("U-A", "token-1", "設定")
            self.assertEqual(reply.call_args.args[1], "請輸入你的房號：")

            app_module.handle_message("U-A", "token-2", "a121")
            self.assertEqual(database.get_user("U-A")["state"], "waiting_phone")

            app_module.handle_message("U-A", "token-3", "invalid")
            self.assertEqual(database.get_user("U-A")["state"], "waiting_phone")

            app_module.handle_message("U-A", "token-4", "0912-345-678")

            user = database.get_user("U-A")
            self.assertEqual(user["room_number"], "A121")
            self.assertEqual(user["phone_number"], "0912345678")
            self.assertEqual(user["state"], "ready")
            self.assertTrue(user["enabled"])

            app_module.handle_message("U-A", "token-5", "我的資料")
            details = reply.call_args.args[1]
            self.assertIn("電話：0912***678", details)
            self.assertNotIn("0912345678", details)

    def test_enabled_users_are_filtered_per_user(self):
        for user_id, room, phone in (
            ("U-A", "A121", "0912345678"),
            ("U-B", "B305", "0987654321"),
        ):
            database.create_user(user_id)
            database.update_room(user_id, room)
            database.update_phone(user_id, phone)

        database.set_enabled("U-A", False)

        self.assertEqual(
            database.get_enabled_users(),
            [{
                "user_id": "U-B",
                "room_number": "B305",
                "phone_number": "0987654321",
            }]
        )

    def test_daily_notifications_query_and_push_each_users_own_data(self):
        users = [
            {
                "user_id": "U-A",
                "room_number": "A121",
                "phone_number": "0912345678",
            },
            {
                "user_id": "U-B",
                "room_number": "B305",
                "phone_number": "0987654321",
            },
        ]
        with (
            patch.object(daily, "get_enabled_users", return_value=users),
            patch.object(
                daily,
                "get_electricity_balance",
                side_effect=["120", "240"]
            ) as query,
            patch.object(daily, "send_line_message") as push,
        ):
            daily.send_daily_notifications()

        self.assertEqual(
            query.call_args_list[0].args,
            ("A121", "0912345678")
        )
        self.assertEqual(
            query.call_args_list[1].args,
            ("B305", "0987654321")
        )
        self.assertEqual(push.call_args_list[0].args[0], "U-A")
        self.assertIn("120 元", push.call_args_list[0].args[1])
        self.assertEqual(push.call_args_list[1].args[0], "U-B")
        self.assertIn("240 元", push.call_args_list[1].args[1])

    def test_webhook_requires_valid_line_signature(self):
        body = json.dumps({"events": []}).encode("utf-8")
        secret = "test-channel-secret"
        signature = base64.b64encode(
            hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        ).decode("ascii")

        with (
            patch.object(app_module.config, "require_env", return_value=secret),
            app_module.app.test_client() as client,
        ):
            response = client.post(
                "/webhook",
                data=body,
                content_type="application/json",
                headers={"X-Line-Signature": signature},
            )
            rejected = client.post(
                "/webhook",
                data=body,
                content_type="application/json",
                headers={"X-Line-Signature": "invalid"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rejected.status_code, 400)

    def test_webhook_dispatches_text_to_the_user_conversation(self):
        payload = {
            "events": [{
                "type": "message",
                "replyToken": "reply-token",
                "source": {"type": "user", "userId": "U-A"},
                "message": {"type": "text", "text": " 設定 "},
            }]
        }
        body = json.dumps(payload).encode("utf-8")
        secret = "test-channel-secret"
        signature = base64.b64encode(
            hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        ).decode("ascii")

        with (
            patch.object(app_module.config, "require_env", return_value=secret),
            patch.object(app_module, "handle_message") as handle_message,
            app_module.app.test_client() as client,
        ):
            response = client.post(
                "/webhook",
                data=body,
                content_type="application/json",
                headers={"X-Line-Signature": signature},
            )

        self.assertEqual(response.status_code, 200)
        handle_message.assert_called_once_with("U-A", "reply-token", "設定")

    def test_line_api_uses_reply_and_private_push_endpoints(self):
        with (
            patch.object(line_api.config, "require_env", return_value="token"),
            patch.object(line_api.requests, "post") as post,
        ):
            post.return_value.raise_for_status.return_value = None
            line_api.reply_line_message("reply-token", "reply")
            line_api.send_line_message("U-A", "push")

        self.assertEqual(
            post.call_args_list[0].args[0],
            "https://api.line.me/v2/bot/message/reply"
        )
        self.assertEqual(
            post.call_args_list[0].kwargs["json"]["replyToken"],
            "reply-token"
        )
        self.assertEqual(
            post.call_args_list[1].args[0],
            "https://api.line.me/v2/bot/message/push"
        )
        self.assertEqual(post.call_args_list[1].kwargs["json"]["to"], "U-A")


if __name__ == "__main__":
    unittest.main()
