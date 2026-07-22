import { useEffect, useState } from 'react';
import { Card } from '@/components/ui';
import { CareerProfilePanel } from '@/components/career/CareerProfilePanel';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface EmployeeProfile {
  id: string;
  first_name: string;
  last_name: string;
  work_email: string;
  designation?: string | null;
  department?: string | null;
}

export function MyCareerProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!user?.email) {
        setLoading(false);
        setError('No employee email found.');
        return;
      }
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`${API_BASE}/auth/me/${encodeURIComponent(user.email)}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.success || !data.employee) {
          throw new Error(data.detail || data.message || 'Could not load employee profile.');
        }
        if (!cancelled) setProfile(data.employee);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load employee profile.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [user?.email]);

  if (loading) {
    return <div className="p-6 text-sm text-gray-500">Loading career profile...</div>;
  }

  if (error || !profile) {
    return (
      <div className="p-6">
        <Card className="p-8 text-center">
          <div className="font-bold text-[var(--color-brand-navy)]">Career profile unavailable</div>
          <div className="mt-1 text-sm text-gray-500">{error || 'Profile data was not found.'}</div>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">My Career Profile</h1>
        <p className="mt-1 text-sm text-gray-500">Maintain your skills, project experience, resume, and career preferences.</p>
      </div>
      <CareerProfilePanel
        employee={{
          id: profile.id,
          name: `${profile.first_name} ${profile.last_name}`.trim(),
          email: profile.work_email,
          designation: profile.designation,
          department: profile.department,
        }}
        editable
      />
    </div>
  );
}
