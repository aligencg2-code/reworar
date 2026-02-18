'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface AccountHealth {
    id: number;
    username: string;
    full_name: string | null;
    profile_picture_url: string | null;
    followers_count: number;
    account_status: string;
    appeal_status: string;
    status_message: string | null;
    last_checked_at: string | null;
    last_appeal_at: string | null;
    is_active: boolean;
}

interface Summary {
    total: number;
    active: number;
    restricted: number;
    action_blocked: number;
    disabled: number;
    checkpoint: number;
    unknown: number;
    never_checked: number;
    session_invalid: number;
    accounts: AccountHealth[];
}

interface CheckStatus {
    status: string;
    total: number;
    checked: number;
    problematic: number;
    results: any[];
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string; badgeClass: string }> = {
    active: { label: 'Aktif', color: '#2ecc71', icon: '✅', badgeClass: 'badge-success' },
    restricted: { label: 'Kısıtlandı', color: '#e67e22', icon: '⚠️', badgeClass: 'badge-warning' },
    action_blocked: { label: 'Engellendi', color: '#e74c3c', icon: '🚫', badgeClass: 'badge-error' },
    disabled: { label: 'Devre Dışı', color: '#95a5a6', icon: '💀', badgeClass: 'badge-error' },
    checkpoint: { label: 'Doğrulama Gerekli', color: '#f39c12', icon: '🔒', badgeClass: 'badge-warning' },
    session_invalid: { label: 'Oturum Geçersiz', color: '#8e44ad', icon: '🔑', badgeClass: 'badge-error' },
    unknown: { label: 'Bilinmiyor', color: '#7f8c8d', icon: '❓', badgeClass: 'badge-warning' },
};

