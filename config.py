#devilimport
import os
from dotenv import load_dotenv
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

MONGODB_URI = os.getenv("MONGODB_URI", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "0"))
SUPPORT_GROUP_LINK = os.getenv("SUPPORT_GROUP_LINK", "https://t.me/your_support_group")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
S3_KEY = os.getenv("S3_KEY", "")
S3_SECRET = os.getenv("S3_SECRET", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "")

PORT = int(os.getenv("PORT", 8000))
SESSION_FOLDER = os.getenv("SESSION_FOLDER", "./sessions")
FILES_TEMP = os.getenv("FILES_TEMP", "/tmp/fileshop")
