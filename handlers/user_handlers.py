# handlers/user_handlers.py
import os, datetime, re, tempfile
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import users, files, orders, payments, otp_queue, logs
from utils.helpers import generate_qr_bytes, make_placeholder_image_bytes
from modules.payment import create_payment_link
from modules.otp_listener import listen_session_for_otp
from bson import ObjectId
from config import SUPPORT_GROUP_LINK
from modules.storage import download_to_path
from modules.logger import LOGGER

MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton('Profile', callback_data='profile'), InlineKeyboardButton('Get Number', callback_data='get_number')],
    [InlineKeyboardButton('Balance', callback_data='balance'), InlineKeyboardButton('How to Use', callback_data='howto')],
])

def register_user_handlers(bot_client):
    @bot_client.on_message(filters.command('start'))
    async def start(_, message):
        uid = message.from_user.id
        await users.update_one({'tg_id': uid}, {'$setOnInsert': {'tg_id': uid, 'username': message.from_user.username or '', 'wallet': 0.0, 'referrals': 0, 'created_at': datetime.datetime.utcnow(), 'banned': False}}, upsert=True)
        img = make_placeholder_image_bytes("Welcome to FileShopBot")
        await message.reply_photo(img, caption="Welcome! Use menu below.", reply_markup=MAIN_MENU)

    @bot_client.on_callback_query()
    async def cb(_, q):
        data = q.data
        uid = q.from_user.id
        if data == 'profile':
            user = await users.find_one({'tg_id': uid}) or {}
            bal = user.get('wallet', 0.0)
            ref_link = f"https://t.me/{(await q._client.get_me()).username}?start={uid}"
            txt = f"👤 User: {q.from_user.mention}\n💰 Wallet: ₹{bal:.2f}\n🔗 Referral: {ref_link}\n👥 Referrals: {user.get('referrals',0)}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('Check Wallet', callback_data='balance'), InlineKeyboardButton('Recharge', callback_data='recharge')],[InlineKeyboardButton('Back', callback_data='back')]])
            await q.message.edit_text(txt, reply_markup=kb)
        elif data == 'get_number':
            platforms = await files.distinct('platform', {'status':'available'})
            if not platforms:
                await q.answer('No numbers available right now. Contact support.', show_alert=True)
                return
            kb = [[InlineKeyboardButton(p, callback_data=f'plat|{p}')] for p in platforms]
            kb.append([InlineKeyboardButton('Back', callback_data='back')])
            await q.message.edit_text('Select platform:', reply_markup=InlineKeyboardMarkup(kb))
        elif data.startswith('plat|'):
            _, platform = data.split('|',1)
            countries = await files.distinct('country', {'platform': platform, 'status':'available'})
            if not countries:
                await q.answer('No countries available.', show_alert=True)
                return
            kb = [[InlineKeyboardButton(c, callback_data=f'ctry|{platform}|{c}')] for c in countries]
            kb.append([InlineKeyboardButton('Back', callback_data='get_number')])
            await q.message.edit_text('Select country:', reply_markup=InlineKeyboardMarkup(kb))
        elif data.startswith('ctry|'):
            _, platform, country = data.split('|',2)
            cursor = files.find({'platform': platform, 'country': country, 'status':'available'})
            kb = []
            docs = []
            async for d in cursor:
                docs.append(d)
                kb.append([InlineKeyboardButton(f"Buy ₹{d['price']}", callback_data=f"buy|{str(d['_id'])}")])
            if not docs:
                await q.answer('No numbers left in this category.', show_alert=True)
                return
            kb.append([InlineKeyboardButton('Back', callback_data=f'plat|{platform}')])
            await q.message.edit_text('Select number to buy:', reply_markup=InlineKeyboardMarkup(kb))
        elif data.startswith('buy|'):
            _, fid = data.split('|',1)
            doc = await files.find_one({'_id': ObjectId(fid)})
            user = await users.find_one({'tg_id': uid})
            if not doc:
                await q.answer('Number not found.', show_alert=True)
                return
            if user.get('wallet',0) < doc['price']:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton('Recharge', callback_data='recharge'), InlineKeyboardButton('Support', url=SUPPORT_GROUP_LINK)]])
                await q.message.reply_text('Your wallet has not enough balance. Minimum recharge ₹20.', reply_markup=kb)
                return
            # atomically mark sold only if available (optimistic)
            res = await files.update_one({'_id': doc['_id'], 'status': 'available'}, {'$set': {'status': 'sold'}})
            if res.modified_count == 0:
                await q.answer('Sorry, number was just taken. Try another.', show_alert=True)
                return
            # create order and deduct balance
            await users.update_one({'tg_id': uid}, {'$inc': {'wallet': -doc['price']}})
            order = {'user_id': uid, 'file_id': doc['_id'], 'number': doc['number'], 'price': doc['price'], 'status': 'purchased', 'created_at': datetime.datetime.utcnow()}
            orres = await orders.insert_one(order)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('I requested OTP', callback_data=f'otpreq|{str(orres.inserted_id)}')],[InlineKeyboardButton('Support', url=SUPPORT_GROUP_LINK)]])
            await q.message.reply_text(f"✅ Your approved number is: `{doc['number']}`\n\nNote: First request OTP on platform then click 'I requested OTP'.", reply_markup=kb)
        elif data.startswith('otpreq|'):
            _, oid = data.split('|',1)
            from bson import ObjectId as OID
            await orders.update_one({'_id': OID(oid)}, {'$set': {'status': 'otp_requested'}})
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('Read OTP', callback_data=f'readotp|{oid}')],[InlineKeyboardButton('Support', url=SUPPORT_GROUP_LINK)]])
            await q.message.reply_text('Only login in original Telegram app. When ready click Read OTP.', reply_markup=kb)
        elif data.startswith('readotp|'):
            _, oid = data.split('|',1)
            from bson import ObjectId as OID
            order = await orders.find_one({'_id': OID(oid)})
            if not order:
                await q.answer('Order not found.', show_alert=True)
                return
            filedoc = await files.find_one({'_id': order['file_id']})
            if not filedoc:
                await q.answer('Associated file not found.', show_alert=True)
                return
            # lock file using conditional update
            res = await files.update_one({'_id': filedoc['_id'], 'status': 'sold'}, {'$set': {'status': 'in_use'}})
            if res.modified_count == 0:
                await q.answer('This number is currently in use or unavailable. Try later.', show_alert=True)
                return
            await orders.update_one({'_id': order['_id']}, {'$set': {'status': 'otp_requested'}})

            session_key = filedoc.get('session_key')
            temp_path = None
            try:
                if not session_key:
                    raise Exception("No session attached for this number.")
                # if session_key looks like S3 key (contains '/'), try download
                if session_key.startswith('sessions/') or '/' in session_key:
                    tmpdir = tempfile.gettempdir()
                    temp_path = os.path.join(tmpdir, f"session_{str(filedoc['_id'])}.session")
                    try:
                        await download_to_path(session_key, temp_path)
                    except Exception:
                        # maybe session_key is already a local path; try as-is
                        if os.path.exists(session_key):
                            temp_path = session_key
                        else:
                            raise
                else:
                    # local path
                    temp_path = session_key

                # listen for OTP using that session
                otp = await listen_session_for_otp(temp_path, match_number=filedoc.get('number'), timeout=120)
                if not otp:
                    # fallback: check db otp_queue
                    otp_doc = await otp_queue.find_one({'file_id': filedoc['_id']})
                    if otp_doc:
                        otp = otp_doc.get('otp')

                if not otp:
                    # timeout: release lock
                    await files.update_one({'_id': filedoc['_id']}, {'$set': {'status': 'available'}})
                    await orders.update_one({'_id': order['_id']}, {'$set': {'status': 'otp_timeout'}})
                    await q.answer('OTP not found within timeout. Contact support.', show_alert=True)
                    return

                # send OTP
                await q.message.reply_text(f"🔐 Your login OTP is: `{otp}`")
                await orders.update_one({'_id': order['_id']}, {'$set': {'status': 'otp_sent', 'completed_at': datetime.datetime.utcnow()}})
                await files.update_one({'_id': filedoc['_id']}, {'$set': {'status': 'used'}})
                await logs.insert_one({'type': 'otp_sent', 'user_id': uid, 'order_id': order['_id'], 'file_id': filedoc['_id'], 'number': filedoc['number'], 'ts': datetime.datetime.utcnow(), 'forwarded': False})
            except Exception as e:
                # release and notify
                await files.update_one({'_id': filedoc['_id']}, {'$set': {'status': 'available'}})
                await orders.update_one({'_id': order['_id']}, {'$set': {'status': 'otp_error'}})
                LOGGER.exception("Error in OTP flow: %s", e)
                await q.answer(f'Error reading OTP: {e}', show_alert=True)
            finally:
                try:
                    if temp_path and temp_path.startswith(tempfile.gettempdir()):
                        os.remove(temp_path)
                except:
                    pass
        elif data == 'balance':
            user = await users.find_one({'tg_id': uid})
            bal = user.get('wallet',0.0)
            await q.message.edit_text(f"💰 Your balance: ₹{bal:.2f}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Recharge', callback_data='recharge'), InlineKeyboardButton('Back', callback_data='back')]]))
        elif data == 'recharge':
            await q.message.edit_text('Enter amount to recharge (minimum ₹20).')
        elif data == 'howto':
            await q.message.edit_text("How to use:\n1. Recharge wallet\n2. Get Number → select platform → country → buy\n3. Request OTP → click 'I requested OTP' → Read OTP")
        elif data == 'back':
            await q.message.edit_text('Main Menu', reply_markup=MAIN_MENU)

    @bot_client.on_message(filters.text & ~filters.command(['start']))
    async def text_handler(_, message):
        text = message.text.strip()
        uid = message.from_user.id
        # numeric amount => create payment link
        if re.fullmatch(r'\d+', text):
            amount = int(text)
            if amount < 20:
                await message.reply_text('Please send minimum amount ₹20.')
                return
            receipt = f"recharge_{uid}_{int(__import__('time').time())}"
            try:
                payment_link = await create_payment_link(amount, receipt, uid, description=f"Wallet Recharge for {uid}")
            except Exception as e:
                LOGGER.exception("create_payment_link failed: %s", e)
                await message.reply_text('Failed to create payment link. Try later.')
                return
            pay_url = payment_link.get('short_url') or payment_link.get('short_link') or payment_link.get('long_url') or ''
            qr = generate_qr_bytes(pay_url)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('Payment Done ✅', callback_data=f'paydone|{payment_link.get(\"id\")}')],[InlineKeyboardButton('Support', url=SUPPORT_GROUP_LINK)]])
            await message.reply_photo(qr, caption=f"Scan QR or open link:\n{pay_url}\nAfter payment, wallet will be updated automatically.", reply_markup=kb)
            return
        # Redeem code handling
        if text.isalnum() and len(text) <= 20:
            rc = await redeem_codes.find_one({'code': text})
            if not rc:
                await message.reply_text('Invalid code.')
                return
            now = datetime.datetime.utcnow()
            if rc.get('expires_at') and rc['expires_at'] < now:
                await message.reply_text('Code expired.')
                return
            used = rc.get('used_by',[])
            if uid in used:
                await message.reply_text('You already used this code.')
                return
            if len(used) >= rc.get('max_users',1):
                await message.reply_text('Code usage limit reached.')
                return
            await users.update_one({'tg_id': uid}, {'$inc': {'wallet': rc['amount']}})
            await redeem_codes.update_one({'_id': rc['_id']}, {'$addToSet': {'used_by': uid}})
            await message.reply_text(f"₹{rc['amount']} added to wallet.")
            return
        # treat as UTR manual input (store for admin/manual verify)
        m = re.fullmatch(r'([A-Za-z0-9-_]{6,})', text)
        if m:
            await manual_utrs.insert_one({'tg_id': uid, 'utr': text, 'ts': datetime.datetime.utcnow()})
            await message.reply_text('UTR received. We will verify and credit if matched.')
            return
