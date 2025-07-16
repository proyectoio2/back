import boto3
from typing import Optional

from src.storage.config import get_storage_config


class SpacesClient:

    def __init__(self):
        self._client = None
        self._config = get_storage_config()
    
    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                's3',
                endpoint_url=self._config.endpoint,
                region_name=self._config.region,
                aws_access_key_id=self._config.key,
                aws_secret_access_key=self._config.secret
            )
        return self._client
    
    def put_object(self, key: str, body, content_type: Optional[str] = None, acl: str = "public-read"):
        params = {
            'Bucket': self._config.bucket,
            'Key': key,
            'Body': body,
            'ACL': acl
        }
        
        if content_type:
            params['ContentType'] = content_type
            
        return self.client.put_object(**params)
    
    def get_object(self, key: str):
        return self.client.get_object(
            Bucket=self._config.bucket,
            Key=key
        )
    
    def delete_object(self, key: str):
        return self.client.delete_object(
            Bucket=self._config.bucket,
            Key=key
        )
    
    def list_objects(self, prefix: str = "", delimiter: str = "/"):
        return self.client.list_objects_v2(
            Bucket=self._config.bucket,
            Prefix=prefix,
            Delimiter=delimiter
        )

spaces_client = SpacesClient()