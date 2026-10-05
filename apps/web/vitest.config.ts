import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname), '@sih/types': path.resolve(__dirname, '../../packages/types/src/index.ts') } },
  test: { environment: 'jsdom', setupFiles: ['./vitest.setup.ts'], globals: true, css: false },
});
