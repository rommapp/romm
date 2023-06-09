// Plugins
import vue from '@vitejs/plugin-vue'
import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'
import { VitePWA } from 'vite-plugin-pwa'
import pluginRewriteAll from 'vite-plugin-rewrite-all'

// Utilities
import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig(({mode}) =>{
  // Load ENV variables from the parent directory and the current directory.
  const env = {...loadEnv(mode, '../'), ...loadEnv(mode, './')};
  const backendPort = env.VITE_BACKEND_DEV_PORT ?? '5000';

  return {
    plugins: [
      pluginRewriteAll(),
      vue({ 
        template: { transformAssetUrls }
      }),
      vuetify({
        autoImport: true,
        styles: {
          configFile: 'src/styles/settings.scss',
        },
      }),
      VitePWA({
        manifest: {
          icons: [
            {
              src: "favicon.ico",
              sizes: "256x256",
              type: "image/ico",
              purpose: "any maskable"
            }
          ]
        }
      })
    ],
    define: { 'process.env': {} },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
      extensions: [
        '.js',
        '.json',
        '.jsx',
        '.mjs',
        '.ts',
        '.tsx',
        '.vue',
      ],
    },
    server: {
      proxy: {
          '/api': {
            target: `http://localhost:${backendPort}`,
            changeOrigin: false,
            secure: false,
            rewrite: (path) => path.replace(/^\/api/, ''),
          },
          '/ws': {
            target: `http://localhost:${backendPort}`,
            changeOrigin: false,
            ws: true,
          },
      },
      port: 3000,
    }
  };
})