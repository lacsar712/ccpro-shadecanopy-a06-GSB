<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const list = ref([])
const greenhouses = ref([])
const activeCount = ref(0)
const error = ref('')
const editingId = ref(null)
const filterGreenhouseId = ref('')

const form = reactive({
  greenhouseId: '',
  startTime: '06:00',
  endTime: '20:00',
  co2LimitPpm: 1000,
  isActive: true,
})

function resetForm() {
  editingId.value = null
  form.greenhouseId = greenhouses.value[0]?.id || ''
  form.startTime = '06:00'
  form.endTime = '20:00'
  form.co2LimitPpm = 1000
  form.isActive = true
}

async function loadGreenhouses() {
  const { data } = await api.get('/greenhouses/')
  greenhouses.value = data.results || data
  if (!form.greenhouseId && greenhouses.value.length) {
    form.greenhouseId = greenhouses.value[0].id
  }
}

async function load() {
  error.value = ''
  try {
    const params = {}
    if (filterGreenhouseId.value) params.greenhouseId = filterGreenhouseId.value
    const { data } = await api.get('/ventilation-slots/', { params })
    list.value = data.results || data
    if (data.activeCount !== undefined) activeCount.value = data.activeCount
  } catch {
    error.value = '加载通风时段失败'
  }
}

function edit(row) {
  editingId.value = row.id
  form.greenhouseId = row.greenhouseId
  form.startTime = row.startTime
  form.endTime = row.endTime
  form.co2LimitPpm = row.co2LimitPpm
  form.isActive = row.isActive
}

function extractError(e) {
  const status = e.response?.status
  const d = e.response?.data
  if (!d) return '保存失败（无响应）'
  if (typeof d === 'string') return d
  if (d.detail) return `${status === 409 ? '冲突：' : ''}${d.detail}`
  return Object.entries(d)
    .map(([k, v]) => `${k}：${Array.isArray(v) ? v.join('；') : v}`)
    .join('；')
}

async function save() {
  error.value = ''
  if (form.startTime === form.endTime) {
    error.value = '开始时刻与结束时刻不得相同（跨午夜请令结束时刻早于开始时刻）'
    return
  }
  const payload = {
    greenhouseId: Number(form.greenhouseId),
    startTime: form.startTime,
    endTime: form.endTime,
    co2LimitPpm: form.co2LimitPpm,
  }
  // is_active 的变更仅管理员可做：种植员提交时不带该字段，保持原值
  if (isAdmin.value) payload.isActive = form.isActive
  try {
    if (editingId.value) {
      await api.put(`/ventilation-slots/${editingId.value}/`, payload)
    } else {
      await api.post('/ventilation-slots/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    error.value = extractError(e)
  }
}

async function toggleActive(row) {
  error.value = ''
  try {
    await api.patch(`/ventilation-slots/${row.id}/`, { isActive: !row.isActive })
    await load()
  } catch (e) {
    error.value = extractError(e)
  }
}

async function remove(row) {
  error.value = ''
  if (!confirm(`确认删除通风时段 #${row.id}？`)) return
  try {
    await api.delete(`/ventilation-slots/${row.id}/`)
    await load()
  } catch (e) {
    error.value = extractError(e)
  }
}

onMounted(async () => {
  await loadGreenhouses()
  await load()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>通风窗时段</h1>
        <p>
          按温室配置每日通风时段与 CO₂ 上限；采样时刻落在启用时段内的气候记录，CO₂ 超限将被拒绝
        </p>
      </div>
      <div class="actions">
        <select v-model="filterGreenhouseId" @change="load">
          <option value="">全部温室</option>
          <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </div>
    </div>

    <div class="stats" style="margin-bottom:18px;grid-template-columns:minmax(160px,260px)">
      <div class="stat">
        <div class="label">启用通风时段数</div>
        <div class="value">{{ activeCount }}</div>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑时段' : '新建时段' }}</h3>
      <div class="form-grid">
        <label>
          所属温室
          <select v-model="form.greenhouseId" :disabled="!!editingId">
            <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </label>
        <label>CO₂ 上限 (ppm)<input v-model.number="form.co2LimitPpm" type="number" min="0" /></label>
        <label>开始时刻<input v-model="form.startTime" type="time" required /></label>
        <label>
          结束时刻
          <input v-model="form.endTime" type="time" required />
          <small style="color:var(--muted)">早于开始时刻表示跨午夜</small>
        </label>
        <label v-if="isAdmin" style="flex-direction:row;align-items:center;gap:8px">
          <input v-model="form.isActive" type="checkbox" style="width:auto" /> 启用
        </label>
        <span v-else style="font-size:.85rem;color:var(--muted);align-self:center">
          新建时段默认启用；停用 / 启用变更仅管理员
        </span>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions" style="margin-top:12px">
        <button class="btn" @click="save">保存</button>
        <button v-if="editingId" class="btn ghost" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>编号</th>
            <th>所属温室</th>
            <th>开始</th>
            <th>结束</th>
            <th>CO₂ 上限</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>#{{ row.id }}</td>
            <td>{{ row.greenhouseName }}</td>
            <td>{{ row.startTime }}</td>
            <td>{{ row.endTime }}</td>
            <td>{{ row.co2LimitPpm }} ppm</td>
            <td>
              <span class="badge" :class="row.isActive ? 'scheduled' : 'skipped'">
                {{ row.isActive ? '启用' : '停用' }}
              </span>
            </td>
            <td class="actions">
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button v-if="isAdmin" class="btn ghost" @click="toggleActive(row)">
                {{ row.isActive ? '停用' : '启用' }}
              </button>
              <button v-if="isAdmin" class="btn danger" @click="remove(row)">删除</button>
              <span v-if="!isAdmin" style="font-size:.8rem;color:var(--muted)">停用仅管理员</span>
            </td>
          </tr>
          <tr v-if="!list.length">
            <td colspan="7" style="color:var(--muted)">暂无通风时段</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
