# main.py
import asyncio, logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, LOG_GROUP_ID
from utils.db import init_db_indexes
from handlers.user_handlers import register_user_handlers
from handlers.admin_handlers import register_admin_handlers
from modules.logger import LOGGER

if not (API_ID and API_HASH and BOT_TOKEN):
    LOGGER.error("Set API_ID, API_HASH, BOT_TOKEN in .env")
    raise SystemExit(1)

app = Client('fileshopbot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def log_forwarder(client):
    from utils.db import logs
    LOGGER.info("Starting log forwarder...")
    while True:
        try:
            cursor = logs.find({'forwarded': {'$ne': True}}).sort('ts', 1).limit(20)
            async for doc in cursor:
                t = doc.get('type')
                text = str(doc)
                if t == 'payment_captured':
                    text = f"💸 Payment captured\nUser: {doc.get('user_id')}\nAmount: ₹{doc.get('amount')}\nPayment ID: {doc.get('payment_id')}"
                elif t == 'payment_link_paid':
                    text = f"💳 Payment link paid\nUser: {doc.get('user_id')}\nAmount: ₹{doc.get('amount')}"
                elif t == 'otp_sent':
                    text = f"🔐 OTP sent\nUser: {doc.get('user_id')}\nNumber: {doc.get('number')}"
                try:
                    if LOG_GROUP_ID:
                        await client.send_message(LOG_GROUP_ID, text)
                    else:
                        if OWNER_ID:
                            await client.send_message(OWNER_ID, text)
                    await logs.update_one({'_id': doc['_id']}, {'$set': {'forwarded': True}})
                except Exception as e:
                    LOGGER.exception("Failed to forward log: %s", e)
        except Exception as e:
            LOGGER.exception("Log forwarder exception: %s", e)
        await asyncio.sleep(4)

async def main():
    await init_db_indexes()
    register_user_handlers(app)
    register_admin_handlers(app)
    await app.start()
    LOGGER.info("Bot started.")
    asyncio.create_task(log_forwarder(app))
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Stopped by user")
