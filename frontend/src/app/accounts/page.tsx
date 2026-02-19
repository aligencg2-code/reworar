'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface AccountInfo {
    id: number;
    username: string;
    full_name: string | null;
    profile_picture_url: string | null;
    biography: string | null;
    followers_count: number;
    following_count: number;
    media_count: number;
    is_active: boolean;
    session_valid: boolean;
    last_login_at: string | null;
    login_method: string;
    proxy_url: string | null;
    account_status: string;
}

export default function AccountsPage() {
    const [accounts, setAccounts] = useState<AccountInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [showImport, setShowImport] = useState(false);
    const [importText, setImportText] = useState('');
    const [defaultProxy, setDefaultProxy] = useState('');
    const [importing, setImporting] = useState(false);
    const [bulkLoggingIn, setBulkLoggingIn] = useState(false);
    const [loginJobId, setLoginJobId] = useState('');
    const [loginProgress, setLoginProgress] = useState<any>(null);
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
    const [editId, setEditId] = useState<number | null>(null);
    const [editData, setEditData] = useState<any>({});
    const [challengeAccountId, setChallengeAccountId] = useState<number | null>(null);
    const [challengeCode, setChallengeCode] = useState('');
    const [challengeMessage, setChallengeMessage] = useState('');
    const [submittingCode, setSubmittingCode] = useState(false);

    // --- Hesap Ayarları Modal ---
    const [settingsAccount, setSettingsAccount] = useState<AccountInfo | null>(null);
    const [accountFiles, setAccountFiles] = useState<any[]>([]);
    const [editingFile, setEditingFile] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState('');
    const [savingFile, setSavingFile] = useState(false);
    const [accountMedia, setAccountMedia] = useState<any[]>([]);
    const [accountMediaCounts, setAccountMediaCounts] = useState<Record<string, number>>({});
    const [accountMediaFilter, setAccountMediaFilter] = useState('');
    const [settingsLoading, setSettingsLoading] = useState(false);

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 6000);
    };

    const loadAccounts = useCallback(async () => {
        try {
            const data = await api.getAccounts();
            setAccounts(data || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { loadAccounts(); }, [loadAccounts]);

    // Toplu giriş ilerleme takibi
    useEffect(() => {
        if (!loginJobId || !bulkLoggingIn) return;
        const interval = setInterval(async () => {
            try {
                const status = await api.request<any>(`/accounts/login-status/${loginJobId}`);
                setLoginProgress(status);
                if (status.status === 'completed') {
                    setBulkLoggingIn(false);
                    const parts = [];
                    if (status.success > 0) parts.push(`✅ ${status.success} başarılı`);
                    if (status.challenges > 0) parts.push(`📧 ${status.challenges} doğrulama bekliyor`);
                    if (status.errors > 0) parts.push(`❌ ${status.errors} hatalı`);
                    showToast(status.success > 0 ? 'success' : 'error', `Toplu giriş tamamlandı: ${parts.join(', ')}`);
                    loadAccounts();
                }
            } catch { /* ignore */ }
        }, 2000);
        return () => clearInterval(interval);
    }, [loginJobId, bulkLoggingIn, loadAccounts]);

    const handleBulkImport = async () => {
        if (!importText.trim()) return;
        setImporting(true);
        try {
            const result = await api.request<any>('/accounts/bulk-import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ accounts_text: importText, default_proxy: defaultProxy || null }),
            });
            showToast('success', `✅ ${result.added} hesap eklendi, ${result.updated} güncellendi` +
                (result.errors?.length ? ` (${result.errors.length} hata)` : ''));
            setImportText('');
            setShowImport(false);
            loadAccounts();
        } catch (err: any) {
            showToast('error', err.message);
        } finally { setImporting(false); }
    };

    const handleBulkLogin = async () => {
        setBulkLoggingIn(true);
        setLoginProgress(null);
        try {
            const result = await api.request<any>('/accounts/bulk-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_ids: null }),
            });
            setLoginJobId(result.job_id);
            showToast('success', '🔄 Toplu giriş başlatıldı...');
        } catch (err: any) {
            setBulkLoggingIn(false);
            showToast('error', err.message);
        }
    };

    const handleSingleLogin = async (id: number) => {
        try {
            showToast('success', '🔄 Giriş deneniyor...');
            const result = await api.request<any>('/accounts/login-single', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: id }),
            });
            if (result.success) {
                showToast('success', `✅ @${result.username} giriş başarılı`);
            } else if (result.needs_code) {
                // Challenge — email doğrulama kodu gerekiyor
                setChallengeAccountId(id);
                setChallengeCode('');
                setChallengeMessage(result.message || 'Email doğrulama kodu girin');
                showToast('success', '📧 Email doğrulama kodu gönderildi');
            } else {
                showToast('error', `❌ ${result.message}`);
            }
            loadAccounts();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleSubmitChallengeCode = async () => {
        if (!challengeAccountId || !challengeCode.trim()) return;
        setSubmittingCode(true);
        try {
            const result = await api.request<any>('/accounts/submit-challenge-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: challengeAccountId, code: challengeCode.trim() }),
            });
            if (result.success) {
                showToast('success', `✅ @${result.username || ''} doğrulama başarılı!`);
                setChallengeAccountId(null);
                setChallengeCode('');
                loadAccounts();
            } else {
                showToast('error', `❌ ${result.message}`);
            }
        } catch (err: any) { showToast('error', err.message); }
        finally { setSubmittingCode(false); }
    };

    const handleBrowserLogin = async (id: number) => {
        try {
            showToast('success', '🌐 Tarayıcı açılıyor...');
            const result = await api.request<any>('/accounts/login-browser', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: id }),
            });
            if (result.success) {
                showToast('success', `✅ @${result.username} tarayıcı ile giriş başarılı`);
            } else {
                showToast('error', `❌ ${result.error || result.message}`);
            }
            loadAccounts();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleDelete = async (id: number, username: string) => {
        if (!confirm(`@${username} hesabını silmek istediğinize emin misiniz?`)) return;
        try {
            await api.deleteAccount(id);
            showToast('success', `✅ @${username} kaldırıldı`);
            loadAccounts();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleSave = async () => {
        if (!editId) return;
        try {
            await api.updateAccount(editId, editData);
            setEditId(null);
            showToast('success', '✅ Hesap güncellendi');
            loadAccounts();
        } catch (err: any) { showToast('error', err.message); }
    };

    // ─── Hesap Ayarları Fonksiyonları ───

    const getMediaUrl = (url: string | null) => {
        if (!url) return '';
        if (url.startsWith('http')) return url;
        if (typeof window !== 'undefined' && (window as any).electronAPI) {
            return `http://127.0.0.1:45678${url}`;
        }
        return url;
    };

    const openSettings = async (acc: AccountInfo) => {
        setSettingsAccount(acc);
        setEditingFile(null);
        setAccountMediaFilter('');
        setSettingsLoading(true);
        try {
            const [filesData, mediaData] = await Promise.all([
                api.getAccountFiles(acc.id),
                api.getAccountMedia(acc.id),
            ]);
            setAccountFiles(filesData.files || []);
            setAccountMedia(mediaData.items || []);
            setAccountMediaCounts(mediaData.counts || {});
        } catch (err: any) {
            showToast('error', `Ayarlar yüklenemedi: ${err.message}`);
        } finally {
            setSettingsLoading(false);
        }
    };

    const refreshSettings = async () => {
        if (!settingsAccount) return;
        setSettingsLoading(true);
        try {
            const [filesData, mediaData] = await Promise.all([
                api.getAccountFiles(settingsAccount.id),
                api.getAccountMedia(settingsAccount.id, accountMediaFilter || undefined),
            ]);
            setAccountFiles(filesData.files || []);
            setAccountMedia(mediaData.items || []);
            setAccountMediaCounts(mediaData.counts || {});
            showToast('success', '🔄 Yenilendi');
        } catch (err: any) {
            showToast('error', err.message);
        } finally {
            setSettingsLoading(false);
        }
    };

    const openFolder = async () => {
        if (!settingsAccount) return;
        try {
            await api.openAccountFolder(settingsAccount.id);
            showToast('success', '📁 Klasör açıldı');
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    const openFileEditor = async (fileKey: string) => {
        if (!settingsAccount) return;
        try {
            const data = await api.getAccountFile(settingsAccount.id, fileKey);
            setFileContent(data.content || '');
            setEditingFile(fileKey);
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    const saveFile = async () => {
        if (!settingsAccount || !editingFile) return;
        setSavingFile(true);
        try {
            await api.updateAccountFile(settingsAccount.id, editingFile, fileContent);
            showToast('success', '💾 Dosya kaydedildi');
            setEditingFile(null);
            // Dosya listesini yenile
            const filesData = await api.getAccountFiles(settingsAccount.id);
            setAccountFiles(filesData.files || []);
        } catch (err: any) {
            showToast('error', err.message);
        } finally {
            setSavingFile(false);
        }
    };

    const filterAccountMedia = async (type: string) => {
        if (!settingsAccount) return;
        setAccountMediaFilter(type);
        try {
            const mediaData = await api.getAccountMedia(settingsAccount.id, type || undefined);
            setAccountMedia(mediaData.items || []);
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    // İstatistikler
    const totalAccounts = accounts.length;
    const activeSessionsCount = accounts.filter(a => a.session_valid).length;
    const invalidSessionsCount = accounts.filter(a => !a.session_valid).length;

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    return (
        <div>
            {/* Toast */}
            {toast && (
                <div style={{
                    position: 'fixed', top: 20, right: 20, zIndex: 10000,
                    padding: '14px 20px', borderRadius: 'var(--radius-lg)',
                    background: toast.type === 'success' ? 'rgba(46,204,113,0.15)' : 'rgba(231,76,60,0.15)',
                    border: `1px solid ${toast.type === 'success' ? 'rgba(46,204,113,0.4)' : 'rgba(231,76,60,0.4)'}`,
                    backdropFilter: 'blur(20px)', color: toast.type === 'success' ? '#2ecc71' : '#e74c3c',
                    fontSize: '0.85rem', fontWeight: 500, maxWidth: 450,
                    boxShadow: '0 8px 32px rgba(0,0,0,0.3)', animation: 'slideIn 0.3s ease', cursor: 'pointer',
                }} onClick={() => setToast(null)}>{toast.message}</div>
            )}
            <style>{`@keyframes slideIn { from { opacity: 0; transform: translateX(30px); } to { opacity: 1; transform: translateX(0); } }`}</style>

            {/* Challenge Code Dialog */}
            {challengeAccountId && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
                    background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }} onClick={() => setChallengeAccountId(null)}>
                    <div style={{
                        background: 'var(--glass-bg, rgba(30,30,40,0.95))',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 'var(--radius-xl, 16px)',
                        padding: '32px', maxWidth: 420, width: '90%',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
                    }} onClick={e => e.stopPropagation()}>
                        <h3 style={{ margin: '0 0 8px', fontSize: '1.1rem' }}>📧 Email Doğrulama</h3>
                        <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', margin: '0 0 20px', lineHeight: 1.5 }}>
                            {challengeMessage}
                        </p>
                        <input
                            type="text"
                            value={challengeCode}
                            onChange={e => setChallengeCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                            placeholder="6 haneli kodu girin"
                            maxLength={6}
                            autoFocus
                            style={{
                                width: '100%', padding: '14px 16px', fontSize: '1.2rem',
                                textAlign: 'center', letterSpacing: '0.3em', fontWeight: 600,
                                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
                                borderRadius: 'var(--radius-md, 10px)', color: '#fff', outline: 'none',
                                boxSizing: 'border-box',
                            }}
                            onKeyDown={e => e.key === 'Enter' && challengeCode.length === 6 && handleSubmitChallengeCode()}
                        />
                        <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                            <button
                                onClick={() => setChallengeAccountId(null)}
                                style={{
                                    flex: 1, padding: '12px', borderRadius: 'var(--radius-md, 10px)',
                                    background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)',
                                    color: 'rgba(255,255,255,0.7)', cursor: 'pointer', fontSize: '0.85rem',
                                }}
                            >İptal</button>
                            <button
                                onClick={handleSubmitChallengeCode}
                                disabled={challengeCode.length !== 6 || submittingCode}
                                style={{
                                    flex: 2, padding: '12px', borderRadius: 'var(--radius-md, 10px)',
                                    background: challengeCode.length === 6 ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.08)',
                                    border: 'none', color: '#fff', cursor: challengeCode.length === 6 ? 'pointer' : 'not-allowed',
                                    fontWeight: 600, fontSize: '0.85rem', opacity: submittingCode ? 0.6 : 1,
                                }}
                            >{submittingCode ? 'Doğrulanıyor...' : 'Kodu Gönder'}</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Hesap Yönetimi</h2>
                    <p className="page-header__subtitle">{totalAccounts} hesap · {activeSessionsCount} aktif oturum</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary" onClick={handleBulkLogin} disabled={bulkLoggingIn || totalAccounts === 0}>
                        {bulkLoggingIn ? '⏳ Giriş yapılıyor...' : '🔑 Toplu Giriş'}
                    </button>
                    <button className="btn btn-primary" onClick={() => setShowImport(!showImport)}>
                        ➕ Toplu Hesap Ekle
                    </button>
                </div>
            </div>

            {/* Özet Kartları */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 20 }}>
                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                    <div style={{ fontSize: '1.6rem', fontWeight: 800 }}>{totalAccounts}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>Toplam Hesap</div>
                </div>
                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                    <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#2ecc71' }}>{activeSessionsCount}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>Aktif Oturum</div>
                </div>
                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                    <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#e74c3c' }}>{invalidSessionsCount}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>Geçersiz Oturum</div>
                </div>
            </div>

            {(bulkLoggingIn || loginProgress) && loginProgress && (
                <div className="card" style={{ padding: '16px', marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontWeight: 600 }}>🔑 Toplu Giriş</span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {loginProgress.done}/{loginProgress.total} · {loginProgress.current || (loginProgress.status === 'completed' ? 'Tamamlandı' : '')}
                        </span>
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 8, height: 8, overflow: 'hidden' }}>
                        <div style={{
                            width: `${loginProgress.total ? (loginProgress.done / loginProgress.total) * 100 : 0}%`,
                            height: '100%', background: 'var(--gradient-primary)',
                            borderRadius: 8, transition: 'width 0.5s ease',
                        }} />
                    </div>
                    <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        <span>✅ {loginProgress.success} başarılı</span>
                        {(loginProgress.challenges || 0) > 0 && <span>📧 {loginProgress.challenges} doğrulama</span>}
                        <span>❌ {loginProgress.errors} hatalı</span>
                    </div>

                    {/* Challenge hesaplar — doğrulama kodu girişi */}
                    {loginProgress.status === 'completed' && loginProgress.challenge_accounts?.length > 0 && (
                        <div style={{ marginTop: 12, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 12 }}>
                            <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 8, color: '#f39c12' }}>
                                📧 Doğrulama Kodu Bekleyen Hesaplar:
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {loginProgress.challenge_accounts.map((acc: any) => (
                                    <div key={acc.id} style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 12px', borderRadius: 8,
                                        background: 'rgba(243,156,18,0.08)', border: '1px solid rgba(243,156,18,0.2)',
                                    }}>
                                        <span style={{ fontSize: '0.8rem' }}>@{acc.username}</span>
                                        <button
                                            className="btn btn-sm btn-primary"
                                            onClick={() => {
                                                setChallengeAccountId(acc.id);
                                                setChallengeCode('');
                                                setChallengeMessage(acc.message || 'Email doğrulama kodu girin');
                                            }}
                                            style={{ fontSize: '0.72rem', padding: '4px 12px' }}
                                        >📧 Kod Gir</button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Toplu Import Paneli */}
            {showImport && (
                <div className="card" style={{ marginBottom: 20, padding: '20px' }}>
                    <h3 style={{ marginBottom: 12, fontSize: '1rem', fontWeight: 700 }}>📋 Toplu Hesap İmport</h3>

                    <div className="info-box blue" style={{ marginBottom: 16 }}>
                        Her satıra bir hesap yazın. Format:<br />
                        <code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: 4, fontSize: '0.75rem' }}>
                            kullanici_adi:sifre:email:email_sifresi:2fa_seed
                        </code><br />
                        <small style={{ opacity: 0.7, fontSize: '0.7rem' }}>
                            📧 Email bilgileri ile checkpoint/2FA otomatik çözülür! Son 3 alan opsiyoneldir.
                        </small>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Hesaplar</label>
                        <textarea
                            className="form-input"
                            rows={8}
                            placeholder={`hesap1:sifre123:mail@aol.com:mailsifre:TOTP2FASEED\nhesap2:sifre456:mail2@gmail.com:mailsifre2\nhesap3:sifre789`}
                            value={importText}
                            onChange={e => setImportText(e.target.value)}
                            style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
                        />
                        <small style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                            {importText.split('\n').filter(l => l.trim()).length} satır
                        </small>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Varsayılan Proxy (opsiyonel — proxy belirtilmeyen hesaplar için)</label>
                        <input
                            className="form-input"
                            placeholder="socks5://user:pass@ip:port veya http://ip:port"
                            value={defaultProxy}
                            onChange={e => setDefaultProxy(e.target.value)}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="btn btn-secondary" onClick={() => setShowImport(false)}>İptal</button>
                        <button className="btn btn-primary" onClick={handleBulkImport} disabled={importing || !importText.trim()}>
                            {importing ? '⏳ İçe aktarılıyor...' : `📥 ${importText.split('\n').filter(l => l.trim()).length} Hesap Ekle`}
                        </button>
                    </div>
                </div>
            )}

            {/* Hesap Listesi */}
            {accounts.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">👤</div>
                    <div className="empty-state__title">Henüz hesap eklenmemiş</div>
                    <p style={{ color: 'var(--text-secondary)', maxWidth: 400, margin: '8px auto' }}>
                        Yukarıdaki &quot;Toplu Hesap Ekle&quot; butonuna tıklayarak kullanıcı_adı:şifre formatında hesaplarınızı ekleyin.
                    </p>
                </div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Hesap</th>
                                <th>Oturum</th>
                                <th>Durum</th>
                                <th>Son Giriş</th>
                                <th>Proxy</th>
                                <th>İşlemler</th>
                            </tr>
                        </thead>
                        <tbody>
                            {accounts.map(acc => (
                                <tr key={acc.id}>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                            <div style={{
                                                width: 36, height: 36, borderRadius: '50%',
                                                background: 'var(--gradient-primary)', display: 'flex',
                                                alignItems: 'center', justifyContent: 'center',
                                                fontSize: '0.75rem', fontWeight: 700, color: '#fff',
                                                overflow: 'hidden', flexShrink: 0,
                                            }}>
                                                {acc.profile_picture_url ? (
                                                    <img src={acc.profile_picture_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                                ) : (acc.username?.[0]?.toUpperCase())}
                                            </div>
                                            <div>
                                                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>@{acc.username}</div>
                                                {acc.full_name && <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{acc.full_name}</div>}
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        <span className={`badge ${acc.session_valid ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '0.65rem' }}>
                                            {acc.session_valid ? '✅ Aktif' : '❌ Geçersiz'}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge ${acc.account_status === 'active' ? 'badge-success' :
                                            acc.account_status === 'checkpoint' ? 'badge-warning' : 'badge-error'}`}
                                            style={{ fontSize: '0.65rem' }}>
                                            {acc.account_status || 'bilinmiyor'}
                                        </span>
                                    </td>
                                    <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        {acc.last_login_at ? new Date(acc.last_login_at).toLocaleString('tr-TR') : '—'}
                                    </td>
                                    <td style={{ fontSize: '0.7rem', color: 'var(--text-muted)', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {acc.proxy_url || '—'}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 4 }}>
                                            <button className="btn btn-sm btn-secondary" onClick={() => openSettings(acc)} title="Ayarlar">
                                                ⚙️
                                            </button>
                                            <button className="btn btn-sm btn-secondary" onClick={() => handleSingleLogin(acc.id)} title="API ile Giriş">
                                                🔑
                                            </button>
                                            <button className="btn btn-sm btn-secondary" onClick={() => handleBrowserLogin(acc.id)} title="Tarayıcı ile Giriş" style={{ background: 'rgba(99,102,241,0.15)' }}>
                                                🌐
                                            </button>
                                            <button className="btn btn-sm btn-danger" onClick={() => handleDelete(acc.id, acc.username)} title="Sil">
                                                🗑️
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* ─── Hesap Ayarları Modal ─── */}
            {settingsAccount && (
                <div className="modal-overlay" onClick={() => { setSettingsAccount(null); setEditingFile(null); }}>
                    <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 720, maxHeight: '90vh', overflow: 'auto' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <div>
                                <h3 className="modal-title" style={{ margin: 0 }}>@{settingsAccount.username} - Ayarlar</h3>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>Config/</div>
                            </div>
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button className="btn btn-sm btn-secondary" onClick={openFolder} title="Klasörü Aç">
                                    📁 Klasörü Aç
                                </button>
                                <button className="btn btn-sm btn-secondary" onClick={refreshSettings} title="Yenile">
                                    🔄 Yenile
                                </button>
                                <button
                                    onClick={() => { setSettingsAccount(null); setEditingFile(null); }}
                                    style={{
                                        background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)',
                                        borderRadius: '50%', width: 32, height: 32, color: '#fff', fontSize: '1rem',
                                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}
                                >✕</button>
                            </div>
                        </div>

                        {settingsLoading ? (
                            <div className="flex-center" style={{ padding: 40 }}><div className="spinner" /></div>
                        ) : (
                            <>
                                {/* Hesap Dosyaları */}
                                <div style={{
                                    border: '1px solid var(--border-color)', borderRadius: 12,
                                    padding: 16, marginBottom: 16,
                                }}>
                                    <h4 style={{ margin: '0 0 12px', fontSize: '0.9rem', fontWeight: 700 }}>📄 Hesap Dosyaları</h4>

                                    {editingFile ? (
                                        /* Dosya Düzenleme */
                                        <div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                                <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                                                    {accountFiles.find((f: any) => f.key === editingFile)?.filename || editingFile}
                                                </span>
                                                <div style={{ display: 'flex', gap: 6 }}>
                                                    <button className="btn btn-sm btn-secondary" onClick={() => setEditingFile(null)}>İptal</button>
                                                    <button className="btn btn-sm btn-primary" onClick={saveFile} disabled={savingFile}>
                                                        {savingFile ? '⏳ Kaydediliyor...' : '💾 Kaydet'}
                                                    </button>
                                                </div>
                                            </div>
                                            <textarea
                                                value={fileContent}
                                                onChange={e => setFileContent(e.target.value)}
                                                rows={10}
                                                style={{
                                                    width: '100%', padding: '10px 12px', fontFamily: 'monospace',
                                                    fontSize: '0.8rem', background: 'rgba(255,255,255,0.03)',
                                                    border: '1px solid var(--border-color)', borderRadius: 8,
                                                    color: 'var(--text-primary)', resize: 'vertical', outline: 'none',
                                                    boxSizing: 'border-box',
                                                }}
                                                placeholder={`Her satıra bir girdi yazın...`}
                                            />
                                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
                                                {fileContent.split('\n').filter(l => l.trim()).length} satır
                                            </div>
                                        </div>
                                    ) : (
                                        /* Dosya Kartları */
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                                            {accountFiles.map((f: any) => (
                                                <div key={f.key} style={{
                                                    border: '1px solid var(--border-color)', borderRadius: 10,
                                                    padding: '14px 12px', textAlign: 'center',
                                                }}>
                                                    <div style={{ fontSize: 28, marginBottom: 6 }}>
                                                        {f.key === 'BioTexts' ? '📝' : f.key === 'BioLinks' ? '🔗' : '👤'}
                                                    </div>
                                                    <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>{f.filename}</div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: '4px 0 8px' }}>
                                                        {f.description}
                                                    </div>
                                                    {f.exists ? (
                                                        <div style={{ fontSize: '0.72rem', color: '#2ecc71', marginBottom: 6 }}>
                                                            ✅ {f.line_count} satır
                                                        </div>
                                                    ) : (
                                                        <div style={{ fontSize: '0.72rem', color: '#e74c3c', marginBottom: 6 }}>
                                                            Dosya bulunamadı
                                                        </div>
                                                    )}
                                                    <button
                                                        className="btn btn-sm btn-primary"
                                                        onClick={() => openFileEditor(f.key)}
                                                        style={{ fontSize: '0.72rem', width: '100%' }}
                                                    >
                                                        {f.exists ? '✏️ Düzenle' : '+ Oluştur'}
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Hesap Medyaları */}
                                <div style={{
                                    border: '1px solid var(--border-color)', borderRadius: 12,
                                    padding: 16,
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                                        <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700 }}>🖼️ Hesap Medyaları</h4>
                                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                            📷 {accountMediaCounts.photo || 0}
                                            {' '}🎬 {accountMediaCounts.video || 0}
                                            {' '}🎭 {accountMediaCounts.reels || 0}
                                            {' '}👤 {accountMediaCounts.profile || 0}
                                        </div>
                                    </div>

                                    {/* Medya Türü Tabları */}
                                    <div className="tabs" style={{ marginBottom: 10 }}>
                                        {[{ key: '', label: '📂 Tümü' }, { key: 'photo', label: '📷 Fotoğraflar' }, { key: 'video', label: '🎬 Videolar' }, { key: 'reels', label: '🎭 Reels' }, { key: 'profile', label: '👤 Profil Fotoğrafları' }].map(t => (
                                            <div
                                                key={t.key}
                                                className={`tab ${accountMediaFilter === t.key ? 'active' : ''}`}
                                                onClick={() => filterAccountMedia(t.key)}
                                                style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                                            >{t.label}</div>
                                        ))}
                                    </div>

                                    {/* Medya Grid */}
                                    {accountMedia.length === 0 ? (
                                        <div style={{
                                            textAlign: 'center', padding: '30px 20px',
                                            border: '2px dashed var(--border-color)', borderRadius: 10,
                                        }}>
                                            <div style={{ fontSize: 40, marginBottom: 8 }}>☁️</div>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Hesaba özel fotoğraf yükle</div>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>
                                                Bu fotoğraflar sadece bu hesap için kullanılacak
                                            </div>
                                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 2 }}>
                                                Desteklenen formatlar: JPG, PNG, GIF, BMP, WEBP, AVI, JPS, HEIC, HEIF
                                            </div>
                                        </div>
                                    ) : (
                                        <div style={{
                                            display: 'grid',
                                            gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))',
                                            gap: 6, maxHeight: 250, overflowY: 'auto',
                                        }}>
                                            {accountMedia.map((m: any) => (
                                                <div key={m.id} style={{
                                                    borderRadius: 8, overflow: 'hidden', aspectRatio: '1',
                                                    background: 'var(--surface-color)',
                                                }}>
                                                    <img
                                                        src={getMediaUrl(m.thumbnail_url || m.file_url) || ''}
                                                        alt={m.filename}
                                                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                                        loading="lazy"
                                                    />
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Kapat Butonu */}
                                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => { setSettingsAccount(null); setEditingFile(null); }}
                                    >Kapat</button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
