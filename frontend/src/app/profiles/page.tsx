'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '@/lib/api';

interface ProfileInfo {
    id: number;
    username: string;
    full_name: string | null;
    biography: string | null;
    profile_picture_url: string | null;
    followers_count: number;
    following_count: number;
    media_count: number;
    is_active: boolean;
    proxy_url: string | null;
    daily_post_limit: number;
    photo_percentage: number;
    video_percentage: number;
    posting_mode: string;
    auto_publish: boolean;
    created_at: string | null;
}

export default function ProfilesPage() {
    const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [editData, setEditData] = useState<any>({});
    const [igEditId, setIgEditId] = useState<number | null>(null);
    const [igEditData, setIgEditData] = useState<any>({});
    const [igSaving, setIgSaving] = useState(false);
    const [photoUploading, setPhotoUploading] = useState(false);
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
    const photoInputRef = useRef<HTMLInputElement>(null);
    const [photoTargetId, setPhotoTargetId] = useState<number | null>(null);

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    const loadProfiles = useCallback(async () => {
        try {
            const data = await api.request<ProfileInfo[]>('/profiles/all');
            setProfiles(data);
        } catch (err: any) {
            showToast('error', err.message || 'Profiller yüklenemedi');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadProfiles(); }, [loadProfiles]);

    const handleRefreshAll = async () => {
        setRefreshing(true);
        try {
            await api.request('/profiles/refresh-all', { method: 'POST' });
            showToast('success', '🔄 Tüm profiller yenileniyor...');
            setTimeout(() => { loadProfiles(); setRefreshing(false); }, 5000);
        } catch (err: any) {
            setRefreshing(false);
            showToast('error', err.message);
        }
    };

    const handleRefreshSingle = async (id: number) => {
        try {
            await api.request(`/profiles/${id}/refresh`, { method: 'POST' });
            showToast('success', '✅ Profil güncellendi');
            loadProfiles();
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    // ─── Yerel ayarlar düzenleme ─────────────────────────────
    const startEdit = (profile: ProfileInfo) => {
        setEditId(profile.id);
        setEditData({
            daily_post_limit: profile.daily_post_limit,
            auto_publish: profile.auto_publish,
            photo_percentage: profile.photo_percentage,
            video_percentage: profile.video_percentage,
            posting_mode: profile.posting_mode,
            proxy_url: profile.proxy_url || '',
        });
    };

    const handleSave = async (id: number) => {
        try {
            await api.request(`/profiles/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editData),
            });
            showToast('success', '✅ Ayarlar kaydedildi');
            setEditId(null);
            loadProfiles();
        } catch (err: any) {
            showToast('error', err.message);
        }
    };

    // ─── Instagram profil düzenleme ──────────────────────────
    const startIgEdit = (profile: ProfileInfo) => {
        setIgEditId(profile.id);
        setIgEditData({
            full_name: profile.full_name || '',
            biography: profile.biography || '',
            external_url: '',
            username: profile.username || '',
        });
    };

    const handleIgSave = async (id: number) => {
        setIgSaving(true);
        try {
            // Sadece değişen alanları gönder
            const payload: any = {};
            const profile = profiles.find(p => p.id === id);
            if (igEditData.full_name !== (profile?.full_name || ''))
                payload.full_name = igEditData.full_name;
            if (igEditData.biography !== (profile?.biography || ''))
                payload.biography = igEditData.biography;
            if (igEditData.external_url)
                payload.external_url = igEditData.external_url;
            if (igEditData.username !== (profile?.username || ''))
                payload.username = igEditData.username;

            if (Object.keys(payload).length === 0) {
                showToast('error', 'Değişiklik yapılmadı');
                setIgSaving(false);
                return;
            }

            await api.request(`/profiles/${id}/update-instagram`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            showToast('success', '✅ Instagram profili güncellendi!');
            setIgEditId(null);
            loadProfiles();
        } catch (err: any) {
            showToast('error', err.message || 'Instagram güncelleme başarısız');
        } finally {
            setIgSaving(false);
        }
    };

    // ─── Profil fotoğrafı değiştirme ─────────────────────────
    const handlePhotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !photoTargetId) return;

        setPhotoUploading(true);
        try {
            const formData = new FormData();
            formData.append('photo', file);

            const token = localStorage.getItem('access_token');
            const response = await fetch(`/api/profiles/${photoTargetId}/update-photo`, {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Fotoğraf yüklenemedi');
            }

            showToast('success', '✅ Profil fotoğrafı güncellendi!');
            loadProfiles();
        } catch (err: any) {
            showToast('error', err.message || 'Fotoğraf güncelleme başarısız');
        } finally {
            setPhotoUploading(false);
            setPhotoTargetId(null);
            if (photoInputRef.current) photoInputRef.current.value = '';
        }
    };

    if (loading) {
        return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;
    }

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

            {/* Hidden file input */}
            <input
                type="file"
                ref={photoInputRef}
                accept="image/*"
                style={{ display: 'none' }}
                onChange={handlePhotoChange}
            />

            {/* Header */}
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Profil Yönetimi</h2>
                    <p className="page-header__subtitle">Instagram hesap bilgilerini düzenleyin — bio, isim, link, fotoğraf</p>
                </div>
                <button className="btn btn-secondary" onClick={handleRefreshAll} disabled={refreshing}>
                    {refreshing ? '⏳ Yenileniyor...' : '🔄 Tüm Profilleri Yenile'}
                </button>
            </div>

            {/* Profil Listesi */}
            {profiles.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">👤</div>
                    <div className="empty-state__title">Henüz hesap eklenmemiş</div>
                    <p>Hesaplar sayfasından Instagram hesabı ekleyin</p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {profiles.map(profile => {
                        const isEditing = editId === profile.id;
                        const isIgEditing = igEditId === profile.id;

                        return (
                            <div key={profile.id} className="card" style={{ padding: '20px' }}>
                                {/* Profil Header */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: (isEditing || isIgEditing) ? 20 : 0 }}>
                                    {/* Avatar — tıklanabilir (fotoğraf değiştirir) */}
                                    <div
                                        style={{
                                            width: 64, height: 64, borderRadius: '50%',
                                            background: 'var(--gradient-primary)', display: 'flex',
                                            alignItems: 'center', justifyContent: 'center',
                                            fontSize: '1.4rem', fontWeight: 700, color: '#fff', overflow: 'hidden',
                                            flexShrink: 0, cursor: 'pointer', position: 'relative',
                                            border: '2px solid transparent',
                                            transition: 'border-color 0.2s',
                                        }}
                                        title="Profil fotoğrafını değiştir"
                                        onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                                        onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
                                        onClick={() => {
                                            setPhotoTargetId(profile.id);
                                            photoInputRef.current?.click();
                                        }}
                                    >
                                        {photoUploading && photoTargetId === profile.id ? (
                                            <div className="spinner" style={{ width: 24, height: 24 }} />
                                        ) : profile.profile_picture_url ? (
                                            <img src={profile.profile_picture_url} alt={profile.username}
                                                style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                        ) : profile.username?.[0]?.toUpperCase()}
                                        {/* Camera overlay */}
                                        <div style={{
                                            position: 'absolute', bottom: 0, right: 0,
                                            width: 22, height: 22, borderRadius: '50%',
                                            background: 'var(--color-primary)', display: 'flex',
                                            alignItems: 'center', justifyContent: 'center',
                                            fontSize: '0.7rem', border: '2px solid var(--bg-card)',
                                        }}>📷</div>
                                    </div>

                                    {/* Bilgiler */}
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>
                                            @{profile.username}
                                            <span className={`badge ${profile.is_active ? 'badge-success' : 'badge-error'}`}
                                                style={{ marginLeft: 8, fontSize: '0.65rem' }}>
                                                {profile.is_active ? '● Aktif' : '○ Pasif'}
                                            </span>
                                        </div>
                                        {profile.full_name && (
                                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                                                {profile.full_name}
                                            </div>
                                        )}
                                        {profile.biography && (
                                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 500 }}>
                                                {profile.biography}
                                            </div>
                                        )}

                                        {/* İstatistikler */}
                                        <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: '0.8rem' }}>
                                            <span><b>{(profile.followers_count || 0).toLocaleString()}</b> takipçi</span>
                                            <span><b>{(profile.following_count || 0).toLocaleString()}</b> takip</span>
                                            <span><b>{(profile.media_count || 0).toLocaleString()}</b> gönderi</span>
                                        </div>
                                    </div>

                                    {/* İşlemler */}
                                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                        <button className="btn btn-sm btn-secondary" onClick={() => handleRefreshSingle(profile.id)}>
                                            🔄
                                        </button>
                                        {/* Instagram Profil Düzenle */}
                                        {isIgEditing ? (
                                            <>
                                                <button className="btn btn-sm btn-primary" onClick={() => handleIgSave(profile.id)} disabled={igSaving}>
                                                    {igSaving ? '⏳' : '💾'} Instagram Kaydet
                                                </button>
                                                <button className="btn btn-sm btn-secondary" onClick={() => setIgEditId(null)}>İptal</button>
                                            </>
                                        ) : (
                                            <button className="btn btn-sm btn-primary" onClick={() => startIgEdit(profile)}
                                                style={{ background: 'linear-gradient(135deg, #E1306C, #C13584, #833AB4)', border: 'none' }}>
                                                ✏️ Profil Düzenle
                                            </button>
                                        )}
                                        {/* Yerel Ayarlar */}
                                        {isEditing ? (
                                            <>
                                                <button className="btn btn-sm btn-secondary" onClick={() => handleSave(profile.id)}>💾 Ayarları Kaydet</button>
                                                <button className="btn btn-sm btn-secondary" onClick={() => setEditId(null)}>İptal</button>
                                            </>
                                        ) : (
                                            <button className="btn btn-sm btn-secondary" onClick={() => startEdit(profile)}>⚙️ Ayarlar</button>
                                        )}
                                    </div>
                                </div>

                                {/* Instagram Profil Düzenleme Formu */}
                                {isIgEditing && (
                                    <div style={{
                                        borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 16, marginTop: 12,
                                    }}>
                                        <div style={{
                                            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
                                            fontSize: '0.8rem', color: 'var(--text-secondary)',
                                        }}>
                                            <span style={{ fontSize: '1.1rem' }}>📸</span>
                                            <b>Instagram Profil Düzenleme</b> — Bu değişiklikler Instagram&apos;a yansır
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 12 }}>
                                            <div className="form-group">
                                                <label className="form-label">Kullanıcı Adı</label>
                                                <input className="form-input" value={igEditData.username}
                                                    placeholder="kullanici_adi"
                                                    onChange={e => setIgEditData({ ...igEditData, username: e.target.value })} />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Tam İsim</label>
                                                <input className="form-input" value={igEditData.full_name}
                                                    placeholder="İsim Soyisim"
                                                    onChange={e => setIgEditData({ ...igEditData, full_name: e.target.value })} />
                                            </div>
                                            <div className="form-group" style={{ gridColumn: 'span 2' }}>
                                                <label className="form-label">Biyografi</label>
                                                <textarea className="form-input" value={igEditData.biography}
                                                    placeholder="Profil açıklamanız..."
                                                    rows={3}
                                                    style={{ resize: 'vertical', minHeight: 60 }}
                                                    onChange={e => setIgEditData({ ...igEditData, biography: e.target.value })} />
                                            </div>
                                            <div className="form-group" style={{ gridColumn: 'span 2' }}>
                                                <label className="form-label">Web Sitesi / Link</label>
                                                <input className="form-input" value={igEditData.external_url}
                                                    placeholder="https://siteniz.com"
                                                    onChange={e => setIgEditData({ ...igEditData, external_url: e.target.value })} />
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Yerel Ayarlar Düzenleme Formu */}
                                {isEditing && (
                                    <div style={{
                                        borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 16, marginTop: 12,
                                    }}>
                                        <div style={{
                                            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
                                            fontSize: '0.8rem', color: 'var(--text-secondary)',
                                        }}>
                                            <span style={{ fontSize: '1.1rem' }}>⚙️</span>
                                            <b>Uygulama Ayarları</b> — Bu ayarlar sadece Demet uygulamasında geçerlidir
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                                            <div className="form-group">
                                                <label className="form-label">Proxy URL</label>
                                                <input className="form-input" placeholder="socks5://user:pass@ip:port"
                                                    value={editData.proxy_url}
                                                    onChange={e => setEditData({ ...editData, proxy_url: e.target.value })} />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Günlük Paylaşım Limiti</label>
                                                <input type="number" className="form-input" min={1} max={50}
                                                    value={editData.daily_post_limit}
                                                    onChange={e => setEditData({ ...editData, daily_post_limit: parseInt(e.target.value) || 5 })} />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Fotoğraf %</label>
                                                <input type="number" className="form-input" min={0} max={100}
                                                    value={editData.photo_percentage}
                                                    onChange={e => setEditData({ ...editData, photo_percentage: parseInt(e.target.value) || 0 })} />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Video %</label>
                                                <input type="number" className="form-input" min={0} max={100}
                                                    value={editData.video_percentage}
                                                    onChange={e => setEditData({ ...editData, video_percentage: parseInt(e.target.value) || 0 })} />
                                            </div>
                                            <div className="form-group">
                                                <label className="form-label">Paylaşım Modu</label>
                                                <select className="form-select" value={editData.posting_mode}
                                                    onChange={e => setEditData({ ...editData, posting_mode: e.target.value })}>
                                                    <option value="manual">Manuel</option>
                                                    <option value="automatic">Otomatik</option>
                                                    <option value="semi_auto">Yarı Otomatik</option>
                                                </select>
                                            </div>
                                            <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 24 }}>
                                                <input type="checkbox" checked={editData.auto_publish}
                                                    onChange={e => setEditData({ ...editData, auto_publish: e.target.checked })}
                                                    style={{ width: 18, height: 18, accentColor: 'var(--color-primary)' }} />
                                                <label className="form-label" style={{ margin: 0 }}>Otomatik Yayınla</label>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
