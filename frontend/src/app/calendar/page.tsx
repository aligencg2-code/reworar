'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function CalendarPage() {
    const [year, setYear] = useState(new Date().getFullYear());
    const [month, setMonth] = useState(new Date().getMonth() + 1);
    const [calendarData, setCalendarData] = useState<Record<number, any[]>>({});
    const [accounts, setAccounts] = useState<any[]>([]);
    const [selectedAccount, setSelectedAccount] = useState<string>('');
    const [loading, setLoading] = useState(true);

    const monthNames = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
        'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
    const dayNames = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];

    useEffect(() => { loadData(); }, [year, month, selectedAccount]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [calData, accData] = await Promise.all([
                api.getCalendar(month, year, selectedAccount ? parseInt(selectedAccount) : undefined),
                api.getAccounts(),
            ]);
            setCalendarData(calData.days || {});
            setAccounts(accData || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const getDaysInMonth = (y: number, m: number) => new Date(y, m, 0).getDate();
    const getFirstDayOfMonth = (y: number, m: number) => {
        const d = new Date(y, m - 1, 1).getDay();
        return d === 0 ? 6 : d - 1; // Pazartesi başlangıç
    };

    const prevMonth = () => {
        if (month === 1) { setMonth(12); setYear(y => y - 1); }
        else setMonth(m => m - 1);
    };

    const nextMonth = () => {
        if (month === 12) { setMonth(1); setYear(y => y + 1); }
        else setMonth(m => m + 1);
    };

    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    const today = new Date();

    return (
        <div>
            <div className="page-header">
                <div>
                    <h2 className="page-header__title">📅 Takvim</h2>
                    <p className="page-header__subtitle">Planlanan gönderilerin takvim görünümü</p>
                </div>
                <select
                    className="form-select"
                    style={{ width: 200 }}
                    value={selectedAccount}
                    onChange={(e) => setSelectedAccount(e.target.value)}
                >
                    <option value="">Tüm Hesaplar</option>
                    {accounts.map((a: any) => <option key={a.id} value={a.id}>@{a.username}</option>)}
                </select>
            </div>

            <div className="card" style={{ marginBottom: 20 }}>
                <div className="flex-between" style={{ marginBottom: 20 }}>
                    <button className="btn btn-secondary btn-sm" onClick={prevMonth}>◀ Önceki</button>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                        {monthNames[month - 1]} {year}
                    </h3>
                    <button className="btn btn-secondary btn-sm" onClick={nextMonth}>Sonraki ▶</button>
                </div>

                {loading ? (
                    <div className="flex-center" style={{ height: 300 }}><div className="spinner" /></div>
                ) : (
                    <div className="calendar-grid">
                        {dayNames.map(d => (
                            <div key={d} className="calendar-day-header">{d}</div>
                        ))}
                        {/* Boş hücreler */}
                        {Array.from({ length: firstDay }, (_, i) => (
                            <div key={`empty-${i}`} style={{ minHeight: 100 }} />
                        ))}
                        {/* Gün hücreleri */}
                        {Array.from({ length: daysInMonth }, (_, i) => {
                            const day = i + 1;
                            const events = calendarData[day] || [];
                            const isToday = today.getFullYear() === year && today.getMonth() + 1 === month && today.getDate() === day;

                            return (
                                <div
                                    key={day}
                                    className="calendar-day"
                                    style={isToday ? { borderColor: 'var(--color-primary)', background: 'rgba(233,30,144,0.05)' } : {}}
                                >
                                    <div className="calendar-day__number" style={isToday ? { color: 'var(--color-primary)' } : {}}>
                                        {day}
                                    </div>
                                    {events.map((ev: any, idx: number) => (
                                        <div key={idx} className={`calendar-day__event ${ev.media_type}`}>
                                            {ev.time} {ev.caption}
                                        </div>
                                    ))}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
