from django.utils.timezone import localtime
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .exceptions import Conflict
from .models import (
    ClimateLog,
    Greenhouse,
    IrrigationCycle,
    VentilationSlot,
    Zone,
    enabled_vent_slot_count,
)


class GreenhouseSerializer(serializers.ModelSerializer):
    areaM2 = serializers.DecimalField(
        source="area_m2", max_digits=10, decimal_places=2
    )
    zoneCount = serializers.SerializerMethodField()

    class Meta:
        model = Greenhouse
        fields = (
            "id",
            "name",
            "location",
            "areaM2",
            "notes",
            "zoneCount",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "zoneCount", "created_at", "updated_at")

    def get_zoneCount(self, obj):
        if hasattr(obj, "zone_count"):
            return obj.zone_count
        return obj.zones.count()


class ZoneSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    zoneCode = serializers.CharField(source="zone_code")
    cropName = serializers.CharField(source="crop_name", allow_blank=True, required=False)
    greenhouseName = serializers.CharField(source="greenhouse.name", read_only=True)

    class Meta:
        model = Zone
        fields = (
            "id",
            "greenhouseId",
            "greenhouseName",
            "zoneCode",
            "cropName",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "greenhouseName", "created_at", "updated_at")

    def validate(self, attrs):
        greenhouse = attrs.get("greenhouse") or getattr(self.instance, "greenhouse", None)
        zone_code = attrs.get("zone_code") or getattr(self.instance, "zone_code", None)
        if greenhouse and zone_code:
            qs = Zone.objects.filter(greenhouse=greenhouse, zone_code=zone_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"zoneCode": "同一温室内分区编码必须唯一"}
                )
        return attrs


class ClimateLogSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    recordedAt = serializers.DateTimeField(source="recorded_at")
    tempC = serializers.DecimalField(source="temp_c", max_digits=5, decimal_places=2)
    humidityPct = serializers.DecimalField(
        source="humidity_pct", max_digits=5, decimal_places=2
    )
    parUmol = serializers.DecimalField(
        source="par_umol", max_digits=8, decimal_places=2, required=False
    )
    co2Ppm = serializers.DecimalField(
        source="co2_ppm", max_digits=8, decimal_places=2, required=False
    )
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )

    class Meta:
        model = ClimateLog
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "recordedAt",
            "tempC",
            "humidityPct",
            "parUmol",
            "co2Ppm",
            "created_at",
        )
        read_only_fields = ("id", "zoneCode", "greenhouseName", "created_at")

    def validate_humidityPct(self, value):
        if value < 20 or value > 100:
            raise serializers.ValidationError("湿度须在 20～100 之间")
        return value

    def validate(self, attrs):
        """写路径联锁：采样时刻被启用通风时段覆盖时，CO₂ 不得超过该时段上限。

        命中越界 → 400，中文信息并带通风时段编号。
        """
        attrs = super().validate(attrs)
        zone = attrs.get("zone") or getattr(self.instance, "zone", None)
        recorded_at = attrs.get("recorded_at") or getattr(
            self.instance, "recorded_at", None
        )
        co2_ppm = attrs.get("co2_ppm")
        if co2_ppm is None and self.instance is not None:
            co2_ppm = self.instance.co2_ppm
        if zone is None or recorded_at is None or co2_ppm is None:
            return attrs

        # 每日时段按项目时区（Asia/Shanghai）的当日墙钟时刻解释。
        local_time = localtime(recorded_at).time()
        # 同温室启用时段互不相交（写入时 409 保证），故至多一个覆盖该时刻。
        for slot in VentilationSlot.objects.filter(
            greenhouse_id=zone.greenhouse_id, is_enabled=True
        ):
            if slot.covers_time(local_time) and co2_ppm > slot.co2_limit_ppm:
                raise serializers.ValidationError(
                    {
                        "co2Ppm": (
                            f"通风时段 #{slot.id}（{slot.start_time:%H:%M}-"
                            f"{slot.end_time:%H:%M}）覆盖该采样时刻，二氧化碳 "
                            f"{co2_ppm} ppm 超过上限 {slot.co2_limit_ppm} ppm"
                        )
                    }
                )
        return attrs


class IrrigationCycleSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    startAt = serializers.DateTimeField(source="start_at")
    durationMin = serializers.IntegerField(source="duration_min")
    waterLiters = serializers.DecimalField(
        source="water_liters", max_digits=10, decimal_places=2
    )
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )

    class Meta:
        model = IrrigationCycle
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "startAt",
            "durationMin",
            "waterLiters",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "zoneCode",
            "greenhouseName",
            "created_at",
            "updated_at",
        )


class VentilationSlotSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    startTime = serializers.TimeField(source="start_time")
    endTime = serializers.TimeField(source="end_time")
    co2LimitPpm = serializers.IntegerField(source="co2_limit_ppm", min_value=0)
    isEnabled = serializers.BooleanField(source="is_enabled", required=False)
    greenhouseName = serializers.CharField(source="greenhouse.name", read_only=True)
    activeVentCount = serializers.SerializerMethodField()

    class Meta:
        model = VentilationSlot
        fields = (
            "id",
            "greenhouseId",
            "greenhouseName",
            "startTime",
            "endTime",
            "co2LimitPpm",
            "isEnabled",
            "activeVentCount",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "greenhouseName",
            "activeVentCount",
            "created_at",
            "updated_at",
        )

    def get_activeVentCount(self, obj):
        """该温室启用时段数。列表走批量 map，单条直接计数，二者口径同源。"""
        counts = self.context.get("active_vent_counts")
        if counts is not None:
            return counts.get(obj.greenhouse_id, 0)
        return enabled_vent_slot_count(obj.greenhouse_id)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        greenhouse = attrs.get("greenhouse") or getattr(
            self.instance, "greenhouse", None
        )
        start_time = attrs.get("start_time") or getattr(
            self.instance, "start_time", None
        )
        end_time = attrs.get("end_time") or getattr(self.instance, "end_time", None)

        if start_time is not None and end_time is not None:
            if start_time == end_time:
                raise serializers.ValidationError(
                    {"endTime": "结束时刻不得等于开始时刻（跨午夜请令结束时刻小于开始时刻）"}
                )
            # 同温室时段相交 → 409（含与停用时段，避免日后重新启用即相撞）。
            candidate = VentilationSlot(
                start_time=start_time, end_time=end_time
            )
            qs = VentilationSlot.objects.filter(greenhouse=greenhouse)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            for other in qs:
                if candidate.intersects(other):
                    raise Conflict(
                        f"与同温室时段 #{other.id}"
                        f"（{other.start_time:%H:%M}-{other.end_time:%H:%M}）相交"
                    )

        # 停用仅管理员：仅当本次写入使状态“变为停用”时受限——
        # 新建即停用、或启用时段被改为停用 → 非管理员 403；
        # 编辑一条本已停用的时段（状态不变）不拦，便于修改其余字段。
        if attrs.get("is_enabled") is False:
            currently_enabled = self.instance.is_enabled if self.instance else False
            will_disable = self.instance is None or currently_enabled
            request = self.context.get("request")
            user = getattr(request, "user", None)
            if will_disable and (user is None or user.role != "admin"):
                raise PermissionDenied("仅管理员可停用通风时段")
        return attrs
