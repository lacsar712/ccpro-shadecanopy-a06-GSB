from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from accounts.models import User

from .exceptions import ConflictError
from .models import ClimateLog, Greenhouse, IrrigationCycle, VentilationSlot, Zone


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


class VentilationSlotSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    startTime = serializers.TimeField(source="start_time", format="%H:%M")
    endTime = serializers.TimeField(source="end_time", format="%H:%M")
    co2LimitPpm = serializers.IntegerField(source="co2_limit_ppm")
    isActive = serializers.BooleanField(source="is_active", required=False)
    greenhouseName = serializers.CharField(source="greenhouse.name", read_only=True)

    class Meta:
        model = VentilationSlot
        fields = (
            "id",
            "greenhouseId",
            "greenhouseName",
            "startTime",
            "endTime",
            "co2LimitPpm",
            "isActive",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "greenhouseName", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        greenhouse = attrs.get("greenhouse") or getattr(
            self.instance, "greenhouse", None
        )
        start_time = attrs.get("start_time") or getattr(
            self.instance, "start_time", None
        )
        end_time = attrs.get("end_time") or getattr(self.instance, "end_time", None)

        if start_time and end_time and start_time == end_time:
            raise serializers.ValidationError(
                {"endTime": "结束时刻须晚于（跨午夜则早于）开始时刻，二者不得相同"}
            )

        # 停用（含以停用状态新建、由启用改为停用）仅管理员；
        # 种植员也不得自行重新启用既有停用时态——is_active 只能保持原值。
        if user is not None and user.role != User.ROLE_ADMIN:
            submitted_active = attrs.get("is_active")
            if self.instance is None:
                if submitted_active is False:
                    raise PermissionDenied("通风时段停用仅管理员可操作")
            else:
                current_active = self.instance.is_active
                effective_active = (
                    submitted_active if submitted_active is not None else current_active
                )
                if effective_active != current_active:
                    raise PermissionDenied("通风时段启用 / 停用变更仅管理员可操作")

        # 同温室时段相交 → 409（停用时段同样占位，避免日后重新启用即冲突）
        if greenhouse and start_time and end_time:
            qs = VentilationSlot.objects.filter(greenhouse=greenhouse)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            for slot in qs:
                if slot.overlaps_with(start_time, end_time):
                    raise ConflictError(
                        f"与通风时段 #{slot.id}（{slot.start_time:%H:%M}-"
                        f"{slot.end_time:%H:%M}）相交，同温室时段不得重叠"
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
        zone = attrs.get("zone") or getattr(self.instance, "zone", None)
        recorded_at = attrs.get("recorded_at") or getattr(
            self.instance, "recorded_at", None
        )
        co2_ppm = attrs.get("co2_ppm")
        if co2_ppm is None and self.instance is not None:
            co2_ppm = self.instance.co2_ppm

        # 写路径联锁：采样时刻被启用通风时段覆盖时，CO₂ 不得超过该时段上限。
        if zone and recorded_at and co2_ppm is not None:
            sample_time = timezone.localtime(recorded_at).time()
            covering = VentilationSlot.active_slots_for(zone.greenhouse, sample_time)
            violated = [s for s in covering if co2_ppm > s.co2_limit_ppm]
            if violated:
                slot = min(violated, key=lambda s: s.co2_limit_ppm)
                raise serializers.ValidationError(
                    {
                        "co2Ppm": (
                            f"CO₂ {co2_ppm} ppm 超出启用通风时段 #{slot.id}"
                            f"（{slot.start_time:%H:%M}-{slot.end_time:%H:%M}）"
                            f"的二氧化碳上限 {slot.co2_limit_ppm} ppm"
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
