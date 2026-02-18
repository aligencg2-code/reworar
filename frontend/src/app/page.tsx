'use client';

import { useEffect, useState, useRef } from 'react';
import { api } from '@/lib/api';

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Bot state
  const [botRunning, setBotRunning] = useState(false);
  const [botLogs, setBotLogs] = useState<any[]>([]);
  const [botInfo, setBotInfo] = useState<any>(null);
  const [botLoading, setBotLoading] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<any>(null);

  useEffect(() => {
    loadData();
    loadBotStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Bot durumu polling
  useEffect(() => {
    if (botRunning) {
      pollRef.current = setInterval(loadBotStatus, 5000);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [botRunning]);

  // Otomatik scroll
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [botLogs]);

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

  const loadBotStatus = async () => {
    try {
      const data = await api.botStatus();
      setBotRunning(data.running);
      setBotLogs(data.logs || []);
      setBotInfo(data);
    } catch { }
  };

  const handleBotToggle = async () => {
    setBotLoading(true);
    try {
      if (botRunning) {
        await api.botStop();
        setBotRunning(false);
      } else {
        await api.botStart();
        setBotRunning(true);
      }
      setTimeout(loadBotStatus, 1000);
    } catch (err: any) {
      alert(err.message || 'Bot hatası');
    } finally {
      setBotLoading(false);
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

      {/* ─── Bot Kontrol Paneli ─── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{
              width: 56, height: 56,
              borderRadius: 16,
              background: botRunning
                ? 'linear-gradient(135deg, #00c853, #00e676)'
                : 'linear-gradient(135deg, #7c4dff, #651fff)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 28,
              boxShadow: botRunning
                ? '0 4px 20px rgba(0,200,83,0.3)'
                : '0 4px 20px rgba(124,77,255,0.3)',
            }}>
              {botRunning ? '🟢' : '🤖'}
            </div>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                Otomatik Paylaşım Botu
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {botRunning ? (
                  <>
                    ✅ Çalışıyor
                    {botInfo?.current_account && <> — @{botInfo.current_account}</>}
                    {botInfo?.posts_made > 0 && <> — {botInfo.posts_made} paylaşım yapıldı</>}
                  </>
                ) : (
                  'Durduruldu — Başlatmak için butona tıklayın'
                )}
              </div>
            </div>
          </div>

          <button
            className={`btn ${botRunning ? 'btn-error' : 'btn-primary'}`}
            onClick={handleBotToggle}
            disabled={botLoading}
            style={{
              padding: '12px 32px',
              fontSize: '1rem',
              fontWeight: 700,
              minWidth: 180,
              borderRadius: 12,
            }}
          >
            {botLoading ? '⏳ İşleniyor...' : botRunning ? '⏹ Botu Durdur' : '🚀 Botu Başlat'}
          </button>
        </div>

        {/* Bot Logları */}
        {botLogs.length > 0 && (
          <div
            ref={logRef}
            style={{
              marginTop: 16,
              maxHeight: 240,
              overflowY: 'auto',
              background: 'var(--bg-darker, #0d1117)',
              borderRadius: 10,
              padding: '12px 16px',
              fontFamily: 'monospace',
              fontSize: '0.78rem',
              lineHeight: 1.6,
            }}
          >
            {botLogs.map((log, i) => (
              <div key={i} style={{
                color: log.level === 'error' ? '#ff5252'
                  : log.level === 'warning' ? '#ffab40'
                    : '#b0bec5',
              }}>
                <span style={{ color: '#546e7a', marginRight: 8 }}>
                  {new Date(log.time).toLocaleTimeString('tr-TR')}
                </span>
                {log.message}
              </div>
            ))}
          </div>
        )}
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
