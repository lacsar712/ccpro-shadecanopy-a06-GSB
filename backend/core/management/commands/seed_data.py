from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ClimateLog, Greenhouse, IrrigationCycle, VentilationSlot, Zone
from core.serializers import ClimateLogSerializer

User = get_user_model()


class Command(BaseCommand):
    help = "初始化演示账号与温室气候/轮灌种子数据"

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@shadecanopy.local",
                "role": User.ROLE_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("123456")
        admin.role = User.ROLE_ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self.stdout.write(self.style.SUCCESS(f"admin {'created' if created else 'updated'}"))

        grower, created = User.objects.get_or_create(
            username="grower",
            defaults={
                "email": "grower@shadecanopy.local",
                "role": User.ROLE_GROWER,
            },
        )
        grower.set_password("123456")
        grower.role = User.ROLE_GROWER
        grower.save()
        self.stdout.write(self.style.SUCCESS(f"grower {'created' if created else 'updated'}"))

        if Greenhouse.objects.exists():
            self.stdout.write("温室数据已存在，跳过业务种子写入。")
            return

        g1 = Greenhouse.objects.create(
            name="东坡一号棚",
            location="东区 A 排",
            area_m2=Decimal("1200.00"),
            notes="番茄与叶菜混作示范棚",
        )
        g2 = Greenhouse.objects.create(
            name="西篱二号棚",
            location="西区 B 排",
            area_m2=Decimal("860.50"),
            notes="草莓高架栽培",
        )

        z1 = Zone.objects.create(
            greenhouse=g1, zone_code="A-01", crop_name="樱桃番茄", status=Zone.STATUS_GROWING
        )
        z2 = Zone.objects.create(
            greenhouse=g1, zone_code="A-02", crop_name="油麦菜", status=Zone.STATUS_GROWING
        )
        z3 = Zone.objects.create(
            greenhouse=g1, zone_code="A-03", crop_name="", status=Zone.STATUS_IDLE
        )
        z4 = Zone.objects.create(
            greenhouse=g2, zone_code="B-01", crop_name="红颜草莓", status=Zone.STATUS_GROWING
        )
        z5 = Zone.objects.create(
            greenhouse=g2, zone_code="B-02", crop_name="章姬草莓", status=Zone.STATUS_FALLOW
        )

        now = timezone.now()
        ClimateLog.objects.bulk_create(
            [
                ClimateLog(
                    zone=z1,
                    recorded_at=now - timedelta(hours=2),
                    temp_c=Decimal("24.50"),
                    humidity_pct=Decimal("68.00"),
                    par_umol=Decimal("420.00"),
                    co2_ppm=Decimal("650.00"),
                ),
                ClimateLog(
                    zone=z1,
                    recorded_at=now - timedelta(hours=6),
                    temp_c=Decimal("22.10"),
                    humidity_pct=Decimal("72.50"),
                    par_umol=Decimal("180.00"),
                    co2_ppm=Decimal("700.00"),
                ),
                ClimateLog(
                    zone=z2,
                    recorded_at=now - timedelta(hours=3),
                    temp_c=Decimal("23.80"),
                    humidity_pct=Decimal("70.00"),
                    par_umol=Decimal("390.00"),
                    co2_ppm=Decimal("620.00"),
                ),
                ClimateLog(
                    zone=z4,
                    recorded_at=now - timedelta(hours=1),
                    temp_c=Decimal("21.20"),
                    humidity_pct=Decimal("75.00"),
                    par_umol=Decimal("350.00"),
                    co2_ppm=Decimal("580.00"),
                ),
                ClimateLog(
                    zone=z4,
                    recorded_at=now - timedelta(hours=20),
                    temp_c=Decimal("18.60"),
                    humidity_pct=Decimal("80.00"),
                    par_umol=Decimal("50.00"),
                    co2_ppm=Decimal("720.00"),
                ),
            ]
        )

        today = now.replace(hour=9, minute=0, second=0, microsecond=0)
        IrrigationCycle.objects.bulk_create(
            [
                IrrigationCycle(
                    zone=z1,
                    start_at=today + timedelta(hours=1),
                    duration_min=25,
                    water_liters=Decimal("180.00"),
                    status=IrrigationCycle.STATUS_SCHEDULED,
                ),
                IrrigationCycle(
                    zone=z2,
                    start_at=today + timedelta(hours=2),
                    duration_min=20,
                    water_liters=Decimal("120.00"),
                    status=IrrigationCycle.STATUS_SCHEDULED,
                ),
                IrrigationCycle(
                    zone=z4,
                    start_at=today - timedelta(hours=3),
                    duration_min=30,
                    water_liters=Decimal("95.00"),
                    status=IrrigationCycle.STATUS_DONE,
                ),
                IrrigationCycle(
                    zone=z1,
                    start_at=today - timedelta(days=1, hours=2),
                    duration_min=25,
                    water_liters=Decimal("175.00"),
                    status=IrrigationCycle.STATUS_DONE,
                ),
                IrrigationCycle(
                    zone=z5,
                    start_at=today + timedelta(hours=4),
                    duration_min=15,
                    water_liters=Decimal("40.00"),
                    status=IrrigationCycle.STATUS_SKIPPED,
                ),
            ]
        )

        # 通风窗时段：东坡一号棚 08:00-11:00 启用，CO₂ 上限 800 ppm。
        slot = VentilationSlot.objects.create(
            greenhouse=g1,
            start_time=time(8, 0),
            end_time=time(11, 0),
            co2_limit_ppm=800,
            is_enabled=True,
        )

        # 写路径联锁演示：为 z1 新建一条落在启用时段内（09:30）且 CO₂ 越界
        # （900 > 800）的气候记录。经与线上写路径同一个序列化器校验，
        # 必须被 400 拒绝（中文，带时段编号），且不得落库。
        sample_at = timezone.localtime(now).replace(
            hour=9, minute=30, second=0, microsecond=0
        )
        blocked_payload = {
            "zoneId": z1.id,
            "recordedAt": sample_at.isoformat(),
            "tempC": "25.00",
            "humidityPct": "66.00",
            "parUmol": "410.00",
            "co2Ppm": "900.00",
        }
        before = ClimateLog.objects.count()
        blocked_serializer = ClimateLogSerializer(data=blocked_payload)
        rejected = not blocked_serializer.is_valid()
        rejection_detail = blocked_serializer.errors.get("co2Ppm")
        if not rejected:
            # 联锁失效属于种子自检失败：直接报错，绝不静默写库。
            raise RuntimeError(
                "通风联锁自检失败：越界气候写入未被拒绝，请检查 ClimateLogSerializer"
            )
        after = ClimateLog.objects.count()
        if after != before:
            raise RuntimeError("通风联锁自检失败：被拒写入竟然落库")
        self.stdout.write(
            self.style.WARNING(
                f"已按预期拒绝越界气候写入（400）：{rejection_detail}"
            )
        )

        # 对照：同一时刻 CO₂ 不越界（760）的写入可通过，落库一条，
        # 证明联锁是“超限才拦”，而非空日历式一律放行/拒绝。
        ok_payload = {**blocked_payload, "co2Ppm": "760.00"}
        ok_serializer = ClimateLogSerializer(data=ok_payload)
        if not ok_serializer.is_valid():
            raise RuntimeError(
                f"通风联锁自检失败：合规写入被误拒 {ok_serializer.errors}"
            )
        ok_serializer.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"种子完成：温室 {Greenhouse.objects.count()}，分区 {Zone.objects.count()}，"
                f"气候 {ClimateLog.objects.count()}，轮灌 {IrrigationCycle.objects.count()}，"
                f"通风时段 {VentilationSlot.objects.count()}（启用 "
                f"{VentilationSlot.objects.filter(is_enabled=True).count()}）"
            )
        )
