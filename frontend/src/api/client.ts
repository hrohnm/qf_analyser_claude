import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

export default apiClient
