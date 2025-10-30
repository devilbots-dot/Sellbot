# handlers/admin_handlers.py
import os, datetime, io, zipfile, json, tempfile, time
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import users, files, logs
from modules.file_manager import process_uploaded_zip
from modules.storage import upload_bytes
from config import OWNER_ID, LOG_GROUP_ID
from modules.logger import LOGGER

def register_admin_handlers(bot_client):
    @bot_client.on_message(filters.command('admin') & filters.user(OWNER_ID))
    async def admin_panel(_, message):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('Add File', callback_data='admin_addfile')],
            [InlineKeyboardButton('Delete File', callback_data='admin_deletefile')],
            [InlineKeyboardButton('Stock', callback_data='admin_stock')],
            [InlineKeyboardButton('Today Sales', callback_data='admin_sales')],
            [InlineKeyboardButton('Generate Code', callback_data='admin_gencode')]
        ])
        await message.reply_text('Admin Panel:', reply_markup=kb)

    @bot_client.on_callback_query(filters.regex(r'^admin_'))
    async def admin_cb(_, q):
        data = q.data
        if data == 'admin_addfile':
            await q.message.reply_text('Send message `Platform|Country|Price` then reply to that message with ZIP file (document). Example:\n`WhatsApp|India|50`')
        elif data == 'admin_deletefile':
            await q.message.reply_text('Use /deletefile <platform> <country>')
        elif data == 'admin_stock':
            rows=[]
            async for doc in files.aggregate([{'$match':{'status':'available'}},{'$group':{'_id':{'platform':'$platform','country':'$country'}, 'count':{'$sum':1}}}] ):
                rows.append(f"{doc['_id']['platform']} - {doc['_id']['country']}: {doc['count']}")
            await q.message.reply_text('\\n'.join(rows) or 'No stock')
        elif data == 'admin_sales':
            today = datetime.datetime.utcnow().date()
            start = datetime.datetime.combine(today, datetime.time.min)
            cursor = __import__('utils.db').orders.find({'created_at': {'$gte': start}})
            rows=[]
            async for o in cursor:
                rows.append(f"User:{o.get('user_id')} Num:{o.get('number')} Price:₹{o.get('price')} Status:{o.get('status')}")
            await q.message.reply_text('\\n'.join(rows) or 'No sales today')

    @bot_client.on_message(filters.reply & filters.document & filters.user(OWNER_ID))
    async def handle_zip_reply(_, message):
        try:
            txt = message.reply_to_message.text.strip()
            if '|' not in txt:
                await message.reply_text('Please first send "Platform|Country|Price" then reply with ZIP.')
                return
            platform, country, price = [x.strip() for x in txt.split('|',2)]
            price = float(price)
            file_path = await message.download()
            with open(file_path, 'rb') as f:
                data = f.read()
            # Optionally upload the whole zip to S3 and keep key in uploaded docs
            s3_key = None
            try:
                if os.getenv('S3_BUCKET'):
                    key_name = f"zips/{platform}/{country}/{os.path.basename(file_path)}_{int(time.time())}"
                    await upload_bytes(key_name, data, content_type='application/zip')
                    s3_key = key_name
            except Exception as e:
                LOGGER.exception("S3 upload failed: %s", e)
            inserted = await process_uploaded_zip(platform, country, price, data, os.path.basename(file_path), message.from_user.id)
            await message.reply_text(f"Inserted {inserted} numbers for {platform}/{country} at ₹{price} each.")
            if LOG_GROUP_ID:
                await bot_client.send_message(LOG_GROUP_ID, f"Admin {message.from_user.id} added {inserted} numbers for {platform}/{country}")
        except Exception as e:
            LOGGER.exception("Error in handle_zip_reply: %s", e)
            await message.reply_text(f"Error processing zip: {e}")

    @bot_client.on_message(filters.command('deletefile') & filters.user(OWNER_ID))
    async def cmd_deletefile(_, message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Usage: /deletefile <platform> <country>")
            return
        _, platform, country = parts
        res = await files.delete_many({'platform': platform, 'country': country})
        await message.reply_text(f"Deleted {res.deleted_count} records.")
        if LOG_GROUP_ID:
            await bot_client.send_message(LOG_GROUP_ID, f"Admin {message.from_user.id} deleted {res.deleted_count} files for {platform}/{country}")

    @bot_client.on_message(filters.command('gencode') & filters.user(OWNER_ID))
    async def cmd_gencode(_, message):
        parts = message.text.split()
        if len(parts) < 4:
            await message.reply_text("Usage: /gencode <amount> <validity e.g., 5m/1h/1d> <max_users>")
            return
        _, amount_s, validity_s, max_users_s = parts
        amount = float(amount_s)
        max_users = int(max_users_s)
        now = datetime.datetime.utcnow()
        if validity_s.endswith('m'):
            delta = datetime.timedelta(minutes=int(validity_s[:-1]))
        elif validity_s.endswith('h'):
            delta = datetime.timedelta(hours=int(validity_s[:-1]))
        elif validity_s.endswith('d'):
            delta = datetime.timedelta(days=int(validity_s[:-1]))
        else:
            await message.reply_text("Invalid validity format.")
            return
        code = __import__('secrets').token_urlsafe(8).upper()
        expiry = now + delta
        await __import__('utils.db').redeem_codes.insert_one({'code': code, 'amount': amount, 'expires_at': expiry, 'max_users': max_users, 'used_by': [], 'created_at': now})
        await message.reply_text(f"Code: {code} Amount: ₹{amount} Expires: {expiry} Max users: {max_users}")
