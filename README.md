# ShadeCanopy-01 · 分区气候日志与轮灌计划

温室「分区气候日志与轮灌计划」全栈种子项目（非考勤 OA、非库存）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python Django 5 · Django REST Framework · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端容器反代 `/api` → Django） |

## 路径与端口

- **项目路径**：`D:\work\document\bytecode\claudeCodePro\ShadeCanopy\ShadeCanopy-01\`
- **前端**：http://localhost:3500
- **后端 API**：http://localhost:8500（也可经前端同源 `/api` 访问）
- **PostgreSQL**：localhost:5435

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | admin（管理员，可进 Django Admin） |
| `grower` | `123456` | grower（种植员） |

启动时 `entrypoint.sh` 会执行 `migrate` + `seed_data` 自动写入账号与示例业务数据。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\ShadeCanopy\ShadeCanopy-01
docker compose up --build
```

浏览器打开 http://localhost:3500 ，使用 `grower` / `123456` 登录。

停止：

```bash
docker compose down
```

## 业务模块

1. **Auth**：JWT `POST /api/auth/token/`，当前用户 `GET /api/auth/me/`
2. **Greenhouse**：name / location / areaM2 / notes
3. **Zone**：greenhouseId / zoneCode / cropName / status(`idle|growing|fallow`)；同温室 zoneCode 唯一
4. **ClimateLog**：zoneId / recordedAt / tempC / humidityPct / parUmol / co2Ppm；**humidityPct ∈ [20, 100]**
5. **IrrigationCycle**：zoneId / startAt / durationMin / waterLiters / status(`scheduled|running|done|skipped`)
6. **VentilationSlot（通风窗时段）**：greenhouseId / startTime / endTime / co2LimitPpm / isEnabled（每日时刻，支持跨午夜）
7. **Dashboard**：温室数、growing 分区数、近 24h 气候日志数、今日 scheduled 轮灌数、**启用通风时段数** → `GET /api/dashboard/`

### 通风时段业务规则

- **挂温室**：时段从属于某一温室；`endTime < startTime` 表示跨午夜（如 23:00–02:00），两端时刻相等返回 400。
- **相交 409**：同一温室内两条时段时间范围相交（半开区间 `[start, end)`，首尾相接不算相交）时，新建/更新返回 **409**，中文信息给出相撞的时段编号。
- **写路径联锁（核心）**：当某分区新建/更新气候记录，且采样时刻 `recordedAt`（按 Asia/Shanghai 的当日时刻）被该温室**启用中**的通风时段覆盖时，`co2Ppm` 不得超过该时段的 `co2LimitPpm`；否则返回 **400**，中文错误并带通风时段编号，例如：
  `通风时段 #1（08:00-11:00）覆盖该采样时刻，二氧化碳 900.00 ppm 超过上限 800 ppm`。
  未被任何启用时段覆盖的时刻不做 CO₂ 限制。
- **权限**：种植员（grower）可新建/编辑时段；**停用仅管理员（admin）**——种植员将时段置为停用（含新建即停用）返回 **403**；未认证返回 401。
- **启用时段数同源**：通风时段列表接口与单条接口均给出该温室的 `activeVentCount`，仪表盘给出全温室 `activeVentSlotCount`，三者取自同一计数函数（`core.models.enabled_vent_slot_count`），口径一致、随停用/启用实时联动。
- **种子**：`seed_data` 会写入一条启用时段（东坡一号棚 08:00–11:00，上限 800 ppm），随后经与线上同一写路径的序列化器尝试写入一条落在时段内、CO₂=900 的气候记录，预期被 400 拒绝且不落库（命令行打印拒绝原因），并写入一条 CO₂=760 的合规记录作为对照。

## API 一览

| 方法 | 路径 |
| --- | --- |
| POST | `/api/auth/token/` |
| POST | `/api/auth/token/refresh/` |
| GET | `/api/auth/me/` |
| CRUD | `/api/greenhouses/` |
| CRUD | `/api/zones/?greenhouseId=&status=` |
| CRUD | `/api/climate-logs/?zoneId=` |
| CRUD | `/api/irrigation-cycles/?zoneId=&status=` |
| CRUD | `/api/ventilation-slots/?greenhouseId=` |
| GET | `/api/dashboard/` |

字段对外使用 camelCase（如 `areaM2`、`zoneCode`、`humidityPct`）。

## 本地开发（可选）

**后端**（需本机 Postgres 或已启动 compose 中的 db）：

```bash
cd backend
pip install -r requirements.txt
set POSTGRES_HOST=127.0.0.1
set POSTGRES_PORT=5435
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:8500
```

**前端**：

```bash
cd frontend
npm install
npm run dev
```

Vite 已将 `/api` 代理到 `http://127.0.0.1:8500`。

## 目录结构

```
ShadeCanopy-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh      # migrate + seed + gunicorn
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/            # settings / urls
│   ├── accounts/          # 自定义 User + role
│   └── core/              # 温室/分区/气候/轮灌 + seed_data
└── frontend/
    ├── Dockerfile
    ├── nginx.conf         # 静态资源 + /api 反代
    ├── package.json
    └── src/               # Vue 页面（叶绿/土色主题）
```

## 配色说明

前端采用叶绿（`#3d6b3a`）与土色（`#8b6b45`）主色，米色底与侧栏深绿渐变，贴近温室场景。
