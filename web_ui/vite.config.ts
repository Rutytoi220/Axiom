import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

import tailwindcss from '@tailwindcss/vite'

import fs from 'fs';
import os from 'os';
import path from 'path';

// Read AXIOM daemon token
let tokenValue = '';
try {
  const tokenPath = path.join(os.homedir(), '.axiom', 'daemon.token');
  tokenValue = fs.readFileSync(tokenPath, 'utf8').trim();
} catch (e) {
  console.warn('Warning: Could not read ~/.axiom/daemon.token');
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    'import.meta.env.VITE_DAEMON_TOKEN': JSON.stringify(tokenValue)
  }
})
