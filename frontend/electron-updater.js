// electron-updater.js — GitHub Releases Otomatik Güncelleme
// GitHub Releases API'den son sürümü kontrol eder, varsa installer'ı indirir ve çalıştırır
const { app, dialog, BrowserWindow, shell } = require('electron');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

// ─── Ayarlar ───────────────────────────────────────────
const GITHUB_OWNER = 'aligencg2-code';
const GITHUB_REPO = 'reworar';
const RELEASES_API = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`;

// ─── Sürüm Yönetimi ────────────────────────────────────
// Lazy init — app.getPath() ancak app ready olduktan sonra çağrılabilir
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
    } catch { /* fallback */ }
    return require('./package.json').version || '1.0.0';
}

function saveInstalledVersion(version) {
    try {
        const vf = getVersionFile();
        const dir = path.dirname(vf);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(vf, JSON.stringify({ version, updated_at: new Date().toISOString() }), 'utf-8');
        console.log(`[Updater] Sürüm kaydedildi: ${version}`);
    } catch (e) {
        console.error(`[Updater] Sürüm kaydetme hatası: ${e.message}`);
    }
}

function getCurrentVersion() {
    if (!_currentVersion) {
        _currentVersion = getInstalledVersion();
    }
    return _currentVersion;
}

// ─── Sürüm Karşılaştırma ───────────────────────────────
function versionToTuple(v) {
    return v.replace(/^v\.?/, '').split('.').map(Number);
}

function isNewerVersion(remote, local) {
    const r = versionToTuple(remote);
    const l = versionToTuple(local);
    for (let i = 0; i < Math.max(r.length, l.length); i++) {
        const rv = r[i] || 0;
        const lv = l[i] || 0;
        if (rv > lv) return true;
        if (rv < lv) return false;
    }
    return false;
}

// ─── GitHub Releases API ────────────────────────────────
function checkForUpdates() {
    return new Promise((resolve, reject) => {
        const options = {
            hostname: 'api.github.com',
            path: `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
            method: 'GET',
            headers: {
                'User-Agent': 'Demet-Updater',
                'Accept': 'application/vnd.github.v3+json',
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                try {
                    if (res.statusCode === 404) {
                        return resolve({ update_available: false, reason: 'No releases found' });
                    }
                    if (res.statusCode !== 200) {
                        return resolve({ update_available: false, reason: `HTTP ${res.statusCode}` });
                    }

                    const release = JSON.parse(data);
                    const remoteVersion = release.tag_name.replace(/^v/, '');
                    const localVersion = getCurrentVersion();
                    const needsUpdate = isNewerVersion(remoteVersion, localVersion);

                    // Setup EXE asset'ini bul
                    const exeAsset = release.assets.find(a =>
                        a.name.toLowerCase().endsWith('.exe') &&
                        a.name.toLowerCase().includes('setup')
                    );

                    resolve({
                        update_available: needsUpdate,
                        latest_version: remoteVersion,
                        current_version: localVersion,
                        changelog: release.body || '',
                        download_url: exeAsset ? exeAsset.browser_download_url : null,
                        download_size: exeAsset ? exeAsset.size : 0,
                        release_name: release.name || '',
                    });
                } catch (e) {
                    resolve({ update_available: false, reason: e.message });
                }
            });
        });

        req.on('error', (e) => {
            // İnternet yoksa sessizce atla
            resolve({ update_available: false, reason: e.message });
        });

        req.setTimeout(10000, () => {
            req.destroy();
            resolve({ update_available: false, reason: 'Timeout' });
        });

        req.end();
    });
}

