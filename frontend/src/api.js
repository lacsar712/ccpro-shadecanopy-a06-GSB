import axios from 'axios'
import { useAuthStore } from './stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const auth = useAuthStore()
    const original = error.config
    if (error.response?.status === 401 && auth.refreshToken && !original._retry) {
      original._retry = true
      try {
        const { data } = await axios.post('/api/auth/token/refresh/', {
          refresh: auth.refreshToken,
        })
        auth.setTokens(data.access, auth.refreshToken)
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch {
        auth.logout()
      }
    }
    return Promise.reject(error)
  }
)

/**
 * 从 DRF 错误体提取中文信息：
 * - 409 / 403 等 APIException：{ detail: "..." }
 * - 400 校验失败：{ 字段: ["..."] } 或 { 字段: "..." } / 非字段错误列表
 */
export function errorMessage(error, fallback = '保存失败') {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  const parts = []
  for (const [key, value] of Object.entries(data)) {
    const text = Array.isArray(value) ? value.join('；') : String(value)
    parts.push(key === 'detail' || key === 'non_field_errors' ? text : `${text}`)
  }
  return parts.filter(Boolean).join('；') || fallback
}

export default api
