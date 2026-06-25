import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const root = path.dirname(fileURLToPath(import.meta.url))
const pdfjsRoot = path.join(root, 'node_modules/pdfjs-dist')
const publicPdfjs = path.join(root, 'public/pdfjs')

/** 把 pdfjs-dist 的 cmaps / standard_fonts 拷贝到 public/pdfjs，供 DocumentPane 渲染中文 PDF。 */
function ensurePdfJsAssets(): void {
  fs.mkdirSync(publicPdfjs, { recursive: true })
  for (const dir of ['cmaps', 'standard_fonts']) {
    const src = path.join(pdfjsRoot, dir)
    const dest = path.join(publicPdfjs, dir)
    if (fs.existsSync(src) && !fs.existsSync(dest)) {
      fs.cpSync(src, dest, { recursive: true })
    }
  }
}

ensurePdfJsAssets()

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    { name: 'ensure-pdfjs-assets', buildStart: ensurePdfJsAssets },
  ],
  base: loadEnv(mode, process.cwd(), '').VITE_BASE_PATH || '/',
}))
