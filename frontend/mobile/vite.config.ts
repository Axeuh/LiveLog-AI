import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

// 从项目根目录的 config.yaml 读取百度地图 API Key
function loadBaiduMapAk(): string {
  try {
    const configPath = path.resolve(__dirname, '../../backend/config/config.yaml')
    const raw = fs.readFileSync(configPath, 'utf-8')
    // 用正则从 YAML 中提取 baidu_map_ak 值
    const match = raw.match(/baidu_map_ak:\s*['"]?([^\s'"]+)['"]?/)
    return match?.[1] || ''
  } catch {
    console.warn('[vite] 无法读取 config.yaml 中的 baidu_map_ak')
    return ''
  }
}

const baiduMapAk = loadBaiduMapAk()

export default defineConfig({
  plugins: [vue()],
  base: '/mobile/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    target: 'es2015',
    outDir: 'dist',
  },
  define: {
    // 构建/开发时注入百度地图 AK，不依赖 .env 文件
    'import.meta.env.VITE_BAIDU_MAP_AK': JSON.stringify(baiduMapAk),
  },
})
