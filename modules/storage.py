import os, boto3
from config import S3_ENDPOINT, S3_KEY, S3_SECRET, S3_BUCKET, S3_REGION
from concurrent.futures import ThreadPoolExecutor
import asyncio

_executor = ThreadPoolExecutor(max_workers=4)

def _get_client():
    kwargs = {}
    if S3_ENDPOINT:
        kwargs['endpoint_url'] = S3_ENDPOINT
    session = boto3.session.Session()
    client = session.client('s3', aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET, region_name=S3_REGION, **kwargs)
    return client

async def upload_bytes(key: str, data: bytes, content_type: str='application/octet-stream'):
    loop = asyncio.get_event_loop()
    client = _get_client()
    def _u():
        client.put_object(Bucket=S3_BUCKET, Key=key, Body=data, ContentType=content_type)
        return True
    return await loop.run_in_executor(_executor, _u)

async def download_to_path(key: str, dest_path: str):
    loop = asyncio.get_event_loop()
    client = _get_client()
    def _d():
        client.download_file(S3_BUCKET, key, dest_path)
        return True
    return await loop.run_in_executor(_executor, _d)

async def generate_presigned_get(key: str, expires_in: int=3600):
    loop = asyncio.get_event_loop()
    client = _get_client()
    def _g():
        return client.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': key}, ExpiresIn=expires_in)
    return await loop.run_in_executor(_executor, _g)
