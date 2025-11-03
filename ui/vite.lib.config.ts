import react from '@vitejs/plugin-react-swc';
import { defineConfig, loadEnv } from 'vite';
import tsconfigPaths from 'vite-tsconfig-paths';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

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
        external: [/@mui.*/, /@emotion.*/],
        plugins: []
      }
    },
    define: {
      'process.env': {}
    }
  };
});
