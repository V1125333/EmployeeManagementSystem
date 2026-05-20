/**
 * API Service Layer
 *
 * Currently returns mock data. Replace with real fetch calls
 * when FastAPI backend is ready.
 *
 * Future base URL: process.env.VITE_API_URL || 'http://localhost:8000/api/v1'
 */

import {
  kpiMetrics,
  pendingTasks,
  departmentData,
  attendanceData,
  newJoiners,
  onLeaveToday,
  activityFeed,
  announcements,
} from '@/data/mockData';

// Simulate network delay
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const api = {
  // ── Dashboard ──
  async getDashboardKPIs() {
    await delay(300);
    return kpiMetrics;
  },

  async getPendingTasks() {
    await delay(200);
    return pendingTasks;
  },

  async getDepartmentHeadcount() {
    await delay(250);
    return departmentData;
  },

  async getAttendanceTrend() {
    await delay(250);
    return attendanceData;
  },

  async getNewJoiners() {
    await delay(200);
    return newJoiners;
  },

  async getOnLeaveToday() {
    await delay(200);
    return onLeaveToday;
  },

  async getActivityFeed() {
    await delay(300);
    return activityFeed;
  },

  async getAnnouncements() {
    await delay(200);
    return announcements;
  },

  // ── Employees (placeholder) ──
  async getEmployees() {
    await delay(400);
    return [];
  },

  // ── Auth (placeholder for JWT) ──
  async login(_email: string, _password: string) {
    await delay(500);
    return { token: 'mock-jwt-token', user: { name: 'Super Admin', role: 'admin' } };
  },
};
