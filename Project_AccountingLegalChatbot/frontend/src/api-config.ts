/**
 * Centralized API configuration
 * Loads from VITE_API_BASE_URL environment variable
 * Defaults to localhost:8000 if not set
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const getApiUrl = (path: string): string => {
  return `${API_BASE_URL}${path.startsWith('/') ? path : '/' + path}`;
};
