'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface LocationItem {
    id: number;
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
    const [cities, setCities] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [cityFilter, setCityFilter] = useState('');
    const [showAdd, setShowAdd] = useState(false);
    const [showBulk, setShowBulk] = useState(false);
    const [bulkText, setBulkText] = useState('');
    const [newLoc, setNewLoc] = useState({ name: '', city: '', instagram_location_pk: '', lat: '', lng: '' });
    const [editId, setEditId] = useState<number | null>(null);
    const [editData, setEditData] = useState<any>({});
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    const loadLocations = useCallback(async () => {
        try {
            const data = await api.getLocations(cityFilter || undefined);
            setLocations(data.items || []);
            setCities(data.cities || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    }, [cityFilter]);

    useEffect(() => { loadLocations(); }, [loadLocations]);

    const handleAdd = async () => {
        if (!newLoc.name.trim()) return;
        try {
            await api.createLocation({
                name: newLoc.name.trim(),
                city: newLoc.city.trim() || null,
                instagram_location_pk: newLoc.instagram_location_pk.trim() || null,
                lat: newLoc.lat.trim() || null,
                lng: newLoc.lng.trim() || null,
            });
            setNewLoc({ name: '', city: '', instagram_location_pk: '', lat: '', lng: '' });
            setShowAdd(false);
            showToast('success', '✅ Konum eklendi');
            loadLocations();
        } catch (err: any) { showToast('error', err.message); }
    };

    const handleBulkImport = async () => {
        if (!bulkText.trim()) return;
        try {
            const result = await api.bulkImportLocations(bulkText);
            setBulkText('');
            setShowBulk(false);
            showToast('success', `✅ ${result.added} konum eklendi`);
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
                    <p className="page-header__subtitle">{locations.length} konum · {cities.length} şehir</p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-secondary" onClick={() => { setShowBulk(!showBulk); setShowAdd(false); }}>
                        📋 Toplu Ekle
                    </button>
                    <button className="btn btn-primary" onClick={() => { setShowAdd(!showAdd); setShowBulk(false); }}>
                        ➕ Konum Ekle
                    </button>
                </div>
            </div>

            {/* Şehir Tab Filtresi */}
            {cities.length > 0 && (
                <div className="tabs">
                    <div className={`tab ${cityFilter === '' ? 'active' : ''}`} onClick={() => setCityFilter('')}>
                        Tümü <span className="tab-count">{locations.length}</span>
                    </div>
                    {cities.map(city => (
                        <div key={city} className={`tab ${cityFilter === city ? 'active' : ''}`} onClick={() => setCityFilter(city)}>
                            📍 {city}
                        </div>
                    ))}
                </div>
            )}

            {/* Tek Ekleme */}
            {showAdd && (
                <div className="card" style={{ marginBottom: 16, padding: 20 }}>
                    <h3 style={{ marginBottom: 12, fontSize: '0.95rem', fontWeight: 700 }}>📍 Yeni Konum</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <div className="form-group">
                            <label className="form-label">Konum Adı *</label>
                            <input className="form-input" placeholder="Örn: Taksim Meydanı" value={newLoc.name}
                                onChange={e => setNewLoc({ ...newLoc, name: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Şehir</label>
                            <input className="form-input" placeholder="Örn: İstanbul" value={newLoc.city}
                                onChange={e => setNewLoc({ ...newLoc, city: e.target.value })} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Instagram Location PK</label>
                            <input className="form-input" placeholder="Instagram konum ID'si" value={newLoc.instagram_location_pk}
                                onChange={e => setNewLoc({ ...newLoc, instagram_location_pk: e.target.value })} />
                        </div>
                        <div className="form-group" style={{ display: 'flex', gap: 8 }}>
                            <div style={{ flex: 1 }}>
                                <label className="form-label">Enlem</label>
                                <input className="form-input" placeholder="41.0082" value={newLoc.lat}
                                    onChange={e => setNewLoc({ ...newLoc, lat: e.target.value })} />
                            </div>
                            <div style={{ flex: 1 }}>
                                <label className="form-label">Boylam</label>
                                <input className="form-input" placeholder="28.9784" value={newLoc.lng}
                                    onChange={e => setNewLoc({ ...newLoc, lng: e.target.value })} />
                            </div>
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
                    <div className="info-box blue" style={{ marginBottom: 12 }}>
                        Her satır: <code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: 4 }}>
                            konum_adı|şehir
                        </code>
                    </div>
                    <textarea
                        className="form-input"
                        rows={8}
                        placeholder={`Taksim Meydanı|İstanbul\nKızılay|Ankara\nKaleiçi|Antalya\nKapadokya|Nevşehir`}
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
            {locations.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">📍</div>
                    <div className="empty-state__title">Henüz konum eklenmemiş</div>
                    <p style={{ color: 'var(--text-secondary)', maxWidth: 400, margin: '8px auto' }}>
                        Paylaşımlara konum eklemek için konum listesi oluşturun.
                    </p>
                </div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Konum</th>
                                <th>Şehir</th>
                                <th>Instagram PK</th>
                                <th>Koordinat</th>
                                <th>Durum</th>
                                <th>İşlemler</th>
                            </tr>
                        </thead>
                        <tbody>
                            {locations.map(loc => (
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
                                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                                        {loc.instagram_location_pk || '—'}
                                    </td>
                                    <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                        {loc.lat && loc.lng ? `${loc.lat}, ${loc.lng}` : '—'}
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
            )}
        </div>
    );
}
