from .models import VentilationSlot


def active_ventilation_slot_count(greenhouse_id=None):
    """启用通风时段数——列表 / 单条 / 仪表盘三处唯一数据源。

    不传 greenhouse_id 时统计全量启用时段；传入时只统计该温室。
    """
    qs = VentilationSlot.objects.filter(is_active=True)
    if greenhouse_id is not None:
        qs = qs.filter(greenhouse_id=greenhouse_id)
    return qs.count()
