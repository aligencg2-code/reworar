'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [statsData, actData] = await Promise.all([
        api.getDashboardStats(),
        api.getRecentActivity(10),
      ]);
      setStats(statsData);
      setActivities(actData.activities || []);
    } catch (err) {
      console.error('Dashboard yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-center" style={{ height: '60vh' }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-header__title">Dashboard</h2>
          <p className="page-header__subtitle">
            Instagram hesaplarınızın genel durumu
          </p>
        </div>
        <button className="btn btn-primary" onClick={loadData}>
          🔄 Yenile
        </button>
      </div>

      {/* İstatistik Kartları */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon pink">👤</div>
          <div>
            <div className="stat-value">{stats?.total_accounts || 0}</div>
            <div className="stat-label">Toplam Hesap</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green">✅</div>
          <div>
            <div className="stat-value">{stats?.active_accounts || 0}</div>
            <div className="stat-label">Aktif Hesap</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon blue">📊</div>
          <div>
            <div className="stat-value">{stats?.posts_today || 0}</div>
            <div className="stat-label">Bugün Paylaşılan</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon orange">⏰</div>
          <div>
            <div className="stat-value">{stats?.scheduled_posts || 0}</div>
            <div className="stat-label">Planlanan Gönderi</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon purple">🖼️</div>
          <div>
            <div className="stat-value">{stats?.total_media || 0}</div>
            <div className="stat-label">Medya Dosyası</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon pink">💬</div>
          <div>
            <div className="stat-value">{stats?.unread_messages || 0}</div>
            <div className="stat-label">Okunmamış Mesaj</div>
          </div>
        </div>
      </div>

      <div className="row-2">
        {/* Son Aktiviteler */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">📋 Son Aktiviteler</h3>
          </div>
          {activities.length > 0 ? (
            <div>
              {activities.map((act: any) => (
                <div key={act.id} style={{
                  padding: '10px 0',
                  borderBottom: '1px solid var(--border-color)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                }}>
                  <span className={`badge badge-${act.level === 'error' ? 'error' : act.level === 'warning' ? 'warning' : 'info'}`}>
                    {act.level}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.85rem' }}>{act.action}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {new Date(act.created_at).toLocaleString('tr-TR')}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state__icon">📋</div>
              <div className="empty-state__title">Henüz aktivite yok</div>
              <p>Hesap bağladığınızda aktiviteler burada görünecek</p>
            </div>
          )}
        </div>

        {/* Hızlı İşlemler */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">⚡ Hızlı İşlemler</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start' }}
              onClick={() => window.location.href = '/accounts'}
            >
              ➕ Yeni Hesap Bağla
            </button>
            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start' }}
              onClick={() => window.location.href = '/posts'}
            >
              📝 Yeni Gönderi Oluştur
            </button>
            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start' }}
              onClick={() => window.location.href = '/media'}
            >
              🖼️ Medya Yükle
            </button>
            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start' }}
              onClick={() => window.location.href = '/messages'}
            >
              💬 Mesajları Görüntüle
            </button>
            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start' }}
              onClick={() => window.location.href = '/downloads'}
            >
              ⬇️ Gönderi İndir
            </button>
          </div>

          {stats?.failed_posts_week > 0 && (
            <div className="info-box pink" style={{ marginTop: 16 }}>
              ⚠️ Son 7 günde <b>{stats.failed_posts_week}</b> gönderi hatalı oldu.
              Hesap ayarlarını kontrol edin.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
