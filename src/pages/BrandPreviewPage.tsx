import { Briefcase, CalendarDays, CheckCircle2, Clock3, Grid3X3, LogIn, Search, Send, ShieldCheck } from 'lucide-react';

const navy = 'var(--color-brand-navy)';
const orange = 'var(--color-brand-orange)';
const warm = 'var(--color-accent-light)';
const deepOrange = '#C2410C';
const activeText = '#9A3412';
const approvedGreen = '#11823B';
const approvedBg = '#EAF7EE';
const muted = 'var(--color-text-muted)';

function StatusBadge({ label, tone }: { label: string; tone: 'draft' | 'approved' | 'review' | 'due' }) {
  const styles = {
    draft: { background: '#F1F1F1', color: '#4B5563' },
    approved: { background: approvedBg, color: approvedGreen },
    review: { background: '#FFE8CC', color: activeText },
    due: { background: deepOrange, color: '#FFFFFF' },
  }[tone];

  return (
    <span className="inline-flex h-8 items-center rounded-full px-4 text-sm font-semibold" style={styles}>
      {label}
    </span>
  );
}

function PreviewCard({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-white p-7 shadow-[0_10px_30px_rgba(37,43,58,0.06)]">
      <div className="mb-5 text-sm font-semibold text-[var(--color-text-muted)]">{title}</div>
      {children}
    </section>
  );
}

