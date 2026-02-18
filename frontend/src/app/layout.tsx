'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api } from '@/lib/api';
import './globals.css';

// Electron API type
declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void;
      maximize: () => void;
      close: () => void;
      isMaximized: () => Promise<boolean>;
      getVersion: () => Promise<string>;
      openExternal: (url: string) => void;
      platform: string;
      isElectron: boolean;
    };
  }
}

const navItems = [
  { key: 'dashboard', icon: '📊', label: 'Dashboard', path: '/' },
  { key: 'accounts', icon: '👤', label: 'Hesaplar', path: '/accounts' },
  { key: 'appeals', icon: '🛡️', label: 'Hesap Sağlığı', path: '/appeals' },
  { key: 'profiles', icon: '✏️', label: 'Profil Yönetimi', path: '/profiles' },
  { key: 'posts', icon: '📝', label: 'Gönderiler', path: '/posts' },
  { key: 'calendar', icon: '📅', label: 'Takvim', path: '/calendar' },
  { key: 'media', icon: '🖼️', label: 'Medya', path: '/media' },
  { key: 'messages', icon: '✉️', label: 'Mesajlar', path: '/messages' },
  { key: 'downloads', icon: '⬇️', label: 'İndirme', path: '/downloads' },
  { key: 'settings', icon: '⚙️', label: 'Ayarlar', path: '/settings' },
];

