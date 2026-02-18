// electron-updater.js — Uzaktan Güncelleme Modülü
// Railway üzerindeki update API'sini kontrol eder, güncelleme varsa indirir ve uygular
const { app, dialog, BrowserWindow } = require('electron');
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ─── Ayarlar ───────────────────────────────────────────
const UPDATE_SERVER = process.env.UPDATE_SERVER || 'https://demet-frontend-production.up.railway.app';

// ─── Sürüm Yönetimi ────────────────────────────────────
// package.json asar içinde olduğu için güncellenemez.
// Güncelleme sonrası yeni sürümü userData'da kalıcı dosyaya yazıyoruz.
// NOT: app.getPath('userData') ancak app ready olduktan sonra çağrılabilir,
// bu yüzden lazy initialization kullanıyoruz.
let _versionFile = null;
let _currentVersion = null;

function getVersionFile() {
    if (!_versionFile) {
        _versionFile = path.join(app.getPath('userData'), 'installed_version.json');
    }
    return _versionFile;
}

function getInstalledVersion() {
    try {
        const vf = getVersionFile();
        if (fs.existsSync(vf)) {
            const data = JSON.parse(fs.readFileSync(vf, 'utf-8'));
            if (data.version) return data.version;
        }
    } catch { /* fallback to package.json */ }
    return require('./package.json').version || '1.0.0';
}

function saveInstalledVersion(version) {
    try {
        const vf = getVersionFile();
        const dir = path.dirname(vf);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(vf, JSON.stringify({ version, updated_at: new Date().toISOString() }), 'utf-8');
        console.log(`[Updater] Sürüm kaydedildi: ${version} -> ${vf}`);
    } catch (e) {
        console.error(`[Updater] Sürüm kaydetme hatası: ${e.message}`);
    }
}

// CURRENT_VERSION: app ready olduktan sonra çağrılmalı
// electron-main.js'de app.whenReady() içinden kullanılır
function getCurrentVersion() {
    if (!_currentVersion) {
        _currentVersion = getInstalledVersion();
    }
    return _currentVersion;
}

// Geriye uyumluluk — getter ile lazy erişim
Object.defineProperty(module.exports, 'CURRENT_VERSION', {
    get: () => getCurrentVersion(),
});

/**
 * Güncelleme kontrolü yapar.
 * @returns {Promise<{update_available: boolean, latest_version: string, changelog: string, download_url: string}>}
 */
function checkForUpdates() {
    return new Promise((resolve, reject) => {
        const url = `${UPDATE_SERVER}/api/update/check?current_version=${CURRENT_VERSION}`;
        console.log(`[Updater] Güncelleme kontrol ediliyor: ${url}`);

        const client = url.startsWith('https') ? https : http;

        const req = client.get(url, { timeout: 10000 }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    console.log(`[Updater] Sonuç:`, result);
                    resolve(result);
                } catch (e) {
                    reject(new Error(`JSON parse hatası: ${e.message}`));
                }
            });
        });

        req.on('error', (err) => {
            console.log(`[Updater] Bağlantı hatası (güncelleme atlanıyor): ${err.message}`);
            resolve({ update_available: false });
        });

        req.on('timeout', () => {
            req.destroy();
            console.log('[Updater] Zaman aşımı (güncelleme atlanıyor)');
            resolve({ update_available: false });
        });
    });
}

/**
 * Güncelleme ZIP dosyasını indirir.
 * @param {BrowserWindow} win - İlerleme göstermek için pencere
 * @returns {Promise<string>} İndirilen ZIP dosyasının yolu
 */
function downloadUpdate(win) {
    return new Promise((resolve, reject) => {
        const url = `${UPDATE_SERVER}/api/update/download`;
        const tempDir = path.join(app.getPath('temp'), 'demet-update');
        const zipPath = path.join(tempDir, 'update.zip');

        // Temp dizini oluştur
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        console.log(`[Updater] İndiriliyor: ${url} -> ${zipPath}`);

        const client = url.startsWith('https') ? https : http;
        const file = fs.createWriteStream(zipPath);

        const req = client.get(url, { timeout: 120000 }, (res) => {
            if (res.statusCode === 302 || res.statusCode === 301) {
                // Redirect takibi
                const redirectUrl = res.headers.location;
                const redirectClient = redirectUrl.startsWith('https') ? https : http;
                redirectClient.get(redirectUrl, (redirectRes) => {
                    redirectRes.pipe(file);
                    file.on('finish', () => {
                        file.close();
                        resolve(zipPath);
                    });
                });
                return;
            }

            if (res.statusCode !== 200) {
                file.close();
                fs.unlinkSync(zipPath);
                reject(new Error(`İndirme hatası: HTTP ${res.statusCode}`));
                return;
            }

            const totalSize = parseInt(res.headers['content-length'], 10) || 0;
            let downloaded = 0;

            res.on('data', (chunk) => {
                downloaded += chunk.length;
                if (totalSize > 0 && win && !win.isDestroyed()) {
                    const percent = Math.round((downloaded / totalSize) * 100);
                    win.setProgressBar(percent / 100);
                    win.webContents.send('update:progress', { percent, downloaded, total: totalSize });
                }
            });

            res.pipe(file);

            file.on('finish', () => {
                file.close();
                if (win && !win.isDestroyed()) {
                    win.setProgressBar(-1); // İlerleme çubuğunu kaldır
                }
                console.log(`[Updater] İndirme tamamlandı: ${zipPath}`);
                resolve(zipPath);
            });
        });

        req.on('error', (err) => {
            file.close();
            if (fs.existsSync(zipPath)) fs.unlinkSync(zipPath);
            reject(new Error(`İndirme hatası: ${err.message}`));
        });

        req.on('timeout', () => {
            req.destroy();
            file.close();
            if (fs.existsSync(zipPath)) fs.unlinkSync(zipPath);
            reject(new Error('İndirme zaman aşımı'));
        });
    });
}

