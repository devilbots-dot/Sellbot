# modules/payment.py
import os, asyncio, base64, hmac, hashlib
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from utils.db import payments, users, logs
from concurrent.futures import ThreadPoolExecutor
import razorpay

executor = ThreadPoolExecutor(max_workers=4)
rz = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

async def create_payment_link(amount_inr: float, receipt: str, user_id: int, description: str="Wallet Recharge"):
    amount_paise = int(round(amount_inr * 100))
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": receipt,
        "description": description,
        "customer": {},
        "notify": {"sms": False, "email": False},
        "reminder_enable": False
    }
    loop = asyncio.get_event_loop()
    payment_link = await loop.run_in_executor(executor, lambda: rz.payment_link.create(payload))
    await payments.insert_one({'user_id': user_id, 'amount': amount_inr, 'razorpay_link_id': payment_link.get('id'), 'short_url': payment_link.get('short_url') or payment_link.get('short_link') or payment_link.get('long_url'), 'status': 'link_created', 'created_at': __import__('datetime').datetime.utcnow()})
    return payment_link

async def handle_razorpay_payload(payload: dict):
    event = payload.get('event')
    if event in ('payment.captured','payment.authorized'):
        payment = payload.get('payload', {}).get('payment', {}).get('entity', {})
        payment_id = payment.get('id')
        order_id = payment.get('order_id')
        amount = (payment.get('amount') or 0) / 100.0
        doc = None
        if order_id:
            doc = await payments.find_one({'razorpay_order_id': order_id})
        if not doc:
            doc = await payments.find_one({'razorpay_payment_id': payment_id})
        if not doc:
            await payments.insert_one({'user_id': None, 'amount': amount, 'razorpay_payment_id': payment_id, 'status': 'captured','created_at': __import__('datetime').datetime.utcnow()})
            return
        await payments.update_one({'_id': doc['_id']}, {'$set': {'razorpay_payment_id': payment_id, 'status': 'captured'}})
        user_id = doc.get('user_id')
        if user_id:
            await users.update_one({'tg_id': user_id}, {'$inc': {'wallet': amount}})
            await logs.insert_one({'type': 'payment_captured', 'user_id': user_id, 'amount': amount, 'payment_id': payment_id, 'order_id': order_id, 'ts': __import__('datetime').datetime.utcnow(), 'forwarded': False})
    elif event in ('payment.link.paid','payment_link.paid'):
        link = payload.get('payload', {}).get('payment_link', {}).get('entity', {})
        link_id = link.get('id')
        amount = (link.get('amount') or 0)/100.0
        doc = await payments.find_one({'razorpay_link_id': link_id})
        if not doc:
            await payments.insert_one({'user_id': None, 'amount': amount, 'razorpay_link_id': link_id, 'status': 'link_paid', 'created_at': __import__('datetime').datetime.utcnow()})
            return
        await payments.update_one({'_id': doc['_id']}, {'$set': {'status': 'link_paid'}})
        user_id = doc.get('user_id')
        if user_id:
            await users.update_one({'tg_id': user_id}, {'$inc': {'wallet': amount}})
            await logs.insert_one({'type': 'payment_link_paid', 'user_id': user_id, 'amount': amount, 'link_id': link_id, 'ts': __import__('datetime').datetime.utcnow(), 'forwarded': False})
