const PASSWORD_RESET_QUERY_KEY = "reset_password_token";

export function readPasswordResetToken() {
  if (typeof window === "undefined") {
    return null;
  }

  const token = new URLSearchParams(window.location.search).get(PASSWORD_RESET_QUERY_KEY);
  return token && token.trim().length > 0 ? token.trim() : null;
}

export function replacePasswordResetToken(token: string | null) {
  if (typeof window === "undefined") {
    return;
  }

  const url = new URL(window.location.href);
  if (token) {
    url.searchParams.set(PASSWORD_RESET_QUERY_KEY, token);
  } else {
    url.searchParams.delete(PASSWORD_RESET_QUERY_KEY);
  }

  window.history.replaceState({}, "", url.toString());
}
