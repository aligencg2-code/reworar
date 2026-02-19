'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '@/lib/api';

// ─── Arayüzler ──────────────────────────────
interface CaptionItem { id: number; text: string; display_order: number; is_active: boolean; use_count: number; created_at: string; }
interface LocationItem { id: number; name: string; city: string | null; instagram_location_pk: string | null; lat: string | null; lng: string | null; is_active: boolean; created_at: string; }

type SettingsTab = 'general' | 'captions' | 'locations' | 'hashtags';

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState<SettingsTab>('general');
    const [settings, setSettings] = useState<Record<string, string>>({});
    const [proxies, setProxies] = useState('');
    const [backups, setBackups] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState<{ type: string; message: string } | null>(null);

    // Caption state
    const [captions, setCaptions] = useState<CaptionItem[]>([]);
    const [newCaption, setNewCaption] = useState('');
    const [bulkCaptions, setBulkCaptions] = useState('');
    const [showAddCaption, setShowAddCaption] = useState(false);
    const [showBulkCaption, setShowBulkCaption] = useState(false);
    const [editCaptionId, setEditCaptionId] = useState<number | null>(null);
    const [editCaptionText, setEditCaptionText] = useState('');

    // Location state
    const [locations, setLocations] = useState<LocationItem[]>([]);
    const [newLoc, setNewLoc] = useState({ name: '', city: '' });
    const [bulkLocations, setBulkLocations] = useState('');
    const [showAddLoc, setShowAddLoc] = useState(false);
    const [showBulkLoc, setShowBulkLoc] = useState(false);

    // Hashtag state
    const [hashGroups, setHashGroups] = useState<any[]>([]);
    const [showHashForm, setShowHashForm] = useState(false);
    const [editHashId, setEditHashId] = useState<number | null>(null);
    const [hashForm, setHashForm] = useState({ name: '', hashtags: '' });

    const showToast = (type: string, message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 5000);
    };

    // ─── Genel Ayar Alanları ──────────────────
    const postingSettings = [
        { key: 'posts_per_account', label: 'Hesap Başı Paylaşım Sayısı', type: 'number', placeholder: '2', desc: 'Her hesap için bir turda kaç paylaşım yapılacak' },
        { key: 'default_posting_mode', label: 'Medya Seçim Modu', type: 'select', options: ['sequential', 'random'], desc: 'Medya dosyaları sıralı mı rastgele mi seçilsin' },
    ];
    const timingSettings = [
        { key: 'posting_interval_min', label: 'Paylaşım Aralığı (min, sn)', type: 'number', placeholder: '50', desc: 'İki paylaşım arası minimum bekleme süresi' },
        { key: 'posting_interval_max', label: 'Paylaşım Aralığı (max, sn)', type: 'number', placeholder: '60', desc: 'İki paylaşım arası maksimum bekleme süresi' },
        { key: 'account_switch_delay_min', label: 'Hesap Geçiş Bekleme (min, sn)', type: 'number', placeholder: '80' },
        { key: 'account_switch_delay_max', label: 'Hesap Geçiş Bekleme (max, sn)', type: 'number', placeholder: '90' },
    ];
    const proxySettings = [
        { key: 'proxy_enabled', label: 'Proxy Kullan', type: 'select', options: ['true', 'false'] },
        { key: 'proxy_mode', label: 'Proxy Seçim Modu', type: 'select', options: ['sequential', 'random'] },
    ];
    const mediaSettings = [
        { key: 'auto_resize', label: 'Otomatik Boyutlandırma', type: 'select', options: ['true', 'false'] },
        { key: 'default_aspect_ratio', label: 'Varsayılan En-Boy Oranı', type: 'select', options: ['1:1', '4:5', '9:16'] },
        { key: 'default_daily_limit', label: 'Varsayılan Günlük Limit', type: 'number', placeholder: '10' },
    ];
    const otherSettings = [
        { key: 'auto_reply_enabled', label: 'Otomatik Yanıt', type: 'select', options: ['true', 'false'] },
        { key: 'message_sync_interval', label: 'Mesaj Senkronizasyon Aralığı (dk)', type: 'number', placeholder: '5' },
        { key: 'backup_retention_days', label: 'Yedekleme Saklama Süresi (gün)', type: 'number', placeholder: '30' },
    ];

    // ─── Data Loading ──────────────────────────
    useEffect(() => { loadAllData(); }, []);

    const loadAllData = async () => {
        try {
            const [settingsData, backupsData, locData, hashData, captData] = await Promise.all([
                api.getSettings(),
                api.getBackups(),
                api.getLocations(),
                api.getHashtagGroups(),
                api.getCaptions(),
            ]);
            setSettings(settingsData.settings || {});
            setBackups(backupsData.backups || []);
            setProxies(settingsData.settings?.proxy_list || '');
            setLocations(locData.items || []);
            setHashGroups(hashData.groups || []);
            setCaptions(captData.items || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const loadCaptions = async () => {
        try { const d = await api.getCaptions(); setCaptions(d.items || []); } catch (e) { console.error(e); }
    };
    const loadLocations = async () => {
        try { const d = await api.getLocations(); setLocations(d.items || []); } catch (e) { console.error(e); }
    };
    const loadHashtags = async () => {
        try { const d = await api.getHashtagGroups(); setHashGroups(d.groups || []); } catch (e) { console.error(e); }
    };

    useEffect(() => {
        if (activeTab === 'captions') loadCaptions();
        if (activeTab === 'locations') loadLocations();
        if (activeTab === 'hashtags') loadHashtags();
    }, [activeTab]);

    // ─── Settings Handlers ──────────────────────
    const handleSave = async () => {
        setSaving(true);
        try {
            const allFields = [...postingSettings, ...timingSettings, ...proxySettings, ...mediaSettings, ...otherSettings];
            const entries = allFields
                .filter(f => settings[f.key] !== undefined && settings[f.key] !== '')
                .map(f => ({ key: f.key, value: settings[f.key] }));
            if (proxies.trim()) entries.push({ key: 'proxy_list', value: proxies.trim() });
            // İçerik Seçimi alanları
            const contentKeys = ['selected_location_city', 'selected_hashtag_group_id', 'caption_mode'];
            contentKeys.forEach(k => {
                if (settings[k] !== undefined) entries.push({ key: k, value: settings[k] });
            });
            await api.updateSettings(entries);
            showToast('success', '✅ Ayarlar kaydedildi!');
        } catch (err: any) { showToast('error', err.message); }
        finally { setSaving(false); }
    };

    const handleBackup = async () => {
        try {
            const result = await api.createBackup();
            if (result.success) { showToast('success', '✅ Yedekleme oluşturuldu!'); loadAllData(); }
        } catch (err: any) { showToast('error', err.message); }
    };

    // ─── Caption Handlers ──────────────────────
    const addCaption = async () => {
        if (!newCaption.trim()) return;
        try { await api.createCaption({ text: newCaption.trim() }); setNewCaption(''); setShowAddCaption(false); showToast('success', '✅ Caption eklendi'); loadCaptions(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const bulkImportCaptions = async () => {
        if (!bulkCaptions.trim()) return;
        try { const r = await api.bulkImportCaptions(bulkCaptions); setBulkCaptions(''); setShowBulkCaption(false); showToast('success', `✅ ${r.added} caption eklendi`); loadCaptions(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const updateCaption = async (id: number) => {
        if (!editCaptionText.trim()) return;
        try { await api.updateCaption(id, { text: editCaptionText.trim() }); setEditCaptionId(null); showToast('success', '✅ Güncellendi'); loadCaptions(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const toggleCaption = async (c: CaptionItem) => {
        try { await api.updateCaption(c.id, { is_active: !c.is_active }); loadCaptions(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const deleteCaption = async (id: number) => {
        if (!confirm('Bu caption\'ı silmek istediğinize emin misiniz?')) return;
        try { await api.deleteCaption(id); showToast('success', '🗑️ Silindi'); loadCaptions(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const deleteAllCaptions = async () => {
        if (!confirm('TÜM caption\'ları silmek istediğinize emin misiniz?')) return;
        try { await api.deleteAllCaptions(); showToast('success', '🗑️ Tümü silindi'); loadCaptions(); }
        catch (e: any) { showToast('error', e.message); }
    };

    // ─── Location Handlers ──────────────────────
    const addLocation = async () => {
        if (!newLoc.name.trim()) return;
        try { await api.createLocation({ name: newLoc.name.trim(), city: newLoc.city.trim() || null }); setNewLoc({ name: '', city: '' }); setShowAddLoc(false); showToast('success', '✅ Konum eklendi'); loadLocations(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const bulkImportLocations = async () => {
        if (!bulkLocations.trim()) return;
        try { const r = await api.bulkImportLocations(bulkLocations); setBulkLocations(''); setShowBulkLoc(false); showToast('success', `✅ ${r.added} konum eklendi`); loadLocations(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const toggleLocation = async (loc: LocationItem) => {
        try { await api.updateLocation(loc.id, { is_active: !loc.is_active }); loadLocations(); }
        catch (e: any) { showToast('error', e.message); }
    };
    const deleteLocation = async (id: number) => {
        if (!confirm('Bu konumu silmek istediğinize emin misiniz?')) return;
        try { await api.deleteLocation(id); showToast('success', '🗑️ Silindi'); loadLocations(); }
        catch (e: any) { showToast('error', e.message); }
    };

    // ─── Hashtag Handlers ──────────────────────
    const saveHashGroup = async () => {
        const tags = hashForm.hashtags.split(/[\n,]/).map(t => t.trim().replace(/^#/, '')).filter(Boolean);
        if (!hashForm.name || tags.length === 0) return showToast('error', 'Ad ve hashtag listesi gerekli');
        try {
            if (editHashId) {
                await api.updateHashtagGroup(editHashId, { name: hashForm.name, hashtags: tags });
            } else {
                await api.createHashtagGroup({ name: hashForm.name, hashtags: tags });
            }
            setHashForm({ name: '', hashtags: '' }); setShowHashForm(false); setEditHashId(null);
            showToast('success', '✅ Hashtag grubu kaydedildi'); loadHashtags();
        } catch (e: any) { showToast('error', e.message); }
    };
    const deleteHashGroup = async (id: number) => {
        if (!confirm('Bu grubu silmek istediğinize emin misiniz?')) return;
        try { await api.deleteHashtagGroup(id); showToast('success', '🗑️ Silindi'); loadHashtags(); }
        catch (e: any) { showToast('error', e.message); }
    };

    // ─── Render Helpers ──────────────────────
    const renderField = (field: any) => (
        <div key={field.key} className="form-group" style={{ marginBottom: 12 }}>
            <label className="form-label" style={{ marginBottom: 2 }}>{field.label}</label>
            {field.desc && <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6 }}>{field.desc}</div>}
            {field.type === 'select' ? (
                <select
                    className="form-select"
                    value={settings[field.key] || field.options?.[0] || ''}
                    onChange={(e) => setSettings({ ...settings, [field.key]: e.target.value })}
                >
                    {field.options?.map((opt: string) => (
                        <option key={opt} value={opt}>
                            {opt === 'true' ? 'Evet' : opt === 'false' ? 'Hayır' :
                                opt === 'sequential' ? 'Sıralı' : opt === 'random' ? 'Rastgele' : opt}
                        </option>
                    ))}
                </select>
            ) : (
                <input
                    type={field.type}
                    className="form-input"
                    placeholder={field.placeholder}
                    value={settings[field.key] || ''}
                    onChange={(e) => setSettings({ ...settings, [field.key]: e.target.value })}
                />
            )}
        </div>
    );

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    // ─── Tab Tanımları ──────────────────────
    const tabs: { key: SettingsTab; icon: string; label: string; count?: number }[] = [
        { key: 'general', icon: '⚙️', label: 'Genel Ayarlar' },
        { key: 'captions', icon: '💬', label: 'Captionlar', count: captions.length },
        { key: 'locations', icon: '📍', label: 'Konumlar', count: locations.length },
        { key: 'hashtags', icon: '#️⃣', label: 'Hashtagler', count: hashGroups.length },
    ];

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
                    <h2 className="page-header__title">Sistem Ayarları</h2>
                    <p className="page-header__subtitle">Uygulama ayarları, captionlar, konumlar ve hashtagler</p>
                </div>
                {activeTab === 'general' && (
                    <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                        {saving ? '⏳ Kaydediliyor...' : '💾 Tüm Ayarları Kaydet'}
                    </button>
                )}
            </div>

            {/* Tab Navigation */}
            <div className="tabs" style={{ marginBottom: 20 }}>
                {tabs.map(t => (
                    <div
                        key={t.key}
                        className={`tab ${activeTab === t.key ? 'active' : ''}`}
                        onClick={() => setActiveTab(t.key)}
                    >
                        {t.icon} {t.label}
                        {t.count !== undefined && <span className="tab-count">{t.count}</span>}
                    </div>
                ))}
            </div>

            {/* ═══════════ GENEL AYARLAR TAB ═══════════ */}
            {activeTab === 'general' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                    <div>
                        {/* ── İçerik Seçim Ayarları ── */}
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header"><h3 className="card-title">🎯 İçerik Seçimi</h3></div>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 12, padding: '0 4px' }}>
                                Bot paylaşım yaparken hangi konum, hashtag ve yazı listesini kullanacağını seçin.
                            </div>
                            <div className="form-group" style={{ marginBottom: 12 }}>
                                <label className="form-label" style={{ marginBottom: 2 }}>📍 Konum Listesi</label>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6 }}>Paylaşımlarda kullanılacak konum grubu</div>
                                <select
                                    className="form-select"
                                    value={settings['selected_location_city'] || ''}
                                    onChange={e => setSettings({ ...settings, selected_location_city: e.target.value })}
                                >
                                    <option value="">Tümü (rastgele)</option>
                                    {(() => {
                                        const cities = [...new Set(locations.map(l => l.city).filter(Boolean))] as string[];
                                        return cities.sort().map(city => (
                                            <option key={city} value={city}>{city} ({locations.filter(l => l.city === city).length} konum)</option>
                                        ));
                                    })()}
                                </select>
                            </div>
                            <div className="form-group" style={{ marginBottom: 12 }}>
                                <label className="form-label" style={{ marginBottom: 2 }}>#️⃣ Hashtag Grubu</label>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6 }}>Paylaşımlarda kullanılacak hashtag grubu</div>
                                <select
                                    className="form-select"
                                    value={settings['selected_hashtag_group_id'] || ''}
                                    onChange={e => setSettings({ ...settings, selected_hashtag_group_id: e.target.value })}
                                >
                                    <option value="">Tümü (rastgele)</option>
                                    {hashGroups.map((g: any) => (
                                        <option key={g.id} value={String(g.id)}>{g.name} ({g.hashtags.length} hashtag)</option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-group" style={{ marginBottom: 0 }}>
                                <label className="form-label" style={{ marginBottom: 2 }}>💬 Paylaşım Yazısı</label>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6 }}>Caption seçim modu (aşağıdan sıralı/rastgele seçilir)</div>
                                <select
                                    className="form-select"
                                    value={settings['caption_mode'] || 'random'}
                                    onChange={e => setSettings({ ...settings, caption_mode: e.target.value })}
                                >
                                    <option value="random">Rastgele</option>
                                    <option value="sequential">Sıralı</option>
                                </select>
                                <div style={{ marginTop: 6, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                    Toplam {captions.filter(c => c.is_active).length} aktif caption kayıtlı
                                </div>
                            </div>
                        </div>
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header"><h3 className="card-title">📤 Paylaşım</h3></div>
                            {postingSettings.map(renderField)}
                        </div>
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header"><h3 className="card-title">⏱️ Zamanlama</h3></div>
                            {timingSettings.map(renderField)}
                        </div>
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header"><h3 className="card-title">🖼️ Medya</h3></div>
                            {mediaSettings.map(renderField)}
                        </div>
                    </div>
                    <div>
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header"><h3 className="card-title">🌐 Proxy</h3></div>
                            {proxySettings.map(renderField)}
                            <div className="form-group" style={{ marginTop: 12 }}>
                                <label className="form-label">Proxy Listesi</label>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 6 }}>
                                    Her satıra bir proxy: http://user:pass@ip:port
                                </div>
                                <textarea
                                    className="form-input" rows={5}
                                    placeholder={`http://user:pass@1.2.3.4:8080\nsocks5://5.6.7.8:1080`}
                                    value={proxies} onChange={e => setProxies(e.target.value)}
                                    style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}
                                />
                            </div>
                        </div>
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header"><h3 className="card-title">⚙️ Diğer</h3></div>
                            {otherSettings.map(renderField)}
                        </div>
                        <div className="card" style={{ marginBottom: 20 }}>
                            <div className="card-header">
                                <h3 className="card-title">💾 Yedekleme</h3>
                                <button className="btn btn-secondary btn-sm" onClick={handleBackup}>➕ Yedekle</button>
                            </div>
                            {backups.length === 0 ? (
                                <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>Henüz yedekleme yok</div>
                            ) : (
                                <div style={{ maxHeight: 150, overflowY: 'auto', marginTop: 8 }}>
                                    {backups.map((b: any, i: number) => (
                                        <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                                            <span>📁 {b.filename || b}</span>
                                            <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{b.date || ''}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div className="card">
                            <div className="card-header"><h3 className="card-title">ℹ️ Hakkında</h3></div>
                            <div style={{ fontSize: '0.85rem', lineHeight: 2 }}>
                                <div><b>Uygulama:</b> Demet</div>
                                <div><b>Versiyon:</b> 1.0.0</div>
                                <div><b>Backend:</b> FastAPI + SQLAlchemy + instagrapi</div>
                            </div>
                            <div style={{ marginTop: 10 }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => {
                                    if ((window as any).electronAPI?.checkUpdate) {
                                        (window as any).electronAPI.checkUpdate();
                                    } else {
                                        fetch('/api/update/check?current_version=1.0.0').then(r => r.json()).then(d => {
                                            if (d.update_available) showToast('success', `🆕 Yeni sürüm: v${d.latest_version}`);
                                            else showToast('success', '✅ Güncel!');
                                        }).catch(() => showToast('error', 'Kontrol yapılamadı'));
                                    }
                                }}>🔄 Güncelleme Kontrol Et</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ═══════════ CAPTİONLAR TAB ═══════════ */}
            {activeTab === 'captions' && (
                <div>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                        {captions.length > 0 && <button className="btn btn-danger btn-sm" onClick={deleteAllCaptions}>🗑️ Tümünü Sil</button>}
                        <button className="btn btn-secondary btn-sm" onClick={() => { setShowBulkCaption(!showBulkCaption); setShowAddCaption(false); }}>📋 Toplu Ekle</button>
                        <button className="btn btn-primary btn-sm" onClick={() => { setShowAddCaption(!showAddCaption); setShowBulkCaption(false); }}>➕ Tek Ekle</button>
                    </div>

                    {showAddCaption && (
                        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
                            <textarea className="form-input" rows={3} placeholder="Paylaşım yazısını yazın... #hashtag" value={newCaption} onChange={e => setNewCaption(e.target.value)} style={{ marginBottom: 8 }} />
                            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => setShowAddCaption(false)}>İptal</button>
                                <button className="btn btn-primary btn-sm" onClick={addCaption} disabled={!newCaption.trim()}>Kaydet</button>
                            </div>
                        </div>
                    )}

                    {showBulkCaption && (
                        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
                            <div className="info-box blue" style={{ marginBottom: 8, fontSize: '0.78rem' }}>Her satır bir caption olarak eklenecektir.</div>
                            <textarea className="form-input" rows={6} placeholder={`Güzel bir gün! ☀️ #günaydın\nHayallerinizin peşinden gidin 🌟`} value={bulkCaptions} onChange={e => setBulkCaptions(e.target.value)} style={{ fontFamily: 'monospace', fontSize: '0.82rem', marginBottom: 8 }} />
                            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{bulkCaptions.split('\n').filter(l => l.trim()).length} satır</span>
                                <button className="btn btn-secondary btn-sm" onClick={() => setShowBulkCaption(false)}>İptal</button>
                                <button className="btn btn-primary btn-sm" onClick={bulkImportCaptions} disabled={!bulkCaptions.trim()}>📥 İçe Aktar</button>
                            </div>
                        </div>
                    )}

                    {captions.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state__icon">📝</div>
                            <div className="empty-state__title">Henüz caption eklenmemiş</div>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Paylaşım yazılarınızı ekleyin.</p>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {captions.map((c, i) => (
                                <div key={c.id} className="card" style={{
                                    padding: '12px 16px', display: 'flex', alignItems: 'flex-start', gap: 12,
                                    opacity: c.is_active ? 1 : 0.5,
                                    borderLeft: `3px solid ${c.is_active ? 'var(--accent-primary, #667eea)' : 'transparent'}`,
                                }}>
                                    <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'rgba(102,126,234,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--accent-primary, #667eea)', flexShrink: 0 }}>{i + 1}</div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        {editCaptionId === c.id ? (
                                            <div>
                                                <textarea className="form-input" rows={2} value={editCaptionText} onChange={e => setEditCaptionText(e.target.value)} autoFocus style={{ marginBottom: 6 }} />
                                                <div style={{ display: 'flex', gap: 6 }}>
                                                    <button className="btn btn-sm btn-primary" onClick={() => updateCaption(c.id)}>Kaydet</button>
                                                    <button className="btn btn-sm btn-secondary" onClick={() => setEditCaptionId(null)}>İptal</button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div style={{ fontSize: '0.82rem', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.text}</div>
                                        )}
                                        <div style={{ marginTop: 4, fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                                            {c.use_count > 0 && <span>🔄 {c.use_count}× · </span>}
                                            {new Date(c.created_at).toLocaleDateString('tr-TR')}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                                        <button className="btn btn-sm btn-secondary" onClick={() => toggleCaption(c)}>{c.is_active ? '🟢' : '⚫'}</button>
                                        <button className="btn btn-sm btn-secondary" onClick={() => { setEditCaptionId(c.id); setEditCaptionText(c.text); }}>✏️</button>
                                        <button className="btn btn-sm btn-danger" onClick={() => deleteCaption(c.id)}>🗑️</button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ═══════════ KONUMLAR TAB ═══════════ */}
            {activeTab === 'locations' && (
                <div>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => { setShowBulkLoc(!showBulkLoc); setShowAddLoc(false); }}>📋 Toplu Ekle</button>
                        <button className="btn btn-primary btn-sm" onClick={() => { setShowAddLoc(!showAddLoc); setShowBulkLoc(false); }}>➕ Konum Ekle</button>
                    </div>

                    {showAddLoc && (
                        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                                <div className="form-group">
                                    <label className="form-label">Konum Adı *</label>
                                    <input className="form-input" placeholder="Taksim Meydanı" value={newLoc.name} onChange={e => setNewLoc({ ...newLoc, name: e.target.value })} />
                                </div>
                                <div className="form-group">
                                    <label className="form-label">Şehir</label>
                                    <input className="form-input" placeholder="İstanbul" value={newLoc.city} onChange={e => setNewLoc({ ...newLoc, city: e.target.value })} />
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => setShowAddLoc(false)}>İptal</button>
                                <button className="btn btn-primary btn-sm" onClick={addLocation} disabled={!newLoc.name.trim()}>Kaydet</button>
                            </div>
                        </div>
                    )}

                    {showBulkLoc && (
                        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
                            <div className="info-box blue" style={{ marginBottom: 8, fontSize: '0.78rem' }}>Her satır: <code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: 4 }}>konum_adı|şehir</code></div>
                            <textarea className="form-input" rows={6} placeholder={`Taksim Meydanı|İstanbul\nKızılay|Ankara\nKaleiçi|Antalya`} value={bulkLocations} onChange={e => setBulkLocations(e.target.value)} style={{ fontFamily: 'monospace', fontSize: '0.82rem', marginBottom: 8 }} />
                            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{bulkLocations.split('\n').filter(l => l.trim()).length} satır</span>
                                <button className="btn btn-secondary btn-sm" onClick={() => setShowBulkLoc(false)}>İptal</button>
                                <button className="btn btn-primary btn-sm" onClick={bulkImportLocations} disabled={!bulkLocations.trim()}>📥 İçe Aktar</button>
                            </div>
                        </div>
                    )}

                    {locations.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state__icon">📍</div>
                            <div className="empty-state__title">Henüz konum eklenmemiş</div>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {locations.map(loc => (
                                <div key={loc.id} className="card" style={{
                                    padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12,
                                    opacity: loc.is_active ? 1 : 0.5,
                                    borderLeft: `3px solid ${loc.is_active ? '#2ecc71' : 'transparent'}`,
                                }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>📍 {loc.name}</div>
                                        {loc.city && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{loc.city}</div>}
                                    </div>
                                    <span className={`badge ${loc.is_active ? 'badge-success' : 'badge-error'}`} style={{ fontSize: '0.65rem' }}>
                                        {loc.is_active ? '✅' : '⚫'}
                                    </span>
                                    <div style={{ display: 'flex', gap: 4 }}>
                                        <button className="btn btn-sm btn-secondary" onClick={() => toggleLocation(loc)}>{loc.is_active ? '⚫' : '🟢'}</button>
                                        <button className="btn btn-sm btn-danger" onClick={() => deleteLocation(loc.id)}>🗑️</button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ═══════════ HASHTAGLER TAB ═══════════ */}
            {activeTab === 'hashtags' && (
                <div>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                        <button className="btn btn-primary btn-sm" onClick={() => { setShowHashForm(true); setEditHashId(null); setHashForm({ name: '', hashtags: '' }); }}>➕ Yeni Grup</button>
                    </div>

                    {showHashForm && (
                        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
                            <h4 style={{ marginBottom: 10, fontSize: '0.9rem', fontWeight: 700 }}>{editHashId ? '✏️ Grubu Düzenle' : '➕ Yeni Hashtag Grubu'}</h4>
                            <div className="form-group" style={{ marginBottom: 10 }}>
                                <label className="form-label">Grup Adı</label>
                                <input className="form-input" placeholder="Moda & Giyim" value={hashForm.name} onChange={e => setHashForm({ ...hashForm, name: e.target.value })} />
                            </div>
                            <div className="form-group" style={{ marginBottom: 10 }}>
                                <label className="form-label">Hashtagler (virgül veya yeni satırla ayırın)</label>
                                <textarea className="form-input" rows={4} placeholder="moda, stil, giyim, trend, fashion..." value={hashForm.hashtags} onChange={e => setHashForm({ ...hashForm, hashtags: e.target.value })} />
                            </div>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 10 }}>
                                {hashForm.hashtags.split(/[\n,]/).filter(t => t.trim()).length} hashtag
                            </div>
                            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                                <button className="btn btn-secondary btn-sm" onClick={() => { setShowHashForm(false); setEditHashId(null); }}>İptal</button>
                                <button className="btn btn-primary btn-sm" onClick={saveHashGroup}>{editHashId ? '💾 Güncelle' : '➕ Oluştur'}</button>
                            </div>
                        </div>
                    )}

                    {hashGroups.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state__icon">#️⃣</div>
                            <div className="empty-state__title">Henüz hashtag grubu yok</div>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
                            {hashGroups.map((g: any) => (
                                <div key={g.id} className="card" style={{ padding: 16 }}>
                                    <div className="flex-between" style={{ marginBottom: 10 }}>
                                        <h4 style={{ fontWeight: 600, fontSize: '0.9rem' }}>{g.name}</h4>
                                        <div style={{ display: 'flex', gap: 6 }}>
                                            <button className="btn btn-secondary btn-sm" onClick={() => {
                                                setEditHashId(g.id);
                                                setHashForm({ name: g.name, hashtags: g.hashtags.join(', ') });
                                                setShowHashForm(true);
                                            }}>✏️</button>
                                            <button className="btn btn-danger btn-sm" onClick={() => deleteHashGroup(g.id)}>🗑️</button>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
                                        {g.hashtags.slice(0, 12).map((tag: string, i: number) => (
                                            <span key={i} className="badge badge-primary" style={{ fontSize: '0.68rem' }}>#{tag}</span>
                                        ))}
                                        {g.hashtags.length > 12 && <span className="badge badge-info" style={{ fontSize: '0.68rem' }}>+{g.hashtags.length - 12}</span>}
                                    </div>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                        {g.hashtags.length} hashtag · {g.usage_count}× kullanıldı
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
