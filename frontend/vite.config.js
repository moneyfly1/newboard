import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    minify: 'esbuild', // 保持使用 esbuild，性能更好
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // 将 node_modules 中的依赖分离
          if (id.includes('node_modules')) {
            // Vue 核心库（必须放在最前面，避免初始化顺序问题）
            if (id.includes('vue') && !id.includes('vue-router') && !id.includes('pinia') && !id.includes('element-plus')) {
              return 'vue-core'
            }
            // Element Plus（依赖 Vue，放在 Vue 之后）
            if (id.includes('element-plus') || id.includes('@element-plus')) {
              return 'element-plus'
            }
            // Vue Router（依赖 Vue）
            if (id.includes('vue-router')) {
              return 'vue-router'
            }
            // Pinia（依赖 Vue）
            if (id.includes('pinia')) {
              return 'pinia'
            }
            // Chart.js
            if (id.includes('chart.js')) {
              return 'chart'
            }
            // 其他第三方库
            return 'vendor'
          }
        },
        // 确保 chunk 加载顺序正确
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    chunkSizeWarningLimit: 1500, // 提高警告阈值到 1500KB
    cssMinify: 'esbuild', // 使用esbuild压缩CSS
    // 确保正确的目标环境
    target: 'es2020',
    // 确保正确的模块格式
    commonjsOptions: {
      include: [/node_modules/],
      transformMixedEsModules: true
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        // 使用现代 SCSS 编译器，支持嵌套语法
        api: 'modern-compiler',
        silenceDeprecations: ['legacy-js-api'],
      },
    },
  },
  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', 'element-plus']
  },
  esbuild: {
    target: 'es2020'
  }
}) 