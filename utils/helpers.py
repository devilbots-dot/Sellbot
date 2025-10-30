import io, zipfile, json, os
from PIL import Image, ImageDraw, ImageFont
import qrcode

def parse_manifest_from_zip_bytes(bytes_data):
    z = zipfile.ZipFile(io.BytesIO(bytes_data))
    namelist = z.namelist()
    if 'manifest.json' in namelist:
        raw = z.read('manifest.json')
        return json.loads(raw)
    if 'numbers.txt' in namelist:
        raw = z.read('numbers.txt').decode()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        out = []
        for ln in lines:
            parts = [p.strip() for p in ln.split(',')]
            out.append({'number': parts[0], 'country_code': parts[1] if len(parts)>1 else '', 'meta': parts[2] if len(parts)>2 else ''})
        return out
    for name in namelist:
        if name.lower().endswith('.txt'):
            raw = z.read(name).decode()
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            out=[]
            for ln in lines:
                parts=[p.strip() for p in ln.split(',')]
                out.append({'number':parts[0], 'country_code': parts[1] if len(parts)>1 else '', 'meta': parts[2] if len(parts)>2 else ''})
            if out:
                return out
    return []

def generate_qr_bytes(data: str):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def make_placeholder_image_bytes(text='Welcome'):
    img = Image.new('RGB', (900,400), color=(30,30,30))
    d = ImageDraw.Draw(img)
    try:
        fpath = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = ImageFont.truetype(fpath, 36)
    except:
        font = None
    d.text((40,160), text, fill=(255,255,255), font=font)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
