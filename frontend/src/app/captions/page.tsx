'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface CaptionItem {
    id: number;
    text: string;
    display_order: number;
    is_active: boolean;
    use_count: number;
    created_at: string;
}

export default function CaptionsPage() {
    const [captions, setCaptions] = useState<CaptionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [newCaption, setNewCaption] = useState('');
    const [bulkText, setBulkText] = useState('');
    const [showBulk, setShowBulk] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [editText, setEditText] = useState('');
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    const loadCaptions = useCallback(async () => {
        try {
            const data = await api.getCaptions();
            setCaptions(data.items || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { loadCaptions(); }, [loadCaptions]);

    const handleAddSingle = async () => {
        if (!newCaption.trim()) return;
        try {
            await api.createCaption({ text: newCaption.trim() });
            setNewCaption('');
            setShowAdd(false);
            showToast('success', '✅ Caption eklendi');
            loadCaptions();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleBulkImport = async () => {
        if (!bulkText.trim()) return;
        try {
            const result = await api.bulkImportCaptions(bulkText);
            setBulkText('');
            setShowBulk(false);
            showToast('success', `✅ ${result.added} caption eklendi`);
            loadCaptions();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleUpdate = async (id: number) => {
        if (!editText.trim()) return;
        try {
            await api.updateCaption(id, { text: editText.trim() });
            setEditId(null);
            showToast('success', '✅ Güncellendi');
            loadCaptions();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleToggle = async (caption: CaptionItem) => {
        try {
            await api.updateCaption(caption.id, { is_active: !caption.is_active });
            loadCaptions();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Bu caption\'ı silmek istediğinize emin misiniz?')) return;
        try {
            await api.deleteCaption(id);
            showToast('success', '🗑️ Silindi');
            loadCaptions();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleDeleteAll = async () => {
        if (!confirm('TÜM caption\'ları silmek istediğinize emin misiniz?')) return;
        try {
            await api.deleteAllCaptions();
            showToast('success', '🗑️ Tümü silindi');
            loadCaptions();
        } catch (err: any) { showToast('error', err.message); }
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
            <style>{`@keyframes slideIn { from { opacity: 0; transform: translateX(30px); } to { opacity: 1; transform: translateX(0); } }`}</style>

            {/* Header */}
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Paylaşım Yazıları (Caption)</h2>
                    <p className="page-header__subtitle">{captions.length} caption · {captions.filter(c => c.is_active).length} aktif</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    {captions.length > 0 && (
                        <button className="btn btn-danger" onClick={handleDeleteAll} style={{ fontSize: '0.75rem' }}>
                            🗑️ Tümünü Sil
                        </button>
                    )}
                    <button className="btn btn-secondary" onClick={() => { setShowBulk(!showBulk); setShowAdd(false); }}>
                        📋 Toplu Ekle
                    </button>
                    <button className="btn btn-primary" onClick={() => { setShowAdd(!showAdd); setShowBulk(false); }}>
                        ➕ Tek Ekle
                    </button>
                </div>
            </div>

            {/* Tek Ekleme */}
            {showAdd && (
                <div className="card" style={{ marginBottom: 16, padding: 20 }}>
                    <h3 style={{ marginBottom: 12, fontSize: '0.95rem', fontWeight: 700 }}>➕ Yeni Caption</h3>
                    <textarea
                        className="form-input"
                        rows={4}
                        placeholder="Paylaşım yazısını buraya yazın... #hashtag #desteği #var"
                        value={newCaption}
                        onChange={e => setNewCaption(e.target.value)}
                        style={{ marginBottom: 12 }}
                    />
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>İptal</button>
                        <button className="btn btn-primary" onClick={handleAddSingle} disabled={!newCaption.trim()}>Kaydet</button>
                    </div>
                </div>
            )}

            {/* Toplu Ekleme */}
            {showBulk && (
                <div className="card" style={{ marginBottom: 16, padding: 20 }}>
                    <h3 style={{ marginBottom: 12, fontSize: '0.95rem', fontWeight: 700 }}>📋 Toplu Caption Import</h3>
                    <div className="info-box blue" style={{ marginBottom: 12 }}>
                        Her satır bir caption olarak eklenecektir. Hashtag ve emoji desteği vardır.
                    </div>
                    <textarea
                        className="form-input"
                        rows={8}
                        placeholder={`Bu harika bir gün! ☀️ #günaydın #mutluluk\nHayallerinizin peşinden gidin 🌟 #motivasyon\nDoğanın güzelliği... 🌿 #doğa #tabiat`}
                        value={bulkText}
                        onChange={e => setBulkText(e.target.value)}
                        style={{ fontFamily: 'monospace', fontSize: '0.82rem', marginBottom: 12 }}
                    />
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {bulkText.split('\n').filter(l => l.trim()).length} satır
                        </span>
                        <button className="btn btn-secondary" onClick={() => setShowBulk(false)}>İptal</button>
                        <button className="btn btn-primary" onClick={handleBulkImport} disabled={!bulkText.trim()}>
                            📥 İçe Aktar
                        </button>
                    </div>
                </div>
            )}

            {/* Caption Listesi */}
            {captions.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">📝</div>
                    <div className="empty-state__title">Henüz caption eklenmemiş</div>
                    <p style={{ color: 'var(--text-secondary)', maxWidth: 400, margin: '8px auto' }}>
                        Paylaşım yazılarınızı ekleyin. Bot, paylaşım yaparken bu listeden sıralı veya rastgele seçim yapacaktır.
                    </p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {captions.map((c, index) => (
                        <div key={c.id} className="card" style={{
                            padding: '16px 20px', display: 'flex', alignItems: 'flex-start', gap: 16,
                            opacity: c.is_active ? 1 : 0.5,
                            borderLeft: `3px solid ${c.is_active ? 'var(--accent-primary, #667eea)' : 'transparent'}`,
                        }}>
                            {/* Sıra Numarası */}
                            <div style={{
                                width: 28, height: 28, borderRadius: '50%',
                                background: 'rgba(102,126,234,0.15)', display: 'flex',
                                alignItems: 'center', justifyContent: 'center',
                                fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-primary, #667eea)',
                                flexShrink: 0,
                            }}>
                                {index + 1}
                            </div>

                            {/* İçerik */}
                            <div style={{ flex: 1, minWidth: 0 }}>
                                {editId === c.id ? (
                                    <div>
                                        <textarea
                                            className="form-input"
                                            rows={3}
                                            value={editText}
                                            onChange={e => setEditText(e.target.value)}
                                            autoFocus
                                            style={{ marginBottom: 8 }}
                                        />
                                        <div style={{ display: 'flex', gap: 6 }}>
                                            <button className="btn btn-sm btn-primary" onClick={() => handleUpdate(c.id)}>Kaydet</button>
                                            <button className="btn btn-sm btn-secondary" onClick={() => setEditId(null)}>İptal</button>
                                        </div>
                                    </div>
                                ) : (
                                    <div style={{
                                        fontSize: '0.85rem', lineHeight: 1.6, color: 'var(--text-primary)',
                                        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                    }}>
                                        {c.text}
                                    </div>
                                )}
                                <div style={{ marginTop: 6, fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                    {c.use_count > 0 && <span>🔄 {c.use_count} kez kullanıldı · </span>}
                                    {new Date(c.created_at).toLocaleDateString('tr-TR')}
                                </div>
                            </div>

                            {/* İşlemler */}
                            <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                                <button
                                    className="btn btn-sm btn-secondary"
                                    onClick={() => handleToggle(c)}
                                    title={c.is_active ? 'Devre dışı bırak' : 'Aktif et'}
                                >
                                    {c.is_active ? '🟢' : '⚫'}
                                </button>
                                <button
                                    className="btn btn-sm btn-secondary"
                                    onClick={() => { setEditId(c.id); setEditText(c.text); }}
                                    title="Düzenle"
                                >✏️</button>
                                <button
                                    className="btn btn-sm btn-danger"
                                    onClick={() => handleDelete(c.id)}
                                    title="Sil"
                                >🗑️</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
