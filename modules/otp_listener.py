import os, re, asyncio, datetime
from pyrogram import Client, filters
from config import API_ID, API_HASH, SESSION_FOLDER

async def listen_session_for_otp(session_path: str, match_number: str = None, timeout: int = 90):
    """
    session_path: absolute path to .session file (or session name accessible to Pyrogram)
    match_number: optional substring used to match OTP messages
    timeout: seconds to wait
    """
    if not os.path.exists(session_path):
        # try in SESSION_FOLDER
        alt = os.path.join(SESSION_FOLDER, os.path.basename(session_path))
        if os.path.exists(alt):
            session_path = alt
        else:
            return None

    # Pyrogram client - pass session_name as path string; ensure API_ID/API_HASH from env
    api_id = API_ID
    api_hash = API_HASH
    if not api_id or not api_hash:
        return None

    client = Client(session_name=session_path, api_id=api_id, api_hash=api_hash)
    await client.start()
    # check recent history in 'me'
    async for msg in client.iter_history('me', limit=50):
        text = msg.text or ''
        if match_number and match_number not in text:
            pass
        m = re.search(r'(\d{4,8})', text)
        if m:
            found = m.group(1)
            await client.stop()
            return found

    # wait for incoming messages
    found = None
    event = asyncio.Event()

    @client.on_message(filters.private & filters.incoming)
    async def _on_msg(c, msg):
        nonlocal found
        txt = msg.text or ''
        if match_number and match_number not in txt:
            pass
        m = re.search(r'(\d{4,8})', txt)
        if m:
            found = m.group(1)
            event.set()

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass

    await client.stop()
    return found
