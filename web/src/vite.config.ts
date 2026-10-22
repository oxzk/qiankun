import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * QianKun 前端 Vite 配置。
 */
export default defineConfig({
    plugins: [react()],
    publicDir: path.resolve(__dirname, '../../public'),
    resolve: {
        alias: {
            '@': path.resolve(__dirname),
        },
    },
})
