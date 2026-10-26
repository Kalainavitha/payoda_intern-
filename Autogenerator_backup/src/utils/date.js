// src/utils/date.js

export function today(daysToAdd = 0) {
  const date = new Date();
  date.setDate(date.getDate() + daysToAdd);
  return date.toISOString().split('T')[0];
}

export function dateLabel(dateString, options = {}) {
  if (!dateString) return '';
  // Append a time so it parses in local timezone correctly
  const date = new Date(`${dateString}T12:00:00`);
  if (isNaN(date.getTime())) return dateString;
  
  return new Intl.DateTimeFormat('en', {
    month: options.month || 'short',
    day: options.day || 'numeric',
    year: options.year || undefined
  }).format(date);
}

export function dayDelta(start, end) {
  if (!start || !end) return 0;
  const startDate = new Date(`${start}T12:00:00`);
  const endDate = new Date(`${end}T12:00:00`);
  const diffTime = Math.abs(endDate - startDate);
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}