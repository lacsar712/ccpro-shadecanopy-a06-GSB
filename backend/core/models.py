import datetime

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def time_ranges_overlap(start_a, end_a, start_b, end_b):
    """半开区间 [start, end) 是否相交；跨午夜时段两端拆开比较。"""
    if start_a < end_a:
        ranges_a = [(start_a, end_a)]
    else:
        # 跨午夜：[start, 24:00) ∪ [00:00, end)
        ranges_a = [(start_a, datetime.time.max), (datetime.time.min, end_a)]
    if start_b < end_b:
        ranges_b = [(start_b, end_b)]
    else:
        ranges_b = [(start_b, datetime.time.max), (datetime.time.min, end_b)]
    for sa, ea in ranges_a:
        for sb, eb in ranges_b:
            if sa < eb and sb < ea:
                return True
    return False


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
    """通风窗开启时段（每日时刻，按温室配置），与分区气候写入路径联锁。"""

    greenhouse = models.ForeignKey(
        Greenhouse, on_delete=models.CASCADE, related_name="ventilation_slots"
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    co2_limit_ppm = models.PositiveIntegerField(
        default=1000, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["greenhouse_id", "start_time"]

    def __str__(self):
        state = "启用" if self.is_active else "停用"
        return f"通风时段#{self.id} {self.greenhouse_id} {self.start_time}-{self.end_time} ({state})"

    @property
    def wraps_midnight(self):
        return self.start_time >= self.end_time

    def covers_time(self, value):
        """时刻 value 是否落在本时段内；跨午夜按 [start,24:00)∪[00:00,end) 处理。"""
        if not self.wraps_midnight:
            return self.start_time <= value < self.end_time
        return value >= self.start_time or value < self.end_time

    def overlaps_with(self, start_time, end_time):
        return time_ranges_overlap(
            self.start_time, self.end_time, start_time, end_time
        )

    @staticmethod
    def active_slots_for(greenhouse, value):
        """该温室在 value 时刻覆盖采样时刻的启用时段（取 CO₂ 上限最严者由调用方决定）。"""
        return [
            slot
            for slot in VentilationSlot.objects.filter(
                greenhouse=greenhouse, is_active=True
            )
            if slot.covers_time(value)
        ]
