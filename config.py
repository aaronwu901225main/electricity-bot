import os

from dotenv import load_dotenv


load_dotenv()

ELECTRICITY_URL = os.getenv(
    "ELECTRICITY_URL",
    "http://140.113.243.122/"
)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Taipei")


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable {name} is not set."
        )
    return value
