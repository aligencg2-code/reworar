// electron-preload.js — Renderer Process IPC Köprüsü
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Pencere kontrolleri
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized'),

    // Uygulama bilgileri
    getVersion: () => ipcRenderer.invoke('app:getVersion'),

    // Güncelleme
    checkUpdate: () => ipcRenderer.invoke('app:checkUpdate'),
    onUpdateProgress: (callback) => ipcRenderer.on('update:progress', (_, data) => callback(data)),

    // Dış linkler
    openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),

    // Platform bilgisi
    platform: process.platform,

    // Electron detect flag
    isElectron: true,
});
