from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import User


class VentilationSlotPermission(BasePermission):
    """通风时段权限：

    - 已登录用户均可查看；
    - 管理员可全部操作（含停用 / 删除）；
    - 种植员可新建时段、调整时刻与 CO₂ 上限，但不得停用；
    - 停用的最终 403 拦截在序列化器内（按 is_active 翻转判定）。
    """

    message = "无权操作通风时段（种植员仅可新建 / 编辑，停用仅管理员）"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if user.role == User.ROLE_ADMIN:
            return True
        if user.role == User.ROLE_GROWER and request.method in ("POST", "PUT", "PATCH"):
            return True
        return False
