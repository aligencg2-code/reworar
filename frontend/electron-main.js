// electron-main.js — Instabot Masaüstü Uygulaması Ana Process
const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const { runUpdateCheck, getCurrentVersion } = require('./electron-updater');

// ─── Tek Örnek Kilidi ──────────────────────────────────
// Aynı anda birden fazla Demet çalışmasını engelle
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
    // Zaten çalışan bir örnek var, onu öne getir ve bu örneği kapat
    app.quit();
}

// ─── Ayarlar ───────────────────────────────────────────
const BACKEND_PORT = 8000;
const FRONTEND_PORT = 45321;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const isDev = !app.isPackaged;

let mainWindow = null;
let backendProcess = null;
let frontendServer = null;

// ─── Port Temizleme ────────────────────────────────────
// Önceki çalışmadan kalan orphan process'leri temizle
function killPortProcess(port) {
    if (process.platform !== 'win32') return;
    try {
        const output = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`, { encoding: 'utf8', timeout: 5000 });
        const lines = output.trim().split('\n');
        const pids = new Set();
        for (const line of lines) {
            const parts = line.trim().split(/\s+/);
            const pid = parts[parts.length - 1];
            if (pid && pid !== '0' && pid !== String(process.pid)) {
                pids.add(pid);
            }
        }
        for (const pid of pids) {
            try {
                execSync(`taskkill /PID ${pid} /F`, { timeout: 3000, windowsHide: true });
                console.log(`[Electron] Port ${port} üzerindeki PID ${pid} sonlandırıldı`);
            } catch { }
        }
    } catch {
        // Port kullanımda değil — sorun yok
    }
}

// ─── Yollar ────────────────────────────────────────────
function getBackendDir() {
    if (isDev) {
        return path.join(__dirname, '..', 'backend');
    }
    return path.join(process.resourcesPath, 'backend');
}

function getFrontendDir() {
    if (isDev) {
        return path.join(__dirname, 'out');
    }
    return path.join(process.resourcesPath, 'frontend-out');
}

// ─── Frontend Static Server ────────────────────────────
// Next.js static export dosyalarını HTTP üzerinden serve eder
function createRequestHandler(frontendDir) {
    const MIME_TYPES = {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.webp': 'image/webp',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.eot': 'application/vnd.ms-fontobject',
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.txt': 'text/plain; charset=utf-8',
        '.xml': 'application/xml',
        '.map': 'application/json',
    };

    return (req, res) => {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);

        // /api isteklerini backend'e proxy'le
        if (urlPath.startsWith('/api/') || urlPath === '/health') {
            const proxyReq = http.request(
                `${BACKEND_URL}${req.url}`,
                { method: req.method, headers: { ...req.headers, host: `127.0.0.1:${BACKEND_PORT}` } },
                (proxyRes) => {
                    res.writeHead(proxyRes.statusCode, proxyRes.headers);
                    proxyRes.pipe(res);
                }
            );
            proxyReq.on('error', () => { res.writeHead(502); res.end('Backend unavailable'); });
            req.pipe(proxyReq);
            return;
        }

        // /uploads isteklerini backend'e proxy'le
        if (urlPath.startsWith('/uploads/')) {
            const proxyReq = http.request(
                `${BACKEND_URL}${req.url}`,
                { method: req.method, headers: { ...req.headers, host: `127.0.0.1:${BACKEND_PORT}` } },
                (proxyRes) => {
                    res.writeHead(proxyRes.statusCode, proxyRes.headers);
                    proxyRes.pipe(res);
                }
            );
            proxyReq.on('error', () => { res.writeHead(502); res.end('Backend unavailable'); });
            req.pipe(proxyReq);
            return;
        }

        // Statik dosya serve et
        let filePath = path.join(frontendDir, urlPath);
        if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
            filePath = path.join(filePath, 'index.html');
        }
        if (!fs.existsSync(filePath)) {
            const htmlPath = filePath + '.html';
            if (fs.existsSync(htmlPath)) filePath = htmlPath;
            else filePath = path.join(frontendDir, 'index.html');
        }
        if (!fs.existsSync(filePath)) {
            res.writeHead(404); res.end('Not Found'); return;
        }

        const ext = path.extname(filePath).toLowerCase();
        const contentType = MIME_TYPES[ext] || 'application/octet-stream';
        const fileStream = fs.createReadStream(filePath);
        res.writeHead(200, { 'Content-Type': contentType });
        fileStream.pipe(res);
        fileStream.on('error', () => { res.writeHead(500); res.end('Internal Error'); });
    };
}

function listenOnPort(server, port) {
    return new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(port, '127.0.0.1', () => {
            server.removeListener('error', reject);
            resolve();
        });
    });
}

async function startFrontendServer() {
    const frontendDir = getFrontendDir();
    console.log(`[Electron] Frontend dizini: ${frontendDir}`);

    if (!fs.existsSync(frontendDir)) {
        throw new Error(`Frontend dizini bulunamadı: ${frontendDir}`);
    }

    const handler = createRequestHandler(frontendDir);

    for (let attempt = 1; attempt <= 3; attempt++) {
        frontendServer = http.createServer(handler);
        try {
            await listenOnPort(frontendServer, FRONTEND_PORT);
            console.log(`[Electron] Frontend server: ${FRONTEND_URL}`);
            return;
        } catch (err) {
            if (err.code === 'EADDRINUSE') {
                console.log(`[Electron] Port ${FRONTEND_PORT} meşgul, temizleniyor... (deneme ${attempt}/3)`);
                killPortProcess(FRONTEND_PORT);
                frontendServer.close();
                await new Promise(r => setTimeout(r, 2000));
            } else {
                throw err;
            }
        }
    }
    throw new Error(`Port ${FRONTEND_PORT} serbest bırakılamadı. Lütfen bilgisayarı yeniden başlatın.`);
}

// ─── Backend Başlatma ──────────────────────────────────
function startBackend() {
    return new Promise((resolve, reject) => {
        const backendDir = getBackendDir();
        console.log(`[Electron] Backend dizini: ${backendDir}`);

        if (isDev) {
            // Geliştirme modunda Python kullan
            const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
            backendProcess = spawn(pythonCmd, [
                '-m', 'uvicorn', 'app.main:app',
                '--host', '127.0.0.1',
                '--port', String(BACKEND_PORT),
                '--log-level', 'warning',
            ], {
                cwd: backendDir,
                stdio: ['pipe', 'pipe', 'pipe'],
                env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
                windowsHide: true,
            });
        } else {
            // Üretim modunda PyInstaller EXE kullan — Python kurulmasına gerek yok!
            const exePath = path.join(backendDir, 'Demet.exe');
            console.log(`[Electron] Backend EXE: ${exePath}`);

            if (!fs.existsSync(exePath)) {
                return reject(new Error(`Backend EXE bulunamadı: ${exePath}`));
            }

            backendProcess = spawn(exePath, [], {
                cwd: backendDir,
                stdio: ['pipe', 'pipe', 'pipe'],
                windowsHide: true,
                detached: false,
            });
        }

        backendProcess.stdout.on('data', (data) => {
            console.log(`[Backend] ${data.toString().trim()}`);
        });

        backendProcess.stderr.on('data', (data) => {
            console.log(`[Backend] ${data.toString().trim()}`);
        });

        backendProcess.on('error', (err) => {
            console.error(`[Backend] Process hatası:`, err);
            reject(err);
        });

        backendProcess.on('exit', (code) => {
            console.log(`[Backend] Process sonlandı (code: ${code})`);
            backendProcess = null;
        });

        // Backend hazır olana kadar bekle
        waitForBackend(30000).then(() => {
            console.log('[Electron] Backend hazır!');
            resolve();
        }).catch(reject);
    });
}

function waitForBackend(timeout = 30000) {
    const start = Date.now();
    return new Promise((resolve, reject) => {
        const check = () => {
            if (Date.now() - start > timeout) {
                return reject(new Error('Backend başlatma zaman aşımı'));
            }
            const req = http.get(`${BACKEND_URL}/health`, (res) => {
                if (res.statusCode === 200) resolve();
                else setTimeout(check, 500);
            });
            req.on('error', () => setTimeout(check, 500));
            req.setTimeout(2000, () => { req.destroy(); setTimeout(check, 500); });
        };
        check();
    });
}

function stopBackend() {
    if (backendProcess) {
        console.log('[Electron] Backend kapatılıyor...');
        if (process.platform === 'win32') {
            spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'], { windowsHide: true });
        } else {
            backendProcess.kill('SIGTERM');
        }
        backendProcess = null;
    }
}

// ─── Pencere Oluşturma ────────────────────────────────
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 700,
        frame: false,
        titleBarStyle: 'hidden',
        backgroundColor: '#0f0f23',
        icon: path.join(__dirname, 'public', 'favicon.ico'),
        webPreferences: {
            preload: path.join(__dirname, 'electron-preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
        },
        show: false,
    });

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    // Frontend'i HTTP server üzerinden yükle (CSS/JS düzgün çalışır)
    mainWindow.loadURL(FRONTEND_URL);

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// ─── IPC Handlers ──────────────────────────────────────
ipcMain.handle('window:minimize', () => mainWindow?.minimize());
ipcMain.handle('window:maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize();
    else mainWindow?.maximize();
});
ipcMain.handle('window:close', () => mainWindow?.close());
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() || false);
ipcMain.handle('app:getVersion', () => getCurrentVersion());
ipcMain.handle('shell:openExternal', (_, url) => shell.openExternal(url));
ipcMain.handle('app:checkUpdate', async () => {
    if (mainWindow) await runUpdateCheck(mainWindow);
});

// ─── Uygulama Yaşam Döngüsü ───────────────────────────
// İkinci örnek açılırsa, mevcut pencereyi öne getir
app.on('second-instance', () => {
    if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.focus();
    }
});

app.whenReady().then(async () => {
    try {
        console.log('[Electron] Başlatılıyor...');

        // 0. Önceki oturumdan kalan portları temizle
        killPortProcess(FRONTEND_PORT);
        killPortProcess(BACKEND_PORT);

        // 1. Frontend static server'ı başlat
        await startFrontendServer();

        // 2. Backend'i başlat
        await startBackend();

        // 3. Pencereyi aç
        console.log('[Electron] Pencere oluşturuluyor...');
        createWindow();

        // 4. Güncelleme kontrolü (arka planda, pencere açıldıktan sonra)
        setTimeout(async () => {
            try {
                await runUpdateCheck(mainWindow);
            } catch (e) {
                console.log('[Updater] Güncelleme kontrolü atlandı:', e.message);
            }
        }, 3000); // 3 sn bekle, önce uygulama açılsın

        app.on('activate', () => {
            if (BrowserWindow.getAllWindows().length === 0) createWindow();
        });
    } catch (err) {
        console.error('[Electron] Başlatma hatası:', err);
        const { dialog } = require('electron');
        dialog.showErrorBox(
            'Instabot — Başlatma Hatası',
            `Uygulama başlatılamadı.\n\n${err.message}\n\nPython ve gereken paketlerin kurulu olduğundan emin olun.`
        );
        app.quit();
    }
});

app.on('window-all-closed', () => {
    stopBackend();
    if (frontendServer) frontendServer.close();
    app.quit();
});

app.on('before-quit', () => {
    stopBackend();
    if (frontendServer) frontendServer.close();
});
