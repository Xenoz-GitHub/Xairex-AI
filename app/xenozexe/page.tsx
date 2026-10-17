'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function AdminLogin() {
  const router = useRouter();
  const [pin, setPin] = useState('');
  const [location, setLocation] = useState<GeolocationPosition | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setLocation(pos),
        (err) => console.error('Geolocation error:', err)
      );
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('/api/admin/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pin,
          location: location ? {
            lat: location.coords.latitude,
            lon: location.coords.longitude,
            accuracy: location.coords.accuracy
          } : null
        })
      });

      if (response.ok) {
        router.push('/xenozexe/dashboard');
      } else {
        setError('Invalid PIN');
      }
    } catch (err) {
      setError('Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="bg-terminal border border-cyan/20 rounded-lg p-8 max-w-md w-full">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-cyan mb-2">ADMIN ACCESS</h1>
          <p className="text-gray-500 text-sm">ENTER 16-DIGIT PIN</p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <input
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            maxLength={16}
            placeholder="················"
            className="w-full bg-neural border border-cyan/30 rounded px-4 py-3 text-center text-cyan text-lg tracking-widest focus:outline-none focus:border-cyan"
            autoFocus
          />

          {!location && (
            <p className="text-amber-500 text-sm text-center">
              Location permission required
            </p>
          )}

          {error && <p className="text-red-500 text-sm text-center">{error}</p>}

          <button
            type="submit"
            disabled={!location || loading || pin.length !== 16}
            className="w-full bg-cyan text-neural py-3 rounded font-bold hover:bg-cyan/90 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'AUTHENTICATING...' : 'AUTHENTICATE'}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-cyan/10 text-center">
          <p className="text-xs text-gray-600">
            All login attempts are logged with IP and location data
          </p>
        </div>
      </div>
    </div>
  );
}
