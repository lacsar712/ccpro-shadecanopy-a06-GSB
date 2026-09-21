from rest_framework import status
from rest_framework.exceptions import APIException


class ConflictError(APIException):
    """同温室通风时段相交等业务冲突 → HTTP 409。"""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "数据冲突"
    default_code = "conflict"
