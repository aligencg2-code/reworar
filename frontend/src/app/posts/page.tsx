'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '@/lib/api';

export default function PostsPage() {
    const [accounts, setAccounts] = useState<any[]>([]);
    const [posts, setPosts] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);

    // Bot state
    const [botRunning, setBotRunning] = useState(false);
    const [botLoading, setBotLoading] = useState(false);
    const [botLogs, setBotLogs] = useState<any[]>([]);
    const logRef = useRef<HTMLDivElement>(null);

    // Settings bilgisi
    const [settings, setSettings] = useState<Record<string, string>>({});

    // Login state
    const [loginLoadingId, setLoginLoadingId] = useState<number | null>(null);
    const [challengeAccountId, setChallengeAccountId] = useState<number | null>(null);
    const [challengeCode, setChallengeCode] = useState('');
    const [challengeMessage, setChallengeMessage] = useState('');

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    useEffect(() => { loadData(); }, []);

    const loadData = async () => {
        try {
            const [accData, postsData, settingsData, botStatus] = await Promise.all([
                api.getAccounts(),
                api.getPosts({ limit: '20' }),
                api.getSettings(),
                api.request<any>('/dashboard/bot/status'),
            ]);
            setAccounts(accData || []);
            setPosts(postsData.posts || []);
            setTotal(postsData.total || 0);
            setSettings(settingsData.settings || {});
            setBotRunning(botStatus.running || false);
            if (botStatus.logs) setBotLogs(botStatus.logs);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    // Bot kontrol
    const handleBotToggle = async () => {
        setBotLoading(true);
        try {
            if (botRunning) {
                await api.request('/dashboard/bot/stop', { method: 'POST' });
                showToast('success', '⏹ Bot durduruldu');
                setBotRunning(false);
            } else {
                await api.request('/dashboard/bot/start', { method: 'POST' });
                showToast('success', '🚀 Bot başlatıldı');
                setBotRunning(true);
            }
        } catch (err: any) { showToast('error', err.message); }
        finally { setBotLoading(false); }
    };

    // Bot log polling
    useEffect(() => {
        if (!botRunning) return;
        const iv = setInterval(async () => {
            try {
                const s = await api.request<any>('/dashboard/bot/status');
                setBotRunning(s.running || false);
                if (s.logs) setBotLogs(s.logs);
            } catch { }
        }, 3000);
        return () => clearInterval(iv);
    }, [botRunning]);

    useEffect(() => {
        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    }, [botLogs]);

    // Giriş yap
    const handleLogin = async (id: number) => {
        setLoginLoadingId(id);
        try {
            const result = await api.request<any>('/accounts/login-single', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: id }),
            });
            if (result.success) {
                showToast('success', `✅ @${result.username} giriş başarılı`);
            } else if (result.needs_code) {
                setChallengeAccountId(id);
                setChallengeCode('');
                setChallengeMessage(result.message || 'Email doğrulama kodu girin');
                showToast('success', '📧 Email doğrulama kodu gönderildi');
            } else {
                showToast('error', `❌ ${result.message}`);
            }
            loadData();
        } catch (err: any) { showToast('error', err.message); }
        finally { setLoginLoadingId(null); }
    };

    // Challenge code submit
    const submitChallenge = async () => {
        if (!challengeAccountId || !challengeCode.trim()) return;
        try {
            const result = await api.request<any>('/accounts/submit-challenge-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: challengeAccountId, code: challengeCode.trim() }),
            });
            if (result.success) {
                showToast('success', `✅ @${result.username} doğrulama başarılı`);
                setChallengeAccountId(null);
            } else {
                showToast('error', result.message || 'Doğrulama başarısız');
            }
            loadData();
        } catch (err: any) { showToast('error', err.message); }
    };

    // Toplu giriş
    const handleBulkLogin = async () => {
        setBotLoading(true);
        try {
            const result = await api.request<any>('/accounts/bulk-login', { method: 'POST' });
            if (result.results) {
                const ok = result.results.filter((r: any) => r.success).length;
                const fail = result.results.filter((r: any) => !r.success).length;
                showToast('success', `✅ ${ok} başarılı, ${fail} başarısız`);
            }
            loadData();
        } catch (err: any) { showToast('error', err.message); }
        finally { setBotLoading(false); }
    };

    const statusIcons: Record<string, string> = {
        published: '✅', failed: '❌', publishing: '⏳', scheduled: '📅', draft: '📝',
    };

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    const activeAccounts = accounts.filter(a => a.is_active);
    const loggedInCount = accounts.filter(a => a.session_valid).length;

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

            {/* Header */}
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Toplu Paylaşım</h2>
                    <p className="page-header__subtitle">
                        Hesaplarınıza toplu sıralı paylaşım yönetimi
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <button className="btn btn-secondary" onClick={handleBulkLogin} disabled={botLoading}>
                        🔑 Toplu Giriş
                    </button>
                    <button
                        className={`btn ${botRunning ? 'btn-error' : 'btn-primary'}`}
                        onClick={handleBotToggle}
                        disabled={botLoading}
                        style={{ padding: '10px 28px', fontWeight: 700, fontSize: '0.95rem' }}
                    >
                        {botLoading ? '⏳ İşleniyor...' : botRunning ? '⏹ Botu Durdur' : '🚀 Botu Başlat'}
                    </button>
                </div>
            </div>

            {/* İstatistik Kartları */}
            <div className="stats-grid" style={{ marginBottom: 20 }}>
                <div className="stat-card">
                    <div className="stat-icon green">✅</div>
                    <div>
                        <div className="stat-value">{loggedInCount}/{accounts.length}</div>
                        <div className="stat-label">Giriş Yapılmış</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon blue">📊</div>
                    <div>
                        <div className="stat-value">{posts.filter(p => p.status === 'published').length}</div>
                        <div className="stat-label">Bugün Yayınlanan</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon orange">⏳</div>
                    <div>
                        <div className="stat-value">{botRunning ? '🟢 Çalışıyor' : '⚫ Durdu'}</div>
                        <div className="stat-label">Bot Durumu</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon pink">❌</div>
                    <div>
                        <div className="stat-value">{posts.filter(p => p.status === 'failed').length}</div>
                        <div className="stat-label">Hatalı</div>
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {/* Sol: Hesaplar + Giriş */}
                <div>
                    <div className="card" style={{ marginBottom: 20 }}>
                        <div className="card-header">
                            <h3 className="card-title">👤 Hesaplar & Giriş Durumu</h3>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                {loggedInCount}/{accounts.length} aktif oturum
                            </span>
                        </div>
                        {accounts.length === 0 ? (
                            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                                Henüz hesap eklenmemiş. <a href="/accounts" style={{ color: 'var(--accent-primary)' }}>Hesap Ekle →</a>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {accounts.map(acc => (
                                    <div key={acc.id} style={{
                                        display: 'flex', alignItems: 'center', gap: 10,
                                        padding: '10px 12px', borderRadius: 8,
                                        background: acc.session_valid ? 'rgba(46,204,113,0.06)' : 'rgba(231,76,60,0.06)',
                                        borderLeft: `3px solid ${acc.session_valid ? '#2ecc71' : '#e74c3c'}`,
                                    }}>
                                        <div style={{
                                            width: 34, height: 34, borderRadius: '50%',
                                            background: 'var(--gradient-primary)', display: 'flex',
                                            alignItems: 'center', justifyContent: 'center',
                                            fontSize: '0.72rem', fontWeight: 700, color: '#fff',
                                            overflow: 'hidden', flexShrink: 0,
                                        }}>
                                            {acc.profile_picture_url ? (
                                                <img src={acc.profile_picture_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                            ) : (acc.username?.[0]?.toUpperCase())}
                                        </div>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>@{acc.username}</div>
                                            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                                                {acc.session_valid ? '✅ Oturum aktif' : '❌ Giriş gerekli'}
                                                {acc.proxy_url && <span> · 🌐 Proxy</span>}
                                            </div>
                                        </div>
                                        <button
                                            className={`btn btn-sm ${acc.session_valid ? 'btn-secondary' : 'btn-primary'}`}
                                            onClick={() => handleLogin(acc.id)}
                                            disabled={loginLoadingId === acc.id}
                                            style={{ fontWeight: 600, minWidth: 90 }}
                                        >
                                            {loginLoadingId === acc.id ? '⏳...' : acc.session_valid ? '🔄 Yenile' : '🔑 Giriş Yap'}
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Ayar Özeti */}
                    <div className="card">
                        <div className="card-header">
                            <h3 className="card-title">⚙️ Paylaşım Ayarları</h3>
                            <a href="/settings" className="btn btn-sm btn-secondary">Düzenle</a>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bg-surface)', fontSize: '0.78rem' }}>
                                <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginBottom: 2 }}>📍 Konum</div>
                                <div style={{ fontWeight: 600 }}>{settings.selected_location_list || 'Tümü'}</div>
                            </div>
                            <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bg-surface)', fontSize: '0.78rem' }}>
                                <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginBottom: 2 }}>#️⃣ Hashtag</div>
                                <div style={{ fontWeight: 600 }}>{settings.selected_hashtag_group_id ? `Grup #${settings.selected_hashtag_group_id}` : 'Tümü'}</div>
                            </div>
                            <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bg-surface)', fontSize: '0.78rem' }}>
                                <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginBottom: 2 }}>💬 Caption</div>
                                <div style={{ fontWeight: 600 }}>{settings.caption_mode === 'sequential' ? 'Sıralı' : 'Rastgele'}</div>
                            </div>
                            <div style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--bg-surface)', fontSize: '0.78rem' }}>
                                <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginBottom: 2 }}>⏱️ Aralık</div>
                                <div style={{ fontWeight: 600 }}>{settings.posting_interval_min || '50'}-{settings.posting_interval_max || '60'}sn</div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Sağ: Bot Logları + Son Paylaşımlar */}
                <div>
                    {/* Bot Logları */}
                    <div className="card" style={{ marginBottom: 20 }}>
                        <div className="card-header">
                            <h3 className="card-title">📋 Bot Logları</h3>
                            <span className={`badge ${botRunning ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '0.65rem' }}>
                                {botRunning ? '🟢 Çalışıyor' : '⚫ Durdu'}
                            </span>
                        </div>
                        {botLogs.length === 0 ? (
                            <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                                Bot başlatıldığında loglar burada görünecek
                            </div>
                        ) : (
                            <div
                                ref={logRef}
                                style={{
                                    maxHeight: 300, overflowY: 'auto',
                                    background: 'var(--bg-darker, #0d1117)',
                                    borderRadius: 10, padding: '12px 16px',
                                    fontFamily: 'monospace', fontSize: '0.76rem', lineHeight: 1.6,
                                }}
                            >
                                {botLogs.map((log, i) => (
                                    <div key={i} style={{
                                        color: log.level === 'error' ? '#ff5252'
                                            : log.level === 'warning' ? '#ffab40' : '#b0bec5',
                                    }}>
                                        <span style={{ color: '#546e7a', marginRight: 8 }}>
                                            {new Date(log.time).toLocaleTimeString('tr-TR')}
                                        </span>
                                        {log.message}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Son Paylaşımlar */}
                    <div className="card">
                        <div className="card-header">
                            <h3 className="card-title">📊 Son Paylaşımlar</h3>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Toplam {total}</span>
                        </div>
                        {posts.length === 0 ? (
                            <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                                Henüz paylaşım yapılmamış
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 350, overflowY: 'auto' }}>
                                {posts.slice(0, 20).map(post => (
                                    <div key={post.id} style={{
                                        display: 'flex', alignItems: 'center', gap: 10,
                                        padding: '8px 10px', borderRadius: 6,
                                        borderLeft: `3px solid ${post.status === 'published' ? '#2ecc71' : post.status === 'failed' ? '#e74c3c' : '#f39c12'}`,
                                        fontSize: '0.78rem',
                                    }}>
                                        <span>{statusIcons[post.status] || '📄'}</span>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ fontWeight: 600 }}>
                                                @{accounts.find(a => a.id === post.account_id)?.username || '?'}
                                            </div>
                                            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {post.caption?.substring(0, 50) || '—'}
                                            </div>
                                        </div>
                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                                            {post.published_at ? new Date(post.published_at).toLocaleString('tr-TR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—'}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Challenge Modal */}
            {challengeAccountId && (
                <div className="modal-overlay" onClick={() => setChallengeAccountId(null)}>
                    <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
                        <h3 className="modal-title">📧 Doğrulama Kodu</h3>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
                            {challengeMessage}
                        </p>
                        <input
                            type="text"
                            className="form-input"
                            placeholder="6 haneli kod"
                            value={challengeCode}
                            onChange={e => setChallengeCode(e.target.value)}
                            autoFocus
                            style={{ marginBottom: 12, textAlign: 'center', fontSize: '1.2rem', letterSpacing: 4 }}
                        />
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => setChallengeAccountId(null)}>İptal</button>
                            <button className="btn btn-primary" onClick={submitChallenge} disabled={!challengeCode.trim()}>Doğrula</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
