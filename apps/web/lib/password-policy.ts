// Client-side mirror of the API password policy (apps/api services/password_auth.py).
// The server stays authoritative; this only gives instant inline feedback and
// keeps both UIs (login modal first-time setup, account center change form)
// consistent.

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 64;

/** Returns a user-facing policy error message, or null when acceptable. */
export function validatePasswordClient(password: string): string | null {
  if (!password || password.length < PASSWORD_MIN_LENGTH) {
    return `密码至少需要 ${PASSWORD_MIN_LENGTH} 个字符`;
  }
  if (password.length > PASSWORD_MAX_LENGTH) {
    return `密码最长 ${PASSWORD_MAX_LENGTH} 个字符`;
  }
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
    return "密码需要同时包含字母和数字";
  }
  return null;
}

/** Confirm-field check used by both password forms. */
export function validatePasswordConfirmation(password: string, confirm: string): string | null {
  const policyError = validatePasswordClient(password);
  if (policyError) return policyError;
  if (password !== confirm) return "两次输入的密码不一致";
  return null;
}
