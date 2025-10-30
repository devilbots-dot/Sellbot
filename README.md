# FileSellingBot — Full Integrated

Features:
- Pyrogram Telegram bot (bot token)
- FastAPI webhook for Razorpay payment events
- Razorpay Payment Link creation + auto wallet credit
- MongoDB (motor) async storage
- S3 upload + presigned URLs (optional)
- Admin ZIP upload: manifest.json + session files -> numbers mapped to sessions
- OTP listener: uses session files to read OTP and send to buyer
- Logs forwarded to owner/group

## Quick start
1. Copy `.env.example` to `.env` and fill values.
2. `pip install -r requirements.txt`
3. Create folders: `mkdir sessions` and `mkdir files`
4. Run locally:
   - `uvicorn webhook:app --reload --port 8000`
   - `python main.py`
5. For Heroku: push repo, set config vars, deploy.

## Admin flow to add numbers
1. Send a message to bot: `Platform|Country|Price` (e.g. `WhatsApp|India|50`)
2. Reply to that message with a ZIP file (document) containing:
   - `manifest.json` (array of objects {number, country_code, meta})
   - session files (.session) and optional `sessions_map.json`
3. Bot will parse and add numbers; each number will have `session_key` linking to associated session.

## Webhook
Set Razorpay webhook URL to `https://<your-app>/webhook/razorpay` and webhook secret to env `RAZORPAY_WEBHOOK_SECRET`.
