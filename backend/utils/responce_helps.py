from datetime import datetime, timezone
from uuid import uuid4


def response_success(**kwargs) -> dict:
    return {
        "status": "success",
        "data": {**kwargs},
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": str(uuid4())
        }
    }

def response_error(code: str = '', message: str = '', details: dict = {}, **kwargs) -> dict:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "details": details,
            **kwargs
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": str(uuid4())
        }
    }