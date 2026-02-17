'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
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
  { key: 'messages', icon: '💬', label: 'Mesajlar', path: '/messages' },
  { key: 'downloads', icon: '⬇️', label: 'İndirme', path: '/downloads' },
  { key: 'hashtags', icon: '#️⃣', label: 'Hashtagler', path: '/hashtags' },
  { key: 'settings', icon: '⚙️', label: 'Ayarlar', path: '/settings' },
];

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

  useEffect(() => {
    // Electron detect
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
          {/* Title bar on login too */}
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
        {/* Custom Title Bar — sadece Electron'da görünür */}
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

            {/* Kullanıcı bilgisi */}
            {user && (
              <div style={{
                padding: '16px',
                borderTop: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}>
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: 'var(--gradient-accent)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 700,
                  fontSize: '0.75rem',
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
                  title="Çıkış"
                  style={{ fontSize: '0.8rem' }}
                >
                  🚪
                </button>
              </div>
            )}
          </aside>

          {/* Main */}
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
