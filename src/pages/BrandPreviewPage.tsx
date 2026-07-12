import {
  Bell, Briefcase, CalendarDays, CheckCircle2, Clock3, LayoutDashboard,
  LogIn, Send, Search, ShieldCheck, UserRound,
} from 'lucide-react';

const navy = '#252B3A';
const orange = '#F5A23A';
const orangeStrong = '#F7941D';
const orangeSoft = '#FFF4E8';
const inkMuted = '#667085';

const navItems = [
  { label: 'My Dashboard', icon: LayoutDashboard, active: true },
  { label: 'Apply Leave', icon: CalendarDays },
  { label: 'Timesheets', icon: Clock3 },
  { label: 'Check In / Out', icon: LogIn },
  { label: 'Requests', icon: Send },
  { label: 'Career Profile', icon: UserRound },
];

function PreviewCard({
  title,
  value,
  meta,
  icon,
  accent = orange,
}: {
  title: string;
  value: string;
  meta: string;
  icon: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-[#E7E9EE] bg-white p-5 shadow-[0_8px_24px_rgba(37,43,58,0.06)]">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-wide text-[#98A2B3]">{title}</div>
          <div className="mt-3 text-3xl font-extrabold tracking-tight" style={{ color: navy }}>{value}</div>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-xl" style={{ backgroundColor: `${accent}18`, color: accent }}>
          {icon}
        </div>
      </div>
      <div className="mt-4 text-sm font-medium" style={{ color: inkMuted }}>{meta}</div>
    </div>
  );
}

export function BrandPreviewPage() {
  return (
    <div className="min-h-screen bg-[#F7F6F2] text-[#252B3A]">
      <div className="flex min-h-screen">
        <aside className="flex w-[272px] shrink-0 flex-col border-r border-[#E4E7EC] bg-white">
          <div className="flex h-[86px] items-center border-b border-[#E4E7EC] px-6">
            <img src="/reknew-orbit.png" alt="Reknew Orbit" className="h-12 w-[190px] object-contain object-left" />
          </div>

          <nav className="flex-1 space-y-1 px-4 py-5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left text-sm font-bold transition"
                  style={{
                    backgroundColor: item.active ? navy : 'transparent',
                    color: item.active ? '#FFFFFF' : inkMuted,
                  }}
                >
                  <Icon size={18} style={{ color: item.active ? orange : inkMuted }} />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="border-t border-[#E4E7EC] p-4">
            <div className="flex items-center gap-3 rounded-xl bg-[#F7F6F2] p-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full text-sm font-extrabold text-white" style={{ backgroundColor: navy }}>
                TS
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-extrabold">Trilok Sai Kambham</div>
                <div className="text-xs font-medium" style={{ color: inkMuted }}>AI Developer</div>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-[70px] items-center justify-between border-b border-[#E4E7EC] bg-white px-8">
            <div className="relative w-[430px]">
              <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#98A2B3]" />
              <input
                value=""
                readOnly
                placeholder="Search employees, projects, skills..."
                className="h-11 w-full rounded-xl border border-[#E4E7EC] bg-[#FAFAF8] pl-11 pr-4 text-sm font-medium outline-none"
              />
            </div>
            <div className="flex items-center gap-3">
              <button className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#E4E7EC] bg-white text-[#667085]"><Bell size={18} /></button>
              <button className="rounded-xl px-4 py-2 text-sm font-extrabold text-white" style={{ backgroundColor: navy }}>Softer Orange Preview</button>
            </div>
          </header>

          <section className="px-8 py-7">
            <div className="mb-7 flex items-start justify-between gap-4">
              <div>
                <div className="text-xs font-extrabold uppercase tracking-[0.22em]" style={{ color: orangeStrong }}>Employee Portal</div>
                <h1 className="mt-2 text-3xl font-extrabold tracking-tight" style={{ color: navy }}>My Dashboard</h1>
                <p className="mt-1 text-sm font-medium" style={{ color: inkMuted }}>Your daily attendance, leave, project, and action summary.</p>
              </div>
              <button className="rounded-xl px-5 py-3 text-sm font-extrabold text-white shadow-[0_12px_24px_rgba(37,43,58,0.18)]" style={{ backgroundColor: navy }}>
                Check In
              </button>
            </div>

            <div className="mb-6 rounded-xl border border-[#F9D7A6] bg-[#FFF8EF] px-5 py-4">
              <div className="text-sm font-extrabold" style={{ color: navy }}>Preview direction: softer orange, stronger navy</div>
              <p className="mt-1 max-w-3xl text-sm leading-6" style={{ color: inkMuted }}>
                Large filled actions use navy. Orange is reserved for highlights, icons, badges, progress bars, and active accents, which makes the UI feel less loud while staying close to the Reknew Orbit logo.
              </p>
              <div className="mt-3 flex flex-wrap gap-3 text-xs font-extrabold">
                <span className="rounded-lg px-3 py-1.5 text-white" style={{ backgroundColor: orangeStrong }}>Logo orange</span>
                <span className="rounded-lg px-3 py-1.5" style={{ backgroundColor: orangeSoft, color: orangeStrong }}>Softer app accent</span>
                <span className="rounded-lg px-3 py-1.5 text-white" style={{ backgroundColor: navy }}>Primary navy</span>
              </div>
            </div>

            <div className="grid gap-5 xl:grid-cols-4">
              <PreviewCard title="Today" value="--" meta="Not checked in yet" icon={<LogIn size={21} />} accent={orange} />
              <PreviewCard title="Leave Balance" value="56 days" meta="CL 9 · SL 10 · EL 15 · PL 15" icon={<CalendarDays size={21} />} accent={navy} />
              <PreviewCard title="Timesheet" value="Approved" meta="Week: Jun 7 - Jun 13, 2026" icon={<CheckCircle2 size={21} />} accent={orange} />
              <PreviewCard title="Pending Actions" value="0" meta="All clear for today" icon={<ShieldCheck size={21} />} accent={orange} />
            </div>

            <div className="mt-6 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-xl border border-[#E7E9EE] bg-white shadow-[0_8px_24px_rgba(37,43,58,0.06)]">
                <div className="flex items-center justify-between border-b border-[#E7E9EE] px-5 py-4">
                  <div className="flex items-center gap-2 text-sm font-extrabold" style={{ color: navy }}>
                    <Briefcase size={18} style={{ color: orange }} />
                    My Projects
                  </div>
                  <button className="rounded-lg border border-[#E4E7EC] px-3 py-1.5 text-xs font-extrabold" style={{ color: navy }}>View Projects</button>
                </div>
                <div className="p-5">
                  <div className="rounded-xl border border-[#E7E9EE] bg-[#FAFAF8] p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-extrabold" style={{ color: navy }}>Reknew Orbit (RO-2026-001)</div>
                        <div className="mt-1 text-sm font-medium" style={{ color: inkMuted }}>AI Developer · 40% allocation</div>
                      </div>
                      <span className="rounded-lg px-2 py-1 text-xs font-extrabold" style={{ backgroundColor: orangeSoft, color: orangeStrong }}>Active</span>
                    </div>
                    <div className="mt-4 h-2 rounded-full bg-[#E4E7EC]">
                      <div className="h-2 rounded-full" style={{ width: '40%', backgroundColor: orange }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-[#E7E9EE] bg-white shadow-[0_8px_24px_rgba(37,43,58,0.06)]">
                <div className="border-b border-[#E7E9EE] px-5 py-4 text-sm font-extrabold" style={{ color: navy }}>Quick Actions</div>
                <div className="grid gap-3 p-5 sm:grid-cols-2">
                  {['Apply Leave', 'Submit Timesheet', 'Report Sick Today', 'New Request'].map((label, index) => (
                    <button
                      key={label}
                      className="rounded-xl border px-4 py-3 text-left text-sm font-extrabold"
                      style={{
                        backgroundColor: index === 0 ? navy : index === 1 ? orangeSoft : '#FFFFFF',
                        borderColor: index === 0 ? navy : index === 1 ? orangeSoft : '#E4E7EC',
                        color: index === 0 ? '#FFFFFF' : navy,
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
