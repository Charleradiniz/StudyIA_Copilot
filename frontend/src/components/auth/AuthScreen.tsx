import { useState, type FormEvent } from "react";

type AuthMode = "login" | "register" | "forgot" | "reset";

type Props = {
  loading: boolean;
  passwordResetToken: string | null;
  onSubmit: (payload: {
    mode: "login" | "register";
    fullName: string;
    email: string;
    password: string;
  }) => Promise<void>;
  onRequestPasswordReset: (email: string) => Promise<{ message?: string } | undefined>;
  onConfirmPasswordReset: (payload: {
    token: string;
    password: string;
  }) => Promise<{ message?: string } | undefined>;
  onClearPasswordResetToken: () => void;
};

export default function AuthScreen({
  loading,
  passwordResetToken,
  onSubmit,
  onRequestPasswordReset,
  onConfirmPasswordReset,
  onClearPasswordResetToken,
}: Props) {
  const [manualMode, setManualMode] = useState<AuthMode>("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const mode: AuthMode = passwordResetToken ? "reset" : manualMode;

  const switchMode = (nextMode: AuthMode) => {
    setManualMode(nextMode);
    setError("");
    setSuccess("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (mode === "forgot") {
      if (!email.trim()) {
        setError("Enter your account email so we can send the recovery link.");
        return;
      }

      try {
        const response = await onRequestPasswordReset(email.trim());
        setSuccess(
          response?.message ??
            "If the email exists in our workspace, a password reset link has been sent.",
        );
      } catch (submitError) {
        setError(
          submitError instanceof Error
            ? submitError.message
            : "There was an error sending the recovery email.",
        );
      }
      return;
    }

    if (mode === "reset") {
      if (!passwordResetToken) {
        setError("This password reset link is missing or invalid.");
        return;
      }

      if (!password.trim()) {
        setError("Enter a new password.");
        return;
      }

      if (password.trim().length < 8) {
        setError("Your new password must have at least 8 characters.");
        return;
      }

      if (password !== confirmPassword) {
        setError("The passwords do not match.");
        return;
      }

      try {
        const response = await onConfirmPasswordReset({
          token: passwordResetToken,
          password,
        });
        onClearPasswordResetToken();
        setPassword("");
        setConfirmPassword("");
        setSuccess(
          response?.message ??
            "Password updated. You can sign in with the new password now.",
        );
        setManualMode("login");
      } catch (submitError) {
        setError(
          submitError instanceof Error
            ? submitError.message
            : "There was an error updating your password.",
        );
      }
      return;
    }

    if (mode === "register" && fullName.trim().length < 2) {
      setError("Enter your full name to create the workspace.");
      return;
    }

    if (!email.trim() || !password.trim()) {
      setError("Email and password are required.");
      return;
    }

    try {
      await onSubmit({
        mode,
        fullName: fullName.trim(),
        email: email.trim(),
        password,
      });
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "There was an error signing you in.",
      );
    }
  };

  const renderIntro = () => {
    if (mode === "forgot") {
      return (
        <>
          <p className="text-sm font-semibold text-white">Recover your password</p>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Enter the email tied to your workspace and we will send a secure reset link.
          </p>
        </>
      );
    }

    if (mode === "reset") {
      return (
        <>
          <p className="text-sm font-semibold text-white">Choose a new password</p>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            This link works once. After saving the new password, sign in with it normally.
          </p>
        </>
      );
    }

    return (
      <>
        <p className="text-sm font-semibold text-white">
          {mode === "login" ? "Welcome back" : "Create your workspace"}
        </p>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">
          {mode === "login"
            ? "Use your email and password to recover your private document library."
            : "Create a local account to unlock isolated documents and activity."}
        </p>
      </>
    );
  };

  const renderSubmitLabel = () => {
    if (loading) {
      if (mode === "forgot") {
        return "Sending email...";
      }

      if (mode === "reset") {
        return "Updating password...";
      }

      return "Securing workspace...";
    }

    if (mode === "register") {
      return "Create account";
    }

    if (mode === "forgot") {
      return "Send reset link";
    }

    if (mode === "reset") {
      return "Update password";
    }

    return "Sign in";
  };

  return (
    <div className="flex min-h-screen items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.16),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.15),transparent_28%),var(--app-bg)] px-5 py-10 text-[var(--app-foreground)]">
      <div className="grid w-full max-w-6xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-[32px] border border-white/10 bg-[var(--panel)]/80 p-8 shadow-[0_40px_120px_-60px_rgba(15,23,42,1)] backdrop-blur">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-[var(--muted-foreground)]">
            Study Copilot
          </p>
          <h1 className="mt-4 max-w-xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Private AI research workspaces for every user.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted-foreground)]">
            Each account now gets its own secure PDF library, grounded answers, and chat
            history isolated from every other user.
          </p>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {[
              {
                title: "Tenant-safe uploads",
                body: "Every PDF and index now lives inside the signed-in user's workspace.",
              },
              {
                title: "Grounded multi-PDF chat",
                body: "Ask across one or more active documents and jump straight to the source.",
              },
              {
                title: "Password recovery by email",
                body: "If you forget your password, the only recovery path is the secure email reset link.",
              },
            ].map((item) => (
              <article
                key={item.title}
                className="rounded-3xl border border-white/10 bg-white/[0.03] p-4"
              >
                <h2 className="text-sm font-semibold text-white">{item.title}</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">
                  {item.body}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-[32px] border border-white/10 bg-[var(--panel-strong)]/92 p-7 shadow-[0_40px_120px_-60px_rgba(15,23,42,1)] backdrop-blur">
          {mode !== "forgot" && mode !== "reset" ? (
            <div className="grid grid-cols-2 gap-2 rounded-2xl border border-white/10 bg-black/10 p-1">
              {[
                ["login", "Sign in"],
                ["register", "Create account"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => switchMode(value as AuthMode)}
                  className={`rounded-xl px-3 py-2 text-sm transition ${
                    mode === value
                      ? "bg-white text-[var(--panel-strong)] shadow-sm"
                      : "text-[var(--muted-foreground)] hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/10 px-4 py-3">
              <p className="text-sm font-medium text-white">
                {mode === "forgot" ? "Password recovery" : "Reset password"}
              </p>
              <button
                type="button"
                onClick={() => {
                  if (mode === "reset") {
                    onClearPasswordResetToken();
                  }
                  switchMode("login");
                }}
                className="text-sm text-[var(--muted-foreground)] transition hover:text-white"
              >
                Back to sign in
              </button>
            </div>
          )}

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div>{renderIntro()}</div>

            {mode === "register" && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-white">Full name</span>
                <input
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-[var(--muted-foreground)] focus:border-[var(--accent)]"
                  placeholder="Ada Lovelace"
                  autoComplete="name"
                  disabled={loading}
                />
              </label>
            )}

            {mode !== "reset" && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-white">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-[var(--muted-foreground)] focus:border-[var(--accent)]"
                  placeholder="you@example.com"
                  autoComplete="email"
                  disabled={loading}
                />
              </label>
            )}

            {mode !== "forgot" && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-white">
                  {mode === "reset" ? "New password" : "Password"}
                </span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-[var(--muted-foreground)] focus:border-[var(--accent)]"
                  placeholder="At least 8 characters"
                  autoComplete={
                    mode === "login"
                      ? "current-password"
                      : mode === "register" || mode === "reset"
                        ? "new-password"
                        : "off"
                  }
                  disabled={loading}
                />
              </label>
            )}

            {mode === "reset" && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-white">
                  Confirm new password
                </span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-[var(--muted-foreground)] focus:border-[var(--accent)]"
                  placeholder="Repeat the new password"
                  autoComplete="new-password"
                  disabled={loading}
                />
              </label>
            )}

            {mode === "login" && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => switchMode("forgot")}
                  className="text-sm text-[var(--muted-foreground)] transition hover:text-white"
                >
                  Forgot password?
                </button>
              </div>
            )}

            {error && (
              <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                {error}
              </div>
            )}

            {success && (
              <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="inline-flex h-12 w-full items-center justify-center rounded-[20px] bg-[var(--accent)] px-5 text-sm font-medium text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {renderSubmitLabel()}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
