import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// BASE_PATH lets the same build serve from a sub-path (GitHub Pages); Vercel uses the root.
// /api goes to the ward server (python tools/serve_ui.py), which runs the real pipeline.
const api = { '/api': 'http://127.0.0.1:8765' };

export default defineConfig({
  base: process.env.BASE_PATH ?? '/',
  plugins: [react()],
  server: { proxy: api },
  preview: { proxy: api },
});
