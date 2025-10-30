import os, hmac, hashlib, base64, json
from fastapi import FastAPI, Request, HTTPException
from config import RAZORPAY_WEBHOOK_SECRET
from modules.payment import handle_razorpay_payload

app = FastAPI()

@app.post('/webhook/razorpay')
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get('X-Razorpay-Signature') or request.headers.get('x-razorpay-signature')
    if not signature or not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail='Missing signature or secret')
    # verify: Razorpay signature is base64(HMAC_SHA256(body, secret))
    digest = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail='Invalid signature')
    payload = json.loads(body)
    await handle_razorpay_payload(payload)
    return {'status': 'ok'}
