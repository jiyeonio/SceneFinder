import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    // 백엔드가 준비되면 주석을 풀고 주소를 맞춰 주세요.
    // proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