// ─── Installer İndirme ──────────────────────────────────
function downloadInstaller(url, win) {
    return new Promise((resolve, reject) => {
        const downloadDir = path.join(app.getPath('temp'), 'demet-update');
        if (!fs.existsSync(downloadDir)) fs.mkdirSync(downloadDir, { recursive: true });

        const fileName = url.split('/').pop() || 'DemetSetup.exe';
        const filePath = path.join(downloadDir, fileName);

        // Önceki indirme varsa sil
        if (fs.existsSync(filePath)) fs.unlinkSync(filePath);

        console.log(`[Updater] İndiriliyor: ${url}`);
        console.log(`[Updater] Hedef: ${filePath}`);

        const download = (downloadUrl) => {
            const protocol = downloadUrl.startsWith('https') ? https : require('http');

            protocol.get(downloadUrl, {
                headers: { 'User-Agent': 'Demet-Updater' },
            }, (res) => {
                // Redirect takibi
                if (res.statusCode === 301 || res.statusCode === 302) {
                    console.log(`[Updater] Redirect: ${res.headers.location}`);
                    download(res.headers.location);
                    return;
                }

                if (res.statusCode !== 200) {
                    return reject(new Error(`İndirme hatası: HTTP ${res.statusCode}`));
                }

                const totalSize = parseInt(res.headers['content-length'] || '0', 10);
                let downloadedSize = 0;
                const fileStream = fs.createWriteStream(filePath);

                res.on('data', (chunk) => {
                    downloadedSize += chunk.length;
                    if (totalSize > 0 && win && !win.isDestroyed()) {
                        const percent = Math.round((downloadedSize / totalSize) * 100);
                        win.setProgressBar(downloadedSize / totalSize);
                        win.setTitle(`Demet — Güncelleniyor %${percent}`);
                    }
                });

                res.pipe(fileStream);

                fileStream.on('finish', () => {
                    fileStream.close();
                    if (win && !win.isDestroyed()) {
                        win.setProgressBar(-1); // Progress bar'ı kaldır
                        win.setTitle('Demet');
                    }
                    console.log(`[Updater] İndirme tamamlandı: ${filePath}`);
                    resolve(filePath);
                });

                fileStream.on('error', (err) => {
                    fs.unlinkSync(filePath);
                    reject(err);
                });
            }).on('error', reject);
        };

        download(url);
    });
}

// ─── Ana Güncelleme Akışı ───────────────────────────────
async function runUpdateCheck(win) {
    try {
        console.log(`[Updater] Sürüm kontrolü... (mevcut: ${getCurrentVersion()})`);
        const result = await checkForUpdates();

        if (!result.update_available) {
            console.log('[Updater] Güncelleme yok.');
            return false;
        }

        console.log(`[Updater] Yeni sürüm: ${result.latest_version}`);

        if (!result.download_url) {
            console.log('[Updater] İndirme linki bulunamadı.');
            return false;
        }

        // Kullanıcıya sor
        const sizeMB = result.download_size ? `${(result.download_size / 1024 / 1024).toFixed(0)} MB` : '';
        const changelogPreview = result.changelog
            ? '\n\nDeğişiklikler:\n' + result.changelog.substring(0, 300)
            : '';

        const response = await dialog.showMessageBox(win, {
            type: 'info',
            title: 'Güncelleme Mevcut',
            message: `Yeni sürüm: v${result.latest_version}`,
            detail: `Mevcut sürüm: v${result.current_version}\n${sizeMB ? `Boyut: ~${sizeMB}` : ''}${changelogPreview}`,
            buttons: ['Güncelle', 'Sonra'],
            defaultId: 0,
            cancelId: 1,
            noLink: true,
        });

        if (response.response !== 0) {
            console.log('[Updater] Kullanıcı güncellemeyi erteledi.');
            return false;
        }

        // İndir
        const installerPath = await downloadInstaller(result.download_url, win);

        // Sürümü kaydet
        saveInstalledVersion(result.latest_version);

        // Installer'ı çalıştır ve uygulamayı kapat
        await dialog.showMessageBox(win, {
            type: 'info',
            title: 'İndirme Tamamlandı',
            message: 'Güncelleme indirildi!',
            detail: 'Şimdi kurulum başlatılacak. Uygulama kapanacak.',
            buttons: ['Kurulumu Başlat'],
            defaultId: 0,
            noLink: true,
        });

        // Installer'ı başlat
        spawn(installerPath, ['/S'], {
            detached: true,
            stdio: 'ignore',
        }).unref();

        // Uygulamayı kapat
        app.quit();
        return true;

    } catch (err) {
        console.error('[Updater] Hata:', err.message);
        return false;
    }
}

module.exports = {
    checkForUpdates,
    runUpdateCheck,
    getCurrentVersion,
    saveInstalledVersion,
};
