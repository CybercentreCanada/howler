import react from '@vitejs/plugin-react-swc';
import { glob } from 'glob';
import { extname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv } from 'vite';
import dts from 'vite-plugin-dts';
import tsconfigPaths from 'vite-tsconfig-paths';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  process.env = { ...process.env, ...loadEnv(mode, process.cwd()) };

  const useMinify = !process.env.npm_package_version?.includes('dev');

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
      },

      dts({
        tsconfigPath: 'tsconfig.json',
        exclude: ['**/*.test.ts', '**/*.test.tsx', '**/*.spec.ts', '**/*.spec.tsx'],
        copyDtsFiles: true
      })
    ],
    worker: {
      plugins: () => [tsconfigPaths()]
    },
    build: {
      sourcemap: false,
      outDir: 'dist',
      minify: useMinify,
      lib: {
        entry: resolve(__dirname, 'src/index.tsx'),
        formats: ['es']
      },
      rollupOptions: {
        external: [/node_modules/],

        input: Object.fromEntries(
          glob
            .sync('src/**/*.{ts,tsx}')
            .filter(
              file =>
                !file.endsWith('setupTests.ts') &&
                !file.includes('.test.') &&
                !file.includes('/tests/') &&
                !file.endsWith('.d.ts')
            )
            .map(file => [
              // The name of the entry point
              // lib/nested/foo.ts becomes nested/foo
              relative('src', file.slice(0, file.length - extname(file).length)),
              // The absolute path to the entry file
              // lib/nested/foo.ts becomes /project/lib/nested/foo.ts
              fileURLToPath(new URL(file, import.meta.url))
            ])
        ),
        plugins: [],
        output: {
          assetFileNames: 'assets/[name][extname]',
          entryFileNames: '[name].js'
        }
      }
    },
    define: {
      'process.env': {}
    }
  };
});
