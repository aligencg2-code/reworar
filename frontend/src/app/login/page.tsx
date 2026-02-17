'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function LoginPage() {
    const router = useRouter();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const data = await api.login(username, password);
            localStorage.setItem('demet_user', JSON.stringify(data.user));
            router.push('/');
        } catch (err: any) {
            setError(err.message || 'Giriş başarısız');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--bg-primary)',
            position: 'relative',
            overflow: 'hidden',
        }}>
            {/* Animated background orbs */}
            <div style={{
                position: 'absolute',
                width: 400,
                height: 400,
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(233,30,144,0.15) 0%, transparent 70%)',
                top: -100,
                left: -100,
                animation: 'float 8s ease-in-out infinite',
            }} />
            <div style={{
                position: 'absolute',
                width: 300,
                height: 300,
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(155,89,182,0.12) 0%, transparent 70%)',
                bottom: -50,
                right: -50,
                animation: 'float 10s ease-in-out infinite reverse',
            }} />

            <style>{`
        @keyframes float {
          0%, 100% { transform: translate(0, 0); }
          50% { transform: translate(20px, -20px); }
        }
      `}</style>

            <form onSubmit={handleLogin} style={{
                width: '100%',
                maxWidth: 400,
                padding: 40,
                background: 'var(--bg-card)',
                backdropFilter: 'blur(20px)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-xl)',
                position: 'relative',
                zIndex: 1,
            }}>
                <div style={{ textAlign: 'center', marginBottom: 32 }}>
                    <h1 style={{
                        fontSize: '2rem',
                        fontWeight: 800,
                        background: 'var(--gradient-primary)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        marginBottom: 8,
                    }}>
                        Demet
                    </h1>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        Instagram İçerik Planlama ve Mesaj Yönetimi
                    </p>
                </div>

                {error && (
                    <div style={{
                        padding: '10px 14px',
                        background: 'rgba(231, 76, 60, 0.1)',
                        border: '1px solid rgba(231, 76, 60, 0.3)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--color-error)',
                        fontSize: '0.82rem',
                        marginBottom: 16,
                    }}>
                        {error}
                    </div>
                )}

                <div className="form-group">
                    <label className="form-label">Kullanıcı Adı</label>
                    <input
                        type="text"
                        className="form-input"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="admin"
                        required
                    />
                </div>

                <div className="form-group">
                    <label className="form-label">Şifre</label>
                    <input
                        type="password"
                        className="form-input"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                    />
                </div>

                <button
                    type="submit"
                    className="btn btn-primary btn-lg"
                    style={{ width: '100%', marginTop: 8 }}
                    disabled={loading}
                >
                    {loading ? (
                        <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                    ) : (
                        'Giriş Yap'
                    )}
                </button>

                <div style={{
                    marginTop: 20,
                    padding: '12px 14px',
                    background: 'rgba(52, 152, 219, 0.08)',
                    border: '1px solid rgba(52, 152, 219, 0.2)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)',
                }}>
                    <b>Varsayılan:</b> admin / admin123
                </div>
            </form>
        </div>
    );
}
