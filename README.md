# Reknew Orbit — Employee Management System

A modern, premium SaaS dashboard for workforce operations built with React, TypeScript, Vite, and Tailwind CSS.

## Tech Stack

- **React** 18 + **TypeScript**
- **Vite** — blazing fast dev server & build
- **Tailwind CSS** — utility-first styling with custom design tokens
- **Recharts** — charts & data visualization
- **Lucide React** — clean icon system
- **React Router DOM** — client-side routing
- **clsx + tailwind-merge** — className utilities (shadcn/ui pattern)

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Start dev server
npm run dev

# 3. Open in browser
# → http://localhost:5173
```

## Project Structure

```
src/
├── components/
│   ├── ui/              # Reusable UI primitives (Card, Badge, Avatar, Button)
│   ├── layout/          # Sidebar, TopNav
│   └── dashboard/       # KpiCards, PendingTasks, Charts, Widgets, ActivityFeed
├── pages/               # Page components (DashboardPage, PlaceholderPages)
├── layouts/             # AppLayout (sidebar + topnav wrapper)
├── routes/              # React Router configuration
├── data/                # Mock JSON data (replace with API calls later)
├── services/            # API service layer (mock, ready for FastAPI)
├── types/               # TypeScript interfaces
├── hooks/               # Custom hooks (ready for TanStack Query)
├── utils/               # Utility functions (cn helper)
└── assets/              # Static assets
```

## Design System

| Token              | Value     |
|---------------------|-----------|
| Primary Olive       | `#66785F` |
| Secondary Sage      | `#A3B18A` |
| Warm Background     | `#F7F6F2` |
| Card Background     | `#FEFEFC` |
| Primary Text        | `#2F3437` |
| Secondary Text      | `#6B7280` |
| Border              | `#E5E7EB` |
| Hover Background    | `#EEF1E8` |

All hover states use olive/sage backgrounds. No black highlights, no dark themes.

## Backend Integration

The frontend is structured for a future FastAPI + PostgreSQL backend:

- `src/services/api.ts` — API layer with mock data, swap to real `fetch()` calls
- `src/types/index.ts` — TypeScript interfaces matching expected API shapes
- `src/data/mockData.ts` — Static data, easily replaceable with API responses

## Available Routes

| Route                  | Page                  |
|------------------------|-----------------------|
| `/`                    | Dashboard Overview    |
| `/employees`           | Employees             |
| `/onboarding`          | Onboarding Center     |
| `/client-onboarding`   | Client Onboarding     |
| `/time-off`            | Time Off & Attendance |
| `/team-allocation`     | Team Allocation       |
| `/assets`              | Assets & Access       |
| `/admin/users`         | User Management       |
| `/admin/roles`         | Roles & Permissions   |
| `/admin/policies`      | Policies              |

## Build for Production

```bash
npm run build
npm run preview
```
