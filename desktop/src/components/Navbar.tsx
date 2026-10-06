import React from "react";
import { Activity, TrendingUp, AlertTriangle, Calculator, Settings, Sun, Moon } from "lucide-react";
import { TabKey } from "../types";

interface NavbarProps {
  activeTab: TabKey;
  setActiveTab: (tab: TabKey) => void;
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
  isMonitoring: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  theme,
  setTheme,
  isMonitoring,
}) => {
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  return (
    <nav className="navbar" aria-label="Main Navigation">
      <div className="brand-section">
        <span>OhMyCrypto</span>
        <span className="brand-badge">v1.0.0</span>
        {isMonitoring ? (
          <span className="badge badge-success" style={{ marginLeft: 6 }}>LIVE</span>
        ) : (
          <span className="badge badge-neutral" style={{ marginLeft: 6 }}>IDLE</span>
        )}
      </div>

      <div className="nav-links">
        <button
          className={`nav-button ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <Activity size={14} />
          Overview
        </button>

        <button
          className={`nav-button ${activeTab === "opportunities" ? "active" : ""}`}
          onClick={() => setActiveTab("opportunities")}
        >
          <TrendingUp size={14} />
          Opportunities
        </button>

        <button
          className={`nav-button ${activeTab === "diagnostics" ? "active" : ""}`}
          onClick={() => setActiveTab("diagnostics")}
        >
          <AlertTriangle size={14} />
          Feed Diagnostics
        </button>

        <button
          className={`nav-button ${activeTab === "cost" ? "active" : ""}`}
          onClick={() => setActiveTab("cost")}
        >
          <Calculator size={14} />
          Cost Comparison
        </button>

        <button
          className={`nav-button ${activeTab === "settings" ? "active" : ""}`}
          onClick={() => setActiveTab("settings")}
        >
          <Settings size={14} />
          Settings
        </button>
      </div>

      <div className="nav-actions">
        <button
          className="btn btn-sm"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
          <span>{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
      </div>
    </nav>
  );
};
