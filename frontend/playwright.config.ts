import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const backendRoot = path.resolve(frontendRoot, "../backend");
const backendRuntimeRoot = path.join(backendRoot, "_runtime_probe");

function toSqliteUrl(filePath: string) {
  return `sqlite:///${filePath.replace(/\\/g, "/")}`;
}

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: {
    timeout: 20_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
    trace: "on-first-retry",
    viewport: { width: 1440, height: 900 },
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: backendRoot,
      url: "http://127.0.0.1:8000/",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        DATABASE_URL: toSqliteUrl(path.join(backendRuntimeRoot, "playwright-e2e.db")),
        STORAGE_ROOT: path.join(backendRuntimeRoot, "playwright-storage"),
        PDF_STORAGE_DIR: path.join(backendRuntimeRoot, "playwright-storage", "pdfs"),
        DATA_DIR: path.join(backendRuntimeRoot, "playwright-storage", "indexes"),
        RAG_MODE: "lite",
        GEMINI_API_KEY: "",
        PASSWORD_RESET_URL_TEMPLATE: "http://127.0.0.1:4173/?reset_password_token={token}",
        AUTH_SESSION_COOKIE_SECURE: "false",
        AUTH_SESSION_COOKIE_SAMESITE: "lax",
        CORS_ORIGINS: "http://127.0.0.1:4173",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      cwd: frontendRoot,
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        VITE_API_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});
