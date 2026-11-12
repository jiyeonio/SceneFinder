import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: false,
    // 복지바로봄 백엔드(backend/welfare_app.py, 8000) — 브라우저는 5173 하나만 열면 됨
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
