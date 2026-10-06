# Electricity LINE Bot

The bot keeps each LINE user's room and phone number in SQLite and sends a
private daily balance notification at noon.

## Configuration

Create a `.env` file with the LINE Messaging API credentials:

```dotenv
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token
LINE_CHANNEL_SECRET=your-channel-secret
ELECTRICITY_URL=http://140.113.243.122/
TIMEZONE=Asia/Taipei
# DATABASE_PATH=C:\path\to\electricity.db
```

Install dependencies and run the single-process web server and scheduler:

```powershell
pip install -r requirements.txt
python app.py
```

Set the LINE Developers webhook URL to `https://<public-host>/webhook` and
enable webhook delivery. The service must be reachable over HTTPS from LINE.
The server must also be able to reach the configured electricity website;
the default address may only be accessible from the campus network. Use a
public HTTPS tunnel for local development or deploy on a host with both
required network paths.

The built-in scheduler runs in the web process, uses `TIMEZONE` (default
`Asia/Taipei`), and should run in exactly one process/instance to avoid
duplicate daily notifications. Use a persistent disk for `electricity.db`
when deploying to a host with an ephemeral filesystem. The database contains
phone numbers and should be access-restricted and backed up securely.

## LINE commands

- `設定` / `修改設定`: collect room and phone number.
- `查詢`: immediately check the current balance.
- `我的資料`: show settings with the phone number masked.
- `關閉通知` / `開啟通知`: pause or resume daily notifications.

The legacy one-shot entry point `python bot.py` sends today's notifications
immediately; use `python app.py` for the webhook and daily scheduler.
