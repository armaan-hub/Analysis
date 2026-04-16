// preload.js — runs in renderer context with Node access disabled.
// Expose safe APIs to the renderer via contextBridge if needed in the future.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
});
