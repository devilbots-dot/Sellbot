# utilsdevil
import motor.motor_asyncio
from config import MONGODB_URI
import asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client.get_default_database()

users = db.users
files = db.files
orders = db.orders
payments = db.payments
redeem_codes = db.redeem_codes
otp_queue = db.otp_queue
logs = db.logs
manual_utrs = db.manual_utrs

async def init_db_indexes():
    await users.create_index('tg_id', unique=True)
    await files.create_index([('platform', 1), ('country', 1), ('status', 1)])
    await payments.create_index('razorpay_link_id')
    await redeem_codes.create_index('code', unique=True)
    await otp_queue.create_index('file_id')
