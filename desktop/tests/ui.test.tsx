import { describe, it, expect, beforeEach, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "../src/App";

describe("OhMyCrypto Desktop UI", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it("renders navigation bar with all 5 destinations and semantic tags", async () => {
    const { container } = render(<App />);

    // Semantic navigation check
    const nav = container.querySelector("nav");
    expect(nav).toBeTruthy();

    // Semantic main content check
    const main = container.querySelector("main");
    expect(main).toBeTruthy();

    // Verify all 5 destination buttons
    expect(screen.getByText("Overview")).toBeTruthy();
    expect(screen.getByText("Opportunities")).toBeTruthy();
    expect(screen.getByText("Feed Diagnostics")).toBeTruthy();
    expect(screen.getByText("Cost Comparison")).toBeTruthy();
    expect(screen.getByText("Settings")).toBeTruthy();

    // Verify labeled offline demo banner is shown
    expect(screen.getByText(/OFFLINE DEMO \/ FIXTURE MODE/i)).toBeTruthy();
  });

  it("switches to Opportunities view upon click", async () => {
    render(<App />);
    const oppsBtn = screen.getByText("Opportunities");
    fireEvent.click(oppsBtn);

    await waitFor(() => {
      expect(screen.getByText(/Opportunity Verification & Evidence Inspection/i)).toBeTruthy();
    });
  });

  it("switches to Cost Comparison view and toggles buy/sell", async () => {
    render(<App />);
    const costBtn = screen.getByText("Cost Comparison");
    fireEvent.click(costBtn);

    await waitFor(() => {
      expect(screen.getByText(/Personal Execution Cost Comparison & Scenarios/i)).toBeTruthy();
    });

    // Test Sell toggle
    const sellBtn = screen.getByText(/Sell \(Base Quantity\)/i);
    fireEvent.click(sellBtn);

    await waitFor(() => {
      expect(screen.getByText(/Base Amount to Sell/i)).toBeTruthy();
    });
  });

  it("toggles dark and light mode correctly", async () => {
    const { container } = render(<App />);
    const appContainer = container.querySelector(".app-container");
    expect(appContainer).toBeTruthy();

    const themeBtn = screen.getByRole("button", { name: /switch to/i });
    const initialTheme = appContainer?.getAttribute("data-theme");

    fireEvent.click(themeBtn);
    const nextTheme = appContainer?.getAttribute("data-theme");
    expect(nextTheme).not.toBe(initialTheme);
  });

  it("switches to Feed Diagnostics view and displays incident metrics", async () => {
    render(<App />);
    const diagBtn = screen.getByText("Feed Diagnostics");
    fireEvent.click(diagBtn);

    await waitFor(() => {
      expect(screen.getByText(/Market Data Quality Diagnostics & Incidents/i)).toBeTruthy();
      expect(screen.getByText(/Latency Distributions/i)).toBeTruthy();
      expect(screen.getByText(/Recorded Feed Incidents/i)).toBeTruthy();
    });
  });

  it("switches to Settings view and displays dials and storage status", async () => {
    render(<App />);
    const settingsBtn = screen.getByText("Settings");
    fireEvent.click(settingsBtn);

    await waitFor(() => {
      expect(screen.getByText(/System Settings, Storage & Privacy/i)).toBeTruthy();
      expect(screen.getByText(/Storage & Retention Quota/i)).toBeTruthy();
      expect(screen.getByText(/Notification Delivery/i)).toBeTruthy();
      expect(screen.getByText(/Privacy & Bundle Export/i)).toBeTruthy();
    });
  });

  it("opens and closes the Deterministic Replay modal", async () => {
    render(<App />);
    const oppsBtn = screen.getByText("Opportunities");
    fireEvent.click(oppsBtn);

    await waitFor(() => {
      expect(screen.getByText(/Opportunity Verification & Evidence Inspection/i)).toBeTruthy();
    });

    await waitFor(() => {
      expect(screen.getByText("BTC/USDT")).toBeTruthy();
    });

    const replayBtn = screen.getAllByRole("button", { name: /Inspect \/ Replay/i })[0];
    fireEvent.click(replayBtn);

    await waitFor(() => {
      expect(screen.getByText(/Deterministic Event Replay & Inspection/i)).toBeTruthy();
      expect(screen.getByText(/Input Hash \(SHA-256\)/i)).toBeTruthy();
    });

    const closeBtn = screen.getByRole("button", { name: /Close dialog/i });
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByText(/Deterministic Event Replay & Inspection/i)).toBeNull();
    });
  });
});
