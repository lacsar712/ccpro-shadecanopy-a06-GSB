from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count


class Greenhouse(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Zone(models.Model):
    STATUS_IDLE = "idle"
    STATUS_GROWING = "growing"
    STATUS_FALLOW = "fallow"
    STATUS_CHOICES = [
        (STATUS_IDLE, "空闲"),
        (STATUS_GROWING, "在种"),
        (STATUS_FALLOW, "休耕"),
    ]

    greenhouse = models.ForeignKey(
        Greenhouse, on_delete=models.CASCADE, related_name="zones"
    )
    zone_code = models.CharField(max_length=40)
    crop_name = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_IDLE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["greenhouse_id", "zone_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["greenhouse", "zone_code"],
                name="uniq_zone_code_per_greenhouse",
            )
        ]

    def __str__(self):
        return f"{self.greenhouse.name}/{self.zone_code}"


class ClimateLog(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="climate_logs")
    recorded_at = models.DateTimeField()
    temp_c = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(20), MaxValueValidator(100)],
    )
    par_umol = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    co2_ppm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Climate@{self.zone_id} {self.recorded_at}"


class IrrigationCycle(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "已排程"),
        (STATUS_RUNNING, "进行中"),
        (STATUS_DONE, "已完成"),
        (STATUS_SKIPPED, "已跳过"),
    ]

    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="irrigation_cycles"
    )
    start_at = models.DateTimeField()
    duration_min = models.PositiveIntegerField(default=30)
    water_liters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]

    def __str__(self):
        return f"Irrig@{self.zone_id} {self.start_at} ({self.status})"


class VentilationSlot(models.Model):
    """通风窗时段：挂温室，按每日时刻定义；可跨午夜（start_time > end_time）。"""

    greenhouse = models.ForeignKey(
        Greenhouse, on_delete=models.CASCADE, related_name="ventilation_slots"
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    co2_limit_ppm = models.PositiveIntegerField()
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["greenhouse_id", "start_time"]

    def __str__(self):
        state = "启用" if self.is_enabled else "停用"
        return f"Vent#{self.id} {self.greenhouse_id} {self.start_time}-{self.end_time} ({state})"

    @staticmethod
    def _time_in_range(start, end, t):
        """半开区间 [start, end)；start > end 视为跨午夜区间。"""
        if start < end:
            return start <= t < end
        if start > end:
            return t >= start or t < end
        return False

    def covers_time(self, t):
        """采样时刻 t（datetime.time）是否被本时段覆盖。"""
        return self._time_in_range(self.start_time, self.end_time, t)

    def intersects(self, other):
        """两个每日时段是否相交（半开，首尾相接不算相交）。"""
        return self._time_in_range(
            self.start_time, self.end_time, other.start_time
        ) or self._time_in_range(other.start_time, other.end_time, self.start_time)


def enabled_vent_slot_counts(greenhouse_ids=None):
    """批量返回 {温室id: 启用时段数}，是各接口启用时段数的唯一数据源。"""
    qs = VentilationSlot.objects.filter(is_enabled=True)
    if greenhouse_ids is not None:
        qs = qs.filter(greenhouse_id__in=greenhouse_ids)
    rows = qs.values("greenhouse_id").annotate(n=Count("id"))
    return {row["greenhouse_id"]: row["n"] for row in rows}


def enabled_vent_slot_count(greenhouse_id=None):
    """启用通风时段数：可按温室统计，无参则为全温室总数。

    通风时段列表 / 单条接口与仪表盘均取自本系列函数，保证两边同源；
    只改其中一边不会改变口径。
    """
    if greenhouse_id is None:
        return VentilationSlot.objects.filter(is_enabled=True).count()
    return enabled_vent_slot_counts([greenhouse_id]).get(greenhouse_id, 0)
