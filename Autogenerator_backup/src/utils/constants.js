import { LayoutDashboard, FolderKanban, UsersRound, CalendarDays, CalendarRange, Settings } from 'lucide-react';

export const NAV = [
  ['dashboard', 'Dashboard', LayoutDashboard],
  ['create', 'New Project', FolderKanban],
  ['team', 'Team', UsersRound],
  ['availability', 'Availability', CalendarDays],
  ['plans', 'Plans', CalendarRange],
  ['settings', 'Settings', Settings],
];

export const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const TYPES = [
  'Web Application',
  'Mobile Application',
  'API',
  'AI/ML',
  'Testing',
  'Other'
];

export const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'];