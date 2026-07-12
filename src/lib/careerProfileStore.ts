export interface CareerSkill {
  id: string;
  name: string;
  level: string;
  years: string;
  lastUsed: string;
}

export interface CareerProject {
  id: string;
  name: string;
  role: string;
  duration: string;
  stack: string;
  summary: string;
}

export interface CareerCertification {
  id: string;
  name: string;
  issuer: string;
  issuedOn: string;
}

export interface CareerProfileData {
  seedVersion?: string;
  summary: string;
  targetRoles: string;
  preferredSkills: string;
  workPreference: string;
  resumeName: string;
  resumeUpdatedAt: string;
  resumeDataUrl: string;
  resumeMimeType: string;
  resumeSize: number;
  skills: CareerSkill[];
  projects: CareerProject[];
  certifications: CareerCertification[];
}

const STORAGE_KEY = 'reknew_orbit_career_profiles';

export const emptyCareerProfile: CareerProfileData = {
  seedVersion: '',
  summary: '',
  targetRoles: '',
  preferredSkills: '',
  workPreference: '',
  resumeName: '',
  resumeUpdatedAt: '',
  resumeDataUrl: '',
  resumeMimeType: '',
  resumeSize: 0,
  skills: [],
  projects: [],
  certifications: [],
};

const seededProfiles: Record<string, CareerProfileData> = {
  '00000000-0000-0000-0000-000000000004': {
    seedVersion: 'trilok-ai-engineer-2026-07-11',
    summary: 'AI Engineer with 3 years of experience building Python and cloud-based machine learning solutions. Strong hands-on work in generative AI prototypes, model evaluation, data pipelines, API integration, and production-ready internal tools.',
    targetRoles: 'AI Engineer, Machine Learning Engineer, GenAI Developer, Applied AI Engineer',
    preferredSkills: 'Python, FastAPI, LangChain, OpenAI APIs, RAG, SQL, Vector Databases, Azure, AWS, React',
    workPreference: 'AI/ML product engineering, internal tools, client POCs, hybrid or remote delivery',
    resumeName: 'Trilok_Sai_Kambham_AI_Engineer_Resume.pdf',
    resumeUpdatedAt: '2026-07-11T00:00:00.000Z',
    resumeDataUrl: '',
    resumeMimeType: 'application/pdf',
    resumeSize: 0,
    skills: [
      { id: 'seed-skill-python', name: 'Python', level: 'Advanced', years: '3', lastUsed: '2026' },
      { id: 'seed-skill-genai', name: 'Generative AI / LLMs', level: 'Intermediate', years: '2', lastUsed: '2026' },
      { id: 'seed-skill-fastapi', name: 'FastAPI', level: 'Intermediate', years: '2', lastUsed: '2026' },
      { id: 'seed-skill-sql', name: 'SQL', level: 'Intermediate', years: '3', lastUsed: '2026' },
      { id: 'seed-skill-react', name: 'React', level: 'Intermediate', years: '2', lastUsed: '2026' },
      { id: 'seed-skill-cloud', name: 'Azure / AWS', level: 'Intermediate', years: '2', lastUsed: '2026' },
    ],
    projects: [
      {
        id: 'seed-project-rag',
        name: 'HR Knowledge Assistant POC',
        role: 'AI Engineer',
        duration: 'Jan 2026 - Mar 2026',
        stack: 'Python, FastAPI, OpenAI APIs, Vector Search, React',
        summary: 'Built a retrieval-augmented assistant for HR policy search, employee FAQs, and document Q&A. Designed prompt templates, source citation flow, and evaluation checks for answer quality.',
      },
      {
        id: 'seed-project-forecasting',
        name: 'Workforce Forecasting Insights',
        role: 'AI Developer',
        duration: 'Apr 2025 - Dec 2025',
        stack: 'Python, Pandas, SQL, FastAPI, Recharts',
        summary: 'Created predictive dashboards for allocation, bench availability, and staffing demand. Implemented data preparation scripts, APIs, and visual summaries for managers.',
      },
      {
        id: 'seed-project-automation',
        name: 'Document Automation Toolkit',
        role: 'Full Stack AI Engineer',
        duration: 'Aug 2024 - Mar 2025',
        stack: 'Python, OCR, React, PostgreSQL',
        summary: 'Developed internal automation for extracting structured data from operational documents and routing review tasks to the right team members.',
      },
    ],
    certifications: [
      { id: 'seed-cert-ai', name: 'Azure AI Fundamentals', issuer: 'Microsoft', issuedOn: '2025-09-15' },
      { id: 'seed-cert-cloud', name: 'AWS Cloud Practitioner', issuer: 'Amazon Web Services', issuedOn: '2024-11-20' },
    ],
  },
};

function isEmptyOrTestProfile(profile: CareerProfileData) {
  const hasNarrative = Boolean(
    profile.summary.trim()
    || profile.targetRoles.trim()
    || profile.preferredSkills.trim()
    || profile.workPreference.trim()
    || profile.skills.length
    || profile.projects.length
  );
  if (!hasNarrative) return true;
  const hasOnlyTestCerts = profile.certifications.length > 0 && profile.certifications.every((cert) => (
    [cert.name, cert.issuer, cert.issuedOn].every((value) => !value.trim() || value.trim().toLowerCase() === 'test')
  ));
  return !hasNarrative && (profile.certifications.length === 0 || hasOnlyTestCerts);
}

function readProfiles(): Record<string, CareerProfileData> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeProfiles(profiles: Record<string, CareerProfileData>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profiles));
}

export function getCareerProfile(employeeId: string): CareerProfileData {
  const profiles = readProfiles();
  const storedProfile = { ...emptyCareerProfile, ...(profiles[employeeId] || {}) };
  const seededProfile = seededProfiles[employeeId];
  if (seededProfile && isEmptyOrTestProfile(storedProfile)) {
    return seededProfile;
  }
  return storedProfile;
}

export function getSeededCareerProfile(employeeId: string, employeeName?: string | null, employeeEmail?: string | null): CareerProfileData {
  const normalizedName = (employeeName || '').toLowerCase();
  const normalizedEmail = (employeeEmail || '').toLowerCase();
  const isTrilok = normalizedName.includes('trilok') || normalizedEmail.includes('trilok');
  if (!isTrilok) return getCareerProfile(employeeId);

  const profiles = readProfiles();
  const storedProfile = { ...emptyCareerProfile, ...(profiles[employeeId] || {}) };
  const seededProfile = seededProfiles['00000000-0000-0000-0000-000000000004'];
  if (storedProfile.seedVersion !== seededProfile.seedVersion) {
    return seededProfile;
  }
  return storedProfile;
}

export function saveCareerProfile(employeeId: string, profile: CareerProfileData) {
  const profiles = readProfiles();
  profiles[employeeId] = profile;
  writeProfiles(profiles);
  window.dispatchEvent(new CustomEvent('reknew:career-profile-updated', { detail: { employeeId } }));
}

export function listCareerProfiles() {
  return readProfiles();
}

export function careerProfileCompleteness(profile: CareerProfileData) {
  const checks = [
    profile.summary.trim(),
    profile.targetRoles.trim(),
    profile.preferredSkills.trim(),
    profile.resumeName.trim(),
    profile.skills.length > 0,
    profile.projects.length > 0,
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}
