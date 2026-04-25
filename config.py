import os
from dotenv import load_dotenv

load_dotenv()

PROXY_BASE_URL: str = os.environ["OPENAI_BASE_URL"]
PROXY_API_KEY: str = os.environ["OPENAI_API_KEY"]
MODEL_NAME: str = os.environ.get("MODEL_NAME", "openai/gpt-4o-mini")
MAPS_API_KEY: str = os.environ.get("MAPS_API_KEY", "")
