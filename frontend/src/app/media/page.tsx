'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '@/lib/api';

interface MediaItem {
    id: number;
    filename: string;
    original_filename: string;
    media_type: string;
    folder: string;
    width: number | null;
    height: number | null;
    file_size: number;
    thumbnail_url: string | null;
    file_url: string;
    created_at: string;
}

interface AccountOption {
    id: number;
    username: string;
}

export default function MediaPage() {
    const [media, setMedia] = useState<MediaItem[]>([]);
    const [counts, setCounts] = useState<Record<string, number>>({});
    const [folders, setFolders] = useState<string[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ media_type: '', folder: '', account_id: '' });
    const [uploading, setUploading] = useState(false);
    const [accounts, setAccounts] = useState<AccountOption[]>([]);
    const [lightbox, setLightbox] = useState<MediaItem | null>(null);
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    // Hesap listesi yükle
    useEffect(() => {
        (async () => {
            try {
                const data = await api.getAccounts();
                setAccounts((data || []).map((a: any) => ({ id: a.id, username: a.username })));
            } catch { }
        })();
    }, []);

    const loadMedia = useCallback(async () => {
        try {
            const params: Record<string, string> = {};
            if (filter.media_type) params.media_type = filter.media_type;
            if (filter.folder) params.folder = filter.folder;
            if (filter.account_id) params.account_id = filter.account_id;
            const data = await api.getMedia(params);
            setMedia(data.items || []);
            setCounts(data.counts || {});
            setFolders(data.folders || []);
            setTotal(data.total || 0);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    }, [filter]);

    useEffect(() => { loadMedia(); }, [loadMedia]);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;
        setUploading(true);
        try {
            await api.uploadMedia(Array.from(files), filter.media_type || 'photo');
            showToast('success', `✅ ${files.length} dosya yüklendi`);
            loadMedia();
        } catch (err: any) { showToast('error', err.message); }
        finally { setUploading(false); }
    };

    const handleResize = async (id: number, ratio: string) => {
        try {
            await api.resizeMedia(id, ratio);
            showToast('success', `✅ ${ratio} olarak boyutlandırıldı`);
            loadMedia();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Bu medyayı silmek istediğinize emin misiniz?')) return;
        try { await api.deleteMedia(id); loadMedia(); showToast('success', '🗑️ Silindi'); }
        catch (err: any) { showToast('error', err.message); }
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1048576).toFixed(1)} MB`;
    };

    // Medya URL'ini doğru oluştur
    // Electron proxy /uploads/* isteklerini doğrudan backend'e yönlendiriyor
    // /api prefix eklemeye GEREK YOK, aksi halde backend'de 404 alır
    const getMediaUrl = (path: string | null) => {
        if (!path) return null;
        // /uploads/ ile başlıyorsa direkt kullan (Electron proxy yönlendirir)
        if (path.startsWith('/uploads/')) return path;
        if (path.startsWith('/api/')) return path;
        return `/uploads/${path}`;
    };

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
            <style>{`
                @keyframes slideIn { from { opacity: 0; transform: translateX(30px); } to { opacity: 1; transform: translateX(0); } }
                @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
                @keyframes scaleIn { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }
            `}</style>

            {/* Lightbox Modal */}
            {lightbox && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 10001,
                    background: 'rgba(0,0,0,0.9)', backdropFilter: 'blur(20px)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    animation: 'fadeIn 0.2s ease', cursor: 'pointer',
                }} onClick={() => setLightbox(null)}>
                    <div style={{
                        position: 'relative', maxWidth: '90vw', maxHeight: '90vh',
                        animation: 'scaleIn 0.25s ease',
                    }} onClick={e => e.stopPropagation()}>
                        {lightbox.media_type === 'video' ? (
                            <video
                                src={getMediaUrl(lightbox.file_url) || ''}
                                controls autoPlay
                                style={{ maxWidth: '90vw', maxHeight: '85vh', borderRadius: 12 }}
                            />
                        ) : (
                            <img
                                src={getMediaUrl(lightbox.file_url) || ''}
                                alt={lightbox.original_filename}
                                style={{ maxWidth: '90vw', maxHeight: '85vh', borderRadius: 12, objectFit: 'contain' }}
                            />
                        )}
                        {/* Info Bar */}
                        <div style={{
                            position: 'absolute', bottom: -48, left: 0, right: 0,
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '8px 0', color: 'rgba(255,255,255,0.7)', fontSize: '0.8rem',
                        }}>
                            <span>{lightbox.original_filename}</span>
                            <span>
                                {lightbox.width && lightbox.height ? `${lightbox.width}×${lightbox.height} · ` : ''}
                                {formatSize(lightbox.file_size || 0)}
                            </span>
                        </div>
                        {/* Close */}
                        <button onClick={() => setLightbox(null)} style={{
                            position: 'absolute', top: -16, right: -16, width: 36, height: 36,
                            borderRadius: '50%', background: 'rgba(255,255,255,0.15)',
                            border: '1px solid rgba(255,255,255,0.2)', color: '#fff',
                            fontSize: '1.1rem', cursor: 'pointer', display: 'flex',
                            alignItems: 'center', justifyContent: 'center',
                        }}>✕</button>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Medya Kütüphanesi</h2>
                    <p className="page-header__subtitle">{total} dosya</p>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    {/* Hesap Filtresi */}
                    <select
                        className="form-select"
                        value={filter.account_id}
                        onChange={e => setFilter({ ...filter, account_id: e.target.value })}
                        style={{ minWidth: 160, padding: '8px 12px', fontSize: '0.82rem' }}
                    >
                        <option value="">👥 Tüm Hesaplar</option>
                        {accounts.map(a => (
                            <option key={a.id} value={a.id}>@{a.username}</option>
                        ))}
                    </select>

                    <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        accept="image/*,video/*"
                        style={{ display: 'none' }}
                        onChange={handleUpload}
                    />
                    <button
                        className="btn btn-primary"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                    >
                        {uploading ? '⏳ Yükleniyor...' : '📤 Dosya Yükle'}
                    </button>
                </div>
            </div>

            {/* Tür Filtreleri — Tab */}
            <div className="tabs">
                <div
                    className={`tab ${filter.media_type === '' ? 'active' : ''}`}
                    onClick={() => setFilter({ ...filter, media_type: '' })}
                >
                    Tümü <span className="tab-count">{total}</span>
                </div>
                {Object.entries(counts).map(([type, count]) => (
                    <div
                        key={type}
                        className={`tab ${filter.media_type === type ? 'active' : ''}`}
                        onClick={() => setFilter({ ...filter, media_type: type })}
                    >
                        {type === 'photo' ? '📷 Fotoğraf' : type === 'video' ? '🎬 Video' : type === 'reels' ? '🎭 Reels' : '👤 Profil'}
                        <span className="tab-count">{count}</span>
                    </div>
                ))}
            </div>

            {/* Klasör / Liste Filtreleri */}
            {folders.length > 0 && (
                <div className="tabs" style={{ marginTop: 8 }}>
                    <div
                        className={`tab ${filter.folder === '' ? 'active' : ''}`}
                        onClick={() => setFilter({ ...filter, folder: '' })}
                    >
                        📂 Tüm Klasörler
                    </div>
                    {folders.map(f => (
                        <div
                            key={f}
                            className={`tab ${filter.folder === f ? 'active' : ''}`}
                            onClick={() => setFilter({ ...filter, folder: f })}
                        >
                            📁 {f}
                        </div>
                    ))}
                </div>
            )}

            {/* Medya Grid */}
            {media.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">🖼️</div>
                    <div className="empty-state__title">Medya dosyası bulunamadı</div>
                    <p>Dosya yüklemek için yukarıdaki butonu kullanın</p>
                </div>
            ) : (
                <div className="media-grid">
                    {media.map((m: MediaItem) => (
                        <div
                            key={m.id}
                            className="media-item"
                            onClick={() => setLightbox(m)}
                            style={{ cursor: 'pointer' }}
                        >
                            {m.thumbnail_url ? (
                                <img
                                    src={getMediaUrl(m.thumbnail_url) || ''}
                                    alt={m.original_filename}
                                    loading="lazy"
                                    onError={(e) => {
                                        // Thumbnail yoksa ana dosyayı dene
                                        const target = e.target as HTMLImageElement;
                                        if (!target.dataset.fallback) {
                                            target.dataset.fallback = '1';
                                            target.src = getMediaUrl(m.file_url) || '';
                                        }
                                    }}
                                />
                            ) : m.file_url && m.media_type === 'photo' ? (
                                <img
                                    src={getMediaUrl(m.file_url) || ''}
                                    alt={m.original_filename}
                                    loading="lazy"
                                />
                            ) : (
                                <div className="flex-center" style={{ height: '100%', background: 'var(--bg-surface)', fontSize: '2rem' }}>
                                    {m.media_type === 'video' ? '🎬' : m.media_type === 'reels' ? '🎭' : '📷'}
                                </div>
                            )}

                            {/* Video badge */}
                            {(m.media_type === 'video' || m.media_type === 'reels') && (
                                <div style={{
                                    position: 'absolute', top: 8, left: 8,
                                    background: 'rgba(0,0,0,0.6)', borderRadius: 6, padding: '2px 8px',
                                    fontSize: '0.65rem', fontWeight: 600, color: '#fff',
                                }}>
                                    {m.media_type === 'video' ? '▶ Video' : '🎭 Reels'}
                                </div>
                            )}

                            <div className="media-item__overlay">
                                <div style={{ width: '100%' }}>
                                    <div style={{
                                        fontSize: '0.75rem', fontWeight: 600, color: 'white', marginBottom: 4,
                                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                                    }}>
                                        {m.original_filename}
                                    </div>
                                    <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.7)' }}>
                                        {m.width && m.height ? `${m.width}×${m.height} · ` : ''}{formatSize(m.file_size || 0)}
                                    </div>
                                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }} onClick={e => e.stopPropagation()}>
                                        {m.media_type === 'photo' && (
                                            <>
                                                <button className="btn btn-sm btn-secondary" onClick={() => handleResize(m.id, '1:1')}>1:1</button>
                                                <button className="btn btn-sm btn-secondary" onClick={() => handleResize(m.id, '4:5')}>4:5</button>
                                                <button className="btn btn-sm btn-secondary" onClick={() => handleResize(m.id, '9:16')}>9:16</button>
                                            </>
                                        )}
                                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(m.id)}>🗑️</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
