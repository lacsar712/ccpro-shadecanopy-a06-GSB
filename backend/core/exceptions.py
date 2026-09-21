from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """同温室通风时段相交等冲突 → HTTP 409。"""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "数据冲突"
    default_code = "conflict"
