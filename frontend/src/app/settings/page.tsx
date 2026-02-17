'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function SettingsPage() {
    const [settings, setSettings] = useState<Record<string, string>>({});
    const [backups, setBackups] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Görüntülenecek ayarlar
    const settingFields = [
        { key: 'default_daily_limit', label: 'Varsayılan Günlük Paylaşım Limiti', type: 'number', placeholder: '10' },
        { key: 'default_posting_mode', label: 'Varsayılan Paylaşım Modu', type: 'select', options: ['sequential', 'random'] },
        { key: 'auto_resize', label: 'Otomatik Boyutlandırma', type: 'select', options: ['true', 'false'] },
        { key: 'default_aspect_ratio', label: 'Varsayılan En-Boy Oranı', type: 'select', options: ['1:1', '4:5', '9:16'] },
        { key: 'backup_retention_days', label: 'Yedekleme Saklama Süresi (gün)', type: 'number', placeholder: '30' },
        { key: 'auto_reply_enabled', label: 'Otomatik Yanıt Aktif', type: 'select', options: ['true', 'false'] },
        { key: 'message_sync_interval', label: 'Mesaj Senkronizasyon Aralığı (dk)', type: 'number', placeholder: '5' },
    ];

    useEffect(() => { loadData(); }, []);

    const loadData = async () => {
        try {
            const [settingsData, backupsData] = await Promise.all([
                api.getSettings(),
                api.getBackups(),
            ]);
            setSettings(settingsData.settings || {});
            setBackups(backupsData.backups || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const entries = Object.entries(settings)
                .filter(([key]) => settingFields.some(f => f.key === key))
                .map(([key, value]) => ({ key, value }));
            await api.updateSettings(entries);
            alert('Ayarlar kaydedildi!');
        } catch (err: any) { alert(err.message); }
        finally { setSaving(false); }
    };

    const handleBackup = async () => {
        try {
            const result = await api.createBackup();
            if (result.success) {
                alert('Yedekleme başarıyla oluşturuldu!');
                loadData();
            }
        } catch (err: any) { alert(err.message); }
    };

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Sistem Ayarları</h2>
                    <p className="page-header__subtitle">Uygulama genelindeki ayarları yönetin</p>
                </div>
                <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                    {saving ? '⏳ Kaydediliyor...' : '💾 Kaydet'}
                </button>
            </div>

            <div className="row-2">
                <div>
                    <div className="card" style={{ marginBottom: 20 }}>
                        <div className="card-header">
                            <h3 className="card-title">⚙️ Genel Ayarlar</h3>
                        </div>

                        {settingFields.map(field => (
                            <div key={field.key} className="form-group">
                                <label className="form-label">{field.label}</label>
                                {field.type === 'select' ? (
                                    <select
                                        className="form-select"
                                        value={settings[field.key] || field.options?.[0] || ''}
                                        onChange={(e) => setSettings({ ...settings, [field.key]: e.target.value })}
                                    >
                                        {field.options?.map(opt => (
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
                        ))}
                    </div>
                </div>

                <div>
                    {/* Yedekleme */}
                    <div className="card" style={{ marginBottom: 20 }}>
                        <div className="card-header">
                            <h3 className="card-title">💾 Yedekleme</h3>
                            <button className="btn btn-secondary btn-sm" onClick={handleBackup}>
                                ➕ Yedekle
                            </button>
                        </div>

                        <div className="info-box blue" style={{ marginTop: 0 }}>
                            Veritabanı otomatik olarak her gece saat 03:00'te yedeklenir.
                            Manuel yedekleme de oluşturabilirsiniz.
                        </div>

                        {backups.length === 0 ? (
                            <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                                Henüz yedekleme oluşturulmamış
                            </div>
                        ) : (
                            <div style={{ maxHeight: 300, overflowY: 'auto', marginTop: 12 }}>
                                {backups.map((b: any, i: number) => (
                                    <div key={i} style={{
                                        padding: '8px 0',
                                        borderBottom: '1px solid var(--border-color)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        fontSize: '0.82rem',
                                    }}>
                                        <span>📁 {b.filename || b}</span>
                                        <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                                            {b.date || ''}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Hakkında */}
                    <div className="card">
                        <div className="card-header">
                            <h3 className="card-title">ℹ️ Hakkında</h3>
                        </div>
                        <div style={{ fontSize: '0.85rem', lineHeight: 2 }}>
                            <div><b>Uygulama:</b> Demet</div>
                            <div><b>Versiyon:</b> 1.0.0</div>
                            <div><b>Backend:</b> FastAPI + SQLAlchemy</div>
                            <div><b>Frontend:</b> Next.js 15 + TypeScript</div>
                            <div><b>API:</b> Instagram Graph API v21.0</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
