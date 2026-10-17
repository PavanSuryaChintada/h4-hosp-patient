import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// BASE_PATH lets the same build serve from a sub-path (GitHub Pages); Vercel uses the root.
export default defineConfig({
  base: process.env.BASE_PATH ?? '/',
  plugins: [react()],
});
