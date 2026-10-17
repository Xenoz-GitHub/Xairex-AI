import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';

export default async function AdminDashboard() {
  const cookieStore = await cookies();
  const session = cookieStore.get('admin_session');

  if (!session || session.value !== 'authenticated') {
    redirect('/xenozexe');
  }

  return (
    <div className="min-h-screen pt-32 pb-20">
      <div className="container mx-auto px-6">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-cyan">Admin Dashboard</h1>
          <Link href="/" className="text-cyan hover:underline">← Back to Site</Link>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
            <h2 className="text-cyan mb-2 text-sm">Total Users</h2>
            <p className="text-4xl font-bold">--</p>
            <p className="text-gray-500 text-xs mt-2">All time</p>
          </div>
          
          <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
            <h2 className="text-cyan mb-2 text-sm">Active Today</h2>
            <p className="text-4xl font-bold">--</p>
            <p className="text-gray-500 text-xs mt-2">Last 24 hours</p>
          </div>
          
          <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
            <h2 className="text-cyan mb-2 text-sm">Total Sessions</h2>
            <p className="text-4xl font-bold">--</p>
            <p className="text-gray-500 text-xs mt-2">App launches</p>
          </div>
        </div>

        <div className="bg-terminal border border-cyan/20 rounded-lg p-6">
          <h2 className="text-xl font-bold text-cyan mb-4">Admin Login Logs</h2>
          <p className="text-gray-400">Login attempt history will appear here.</p>
        </div>
      </div>
    </div>
  );
}
