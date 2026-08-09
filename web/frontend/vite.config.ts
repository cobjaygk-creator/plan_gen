import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxying /auth and /generations to the FastAPI backend means the browser
// sees everything as same-origin in dev — no CORS setup needed, and the
// session cookie behaves exactly like it will in production behind the
// same Nginx reverse proxy described in the architecture doc.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/generations': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