/**
 * İndirilen ZIP dosyasını çıkartır ve dosyaları değiştirir.
 * @param {string} zipPath - İndirilen ZIP dosya yolu
 */
function applyUpdate(zipPath) {
    const extractDir = path.join(app.getPath('temp'), 'demet-update', 'extracted');

    // Eski extract dizinini temizle
    if (fs.existsSync(extractDir)) {
        fs.rmSync(extractDir, { recursive: true, force: true });
    }
    fs.mkdirSync(extractDir, { recursive: true });

    // PowerShell ile ZIP çıkart (Windows'ta native)
    try {
        execSync(
            `powershell -NoProfile -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${extractDir}' -Force"`,
            { windowsHide: true, timeout: 60000 }
        );
    } catch (e) {
        throw new Error(`ZIP çıkartma hatası: ${e.message}`);
    }

    console.log(`[Updater] ZIP çıkartıldı: ${extractDir}`);

    // Dosya yapısını belirle
    const resourcesPath = process.resourcesPath || path.join(path.dirname(process.execPath), 'resources');
    const backendDest = path.join(resourcesPath, 'backend');
    const frontendDest = path.join(resourcesPath, 'frontend-out');

    // Backend dosyalarını kopyala
    const backendSrc = path.join(extractDir, 'backend');
    if (fs.existsSync(backendSrc)) {
        copyDirSync(backendSrc, backendDest);
        console.log('[Updater] Backend dosyaları güncellendi');
    }

    // Frontend dosyalarını kopyala
    const frontendSrc = path.join(extractDir, 'frontend-out');
    if (fs.existsSync(frontendSrc)) {
        copyDirSync(frontendSrc, frontendDest);
        console.log('[Updater] Frontend dosyaları güncellendi');
    }

    // Temizlik
    try {
        fs.rmSync(path.join(app.getPath('temp'), 'demet-update'), { recursive: true, force: true });
    } catch { /* ignore */ }

    console.log('[Updater] Güncelleme uygulandı!');
}

/**
 * Dizin kopyalama (recursive)
 */
function copyDirSync(src, dest) {
    if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
    }

    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (const entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);

        if (entry.isDirectory()) {
            copyDirSync(srcPath, destPath);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

/**
 * Ana güncelleme akışı — uygulama açılışında çağrılır.
 * @param {BrowserWindow} win
 */
async function runUpdateCheck(win) {
    try {
        const result = await checkForUpdates();

        if (!result.update_available) {
            console.log('[Updater] Uygulama güncel.');
            return false;
        }

        // Kullanıcıya sor
        const response = await dialog.showMessageBox(win, {
            type: 'info',
            title: 'Güncelleme Mevcut!',
            message: `Yeni sürüm: v${result.latest_version}`,
            detail: [
                `Mevcut sürüm: v${CURRENT_VERSION}`,
                '',
                result.changelog ? `Değişiklikler:\n${result.changelog}` : '',
                '',
                result.force_update ? '⚠️ Bu güncelleme zorunludur!' : 'Şimdi güncellemek ister misiniz?',
            ].filter(Boolean).join('\n'),
            buttons: result.force_update
                ? ['Güncelle']
                : ['Güncelle', 'Daha Sonra'],
            defaultId: 0,
            cancelId: result.force_update ? -1 : 1,
            noLink: true,
        });

        if (response.response !== 0) {
            console.log('[Updater] Kullanıcı güncellemeyi erteledi.');
            return false;
        }

        // İndir
        const zipPath = await downloadUpdate(win);

        // Uygula
        applyUpdate(zipPath);

        // Yeni sürümü kalıcı dosyaya kaydet (tekrar popup göstermemesi için)
        saveInstalledVersion(result.latest_version);

        // Yeniden başlat
        const restartResponse = await dialog.showMessageBox(win, {
            type: 'info',
            title: 'Güncelleme Tamamlandı!',
            message: `v${result.latest_version} başarıyla yüklendi!`,
            detail: 'Değişikliklerin geçerli olması için uygulama yeniden başlatılacak.',
            buttons: ['Yeniden Başlat'],
            defaultId: 0,
            noLink: true,
        });

        // Uygulamayı yeniden başlat
        app.relaunch();
        app.exit(0);

        return true;
    } catch (err) {
        console.error('[Updater] Hata:', err.message);
        // Güncelleme hatası uygulamanın açılmasını engellemesin
        return false;
    }
}

module.exports = {
    checkForUpdates,
    downloadUpdate,
    applyUpdate,
    runUpdateCheck,
    saveInstalledVersion,
    getCurrentVersion,
};
