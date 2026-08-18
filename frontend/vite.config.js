import { defineConfig } from 'vite';
import { resolve } from 'path';

const backendPort = process.env.VITE_BACKEND_PORT || 8000;
const backendHost = process.env.VITE_BACKEND_HOST || '127.0.0.1';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.VITE_PORT || '5173'),
    proxy: {
      '/api': {
        target: `http://${backendHost}:${backendPort}`,
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            // Không làm crash server dev khi backend đang reload
          });
        }
      },
      '/ws': {
        target: `ws://${backendHost}:${backendPort}`,
        ws: true,
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        training: resolve(__dirname, 'training.html')
      }
    }
  }
});