export default function AppealsPage() {
    const [summary, setSummary] = useState<Summary | null>(null);
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);
    const [checkProgress, setCheckProgress] = useState<CheckStatus | null>(null);
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
    const [filter, setFilter] = useState<string>('all');
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 6000);
    };

    const loadSummary = useCallback(async () => {
        try {
            const data = await api.request<Summary>('/appeals/summary');
            setSummary(data);
        } catch (err: any) {
            showToast('error', err.message || 'Veri yüklenemedi');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadSummary(); }, [loadSummary]);

    // Kontrol durumu polling
    useEffect(() => {
        if (!checking) return;
        const interval = setInterval(async () => {
            try {
                const status = await api.request<CheckStatus>('/appeals/check-status');
                setCheckProgress(status);
                if (status.status === 'completed' || status.status === 'error') {
                    setChecking(false);
                    showToast('success', `✅ ${status.checked} hesap kontrol edildi — ${status.problematic} sorunlu`);
                    loadSummary();
                }
            } catch { /* ignore */ }
        }, 1500);
        return () => clearInterval(interval);
    }, [checking, loadSummary]);

    const handleCheckAll = async () => {
        setChecking(true);
        setCheckProgress(null);
        try {
            await api.request('/appeals/check-all', { method: 'POST' });
            showToast('success', '🔍 Hesap kontrolü başlatıldı...');
        } catch (err: any) {
            setChecking(false);
            showToast('error', err.message);
        }
    };

    const handleBulkAppeal = async () => {
        const ids = selectedIds.size > 0 ? Array.from(selectedIds) : null;
        try {
            const result = await api.request<{ total: number }>('/appeals/submit-bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_ids: ids }),
            });
            showToast('success', `✅ ${result.total} hesap için itiraz gönderildi!`);
            setSelectedIds(new Set());
            loadSummary();
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    const handleCheckSingle = async (id: number) => {
        try {
            const result = await api.request<{ message: string; healthy: boolean }>(
                `/appeals/check-single/${id}`, { method: 'POST' }
            );
            showToast(result.healthy ? 'success' : 'error', result.message);
            loadSummary();
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    const toggleSelect = (id: number) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const selectAllProblematic = () => {
        if (!summary) return;
        const problematic = summary.accounts
            .filter(a => a.account_status !== 'active')
            .map(a => a.id);
        setSelectedIds(new Set(problematic));
    };

    if (loading) {
        return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;
    }

    const filteredAccounts = summary?.accounts.filter(a => {
        if (filter === 'all') return true;
        if (filter === 'problematic') return a.account_status !== 'active';
        return a.account_status === filter;
    }) || [];

    const problematicCount = summary ? summary.restricted + summary.action_blocked + summary.disabled + summary.checkpoint + (summary.session_invalid || 0) : 0;

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
                    <h2 className="page-header__title">Sorunlu Hesap Yönetimi</h2>
                    <p className="page-header__subtitle">
                        Hesap durumlarını kontrol edin, toplu itiraz gönderin
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary" onClick={handleCheckAll} disabled={checking}>
                        {checking ? '⏳ Kontrol Ediliyor...' : '🔍 Tümünü Kontrol Et'}
                    </button>
                    {problematicCount > 0 && (
                        <button className="btn btn-primary" onClick={handleBulkAppeal}>
                            📩 Toplu İtiraz ({selectedIds.size > 0 ? selectedIds.size : problematicCount} hesap)
                        </button>
                    )}
                </div>
            </div>

            {/* Kontrol ilerleme çubuğu */}
            {checking && checkProgress && (
                <div className="card" style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: '0.85rem' }}>
                        <span>🔍 Hesaplar kontrol ediliyor...</span>
                        <span>{checkProgress.checked} / {checkProgress.total}</span>
                    </div>
                    <div className="progress-bar">
                        <div className="progress-bar__fill" style={{
                            width: `${checkProgress.total > 0 ? (checkProgress.checked / checkProgress.total) * 100 : 0}%`
                        }} />
                    </div>
                    {checkProgress.problematic > 0 && (
                        <div style={{ marginTop: 8, fontSize: '0.8rem', color: '#e74c3c' }}>
                            ⚠️ {checkProgress.problematic} sorunlu hesap bulundu
                        </div>
                    )}
                </div>
            )}

            {/* Durum özeti kartları */}
            {summary && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 20 }}>
                    {[
                        { key: 'all', label: 'Toplam', value: summary.total, icon: '📊', color: 'var(--text-primary)' },
                        { key: 'active', label: 'Aktif', value: summary.active, icon: '✅', color: '#2ecc71' },
                        { key: 'restricted', label: 'Kısıtlı', value: summary.restricted, icon: '⚠️', color: '#e67e22' },
                        { key: 'action_blocked', label: 'Engelli', value: summary.action_blocked, icon: '🚫', color: '#e74c3c' },
                        { key: 'disabled', label: 'Devre Dışı', value: summary.disabled, icon: '💀', color: '#95a5a6' },
                        { key: 'session_invalid', label: 'Oturum Geçersiz', value: summary.session_invalid || 0, icon: '🔑', color: '#8e44ad' },
                        { key: 'checkpoint', label: 'Doğrulama', value: summary.checkpoint, icon: '🔒', color: '#f39c12' },
                    ].map(s => (
                        <div
                            key={s.key}
                            className="card"
                            onClick={() => setFilter(s.key === filter ? 'all' : s.key)}
                            style={{
                                cursor: 'pointer', textAlign: 'center', padding: '16px 12px',
                                border: filter === s.key ? `2px solid ${s.color}` : undefined,
                                transition: 'all 200ms ease',
                            }}
                        >
                            <div style={{ fontSize: '1.5rem', marginBottom: 4 }}>{s.icon}</div>
                            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color }}>{s.value}</div>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{s.label}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Filtreleme + toplu seçim */}
            {problematicCount > 0 && (
                <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                        className={`btn btn-sm ${filter === 'problematic' ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setFilter(filter === 'problematic' ? 'all' : 'problematic')}
                    >
                        🔴 Sorunlu Hesaplar ({problematicCount})
                    </button>
                    <button className="btn btn-sm btn-secondary" onClick={selectAllProblematic}>
                        ☑️ Tüm Sorunluları Seç
                    </button>
                    {selectedIds.size > 0 && (
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            {selectedIds.size} hesap seçildi
                        </span>
                    )}
                </div>
            )}

            {/* Hesap listesi */}
            {filteredAccounts.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">✅</div>
                    <div className="empty-state__title">
                        {filter === 'all' ? 'Henüz hesap eklenmemiş' : 'Bu kategoride hesap yok'}
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {filteredAccounts.map(acc => {
                        const config = STATUS_CONFIG[acc.account_status] || STATUS_CONFIG.unknown;
                        const isSelected = selectedIds.has(acc.id);

                        return (
                            <div
                                key={acc.id}
                                className="card"
                                style={{
                                    padding: '14px 16px',
                                    border: isSelected ? '2px solid var(--color-primary)' : undefined,
                                    background: isSelected ? 'rgba(233,30,144,0.04)' : undefined,
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, flexWrap: 'wrap' }}>
                                    {/* Checkbox */}
                                    {acc.account_status !== 'active' && (
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => toggleSelect(acc.id)}
                                            style={{ width: 18, height: 18, cursor: 'pointer', accentColor: 'var(--color-primary)' }}
                                        />
                                    )}

                                    {/* Avatar */}
                                    <div style={{
                                        width: 42, height: 42, borderRadius: '50%',
                                        background: 'var(--gradient-primary)', display: 'flex',
                                        alignItems: 'center', justifyContent: 'center',
                                        fontSize: '0.85rem', fontWeight: 600, color: '#fff', overflow: 'hidden',
                                    }}>
                                        {acc.profile_picture_url ? (
                                            <img src={acc.profile_picture_url} alt={acc.username}
                                                style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
                                        ) : acc.username?.[0]?.toUpperCase()}
                                    </div>

                                    {/* Bilgiler */}
                                    <div style={{ flex: 1, minWidth: 120 }}>
                                        <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                                            @{acc.username}
                                            {acc.full_name && <span style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: 6 }}>{acc.full_name}</span>}
                                        </div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                                            {acc.followers_count.toLocaleString()} takipçi
                                            {acc.last_checked_at && (
                                                <span> • Son kontrol: {new Date(acc.last_checked_at).toLocaleString('tr-TR')}</span>
                                            )}
                                        </div>
                                        {acc.status_message && acc.account_status !== 'active' && (
                                            <div style={{ fontSize: '0.72rem', color: config.color, marginTop: 4 }}>
                                                {acc.status_message}
                                            </div>
                                        )}
                                    </div>

                                    {/* Durum badge */}
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
                                        <span className={`badge ${config.badgeClass}`}>
                                            {config.icon} {config.label}
                                        </span>
                                        {acc.appeal_status !== 'none' && (
                                            <span className="badge badge-info" style={{ fontSize: '0.65rem' }}>
                                                📩 İtiraz: {acc.appeal_status === 'submitted' ? 'Gönderildi' : acc.appeal_status === 'pending' ? 'Bekliyor' : acc.appeal_status}
                                            </span>
                                        )}
                                    </div>

                                    {/* İşlemler */}
                                    <div style={{ display: 'flex', gap: 6 }}>
                                        <button className="btn btn-icon btn-secondary" onClick={() => handleCheckSingle(acc.id)} title="Kontrol Et">
                                            🔍
                                        </button>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
