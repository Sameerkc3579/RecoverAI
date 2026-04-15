/**
 * RecoverAI — Auth token helpers
 * Tokens are stored in localStorage.
 */

const ACCESS_KEY  = 'recoverai_token';
const REFRESH_KEY = 'recoverai_refresh';
const USER_KEY    = 'recoverai_user_details';
const IS_ADMIN    = 'recoverai_is_admin';

export interface StoredUser {
  email?: string;
  business_name?: string | null;
  is_admin?: boolean;
}

export function saveTokens(access: string, refresh: string, user?: StoredUser) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    if (user.is_admin) {
      localStorage.setItem(IS_ADMIN, 'true');
    } else {
      localStorage.removeItem(IS_ADMIN);
    }
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): StoredUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(IS_ADMIN);
}

export function isLoggedIn(): boolean {
  return !!getAccessToken();
}
