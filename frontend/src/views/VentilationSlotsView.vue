<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api, { errorMessage } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const list = ref([])
const greenhouses = ref([])
const error = ref('')
const editingId = ref(null)
const filterGreenhouseId = ref('')

const form = reactive({
  greenhouseId: '',
  startTime: '08:00',
  endTime: '11:00',
  co2LimitPpm: 800,
  isEnabled: true,
})

function resetForm() {
  editingId.value = null
  form.greenhouseId = filterGreenhouseId.value || greenhouses.value[0]?.id || ''
  form.startTime = '08:00'
  form.endTime = '11:00'
  form.co2LimitPpm = 800
  form.isEnabled = true
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
  } catch (e) {
    error.value = errorMessage(e, '加载通风时段失败')
  }
}

function greenhouseName(id) {
  return greenhouses.value.find((g) => g.id === id)?.name || `#${id}`
}

function edit(row) {
  editingId.value = row.id
  form.greenhouseId = row.greenhouseId
  form.startTime = row.startTime.slice(0, 5)
  form.endTime = row.endTime.slice(0, 5)
  form.co2LimitPpm = row.co2LimitPpm
  form.isEnabled = row.isEnabled
}

async function save() {
  error.value = ''
  // 非管理员无权停用：强制保持启用，后端亦会 403 兜底。
  if (!isAdmin.value) form.isEnabled = true
  const payload = {
    greenhouseId: Number(form.greenhouseId),
    startTime: form.startTime,
    endTime: form.endTime,
    co2LimitPpm: form.co2LimitPpm,
    isEnabled: form.isEnabled,
  }
  try {
    if (editingId.value) {
      await api.put(`/ventilation-slots/${editingId.value}/`, payload)
    } else {
      await api.post('/ventilation-slots/', payload)
    }
    resetForm()
    await load()
  } catch (e) {
    // 相交 → 409；非管理员停用 → 403；时间非法 → 400。
    error.value = errorMessage(e, '保存失败')
  }
}

async function setEnabled(row, value) {
  error.value = ''
  try {
    await api.patch(`/ventilation-slots/${row.id}/`, { isEnabled: value })
    await load()
  } catch (e) {
    error.value = errorMessage(e, '更新启用状态失败')
  }
}

async function remove(id) {
  if (!confirm('确认删除该通风时段？')) return
  try {
    await api.delete(`/ventilation-slots/${id}/`)
    await load()
  } catch (e) {
    error.value = errorMessage(e, '删除失败')
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
        <h1>通风时段</h1>
        <p>按温室设定每日通风窗时段与 CO₂ 上限；时段覆盖采样时刻时，分区气候写入受联锁约束</p>
      </div>
      <div class="actions">
        <select v-model="filterGreenhouseId" @change="load">
          <option value="">全部温室</option>
          <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </div>
    </div>

    <div class="panel">
      <h3 style="margin-top:0">{{ editingId ? '编辑时段' : '新建时段' }}</h3>
      <div class="form-grid">
        <label>
          所属温室
          <select v-model="form.greenhouseId">
            <option v-for="g in greenhouses" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </label>
        <label>CO₂ 上限 (ppm)<input v-model.number="form.co2LimitPpm" type="number" min="0" /></label>
        <label>开始时刻<input v-model="form.startTime" type="time" /></label>
        <label>结束时刻（可早于开始，表示跨午夜）<input v-model="form.endTime" type="time" /></label>
        <label>
          是否启用
          <input
            v-model="form.isEnabled"
            type="checkbox"
            :disabled="!isAdmin && !form.isEnabled"
            style="width:auto"
          />
          <small v-if="!isAdmin" style="color:var(--danger)">种植员仅可建立启用时段，停用须管理员</small>
        </label>
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
            <th>该温室启用时段数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list" :key="row.id">
            <td>#{{ row.id }}</td>
            <td>{{ row.greenhouseName || greenhouseName(row.greenhouseId) }}</td>
            <td>{{ row.startTime.slice(0, 5) }}</td>
            <td>{{ row.endTime.slice(0, 5) }}</td>
            <td>{{ row.co2LimitPpm }} ppm</td>
            <td>
              <span class="badge" :class="row.isEnabled ? 'growing' : 'fallow'">
                {{ row.isEnabled ? '启用' : '停用' }}
              </span>
            </td>
            <td><strong>{{ row.activeVentCount }}</strong></td>
            <td class="actions">
              <button class="btn ghost" @click="edit(row)">编辑</button>
              <button
                v-if="isAdmin && row.isEnabled"
                class="btn secondary"
                @click="setEnabled(row, false)"
              >
                停用
              </button>
              <button
                v-else-if="isAdmin && !row.isEnabled"
                class="btn ghost"
                @click="setEnabled(row, true)"
              >
                启用
              </button>
              <button class="btn danger" @click="remove(row.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!list.length">
            <td colspan="8" style="color:var(--muted)">暂无通风时段</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