// Log seviyeleri renkleri
const levelColors: Record<string, string> = {
  DEBUG: '#95a5a6', INFO: '#3498db', WARNING: '#f39c12', ERROR: '#e74c3c', CRITICAL: '#c0392b',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [isElectron, setIsElectron] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);

  // Canlı log paneli
  const [logPanelOpen, setLogPanelOpen] = useState(false);
  const [logPanelHeight, setLogPanelHeight] = useState(250);
  const [logs, setLogs] = useState<any[]>([]);
  const [logAutoRefresh, setLogAutoRefresh] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.electronAPI?.isElectron) {
      setIsElectron(true);
    }
    const token = localStorage.getItem('demet_token');
    const userData = localStorage.getItem('demet_user');
    if (token && userData) {
      setIsLoggedIn(true);
      setUser(JSON.parse(userData));
    } else if (pathname !== '/login') {
      router.push('/login');
    }
  }, [pathname, router]);

  // Log yükleme
  const loadLogs = useCallback(async () => {
    try {
      const data = await api.getLogs({ limit: 100 });
      setLogs(data.items || []);
    } catch { }
  }, []);

  // Panel açıldığında logları yükle
  useEffect(() => {
    if (logPanelOpen) loadLogs();
  }, [logPanelOpen, loadLogs]);

  // Auto-refresh
  useEffect(() => {
    if (!logAutoRefresh || !logPanelOpen) return;
    const interval = setInterval(loadLogs, 3000);
    return () => clearInterval(interval);
  }, [logAutoRefresh, logPanelOpen, loadLogs]);

  // Scroll to bottom
  useEffect(() => {
    if (logAutoRefresh && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, logAutoRefresh]);

  const handleMinimize = () => window.electronAPI?.minimize();
  const handleMaximize = async () => {
    window.electronAPI?.maximize();
    const maxed = await window.electronAPI?.isMaximized();
    setIsMaximized(!!maxed);
  };
  const handleClose = () => window.electronAPI?.close();

  if (pathname === '/login') {
    return (
      <html lang="tr">
        <head>
          <title>Demet — Giriş</title>
          <meta name="description" content="Instagram İçerik Planlama ve Mesaj Yönetim Sistemi" />
        </head>
        <body>
          {isElectron && (
            <div className="title-bar">
              <div className="title-bar__drag">
                <span className="title-bar__title">Demet</span>
              </div>
              <div className="title-bar__controls">
                <button className="title-bar__btn title-bar__btn--minimize" onClick={handleMinimize}>─</button>
                <button className="title-bar__btn title-bar__btn--maximize" onClick={handleMaximize}>
                  {isMaximized ? '❐' : '□'}
                </button>
                <button className="title-bar__btn title-bar__btn--close" onClick={handleClose}>✕</button>
              </div>
            </div>
          )}
          {children}
        </body>
      </html>
    );
  }

  return (
    <html lang="tr">
      <head>
        <title>Demet — Instagram Yönetim Sistemi</title>
        <meta name="description" content="Instagram İçerik Planlama ve Mesaj Yönetim Sistemi" />
      </head>
      <body>
        {isElectron && (
          <div className="title-bar">
            <div className="title-bar__drag">
              <span className="title-bar__title">Demet — Instagram Yönetim Sistemi</span>
            </div>
            <div className="title-bar__controls">
              <button className="title-bar__btn title-bar__btn--minimize" onClick={handleMinimize}>─</button>
              <button className="title-bar__btn title-bar__btn--maximize" onClick={handleMaximize}>
                {isMaximized ? '❐' : '□'}
              </button>
              <button className="title-bar__btn title-bar__btn--close" onClick={handleClose}>✕</button>
            </div>
          </div>
        )}

        <div className={`app-layout ${isElectron ? 'has-title-bar' : ''}`}>
          {/* Sidebar */}
          <aside className="sidebar">
            <div className="sidebar__brand">
              <h1>Demet</h1>
              <div className="status-badge">
                <span className="status-dot"></span>
                {isElectron ? 'Desktop' : 'Web'}
              </div>
            </div>

            <nav className="sidebar__nav">
              {navItems.map(item => (
                <div
                  key={item.key}
                  className={`nav-item ${pathname === item.path ? 'active' : ''}`}
                  onClick={() => router.push(item.path)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </div>
              ))}
            </nav>

            {/* Loglar Toggle — Sidebar altında */}
            <div style={{
              padding: '8px 12px',
              borderTop: '1px solid var(--border-color)',
            }}>
              <button
                onClick={() => { setLogPanelOpen(!logPanelOpen); if (!logPanelOpen) setLogAutoRefresh(true); }}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                  background: logPanelOpen ? 'rgba(46,204,113,0.15)' : 'rgba(255,255,255,0.05)',
                  border: `1px solid ${logPanelOpen ? 'rgba(46,204,113,0.3)' : 'var(--border-color)'}`,
                  color: logPanelOpen ? '#2ecc71' : 'var(--text-primary)',
                  cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 8,
                  transition: 'all 0.2s ease',
                }}
              >
                <span style={{ fontSize: '1rem' }}>{logPanelOpen ? '🔴' : '▶️'}</span>
                {logPanelOpen ? 'Canlı Loglar' : 'Logları Aç'}
                {logPanelOpen && (
                  <span style={{
                    marginLeft: 'auto', width: 8, height: 8, borderRadius: '50%',
                    background: '#2ecc71', animation: 'pulse 1.5s infinite',
                  }} />
                )}
              </button>
            </div>

            {/* Kullanıcı bilgisi */}
            {user && (
              <div style={{
                padding: '16px',
                borderTop: '1px solid var(--border-color)',
                display: 'flex', alignItems: 'center', gap: '10px',
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%',
                  background: 'var(--gradient-accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: '0.75rem',
                }}>
                  {user.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div style={{ flex: 1, fontSize: '0.82rem' }}>
                  <div style={{ fontWeight: 600 }}>{user.username}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                    {user.role === 'admin' ? 'Yönetici' : 'Editör'}
                  </div>
                </div>
                <button
                  className="btn btn-icon btn-secondary"
                  onClick={() => {
                    localStorage.removeItem('demet_token');
                    localStorage.removeItem('demet_user');
                    router.push('/login');
                  }}
                  title="Çıkış" style={{ fontSize: '0.8rem' }}
                >🚪</button>
              </div>
            )}
          </aside>

          {/* Main Content + Log Panel */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
            <main className="main-content" style={{ flex: 1, overflow: 'auto' }}>
              {children}
            </main>

            {/* ═══ Canlı Log Paneli ═══ */}
            {logPanelOpen && (
              <div style={{
                height: logPanelHeight,
                borderTop: '2px solid rgba(46,204,113,0.3)',
                background: 'var(--bg-secondary, #0a0a1a)',
                display: 'flex', flexDirection: 'column',
                flexShrink: 0,
              }}>
                {/* Log Panel Header */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 16px',
                  background: 'rgba(0,0,0,0.3)',
                  borderBottom: '1px solid var(--border-color)',
                  fontSize: '0.78rem', fontWeight: 600,
                  cursor: 'ns-resize', userSelect: 'none',
                }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    📋 Canlı Loglar
                    {logAutoRefresh && (
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: '#2ecc71', animation: 'pulse 1.5s infinite',
                      }} />
                    )}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{logs.length} kayıt</span>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => setLogAutoRefresh(!logAutoRefresh)}
                      style={{
                        padding: '2px 8px', borderRadius: 4, border: 'none', cursor: 'pointer',
                        background: logAutoRefresh ? 'rgba(46,204,113,0.2)' : 'rgba(255,255,255,0.05)',
                        color: logAutoRefresh ? '#2ecc71' : 'var(--text-muted)',
                        fontSize: '0.7rem', fontWeight: 600,
                      }}
                    >{logAutoRefresh ? '⏸ Duraklat' : '▶ Canlı'}</button>
                    <button
                      onClick={loadLogs}
                      style={{
                        padding: '2px 8px', borderRadius: 4, border: 'none', cursor: 'pointer',
                        background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)',
                        fontSize: '0.7rem',
                      }}
                    >🔄</button>
                    <button
                      onClick={() => { setLogPanelOpen(false); setLogAutoRefresh(false); }}
                      style={{
                        padding: '2px 8px', borderRadius: 4, border: 'none', cursor: 'pointer',
                        background: 'rgba(231,76,60,0.15)', color: '#e74c3c',
                        fontSize: '0.7rem',
                      }}
                    >✕</button>
                  </div>
                </div>

                {/* Log Items */}
                <div style={{
                  flex: 1, overflowY: 'auto', padding: '4px 0',
                  fontFamily: 'monospace', fontSize: '0.75rem',
                }}>
                  {logs.length === 0 ? (
                    <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                      Henüz log kaydı yok. Bot başlatıldığında loglar burada görünecek.
                    </div>
                  ) : (
                    logs.map(log => (
                      <div key={log.id} style={{
                        display: 'flex', gap: 8, padding: '3px 16px',
                        borderLeft: `2px solid ${levelColors[log.level] || '#95a5a6'}`,
                        lineHeight: 1.4,
                      }}>
                        <span style={{ color: 'var(--text-muted)', minWidth: 60, flexShrink: 0, fontSize: '0.68rem' }}>
                          {new Date(log.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                        <span style={{
                          fontSize: '0.6rem', fontWeight: 700, padding: '1px 4px',
                          borderRadius: 3, color: '#fff', flexShrink: 0,
                          background: levelColors[log.level] || '#95a5a6',
                          alignSelf: 'center',
                        }}>{log.level}</span>
                        <span style={{ color: 'var(--text-muted)', flexShrink: 0, fontSize: '0.68rem' }}>[{log.category}]</span>
                        <span style={{ color: 'var(--text-primary)' }}>
                          {log.account_username && <span style={{ color: '#667eea', fontWeight: 600 }}>@{log.account_username} </span>}
                          {log.action}
                          {log.details && <span style={{ color: 'var(--text-muted)' }}> — {log.details}</span>}
                        </span>
                      </div>
                    ))
                  )}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Pulse animation */}
        <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
      </body>
    </html>
  );
}
