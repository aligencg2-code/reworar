'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface LocationItem {
    id: number;
    list_name: string;
    name: string;
    city: string | null;
    instagram_location_pk: string | null;
    lat: string | null;
    lng: string | null;
    is_active: boolean;
    created_at: string;
}

export default function LocationsPage() {
    const [locations, setLocations] = useState<LocationItem[]>([]);
    const [lists, setLists] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeList, setActiveList] = useState('');
    const [showAdd, setShowAdd] = useState(false);
    const [showBulk, setShowBulk] = useState(false);
    const [showNewList, setShowNewList] = useState(false);
    const [newListName, setNewListName] = useState('');
    const [bulkText, setBulkText] = useState('');
    const [bulkListName, setBulkListName] = useState('');
    const [newLoc, setNewLoc] = useState({ name: '', city: '', list_name: '' });
    const [editId, setEditId] = useState<number | null>(null);
    const [editData, setEditData] = useState<any>({});
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    const loadLocations = useCallback(async () => {
        try {
            const params: Record<string, string> = {};
            if (activeList) params.list_name = activeList;
            const query = Object.keys(params).length
                ? '?' + new URLSearchParams(params).toString()
                : '';
            const data = await api.getLocations(undefined);
            setLocations(data.items || []);
            setLists(data.lists || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { loadLocations(); }, [loadLocations]);

    // Aktif listeye göre filtrelenmiş konumlar
    const filteredLocations = activeList
        ? locations.filter(l => l.list_name === activeList)
        : locations;

    // Liste bazında gruplanmış konumlar (Tümü görünümü için)
    const groupedByList = locations.reduce((acc, loc) => {
        const key = loc.list_name || 'Genel';
        if (!acc[key]) acc[key] = [];
        acc[key].push(loc);
        return acc;
    }, {} as Record<string, LocationItem[]>);

    const handleAdd = async () => {
        if (!newLoc.name.trim()) return;
        try {
            const listName = newLoc.list_name || activeList || 'Genel';
            await api.createLocation({
                list_name: listName,
                name: newLoc.name.trim(),
                city: newLoc.city.trim() || null,
            });
            setNewLoc({ name: '', city: '', list_name: '' });
            setShowAdd(false);
            showToast('success', '✅ Konum eklendi');
            loadLocations();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleCreateList = async () => {
        if (!newListName.trim()) return;
        // Listeyi ilk konum eklendiğinde oluşturuyoruz
        setActiveList(newListName.trim());
        setNewListName('');
        setShowNewList(false);
        setShowAdd(true);
        setNewLoc({ name: '', city: '', list_name: newListName.trim() });
        showToast('success', `📋 "${newListName.trim()}" listesi oluşturuldu — şimdi konum ekleyin`);
    };

    const handleBulkImport = async () => {
        if (!bulkText.trim()) return;
        try {
            const listName = bulkListName || activeList || 'Genel';
            const result = await api.bulkImportLocations(bulkText, listName);
            setBulkText('');
            setBulkListName('');
            setShowBulk(false);
            showToast('success', `✅ ${result.added} konum "${listName}" listesine eklendi`);
            loadLocations();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleUpdate = async (id: number) => {
        try {
            await api.updateLocation(id, editData);
            setEditId(null);
            showToast('success', '✅ Güncellendi');
            loadLocations();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleToggle = async (loc: LocationItem) => {
        try {
            await api.updateLocation(loc.id, { is_active: !loc.is_active });
            loadLocations();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Bu konumu silmek istediğinize emin misiniz?')) return;
        try {
            await api.deleteLocation(id);
            showToast('success', '🗑️ Silindi');
            loadLocations();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleDeleteList = async (listName: string) => {
        if (!confirm(`"${listName}" listesindeki TÜM konumlar silinecek. Emin misiniz?`)) return;
        try {
            await api.request<any>(`/locations/list/${encodeURIComponent(listName)}`, { method: 'DELETE' });
            if (activeList === listName) setActiveList('');
            showToast('success', `🗑️ "${listName}" listesi silindi`);
            loadLocations();
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
                    <h2 className="page-header__title">Konum Yönetimi</h2>
                    <p className="page-header__subtitle">{locations.length} konum · {lists.length} liste</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary" onClick={() => { setShowBulk(!showBulk); setShowAdd(false); setShowNewList(false); }}>
                        📋 Toplu Ekle
                    </button>
                    <button className="btn btn-secondary" onClick={() => { setShowNewList(!showNewList); setShowAdd(false); setShowBulk(false); }}>
                        📁 Yeni Liste
                    </button>
                    <button className="btn btn-primary" onClick={() => { setShowAdd(!showAdd); setShowBulk(false); setShowNewList(false); }}>
                        ➕ Konum Ekle
                    </button>
                </div>
            </div>

            {/* Liste Tab Filtresi */}
            <div className="tabs">
                <div className={`tab ${activeList === '' ? 'active' : ''}`} onClick={() => setActiveList('')}>
                    Tümü <span className="tab-count">{locations.length}</span>
                </div>
                {lists.map(list => (
                    <div key={list} className={`tab ${activeList === list ? 'active' : ''}`} onClick={() => setActiveList(list)}>
                        📁 {list}
                        <span className="tab-count">
                            {locations.filter(l => l.list_name === list).length}
                        </span>
                    </div>
                ))}
            </div>

            {/* Yeni Liste Oluştur */}
            {showNewList && (
                <div className="card" style={{ marginBottom: 16, padding: 20 }}>
                    <h3 style={{ marginBottom: 12, fontSize: '0.95rem', fontWeight: 700 }}>📁 Yeni Liste Oluştur</h3>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label className="form-label">Liste Adı *</label>
                            <input className="form-input" placeholder="Örn: Kadıköy Konumları" value={newListName}
                                onChange={e => setNewListName(e.target.value)} />
                        </div>
                        <button className="btn btn-secondary" onClick={() => setShowNewList(false)}>İptal</button>
                        <button className="btn btn-primary" onClick={handleCreateList} disabled={!newListName.trim()}>Oluştur</button>
                    </div>
                </div>
            )}

            {/* Tek Ekleme */}
            {showAdd && (
                <div className="card" style={{ marginBottom: 16, padding: 20 }}>
                    <h3 style={{ marginBottom: 12, fontSize: '0.95rem', fontWeight: 700 }}>📍 Yeni Konum</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <div className="form-group">
                            <label className="form-label">Liste *</label>
                            <select className="form-select" value={newLoc.list_name || activeList || ''}
                                onChange={e => setNewLoc({ ...newLoc, list_name: e.target.value })}>
                                <option value="">Genel</option>
                                {lists.map(l => <option key={l} value={l}>{l}</option>)}
                            </select>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Konum Adı *</label>
                            <input className="form-input" placeholder="Örn: Taksim Meydanı" value={newLoc.name}
                                onChange={e => setNewLoc({ ...newLoc, name: e.target.value })} />
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
                        <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>İptal</button>
                        <button className="btn btn-primary" onClick={handleAdd} disabled={!newLoc.name.trim()}>Kaydet</button>
                    </div>
                </div>
            )}

            {/* Toplu Import */}
            {showBulk && (
                <div className="card" style={{ marginBottom: 16, padding: 20 }}>
                    <h3 style={{ marginBottom: 12, fontSize: '0.95rem', fontWeight: 700 }}>📋 Toplu Konum Import</h3>
                    <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                        <div className="form-group" style={{ minWidth: 200 }}>
                            <label className="form-label">Listeye Ekle</label>
                            <select className="form-select" value={bulkListName || activeList || ''}
                                onChange={e => setBulkListName(e.target.value)}>
                                <option value="">Genel</option>
                                {lists.map(l => <option key={l} value={l}>{l}</option>)}
                            </select>
                        </div>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label className="form-label">veya Yeni Liste Adı</label>
                            <input className="form-input" placeholder="Yeni liste adı yazın..." value={bulkListName}
                                onChange={e => setBulkListName(e.target.value)} />
                        </div>
                    </div>
                    <div className="info-box blue" style={{ marginBottom: 12 }}>
                        Her satıra bir konum adı yazın (şehir gerekmez)
                    </div>
                    <textarea
                        className="form-input"
                        rows={8}
                        placeholder={`Altunizade Residences\nBakırköy Sahil\nKadıköy Moda\nBeşiktaş Meydanı\nÜsküdar Çamlıca`}
                        value={bulkText}
                        onChange={e => setBulkText(e.target.value)}
                        style={{ fontFamily: 'monospace', fontSize: '0.82rem', marginBottom: 12 }}
                    />
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {bulkText.split('\n').filter(l => l.trim()).length} satır
                        </span>
                        <button className="btn btn-secondary" onClick={() => setShowBulk(false)}>İptal</button>
                        <button className="btn btn-primary" onClick={handleBulkImport} disabled={!bulkText.trim()}>📥 İçe Aktar</button>
                    </div>
                </div>
            )}

            {/* Konum Listesi */}
            {filteredLocations.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">📍</div>
                    <div className="empty-state__title">
                        {activeList ? `"${activeList}" listesinde konum yok` : 'Henüz konum eklenmemiş'}
                    </div>
                    <p style={{ color: 'var(--text-secondary)', maxWidth: 400, margin: '8px auto' }}>
                        Paylaşımlara konum eklemek için konum listesi oluşturun.
                    </p>
                </div>
            ) : activeList ? (
                /* Tek liste görünümü */
                <div>
                    <div className="flex-between" style={{ marginBottom: 12 }}>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>📁 {activeList}</h3>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDeleteList(activeList)}>
                            🗑️ Listeyi Sil
                        </button>
                    </div>
                    {renderLocationTable(filteredLocations)}
                </div>
            ) : (
                /* Tüm listeler görünümü — gruplu */
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    {Object.entries(groupedByList).map(([listName, items]) => (
                        <div key={listName} className="card" style={{ padding: 16 }}>
                            <div className="flex-between" style={{ marginBottom: 12 }}>
                                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                                    📁 {listName}
                                    <span className="badge badge-primary" style={{ fontSize: '0.65rem' }}>
                                        {items.length} konum
                                    </span>
                                </h3>
                                <div style={{ display: 'flex', gap: 6 }}>
                                    <button className="btn btn-sm btn-secondary" onClick={() => setActiveList(listName)}>
                                        Görüntüle →
                                    </button>
                                    <button className="btn btn-sm btn-danger" onClick={() => handleDeleteList(listName)}>
                                        🗑️
                                    </button>
                                </div>
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                {items.slice(0, 10).map(loc => (
                                    <span key={loc.id} style={{
                                        padding: '4px 10px', borderRadius: 6,
                                        background: loc.is_active ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.05)',
                                        border: '1px solid rgba(99,102,241,0.2)',
                                        fontSize: '0.78rem', color: loc.is_active ? 'var(--text-primary)' : 'var(--text-muted)',
                                    }}>
                                        📍 {loc.name} {loc.city ? `· ${loc.city}` : ''}
                                    </span>
                                ))}
                                {items.length > 10 && (
                                    <span style={{
                                        padding: '4px 10px', borderRadius: 6,
                                        background: 'rgba(255,255,255,0.05)',
                                        fontSize: '0.78rem', color: 'var(--text-muted)',
                                    }}>
                                        +{items.length - 10} daha...
                                    </span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );

    function renderLocationTable(items: LocationItem[]) {
        return (
            <div className="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Konum</th>
                            <th>Şehir</th>
                            <th>Durum</th>
                            <th>İşlemler</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items.map(loc => (
                            <tr key={loc.id} style={{ opacity: loc.is_active ? 1 : 0.5 }}>
                                <td>
                                    {editId === loc.id ? (
                                        <input className="form-input" value={editData.name || ''} style={{ padding: '4px 8px', fontSize: '0.82rem' }}
                                            onChange={e => setEditData({ ...editData, name: e.target.value })} />
                                    ) : (
                                        <span style={{ fontWeight: 600 }}>📍 {loc.name}</span>
                                    )}
                                </td>
                                <td>
                                    {editId === loc.id ? (
                                        <input className="form-input" value={editData.city || ''} style={{ padding: '4px 8px', fontSize: '0.82rem', width: 100 }}
                                            onChange={e => setEditData({ ...editData, city: e.target.value })} />
                                    ) : (
                                        <span style={{ fontSize: '0.82rem' }}>{loc.city || '—'}</span>
                                    )}
                                </td>
                                <td>
                                    <span className={`badge ${loc.is_active ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '0.65rem' }}>
                                        {loc.is_active ? '✅ Aktif' : '⚫ Pasif'}
                                    </span>
                                </td>
                                <td>
                                    <div style={{ display: 'flex', gap: 4 }}>
                                        {editId === loc.id ? (
                                            <>
                                                <button className="btn btn-sm btn-primary" onClick={() => handleUpdate(loc.id)}>💾</button>
                                                <button className="btn btn-sm btn-secondary" onClick={() => setEditId(null)}>✕</button>
                                            </>
                                        ) : (
                                            <>
                                                <button className="btn btn-sm btn-secondary" onClick={() => handleToggle(loc)}>
                                                    {loc.is_active ? '⚫' : '🟢'}
                                                </button>
                                                <button className="btn btn-sm btn-secondary" onClick={() => {
                                                    setEditId(loc.id);
                                                    setEditData({ name: loc.name, city: loc.city || '' });
                                                }}>✏️</button>
                                                <button className="btn btn-sm btn-danger" onClick={() => handleDelete(loc.id)}>🗑️</button>
                                            </>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    }
}
