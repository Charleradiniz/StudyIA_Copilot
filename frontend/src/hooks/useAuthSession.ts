import { useCallback, useEffect, useState } from "react";
import { readPasswordResetToken, replacePasswordResetToken } from "../app/auth-utils";
import { mapAuthSession } from "../app/workspace-utils";
import type { AuthSession } from "../app/types";
import {
  ApiError,
  confirmPasswordReset,
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
  requestPasswordReset,
} from "../services/api";

type AuthSubmitPayload = {
  mode: "login" | "register";
  fullName: string;
  email: string;
  password: string;
};

type PasswordResetConfirmPayload = {
  token: string;
  password: string;
};

type UseAuthSessionOptions = {
  onSignedOut?: (userId: string | null) => void;
};

export function useAuthSession({ onSignedOut }: UseAuthSessionOptions = {}) {
  const [auth, setAuth] = useState<AuthSession | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [passwordResetToken, setPasswordResetToken] = useState<string | null>(() =>
    readPasswordResetToken(),
  );

  const clearPasswordResetToken = useCallback(() => {
    setPasswordResetToken(null);
    replacePasswordResetToken(null);
  }, []);

  const performLocalSignOut = useCallback(() => {
    onSignedOut?.(auth?.user.id ?? null);
    setAuth(null);
    setAuthLoading(false);
  }, [auth?.user.id, onSignedOut]);

  const handleUnauthorized = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        performLocalSignOut();
        return true;
      }

      return false;
    },
    [performLocalSignOut],
  );

  useEffect(() => {
    let ignore = false;

    getCurrentUser()
      .then((response) => {
        if (ignore) {
          return;
        }

        setAuth(mapAuthSession(response));
        setAuthLoading(false);
      })
      .catch((error) => {
        if (ignore) {
          return;
        }

        if (!(error instanceof ApiError && error.status === 401)) {
          console.error("Failed to restore session", error);
        }

        setAuth(null);
        setAuthLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  const handleAuthSubmit = useCallback(
    async (payload: AuthSubmitPayload) => {
      setAuthSubmitting(true);

      try {
        const response =
          payload.mode === "login"
            ? await loginUser({
                email: payload.email,
                password: payload.password,
              })
            : await registerUser({
                fullName: payload.fullName,
                email: payload.email,
                password: payload.password,
              });

        setAuth(mapAuthSession(response));
        clearPasswordResetToken();
      } finally {
        setAuthSubmitting(false);
      }
    },
    [clearPasswordResetToken],
  );

  const handlePasswordResetRequest = useCallback(async (email: string) => {
    setAuthSubmitting(true);

    try {
      return await requestPasswordReset({ email });
    } finally {
      setAuthSubmitting(false);
    }
  }, []);

  const handlePasswordResetConfirm = useCallback(
    async (payload: PasswordResetConfirmPayload) => {
      setAuthSubmitting(true);

      try {
        return await confirmPasswordReset(payload);
      } finally {
        setAuthSubmitting(false);
      }
    },
    [],
  );

  const handleLogout = useCallback(async () => {
    try {
      await logoutUser();
    } catch (error) {
      console.error("Failed to logout cleanly", error);
    } finally {
      performLocalSignOut();
    }
  }, [performLocalSignOut]);

  return {
    auth,
    authLoading,
    authSubmitting,
    currentUser: auth?.user ?? null,
    isAuthenticated: Boolean(auth?.user.id),
    passwordResetToken,
    clearPasswordResetToken,
    handleAuthSubmit,
    handlePasswordResetRequest,
    handlePasswordResetConfirm,
    handleLogout,
    handleUnauthorized,
  };
}
