'use client';

import { useState } from 'react';
import { api } from '@/lib/api';

interface DownloadJob {
    job_id: string;
    status: string;
    total: number;
    downloaded: number;
    failed: number;
    errors: string[];
}

export default function DownloadsPage() {
    const [targetUsername, setTargetUsername] = useState('');
    const [mediaFilter, setMediaFilter] = useState('all');
    const [limit, setLimit] = useState(50);
    const [activeJobs, setActiveJobs] = useState<DownloadJob[]>([]);
    const [starting, setStarting] = useState(false);

    const handleStart = async () => {
        if (!targetUsername.trim()) return alert('Kullanıcı adı girin');
        setStarting(true);
        try {
            const result = await api.startDownload({
                target_username: targetUsername.replace('@', '').trim(),
                media_type_filter: mediaFilter,
                limit,
                mode: 'scrape',
            });
            const jobId = result.job_id;
            pollJob(jobId);
        } catch (err: any) { alert(err.message); }
        finally { setStarting(false); }
    };

    const pollJob = (jobId: string) => {
        const job: DownloadJob = {
            job_id: jobId,
            status: 'running',
            total: 0,
            downloaded: 0,
            failed: 0,
            errors: [],
        };
        setActiveJobs(prev => [...prev, job]);

        const interval = setInterval(async () => {
            try {
                const status = await api.getDownloadStatus(jobId);
                setActiveJobs(prev =>
                    prev.map(j => j.job_id === jobId ? { ...j, ...status } : j)
                );
                if (status.status === 'completed' || status.status === 'stopped' || status.status === 'error') {
                    clearInterval(interval);
                }
            } catch { clearInterval(interval); }
        }, 2000);
    };

    const handleStop = async (jobId: string) => {
        try { await api.stopDownload(jobId); }
        catch (err: any) { alert(err.message); }
    };

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">Gönderi İndirme</h2>
                    <p className="page-header__subtitle">Herhangi bir hesabın gönderilerini indirin — takip gerekmez</p>
                </div>
            </div>

            <div className="card" style={{ marginBottom: 24 }}>
                <h4 style={{ marginBottom: 16, fontSize: '0.95rem', fontWeight: 600 }}>
                    ⬇️ Yeni İndirme Başlat
                </h4>

                <div className="row-3">
                    <div className="form-group">
                        <label className="form-label">Hedef Kullanıcı Adı</label>
                        <input
                            className="form-input"
                            placeholder="@kullanici_adi"
                            value={targetUsername}
                            onChange={(e) => setTargetUsername(e.target.value)}
                        />
                    </div>
                    <div className="form-group">
                        <label className="form-label">Medya Türü Filtresi</label>
                        <select
                            className="form-select"
                            value={mediaFilter}
                            onChange={(e) => setMediaFilter(e.target.value)}
                        >
                            <option value="all">Tümü</option>
                            <option value="photo">Fotoğraf</option>
                            <option value="video">Video</option>
                            <option value="carousel">Carousel</option>
                        </select>
                    </div>
                    <div className="form-group">
                        <label className="form-label">Limit (0 = sınırsız)</label>
                        <input
                            type="number"
                            className="form-input"
                            min={0}
                            value={limit}
                            onChange={(e) => setLimit(parseInt(e.target.value) || 0)}
                        />
                    </div>
                </div>

                <div className="info-box blue" style={{ marginBottom: 16 }}>
                    💡 Hesabı <b>takip etmenize gerek yoktur</b>. Kullanıcı adını girmeniz yeterli —
                    fotoğraf ve videolar otomatik olarak indirilir. Profil <b>public</b> (herkese açık)
                    olmalıdır.
                </div>

                <button
                    className="btn btn-primary btn-lg"
                    onClick={handleStart}
                    disabled={starting || !targetUsername.trim()}
                >
                    {starting ? '⏳ Başlatılıyor...' : '🚀 İndirmeye Başla'}
                </button>
            </div>

            {/* Aktif İndirmeler */}
            {activeJobs.length > 0 && (
                <div>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>
                        📥 İndirme İşleri
                    </h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {activeJobs.map(job => {
                            const progress = job.total > 0 ? (job.downloaded / job.total) * 100 : 0;
                            const statusColor = job.status === 'completed' ? 'badge-success' :
                                job.status === 'running' ? 'badge-primary' :
                                    job.status === 'error' ? 'badge-error' : 'badge-warning';

                            return (
                                <div key={job.job_id} className="card" style={{ padding: 16 }}>
                                    <div className="flex-between" style={{ marginBottom: 12 }}>
                                        <div>
                                            <span style={{ fontWeight: 600, fontSize: '0.9rem', marginRight: 8 }}>
                                                İş: {job.job_id}
                                            </span>
                                            <span className={`badge ${statusColor}`}>{job.status}</span>
                                        </div>
                                        {job.status === 'running' && (
                                            <button
                                                className="btn btn-danger btn-sm"
                                                onClick={() => handleStop(job.job_id)}
                                            >
                                                ⏹️ Durdur
                                            </button>
                                        )}
                                    </div>

                                    <div className="progress-bar" style={{ marginBottom: 8 }}>
                                        <div className="progress-bar__fill" style={{ width: `${progress}%` }} />
                                    </div>

                                    <div style={{ display: 'flex', gap: 24, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                        <span>📊 Toplam: {job.total}</span>
                                        <span>✅ İndirilen: {job.downloaded}</span>
                                        <span>❌ Hatalı: {job.failed}</span>
                                        <span>📈 İlerleme: {progress.toFixed(0)}%</span>
                                    </div>

                                    {job.errors.length > 0 && (
                                        <div style={{ marginTop: 8 }}>
                                            {job.errors.map((e, i) => (
                                                <div key={i} style={{ fontSize: '0.72rem', color: 'var(--color-error)', marginTop: 2 }}>
                                                    ⚠️ {e}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {activeJobs.length === 0 && (
                <div className="empty-state">
                    <div className="empty-state__icon">📥</div>
                    <div className="empty-state__title">Aktif indirme işi yok</div>
                    <p>Yukarıdan yeni bir indirme başlatabilirsiniz</p>
                </div>
            )}
        </div>
    );
}
