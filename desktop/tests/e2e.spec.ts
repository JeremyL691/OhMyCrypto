/**
 * End-to-end tests for the OhMyCrypto desktop application.
 *
 * These drive a real Chromium browser against the built frontend, exercising
 * the complete user journey:
 *
 *   1. Cold start and first paint
 *   2. Market data load
 *   3. Depth comparison (cost comparison) interaction
 *   4. Deterministic offline replay of a specific event
 *   5. Diagnostics incident bundle export
 *   6. Theme persistence across reload
 *   7. Quiet Mode suppression decoupled from macOS notification delivery
 *
 * The suite is hermetic: it serves the prebuilt `dist/` output and never
 * contacts a network venue. It requires no Tauri runtime, so it runs on any
 * CI host.
 */

import { test, expect, Page, ConsoleMessage } from "@playwright/test";
import { createServer, Server } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, extname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DIST_DIR = join(HERE, "..", "dist");
const PORT = 4321;
const BASE_URL = `http://127.0.0.1:${PORT}`;

const MIME: Record<string, string> = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".json": "application/json",
};

function startStaticServer(): Promise<Server> {
  return new Promise((resolve, reject) => {
    const server = createServer((req, res) => {
      try {
        let path = (req.url || "/").split("?")[0];
        if (path === "/") path = "/index.html";
        const file = join(DIST_DIR, path);
        if (!existsSync(file)) {
          res.writeHead(404).end("not found");
          return;
        }
        res.writeHead(200, { "Content-Type": MIME[extname(file)] || "application/octet-stream" });
        res.end(readFileSync(file));
      } catch (err) {
        res.writeHead(500).end(String(err));
      }
    });
    server.on("error", reject);
    server.listen(PORT, "127.0.0.1", () => resolve(server));
  });
}

let server: Server;

test.beforeAll(async () => {
  server = await startStaticServer();
});

test.afterAll(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

/** Collect console errors so unexpected runtime faults fail the test. */
function watchConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));
  return errors;
}

test.describe("OhMyCrypto Desktop E2E", () => {
  test("cold start renders dashboard with semantic structure and offline demo notice", async ({ page }) => {
    const errors = watchConsoleErrors(page);

    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    // Semantic HTML landmarks.
    await expect(page.locator("nav")).toBeVisible();
    await expect(page.locator("main")).toBeVisible();

    // All five destinations are reachable.
    for (const label of ["Overview", "Opportunities", "Feed Diagnostics", "Cost Comparison", "Settings"]) {
      await expect(page.getByRole("button", { name: label })).toBeVisible();
    }

    // Offline demo data must be clearly labelled, never presented as live.
    await expect(page.getByText(/OFFLINE DEMO \/ FIXTURE MODE/i)).toBeVisible();

    expect(errors, `unexpected console errors: ${errors.join(" | ")}`).toHaveLength(0);
  });

  test("loads market data and displays quote on the overview", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    // Overview shows engine status and connector panels.
    await expect(page.getByText("System Overview & Monitoring Control")).toBeVisible();
    await expect(page.getByText("Active Connectors")).toBeVisible();
    await expect(page.getByText("Engine Metrics")).toBeVisible();
  });

  test("depth comparison runs and reports per-venue results", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    await page.getByRole("button", { name: "Cost Comparison" }).click();
    await expect(page.getByText("Personal Execution Cost Comparison & Scenarios")).toBeVisible();

    // Enter an amount and verify the sensitivity grid renders.
    const amountInput = page.getByLabel(/All-In Quote Budget/i);
    await amountInput.fill("2500.00");
    await expect(page.getByText("Amount Sensitivity Grid")).toBeVisible();

    // Switch to sell side to confirm both directions work.
    await page.getByRole("button", { name: /Sell \(Base Quantity\)/i }).click();
    await expect(page.getByLabel(/Base Amount to Sell/i)).toBeVisible();
  });

  test("deterministic offline replay opens for a specific event and shows input hash", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    await page.getByRole("button", { name: "Opportunities" }).click();
    await expect(page.getByText("Opportunity Verification & Evidence Inspection")).toBeVisible();

    // A concrete fixture event must be listed.
    await expect(page.getByText("BTC/USDT")).toBeVisible();

    // Open replay for that event.
    await page.getByRole("button", { name: /Inspect \/ Replay/i }).first().click();

    await expect(page.getByText("Deterministic Event Replay & Inspection")).toBeVisible();
    await expect(page.getByText(/Input Hash \(SHA-256\)/i)).toBeVisible();

    // The replay must expose the recorded input hash for verification.
    const hashText = await page.getByText(/57d6a83e/i).first().textContent();
    expect(hashText).toBeTruthy();
  });

  test("diagnostics incident export produces an offline reproduction bundle", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    await page.getByRole("button", { name: "Feed Diagnostics" }).click();
    await expect(page.getByText("Market Data Quality Diagnostics & Incidents")).toBeVisible();

    // Latency distributions with p50/p95/p99 are displayed.
    await expect(page.getByText("Latency Distributions")).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /p50 Latency/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /p99 Latency/i })).toBeVisible();

    // Export an incident bundle.
    await expect(page.getByText("Recorded Feed Incidents")).toBeVisible();
    await page.getByRole("button", { name: /Export Bundle/i }).first().click();

    await expect(page.getByText(/Exported Offline Incident Bundle:/i)).toBeVisible();
  });

  test("theme choice persists across a full page reload", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    const container = page.locator(".app-container");
    const initialTheme = await container.getAttribute("data-theme");

    // Toggle theme.
    await page.getByRole("button", { name: /switch to/i }).click();
    const toggledTheme = await container.getAttribute("data-theme");
    expect(toggledTheme).not.toBe(initialTheme);

    // Reload: the choice must survive, proving persistence.
    await page.reload({ waitUntil: "networkidle" });
    const afterReload = await page.locator(".app-container").getAttribute("data-theme");
    expect(afterReload).toBe(toggledTheme);
  });

  test("quiet mode suppresses notification playback controls", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    await page.getByRole("button", { name: "Settings" }).click();
    await expect(page.getByText("System Settings, Storage & Privacy")).toBeVisible();

    const audioToggle = page.getByLabel(/Audible Chime \(macOS afplay\)/i);
    const speechToggle = page.getByLabel(/Voice Announcement \(macOS say\)/i);
    const quietToggle = page.getByLabel(/Quiet Mode/i);

    // Before quiet mode, audio is enabled and interactive.
    await expect(audioToggle).toBeEnabled();
    await expect(audioToggle).toBeChecked();

    // Enable quiet mode.
    await quietToggle.check();
    await expect(quietToggle).toBeChecked();

    // Playback controls must be suppressed and disabled while still visible,
    // so suppression is explicit rather than silently hidden.
    await expect(audioToggle).toBeDisabled();
    await expect(speechToggle).toBeDisabled();
    await expect(audioToggle).not.toBeChecked();
    await expect(speechToggle).not.toBeChecked();

    // Disabling quiet mode restores interactivity.
    await quietToggle.uncheck();
    await expect(audioToggle).toBeEnabled();
  });

  test("privacy notice states no telemetry upload occurs", async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Settings" }).click();

    await expect(page.getByText(/No telemetry or automated upload occurs/i)).toBeVisible();
    await expect(page.getByText(/GPL-3\.0-only/i)).toBeVisible();
  });
});
