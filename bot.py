from daily import send_daily_notifications
from electricity import get_electricity_balance


__all__ = ["get_electricity_balance", "send_daily_notifications"]


if __name__ == "__main__":
    send_daily_notifications()
