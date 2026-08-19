from typing import Any

from fastapi import Request


def response(request: Request, data: Any) -> dict[str, Any]:
    return {"request_id": request.state.request_id, "data": data}
