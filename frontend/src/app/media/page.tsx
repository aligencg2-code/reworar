'use client';

import { useEffect, useState, useRef } from 'react';
import { api } from '@/lib/api';

export default function MediaPage() {
    const [media, setMedia] = useState<any[]>([]);
    const [counts, setCounts] = useState<Record<string, number>>({});
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ media_type: '', folder: '' });
    const [uploading, setUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => { loadMedia(); }, [filter]);

    const loadMedia = async () => {
        try {
            const params: Record<string, string> = {};
            if (filter.media_type) params.media_type = filter.media_type;
            if (filter.folder) params.folder = filter.folder;
            const data = await api.getMedia(params);
            setMedia(data.items || []);
            setCounts(data.counts || {});
            setTotal(data.total || 0);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setUploading(true);
        try {
            await api.uploadMedia(Array.from(files), filter.media_type || 'photo');
            loadMedia();
        } catch (err: any) { alert(err.message); }
        finally { setUploading(false); }
    };

    const handleResize = async (id: number, ratio: string) => {
        try {
            await api.resizeMedia(id, ratio);
            loadMedia();
        } catch (err: any) { alert(err.message); }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Bu medyayı silmek istediğinize emin misiniz?')) return;
        try { await api.deleteMedia(id); loadMedia(); }
        catch (err: any) { alert(err.message); }
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1048576).toFixed(1)} MB`;
    };

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Medya Kütüphanesi</h2>
                    <p className="page-header__subtitle">{total} dosya</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
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

            {/* Medya Grid */}
            {media.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">🖼️</div>
                    <div className="empty-state__title">Medya dosyası bulunamadı</div>
                    <p>Dosya yüklemek için yukarıdaki butonu kullanın</p>
                </div>
            ) : (
                <div className="media-grid">
                    {media.map((m: any) => (
                        <div key={m.id} className="media-item">
                            {m.thumbnail_url ? (
                                <img src={`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api'}${m.thumbnail_url}`} alt={m.filename} />
                            ) : (
                                <div className="flex-center" style={{ height: '100%', background: 'var(--bg-surface)' }}>
                                    {m.media_type === 'video' ? '🎬' : '📷'}
                                </div>
                            )}
                            <div className="media-item__overlay">
                                <div style={{ width: '100%' }}>
                                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'white', marginBottom: 4 }}>
                                        {m.original_filename}
                                    </div>
                                    <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.7)' }}>
                                        {m.width && m.height ? `${m.width}×${m.height} • ` : ''}{formatSize(m.file_size || 0)}
                                    </div>
                                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                                        {m.media_type === 'photo' && (
                                            <>
                                                <button className="btn btn-sm btn-secondary" onClick={(e) => { e.stopPropagation(); handleResize(m.id, '1:1'); }}>1:1</button>
                                                <button className="btn btn-sm btn-secondary" onClick={(e) => { e.stopPropagation(); handleResize(m.id, '4:5'); }}>4:5</button>
                                                <button className="btn btn-sm btn-secondary" onClick={(e) => { e.stopPropagation(); handleResize(m.id, '9:16'); }}>9:16</button>
                                            </>
                                        )}
                                        <button className="btn btn-sm btn-danger" onClick={(e) => { e.stopPropagation(); handleDelete(m.id); }}>🗑️</button>
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
