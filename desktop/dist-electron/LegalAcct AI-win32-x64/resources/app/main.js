const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const fs = require('fs');

const DEV_URL = 'http://localhost:5173';
const PROD_INDEX = path.join(__dirname, 'frontend/dist/index.html');

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'LegalAcct AI',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Dev mode: load from Vite dev server; Production: load built dist
  const isDev = !fs.existsSync(PROD_INDEX);
  if (isDev) {
    win.loadURL(DEV_URL);
    win.webContents.openDevTools();
  } else {
    win.loadFile(PROD_INDEX);
  }

  // Open external links in the system browser, not in Electron
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
