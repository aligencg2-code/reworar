'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function MessagesPage() {
    const [accounts, setAccounts] = useState<any[]>([]);
    const [selectedAccount, setSelectedAccount] = useState<number | null>(null);
    const [conversations, setConversations] = useState<any[]>([]);
    const [messages, setMessages] = useState<any[]>([]);
    const [selectedConvo, setSelectedConvo] = useState<string | null>(null);
    const [templates, setTemplates] = useState<any[]>([]);
    const [rules, setRules] = useState<any[]>([]);
    const [activeTab, setActiveTab] = useState<'chats' | 'templates' | 'auto-reply'>('chats');
    const [loading, setLoading] = useState(true);

    // Template form
    const [newTemplate, setNewTemplate] = useState({ name: '', content: '', category: 'general', shortcut: '' });
    // Auto-reply form
    const [newRule, setNewRule] = useState({ keywords: '', response: '', match_type: 'contains', whatsapp_redirect: '' });

    useEffect(() => {
        api.getAccounts().then(data => {
            setAccounts(data || []);
            if (data.length > 0) { setSelectedAccount(data[0].id); }
            setLoading(false);
        });
        loadTemplates();
        loadRules();
    }, []);

    useEffect(() => {
        if (selectedAccount) loadConversations();
    }, [selectedAccount]);

    const loadConversations = async () => {
        if (!selectedAccount) return;
        try {
            const data = await api.getConversations(selectedAccount);
            setConversations(data.conversations || []);
        } catch { setConversations([]); }
    };

    const loadMessages = async (convoId: string) => {
        if (!selectedAccount) return;
        setSelectedConvo(convoId);
        try {
            const data = await api.getMessageHistory(selectedAccount, convoId);
            setMessages(data.messages || []);
        } catch { setMessages([]); }
    };

    const loadTemplates = async () => {
        try {
            const data = await api.getTemplates();
            setTemplates(data.templates || []);
        } catch { }
    };

    const loadRules = async () => {
        try {
            const data = await api.getAutoReplyRules();
            setRules(data.rules || []);
        } catch { }
    };

    const handleCreateTemplate = async () => {
        try {
            await api.createTemplate(newTemplate);
            setNewTemplate({ name: '', content: '', category: 'general', shortcut: '' });
            loadTemplates();
        } catch (err: any) { alert(err.message); }
    };

    const handleCreateRule = async () => {
        try {
            await api.createAutoReplyRule({
                ...newRule,
                keywords: newRule.keywords.split(',').map(k => k.trim()),
                account_id: selectedAccount,
            });
            setNewRule({ keywords: '', response: '', match_type: 'contains', whatsapp_redirect: '' });
            loadRules();
        } catch (err: any) { alert(err.message); }
    };

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Mesaj Yönetimi</h2>
                    <p className="page-header__subtitle">DM konuşmaları ve otomatik yanıtlar</p>
                </div>
                <select
                    className="form-select"
                    style={{ width: 200 }}
                    value={selectedAccount || ''}
                    onChange={(e) => setSelectedAccount(Number(e.target.value))}
                >
                    {accounts.map((a: any) => <option key={a.id} value={a.id}>@{a.username}</option>)}
                </select>
            </div>

            <div className="tabs">
                <div className={`tab ${activeTab === 'chats' ? 'active' : ''}`} onClick={() => setActiveTab('chats')}>
                    💬 Konuşmalar
                </div>
                <div className={`tab ${activeTab === 'templates' ? 'active' : ''}`} onClick={() => setActiveTab('templates')}>
                    📋 Şablonlar <span className="tab-count">{templates.length}</span>
                </div>
                <div className={`tab ${activeTab === 'auto-reply' ? 'active' : ''}`} onClick={() => setActiveTab('auto-reply')}>
                    🤖 Otomatik Yanıt <span className="tab-count">{rules.length}</span>
                </div>
            </div>

            {/* Konuşmalar */}
            {activeTab === 'chats' && (
                <div className="chat-layout">
                    <div className="chat-list">
                        {conversations.length === 0 ? (
                            <div className="empty-state" style={{ padding: 30 }}>
                                <div className="empty-state__icon">💬</div>
                                <div className="empty-state__title" style={{ fontSize: '0.85rem' }}>Konuşma yok</div>
                            </div>
                        ) : (
                            conversations.map((c: any, i: number) => (
                                <div
                                    key={i}
                                    className={`chat-list__item ${selectedConvo === c.id ? 'active' : ''}`}
                                    onClick={() => loadMessages(c.id)}
                                >
                                    <div className="chat-avatar">
                                        {c.username?.[0]?.toUpperCase() || '?'}
                                    </div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{c.username || 'Anonim'}</div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {c.last_message || '...'}
                                        </div>
                                    </div>
                                    {c.unread > 0 && <span className="nav-badge">{c.unread}</span>}
                                </div>
                            ))
                        )}
                    </div>
                    <div className="chat-messages">
                        <div className="chat-messages__body">
                            {messages.length === 0 ? (
                                <div className="empty-state">
                                    <div className="empty-state__icon">👈</div>
                                    <div className="empty-state__title">Bir konuşma seçin</div>
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                    {messages.map((m: any) => (
                                        <div
                                            key={m.id}
                                            className={`message-bubble ${m.is_incoming ? 'incoming' : 'outgoing'}`}
                                        >
                                            {m.content}
                                            <div className="message-time">
                                                {new Date(m.timestamp).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                                                {m.auto_replied && ' 🤖'}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Şablonlar */}
            {activeTab === 'templates' && (
                <div>
                    <div className="card" style={{ marginBottom: 20 }}>
                        <h4 style={{ marginBottom: 12, fontSize: '0.9rem', fontWeight: 600 }}>Yeni Şablon</h4>
                        <div className="row-2">
                            <div className="form-group">
                                <label className="form-label">Şablon Adı</label>
                                <input
                                    className="form-input"
                                    placeholder="örn: Hoşgeldiniz mesajı"
                                    value={newTemplate.name}
                                    onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Kısayol</label>
                                <input
                                    className="form-input"
                                    placeholder="örn: /hosgeldin"
                                    value={newTemplate.shortcut}
                                    onChange={(e) => setNewTemplate({ ...newTemplate, shortcut: e.target.value })}
                                />
                            </div>
                        </div>
                        <div className="form-group">
                            <label className="form-label">İçerik</label>
                            <textarea
                                className="form-input"
                                rows={3}
                                placeholder="Merhaba! Mesajınız için teşekkürler..."
                                value={newTemplate.content}
                                onChange={(e) => setNewTemplate({ ...newTemplate, content: e.target.value })}
                            />
                        </div>
                        <button className="btn btn-primary" onClick={handleCreateTemplate}>➕ Şablon Ekle</button>
                    </div>

                    {templates.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state__icon">📋</div>
                            <div className="empty-state__title">Henüz şablon oluşturulmadı</div>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                            {templates.map((t: any) => (
                                <div key={t.id} className="card" style={{ padding: 16 }}>
                                    <div className="flex-between" style={{ marginBottom: 8 }}>
                                        <strong style={{ fontSize: '0.9rem' }}>{t.name}</strong>
                                        <button className="btn btn-danger btn-sm" onClick={() => api.deleteTemplate(t.id).then(loadTemplates)}>🗑️</button>
                                    </div>
                                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{t.content}</p>
                                    <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                                        {t.shortcut && <span className="badge badge-primary">{t.shortcut}</span>}
                                        <span className="badge badge-info">{t.use_count}× kullanıldı</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Otomatik Yanıt */}
            {activeTab === 'auto-reply' && (
                <div>
                    <div className="card" style={{ marginBottom: 20 }}>
                        <h4 style={{ marginBottom: 12, fontSize: '0.9rem', fontWeight: 600 }}>Yeni Kural</h4>
                        <div className="row-2">
                            <div className="form-group">
                                <label className="form-label">Anahtar Kelimeler (virgülle ayırın)</label>
                                <input
                                    className="form-input"
                                    placeholder="fiyat, kaç tl, ne kadar"
                                    value={newRule.keywords}
                                    onChange={(e) => setNewRule({ ...newRule, keywords: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Eşleşme Türü</label>
                                <select
                                    className="form-select"
                                    value={newRule.match_type}
                                    onChange={(e) => setNewRule({ ...newRule, match_type: e.target.value })}
                                >
                                    <option value="contains">İçerir</option>
                                    <option value="exact">Tam Eşleşme</option>
                                    <option value="starts_with">İle Başlar</option>
                                </select>
                            </div>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Otomatik Yanıt</label>
                            <textarea
                                className="form-input"
                                rows={2}
                                placeholder="Fiyat bilgisi için profilimizdeki linke tıklayın..."
                                value={newRule.response}
                                onChange={(e) => setNewRule({ ...newRule, response: e.target.value })}
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label">WhatsApp Yönlendirme (Opsiyonel)</label>
                            <input
                                className="form-input"
                                placeholder="905551234567"
                                value={newRule.whatsapp_redirect}
                                onChange={(e) => setNewRule({ ...newRule, whatsapp_redirect: e.target.value })}
                            />
                        </div>
                        <button className="btn btn-primary" onClick={handleCreateRule}>➕ Kural Ekle</button>
                    </div>

                    {rules.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state__icon">🤖</div>
                            <div className="empty-state__title">Henüz otomatik yanıt kuralı yok</div>
                        </div>
                    ) : (
                        <div className="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Anahtar Kelimeler</th>
                                        <th>Yanıt</th>
                                        <th>Tür</th>
                                        <th>WhatsApp</th>
                                        <th>Tetiklenme</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rules.map((r: any) => (
                                        <tr key={r.id}>
                                            <td>
                                                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                                    {r.keywords?.map((k: string, i: number) => (
                                                        <span key={i} className="badge badge-primary">{k}</span>
                                                    ))}
                                                </div>
                                            </td>
                                            <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {r.response}
                                            </td>
                                            <td><span className="badge badge-info">{r.match_type}</span></td>
                                            <td>{r.whatsapp_redirect ? `📱 ${r.whatsapp_redirect}` : '—'}</td>
                                            <td>{r.trigger_count}×</td>
                                            <td>
                                                <button className="btn btn-danger btn-sm" onClick={() => api.deleteAutoReplyRule(r.id).then(loadRules)}>
                                                    🗑️
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
