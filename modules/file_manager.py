import io, zipfile, os, tempfile, datetime
from utils.helpers import parse_manifest_from_zip_bytes
from modules.storage import upload_bytes
from utils.db import files
import time

async def process_uploaded_zip(platform: str, country: str, price: float, file_bytes: bytes, orig_filename: str, uploader_id: int):
    """
    Parse manifest, upload session files, assign sessions to numbers, insert into files collection.
    Expects manifest.json inside ZIP. Looks for session files (.session).
    """
    z = zipfile.ZipFile(io.BytesIO(file_bytes))
    manifest = parse_manifest_from_zip_bytes(file_bytes)
    session_files = [name for name in z.namelist() if name.lower().endswith('.session')]
    sessions_map = {}
    if 'sessions_map.json' in z.namelist():
        try:
            sessions_map = json.loads(z.read('sessions_map.json').decode())
        except:
            sessions_map = {}

    # upload each session file to S3 (if configured) or save locally
    session_key_map = {}
    for sfn in session_files:
        content = z.read(sfn)
        key_name = f"sessions/{platform}/{country}/{os.path.basename(sfn)}_{int(time.time())}"
        try:
            await upload_bytes(key_name, content, content_type='application/octet-stream')
            session_key_map[sfn] = key_name
        except Exception:
            # fallback: save locally
            tmp = tempfile.gettempdir()
            local_path = os.path.join(tmp, os.path.basename(sfn))
            with open(local_path, 'wb') as f:
                f.write(content)
            session_key_map[sfn] = local_path

    inserted = 0
    idx = 0
    for entry in manifest:
        number = entry.get('number')
        country_code = entry.get('country_code', '')
        meta = entry.get('meta', '')
        # map session via sessions_map
        sess_for_number = None
        if sessions_map:
            for sfn, nums in sessions_map.items():
                if number in nums:
                    sess_for_number = session_key_map.get(sfn)
                    break
        if not sess_for_number and session_files:
            chosen = session_files[idx % len(session_files)]
            sess_for_number = session_key_map.get(chosen)
        doc = {
            'platform': platform,
            'country': country,
            'country_code': country_code,
            'number': number,
            'price': price,
            'meta': meta,
            's3_key': None,   # optional original zip s3 key
            'session_key': sess_for_number,
            'status': 'available',
            'added_by': uploader_id,
            'added_at': datetime.datetime.utcnow()
        }
        await files.insert_one(doc)
        inserted += 1
        idx += 1
    return inserted
