import { defineConfig } from 'vite';

// The page talks to the bot server through the dev server, so it needs no
// CORS setup and no hard-coded backend address.
const BACKEND = process.env.TUTOR_BACKEND ?? 'http://localhost:7860';

export default defineConfig({
  server: {
    proxy: {
      '/connect': { target: BACKEND, changeOrigin: true },
      '/slides': { target: BACKEND, changeOrigin: true },
    },
  },
});
