import react from '@vitejs/plugin-react-swc';
import { defineConfig, loadEnv, ProxyOptions } from 'vite';
import tsconfigPaths from 'vite-tsconfig-paths';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  const apiTarget = env.VITE_API_TARGET ?? `http://localhost:${env.VITE_REST_PORT ?? 5000}`;

  const proxy: Record<string, string | ProxyOptions> = env.VITE_API === 'REST' && {
    '/api': {
      target: apiTarget,
      changeOrigin: true,
      ws: true,
      configure: (proxy, _options) => {
        proxy.on('error', (err, _req, _res) => {
          if (_req.url?.includes('borealis')) {
            console.error('[borealis]', err);
          } else {
            console.error('[howler]', err);
          }
        });

        proxy.on('proxyRes', (proxyRes, req, _res) => {
          if (req.url?.includes('borealis')) {
            console.log('[borealis]', proxyRes.statusCode, req.url);
          } else {
            console.log('[howler]', proxyRes.statusCode, req.url);
          }
        });
      }
    }
  };

  return {
    plugins: [
      react(),
      tsconfigPaths(),
      {
        name: 'markdown-loader',
        transform(code, id) {
          if (id.slice(-3) === '.md') {
            // For .md files, get the raw content
            return `export default ${JSON.stringify(code)};`;
          }
        }
      }
    ],
    worker: {
      plugins: () => [tsconfigPaths()]
    },
    build: {
      sourcemap: false,
      outDir: 'build',
      rollupOptions: {
        plugins: [],
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              return 'node_modules';
            }
          }
        }
      }
    },
    define: {
      'process.env': {}
    },
    server: {
      port: 3000,
      proxy
    },
    preview: {
      port: 3000,
      proxy
    }
  };
});