function MiniMetric({
  title,
  value,
  badge,
  icon,
}: {
  title: string;
  value: string;
  badge?: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-white p-6 shadow-[0_10px_30px_rgba(37,43,58,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">{title}</div>
          <div className="mt-4 text-3xl font-bold text-[var(--color-brand-navy)]">{value}</div>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--color-accent-light)] text-[#C2410C]">
          {icon}
        </div>
      </div>
      {badge && <div className="mt-4">{badge}</div>}
    </div>
  );
}

export function BrandPreviewPage() {
  return (
    <div className="min-h-screen bg-white text-[var(--color-brand-navy)]">
      <div className="flex min-h-screen">
        <aside className="flex w-[286px] shrink-0 flex-col border-r border-[var(--color-border)] bg-white">
          <div className="flex h-[92px] items-center border-b border-[var(--color-border)] px-7">
            <img src="/reknew-orbit.png" alt="Reknew Orbit" className="h-12 w-[190px] object-contain object-left" />
          </div>

          <nav className="flex-1 space-y-2 px-5 py-6">
            {[
              ['My Dashboard', Grid3X3, true],
              ['Apply Leave', CalendarDays, false],
              ['Timesheets', Clock3, false],
              ['Check In / Out', LogIn, false],
              ['Requests', Send, false],
            ].map(([label, Icon, active]) => {
              const IconComp = Icon as typeof Grid3X3;
              return (
                <button
                  key={label as string}
                  className="relative flex w-full items-center gap-3 rounded-xl px-5 py-4 text-left text-base font-semibold transition"
                  style={{
                    backgroundColor: active ? warm : 'transparent',
                    color: active ? activeText : muted,
                  }}
                >
                  {active && <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-1 rounded-r-full" style={{ backgroundColor: deepOrange }} />}
                  <IconComp size={19} style={{ color: active ? deepOrange : muted }} />
                  {label as string}
                </button>
              );
            })}
          </nav>

          <div className="border-t border-[var(--color-border)] p-5">
            <div className="flex items-center gap-3 rounded-xl bg-[var(--color-brand-canvas)] p-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-brand-navy)] text-sm font-semibold text-white">TS</div>
              <div>
                <div className="text-sm font-semibold">Trilok Sai Kambham</div>
                <div className="text-xs font-semibold text-[var(--color-text-muted)]">AI Developer</div>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col bg-[var(--color-brand-canvas)]">
          <header className="flex h-[74px] items-center justify-between border-b border-[var(--color-border)] bg-white px-9">
            <div className="relative w-[460px]">
              <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
              <input
                readOnly
                placeholder="Search employees, projects, skills..."
                className="h-12 w-full rounded-xl border border-[var(--color-border)] bg-white pl-12 pr-4 text-sm font-semibold outline-none"
              />
            </div>
            <button className="rounded-xl px-5 py-3 text-sm font-semibold text-white" style={{ backgroundColor: navy }}>
              Apply Preview
            </button>
          </header>

          <section className="space-y-6 px-9 py-8">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.22em]" style={{ color: orange }}>Brand System Preview</div>
              <h1 className="mt-2 text-3xl font-bold tracking-tight">Softer navigation, clearer status, quieter cards</h1>
              <p className="mt-2 max-w-4xl text-base font-medium text-[var(--color-text-muted)]">
                This preview uses the screenshot direction: warm active states, deeper readable text, orange only for attention, and navy for primary actions.
              </p>
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              <PreviewCard title="01 · Active sidebar item">
                <div className="relative flex items-center gap-3 rounded-xl px-6 py-5 text-lg font-semibold" style={{ backgroundColor: warm, color: activeText }}>
                  <span className="absolute left-0 top-2 h-[calc(100%-16px)] w-1 rounded-r-full" style={{ backgroundColor: deepOrange }} />
                  <Grid3X3 size={20} style={{ color: deepOrange }} />
                  My Dashboard
                </div>
                <p className="mt-5 text-base leading-7 text-[var(--color-text-muted)]">
                  Uses warm fill, readable deep-orange text, and a left accent bar for selection.
                </p>
              </PreviewCard>

              <PreviewCard title="02 · Status badges">
                <div className="flex flex-wrap gap-3">
                  <StatusBadge label="draft" tone="draft" />
                  <StatusBadge label="approved" tone="approved" />
                  <StatusBadge label="Needs review" tone="review" />
                  <StatusBadge label="Due" tone="due" />
                </div>
                <p className="mt-5 text-base leading-7 text-[var(--color-text-muted)]">
                  Each status gets one meaning: neutral, approved, review, and urgent.
                </p>
              </PreviewCard>

              <PreviewCard title="03 · Icon chips on cards">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-[var(--color-accent-light)] text-[#C2410C]">
                  <CheckCircle2 size={25} strokeWidth={2.5} />
                </div>
                <p className="mt-5 text-base leading-7 text-[var(--color-text-muted)]">
                  Keeps the tinted chip but deepens the icon so it reads clearly.
                </p>
              </PreviewCard>
            </div>

            <div className="grid gap-6 xl:grid-cols-4">
              <MiniMetric title="Today" value="0h 0m" badge={<StatusBadge label="Not checked in" tone="draft" />} icon={<LogIn size={22} />} />
              <MiniMetric title="Leave Balance" value="56 days" badge={<div className="h-2 rounded-full bg-[#FFE8CC]"><div className="h-2 w-3/4 rounded-full bg-[var(--color-brand-orange)]" /></div>} icon={<CalendarDays size={22} />} />
              <MiniMetric title="Timesheet" value="Draft" badge={<StatusBadge label="Needs review" tone="review" />} icon={<Clock3 size={22} />} />
              <MiniMetric title="Pending Actions" value="1" badge={<StatusBadge label="Due" tone="due" />} icon={<ShieldCheck size={22} />} />
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
              <div className="rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_10px_30px_rgba(37,43,58,0.06)]">
                <div className="flex items-center justify-between border-b border-[var(--color-border)] px-6 py-5">
                  <div className="flex items-center gap-3 text-lg font-semibold">
                    <Briefcase size={20} className="text-[var(--color-brand-orange)]" />
                    My Projects
                  </div>
                  <button className="rounded-xl border border-[var(--color-border)] px-4 py-2 text-sm font-semibold">View Projects</button>
                </div>
                <div className="p-6">
                  <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-brand-canvas)] p-5">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-lg font-semibold">Reknew Orbit (RO-2026-001)</div>
                        <div className="mt-1 text-sm font-semibold text-[var(--color-text-muted)]">AI Developer · 40% allocation</div>
                      </div>
                      <StatusBadge label="approved" tone="approved" />
                    </div>
                    <div className="mt-5 h-2 rounded-full bg-[#FFE8CC]">
                      <div className="h-2 w-2/5 rounded-full bg-[var(--color-brand-orange)]" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-[var(--color-border)] bg-white shadow-[0_10px_30px_rgba(37,43,58,0.06)]">
                <div className="border-b border-[var(--color-border)] px-6 py-5 text-lg font-semibold">Quick Actions</div>
                <div className="grid gap-3 p-6 sm:grid-cols-2">
                  {['Apply Leave', 'Submit Timesheet', 'Report Sick Today', 'New Request'].map((label, index) => (
                    <button
                      key={label}
                      className="rounded-xl border px-5 py-4 text-left text-sm font-semibold transition hover:border-[#C2410C] hover:bg-[var(--color-accent-light)] hover:text-[#9A3412]"
                      style={{
                        backgroundColor: index === 0 ? navy : 'white',
                        borderColor: index === 0 ? navy : 'var(--color-border)',
                        color: index === 0 ? 'white' : navy,
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
