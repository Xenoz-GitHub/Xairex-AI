import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/db';

const ADMIN_PIN = process.env.ADMIN_PIN || '1346251346795846';

export async function POST(req: NextRequest) {
  const { pin, location } = await req.json();
  const ip = req.headers.get('x-forwarded-for') || req.headers.get('x-real-ip') || 'unknown';
  const userAgent = req.headers.get('user-agent');

  const success = pin === ADMIN_PIN;

  // Log attempt to database
  try {
    const sql = getDb();
    await sql`
      INSERT INTO admin_logs (ip_address, user_agent, location, success, pin_attempt)
      VALUES (${ip}, ${userAgent}, ${JSON.stringify(location)}, ${success}, ${pin})
    `;
  } catch (error) {
    console.error('Failed to log admin attempt:', error);
  }

  if (success) {
    const response = NextResponse.json({ ok: true });
    response.cookies.set('admin_session', 'authenticated', {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 60 * 4 // 4 hours
    });
    return response;
  }

  return NextResponse.json({ error: 'Invalid PIN' }, { status: 401 });
}
