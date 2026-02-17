'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function HashtagsPage() {
    const [groups, setGroups] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [form, setForm] = useState({ name: '', hashtags: '' });

    useEffect(() => { loadGroups(); }, []);

    const loadGroups = async () => {
        try {
            const data = await api.getHashtagGroups();
            setGroups(data.groups || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const handleCreate = async () => {
        const tags = form.hashtags.split(/[\n,]/).map(t => t.trim().replace(/^#/, '')).filter(Boolean);
        if (!form.name || tags.length === 0) return alert('Ad ve hashtag listesi gerekli');
        try {
            await api.createHashtagGroup({ name: form.name, hashtags: tags });
            setForm({ name: '', hashtags: '' });
            setShowCreate(false);
            loadGroups();
        } catch (err: any) { alert(err.message); }
    };

    const handleUpdate = async () => {
        if (!editId) return;
        const tags = form.hashtags.split(/[\n,]/).map(t => t.trim().replace(/^#/, '')).filter(Boolean);
        try {
            await api.updateHashtagGroup(editId, { name: form.name, hashtags: tags });
            setEditId(null);
            setForm({ name: '', hashtags: '' });
            loadGroups();
        } catch (err: any) { alert(err.message); }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Bu grubu silmek istediğinize emin misiniz?')) return;
        try { await api.deleteHashtagGroup(id); loadGroups(); }
        catch (err: any) { alert(err.message); }
    };

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">#️⃣ Hashtag Grupları</h2>
                    <p className="page-header__subtitle">{groups.length} grup</p>
                </div>
                <button className="btn btn-primary" onClick={() => { setShowCreate(true); setEditId(null); setForm({ name: '', hashtags: '' }); }}>
                    ➕ Yeni Grup
                </button>
            </div>

            <div className="info-box blue" style={{ marginBottom: 20 }}>
                Hashtag grupları oluşturun ve gönderilerinize kolayca ekleyin. Her gönderide farklı gruplardan
                hashtag çekerek çeşitlilik sağlayabilirsiniz.
            </div>

            {groups.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">#️⃣</div>
                    <div className="empty-state__title">Henüz hashtag grubu yok</div>
                    <p>Yeni grup oluşturmak için butonu kullanın</p>
                </div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
                    {groups.map((g: any) => (
                        <div key={g.id} className="card" style={{ padding: 20 }}>
                            <div className="flex-between" style={{ marginBottom: 12 }}>
                                <h4 style={{ fontWeight: 600 }}>{g.name}</h4>
                                <div style={{ display: 'flex', gap: 6 }}>
                                    <button
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => {
                                            setEditId(g.id);
                                            setForm({ name: g.name, hashtags: g.hashtags.join(', ') });
                                            setShowCreate(true);
                                        }}
                                    >
                                        ✏️
                                    </button>
                                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(g.id)}>🗑️</button>
                                </div>
                            </div>

                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                                {g.hashtags.slice(0, 15).map((tag: string, i: number) => (
                                    <span key={i} className="badge badge-primary" style={{ fontSize: '0.72rem' }}>
                                        #{tag}
                                    </span>
                                ))}
                                {g.hashtags.length > 15 && (
                                    <span className="badge badge-info">+{g.hashtags.length - 15} daha</span>
                                )}
                            </div>

                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: 16 }}>
                                <span>{g.hashtags.length} hashtag</span>
                                <span>{g.usage_count}× kullanıldı</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Oluştur/Düzenle Modal */}
            {showCreate && (
                <div className="modal-overlay" onClick={() => { setShowCreate(false); setEditId(null); }}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <h3 className="modal-title">
                            {editId ? '✏️ Grubu Düzenle' : '➕ Yeni Hashtag Grubu'}
                        </h3>

                        <div className="form-group">
                            <label className="form-label">Grup Adı</label>
                            <input
                                className="form-input"
                                placeholder="örn: Moda & Giyim"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Hashtagler (virgül veya yeni satırla ayırın)</label>
                            <textarea
                                className="form-input"
                                rows={6}
                                placeholder="moda, stil, giyim, trend, fashion..."
                                value={form.hashtags}
                                onChange={(e) => setForm({ ...form, hashtags: e.target.value })}
                            />
                        </div>

                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 16 }}>
                            {form.hashtags.split(/[\n,]/).filter(t => t.trim()).length} hashtag girildi
                        </div>

                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => { setShowCreate(false); setEditId(null); }}>İptal</button>
                            <button className="btn btn-primary" onClick={editId ? handleUpdate : handleCreate}>
                                {editId ? '💾 Güncelle' : '➕ Oluştur'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
