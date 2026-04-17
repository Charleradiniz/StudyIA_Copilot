import { expect, test, devices, type Browser } from "@playwright/test";

async function buildPdfBuffer(browser: Browser, title: string, body: string) {
  const context = await browser.newContext();

  try {
    const page = await context.newPage();
    await page.setContent(`
      <html>
        <body style="font-family: Arial, sans-serif; padding: 48px; line-height: 1.6;">
          <h1>${title}</h1>
          <p>${body}</p>
          <p>${body}</p>
          <p>${body}</p>
        </body>
      </html>
    `);

    return await page.pdf({
      format: "A4",
      printBackground: true,
      margin: {
        top: "18mm",
        right: "16mm",
        bottom: "18mm",
        left: "16mm",
      },
    });
  } finally {
    await context.close();
  }
}

test("keeps PDF library and chat history in sync between desktop and mobile with the real backend", async ({
  page,
  browser,
}) => {
  const uniqueSuffix = Date.now();
  const email = `charles+${uniqueSuffix}@example.com`;
  const password = "Password123!";
  const desktopPdfTitle = "Desktop Sync Document";
  const mobilePdfTitle = "Mobile Sync Document";
  const sharedBody =
    "StudyIA Copilot keeps PDF libraries and conversation history synchronized across authenticated devices while grounding answers in indexed document evidence.";
  const desktopPdfBytes = await buildPdfBuffer(
    browser,
    desktopPdfTitle,
    `${sharedBody} This desktop upload proves the source document remains available after sign-in from another device.`,
  );
  const mobilePdfBytes = await buildPdfBuffer(
    browser,
    mobilePdfTitle,
    `${sharedBody} This mobile upload should appear on the desktop client after the workspace refreshes.`,
  );

  page.on("dialog", (dialog) => dialog.accept());

  await page.goto("/");
  await expect(
    page.getByText("Private AI research workspaces for every user."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Create account" }).first().click();
  await page.getByLabel("Full name").fill("Charles Study");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.locator("form").getByRole("button", { name: "Create account" }).click();

  await expect(page.getByText("Research workspace")).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "Desktop Sync.pdf",
    mimeType: "application/pdf",
    buffer: desktopPdfBytes,
  });

  await expect(
    page.getByText(/Desktop Sync\.pdf" indexed with/i),
  ).toBeVisible();
  await expect(
    page.locator("main").getByRole("heading", { name: "Desktop Sync.pdf" }).first(),
  ).toBeVisible();

  await page.getByRole("textbox", { name: "Message" }).fill("What title appears in the PDF?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(
    page.getByText("Google AI Studio API key is not configured."),
  ).toBeVisible();
  await expect(page.getByText("Source 1")).toBeVisible();
  await expect(page.getByText(desktopPdfTitle, { exact: true }).last()).toBeVisible();

  await page.waitForTimeout(2500);

  const mobileContext = await browser.newContext({
    ...devices["Pixel 7"],
  });

  try {
    const mobilePage = await mobileContext.newPage();
    mobilePage.on("dialog", (dialog) => dialog.accept());

    await mobilePage.goto("/");
    await expect(
      mobilePage.getByText("Private AI research workspaces for every user."),
    ).toBeVisible();

    await mobilePage.getByLabel("Email").fill(email);
    await mobilePage.getByLabel("Password").fill(password);
    await mobilePage.locator("form").getByRole("button", { name: "Sign in" }).click();

    await expect(mobilePage.getByText("What title appears in the PDF?")).toBeVisible();

    await mobilePage.getByRole("button", { name: "Open workspace panel" }).click();
    await expect(mobilePage.getByText("Document library")).toBeVisible();
    await expect(mobilePage.getByText("Desktop Sync.pdf").first()).toBeVisible();

    await mobilePage.locator('input[type="file"]').setInputFiles({
      name: "Mobile Sync.pdf",
      mimeType: "application/pdf",
      buffer: mobilePdfBytes,
    });

    await expect(
      mobilePage.getByText(/Mobile Sync\.pdf" indexed with/i),
    ).toBeVisible();
    await mobilePage.waitForTimeout(1200);

    await page.bringToFront();
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));

    await expect(page.getByText("Mobile Sync.pdf").first()).toBeVisible();
  } finally {
    await mobileContext.close();
  }
});
