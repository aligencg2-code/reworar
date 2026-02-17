'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '@/lib/api';

export default function PostsPage() {
    const [posts, setPosts] = useState<any[]>([]);
    const [accounts, setAccounts] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [filter, setFilter] = useState({ status: '', account_id: '' });

    // Yeni gönderi form state
    const [newPost, setNewPost] = useState({
        account_id: 0, caption: '', media_type: 'photo',
        scheduled_at: '', status: 'draft', hashtag_group_id: null as number | null,
    });

    // Medya yükleme state
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [filePreviews, setFilePreviews] = useState<string[]>([]);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState('');
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Düzenleme state
    const [editPost, setEditPost] = useState<any>(null);

    useEffect(() => { loadData(); }, [filter]);

    const loadData = async () => {
        try {
            const params: Record<string, string> = {};
            if (filter.status) params.status = filter.status;
            if (filter.account_id) params.account_id = filter.account_id;

            const [postsData, accData] = await Promise.all([
                api.getPosts(params),
                api.getAccounts(),
            ]);
            setPosts(postsData.posts || []);
            setTotal(postsData.total || 0);
            setAccounts(accData || []);
            if (!newPost.account_id && accData.length > 0) {
                setNewPost(p => ({ ...p, account_id: accData[0].id }));
            }
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    // Dosya seçme
    const handleFileSelect = (files: FileList | null) => {
        if (!files) return;
        const fileArr = Array.from(files);
        setSelectedFiles(prev => [...prev, ...fileArr]);

        // Önizlemeler oluştur
        fileArr.forEach(file => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    setFilePreviews(prev => [...prev, e.target?.result as string]);
                };
                reader.readAsDataURL(file);
            } else if (file.type.startsWith('video/')) {
                setFilePreviews(prev => [...prev, '🎬']);
            } else {
                setFilePreviews(prev => [...prev, '📁']);
            }
        });

        // Medya türünü otomatik belirle
        if (fileArr.some(f => f.type.startsWith('video/'))) {
            setNewPost(p => ({ ...p, media_type: 'video' }));
        }
        if (fileArr.length > 1) {
            setNewPost(p => ({ ...p, media_type: 'carousel' }));
        }
    };

    // Dosya kaldır
    const removeFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
        setFilePreviews(prev => prev.filter((_, i) => i !== index));
    };

    // Drag & Drop
    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        handleFileSelect(e.dataTransfer.files);
    }, []);

    // Gönderi oluştur
    const handleCreate = async () => {
        if (selectedFiles.length === 0) {
            alert('Lütfen en az bir medya dosyası ekleyin!');
            return;
        }

        setUploading(true);
        setUploadProgress('Dosyalar yükleniyor...');

        try {
            // 1) Medya dosyalarını yükle
            const uploadResult = await api.uploadMedia(
                selectedFiles,
                newPost.media_type,
                'posts',
                newPost.account_id || undefined,
            );
            setUploadProgress('Gönderi oluşturuluyor...');

            // 2) Gönderiyi oluştur
            const postData = {
                ...newPost,
                media_ids: uploadResult.media_ids || [],
            };

            if (!postData.scheduled_at) {
                delete (postData as any).scheduled_at;
            }

            await api.createPost(postData);

            // Reset
            setShowCreate(false);
            setSelectedFiles([]);
            setFilePreviews([]);
            setNewPost({
                account_id: accounts[0]?.id || 0, caption: '', media_type: 'photo',
                scheduled_at: '', status: 'draft', hashtag_group_id: null,
            });
            setUploadProgress('');
            loadData();
        } catch (err: any) {
            alert(err.message || 'Gönderi oluşturulamadı');
        } finally {
            setUploading(false);
            setUploadProgress('');
        }
    };

    const handlePublish = async (id: number) => {
        if (!confirm('Bu gönderiyi şimdi yayınlamak istediğinize emin misiniz?')) return;
        try {
            await api.publishPost(id);
            loadData();
        } catch (err: any) { alert(err.message); }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Bu gönderiyi silmek istediğinize emin misiniz?')) return;
        try { await api.deletePost(id); loadData(); }
        catch (err: any) { alert(err.message); }
    };

    // Düzenleme
    const handleEditSave = async () => {
        if (!editPost) return;
        try {
            await api.updatePost(editPost.id, {
                caption: editPost.caption,
                scheduled_at: editPost.scheduled_at || null,
                status: editPost.status,
            });
            setEditPost(null);
            loadData();
        } catch (err: any) { alert(err.message); }
    };

    const statusColors: Record<string, string> = {
        draft: 'badge-info', scheduled: 'badge-warning',
        publishing: 'badge-primary', published: 'badge-success', failed: 'badge-error',
    };

    const statusLabels: Record<string, string> = {
        draft: 'Taslak', scheduled: 'Planlandı',
        publishing: 'Yayınlanıyor', published: 'Yayınlandı', failed: 'Hatalı',
    };

    const mediaIcons: Record<string, string> = {
        photo: '📷', video: '🎬', story: '📱', reels: '🎭', carousel: '🎠',
    };

    // Hesap adını bul
    const getAccountName = (accountId: number) => {
        const acc = accounts.find(a => a.id === accountId);
        return acc ? `@${acc.username}` : `#${accountId}`;
    };

    if (loading) return <div className="flex-center" style={{ height: '60vh' }}><div className="spinner" /></div>;

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Gönderi Yönetimi</h2>
                    <p className="page-header__subtitle">{total} gönderi</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
                    ➕ Yeni Gönderi
                </button>
            </div>

            {/* Filtreler */}
            <div className="row" style={{ marginBottom: 20, gap: 12 }}>
                <select
                    className="form-select"
                    style={{ width: 160 }}
                    value={filter.status}
                    onChange={(e) => setFilter({ ...filter, status: e.target.value })}
                >
                    <option value="">Tüm Durumlar</option>
                    <option value="draft">Taslak</option>
                    <option value="scheduled">Planlandı</option>
                    <option value="published">Yayınlandı</option>
                    <option value="failed">Hatalı</option>
                </select>
                <select
                    className="form-select"
                    style={{ width: 200 }}
                    value={filter.account_id}
                    onChange={(e) => setFilter({ ...filter, account_id: e.target.value })}
                >
                    <option value="">Tüm Hesaplar</option>
                    {accounts.map((a: any) => <option key={a.id} value={a.id}>@{a.username}</option>)}
                </select>
            </div>

            {/* Gönderi Listesi */}
            {posts.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state__icon">📝</div>
                    <div className="empty-state__title">Henüz gönderi yok</div>
                    <p>Yeni gönderi oluşturmak için butonu kullanın</p>
                </div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Hesap</th>
                                <th>Tür</th>
                                <th>Açıklama</th>
                                <th>Durum</th>
                                <th>Tarih</th>
                                <th>Medya</th>
                                <th>İşlemler</th>
                            </tr>
                        </thead>
                        <tbody>
                            {posts.map((p: any) => (
                                <tr key={p.id}>
                                    <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                        {getAccountName(p.account_id)}
                                    </td>
                                    <td>{mediaIcons[p.media_type] || '📷'} {p.media_type}</td>
                                    <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {p.caption || <span style={{ color: 'var(--text-muted)' }}>Açıklama yok</span>}
                                    </td>
                                    <td>
                                        <span className={`badge ${statusColors[p.status] || 'badge-info'}`}>
                                            {statusLabels[p.status] || p.status}
                                        </span>
                                        {p.error_message && (
                                            <div style={{ fontSize: '0.7rem', color: 'var(--color-error)', marginTop: 4 }}>
                                                {p.error_message.substring(0, 80)}
                                            </div>
                                        )}
                                    </td>
                                    <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                        {p.scheduled_at ? new Date(p.scheduled_at).toLocaleString('tr-TR') : '—'}
                                    </td>
                                    <td>{p.media_count} dosya</td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 6 }}>
                                            {p.status !== 'published' && (
                                                <button
                                                    className="btn btn-primary btn-sm"
                                                    onClick={() => handlePublish(p.id)}
                                                    title="Şimdi Yayınla"
                                                >🚀</button>
                                            )}
                                            {p.status !== 'published' && (
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={() => setEditPost({
                                                        ...p,
                                                        scheduled_at: p.scheduled_at ? p.scheduled_at.slice(0, 16) : '',
                                                    })}
                                                    title="Düzenle"
                                                >✏️</button>
                                            )}
                                            <button
                                                className="btn btn-danger btn-sm"
                                                onClick={() => handleDelete(p.id)}
                                                title="Sil"
                                            >🗑️</button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* ─── Yeni Gönderi Modal ─── */}
            {showCreate && (
                <div className="modal-overlay" onClick={() => { if (!uploading) setShowCreate(false); }}>
                    <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
                        <h3 className="modal-title">📝 Yeni Gönderi Oluştur</h3>

                        <div className="form-group">
                            <label className="form-label">Hesap</label>
                            <select
                                className="form-select"
                                value={newPost.account_id}
                                onChange={(e) => setNewPost({ ...newPost, account_id: Number(e.target.value) })}
                            >
                                {accounts.map((a: any) => <option key={a.id} value={a.id}>@{a.username}</option>)}
                            </select>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Medya Türü</label>
                            <select
                                className="form-select"
                                value={newPost.media_type}
                                onChange={(e) => setNewPost({ ...newPost, media_type: e.target.value })}
                            >
                                <option value="photo">📷 Fotoğraf</option>
                                <option value="video">🎬 Video</option>
                                <option value="story">📱 Story</option>
                                <option value="reels">🎭 Reels</option>
                                <option value="carousel">🎠 Carousel</option>
                            </select>
                        </div>

                        {/* Dosya Yükleme Alanı */}
                        <div className="form-group">
                            <label className="form-label">Medya Dosyaları</label>
                            <div
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                                style={{
                                    border: `2px dashed ${dragOver ? 'var(--color-primary)' : 'var(--border-color)'}`,
                                    borderRadius: 12,
                                    padding: selectedFiles.length > 0 ? 12 : 40,
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s',
                                    background: dragOver ? 'rgba(233, 30, 99, 0.05)' : 'transparent',
                                    minHeight: 100,
                                }}
                            >
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    multiple
                                    accept="image/*,video/*"
                                    style={{ display: 'none' }}
                                    onChange={(e) => handleFileSelect(e.target.files)}
                                />

                                {selectedFiles.length === 0 ? (
                                    <div>
                                        <div style={{ fontSize: 36, marginBottom: 8 }}>📁</div>
                                        <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                                            Dosyaları sürükleyip bırakın
                                        </div>
                                        <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: 4 }}>
                                            veya tıklayarak seçin
                                        </div>
                                    </div>
                                ) : (
                                    <div style={{
                                        display: 'grid',
                                        gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))',
                                        gap: 8,
                                    }}>
                                        {selectedFiles.map((file, i) => (
                                            <div key={i} style={{
                                                position: 'relative',
                                                borderRadius: 8,
                                                overflow: 'hidden',
                                                background: 'var(--surface-color)',
                                                aspectRatio: '1',
                                            }}>
                                                {filePreviews[i] && filePreviews[i] !== '🎬' && filePreviews[i] !== '📁' ? (
                                                    <img
                                                        src={filePreviews[i]}
                                                        alt={file.name}
                                                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                                    />
                                                ) : (
                                                    <div style={{
                                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                        height: '100%', fontSize: 28,
                                                    }}>
                                                        {filePreviews[i] || '📁'}
                                                    </div>
                                                )}
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                                                    style={{
                                                        position: 'absolute', top: 2, right: 2,
                                                        background: 'rgba(0,0,0,0.7)', color: '#fff',
                                                        border: 'none', borderRadius: '50%',
                                                        width: 20, height: 20, fontSize: 10,
                                                        cursor: 'pointer', display: 'flex',
                                                        alignItems: 'center', justifyContent: 'center',
                                                    }}
                                                >✕</button>
                                                <div style={{
                                                    position: 'absolute', bottom: 0, left: 0, right: 0,
                                                    background: 'rgba(0,0,0,0.6)', color: '#fff',
                                                    fontSize: '0.6rem', padding: '2px 4px',
                                                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                                }}>
                                                    {file.name}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                                {selectedFiles.length > 0 && `${selectedFiles.length} dosya seçildi`}
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Açıklama</label>
                            <textarea
                                className="form-input"
                                rows={4}
                                placeholder="Gönderi açıklamasını yazın... #hashtag @mention"
                                value={newPost.caption}
                                onChange={(e) => setNewPost({ ...newPost, caption: e.target.value })}
                            />
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'right' }}>
                                {(newPost.caption || '').length}/2200
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Planlanan Tarih (Opsiyonel)</label>
                            <input
                                type="datetime-local"
                                className="form-input"
                                value={newPost.scheduled_at}
                                onChange={(e) => setNewPost({
                                    ...newPost,
                                    scheduled_at: e.target.value,
                                    status: e.target.value ? 'scheduled' : 'draft',
                                })}
                            />
                        </div>

                        {uploadProgress && (
                            <div style={{
                                padding: '8px 12px', borderRadius: 8,
                                background: 'rgba(233, 30, 99, 0.1)',
                                color: 'var(--color-primary)', fontSize: '0.85rem',
                                display: 'flex', alignItems: 'center', gap: 8,
                            }}>
                                <div className="spinner" style={{ width: 16, height: 16 }} />
                                {uploadProgress}
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
                            <button
                                className="btn btn-secondary"
                                onClick={() => {
                                    setShowCreate(false);
                                    setSelectedFiles([]);
                                    setFilePreviews([]);
                                }}
                                disabled={uploading}
                            >İptal</button>
                            <button
                                className="btn btn-primary"
                                onClick={handleCreate}
                                disabled={uploading || selectedFiles.length === 0}
                            >
                                {uploading ? '⏳ Yükleniyor...' :
                                    newPost.status === 'scheduled' ? '📅 Planla' : '💾 Taslak Kaydet'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ─── Düzenleme Modal ─── */}
            {editPost && (
                <div className="modal-overlay" onClick={() => setEditPost(null)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 500 }}>
                        <h3 className="modal-title">✏️ Gönderiyi Düzenle</h3>

                        <div className="form-group">
                            <label className="form-label">Açıklama</label>
                            <textarea
                                className="form-input"
                                rows={4}
                                value={editPost.caption || ''}
                                onChange={(e) => setEditPost({ ...editPost, caption: e.target.value })}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Planlanan Tarih</label>
                            <input
                                type="datetime-local"
                                className="form-input"
                                value={editPost.scheduled_at || ''}
                                onChange={(e) => setEditPost({
                                    ...editPost,
                                    scheduled_at: e.target.value,
                                    status: e.target.value ? 'scheduled' : 'draft',
                                })}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Durum</label>
                            <select
                                className="form-select"
                                value={editPost.status}
                                onChange={(e) => setEditPost({ ...editPost, status: e.target.value })}
                            >
                                <option value="draft">Taslak</option>
                                <option value="scheduled">Planlandı</option>
                            </select>
                        </div>

                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
                            <button className="btn btn-secondary" onClick={() => setEditPost(null)}>İptal</button>
                            <button className="btn btn-primary" onClick={handleEditSave}>💾 Kaydet</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
