import React, { useState, useEffect } from "react";
import { Shield, Bell, HardDrive, FileArchive, Download, Check } from "lucide-react";
import { api } from "../ipc";

export const SettingsView: React.FC = () => {
  const [retentionDays, setRetentionDays] = useState(7);
  const [rawQuotaGb, setRawQuotaGb] = useState(2);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [quietMode, setQuietMode] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.getSettings().then((s) => {
      if (!mounted || !s) return;
      setRetentionDays(s.retention_days);
      setRawQuotaGb(s.raw_quota_gb);
      setAudioEnabled(s.audio_enabled);
      setSpeechEnabled(s.speech_enabled);
      setQuietMode(s.quiet_mode);
    }).catch((err) => {
      console.warn("Failed to load settings:", err);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const handleUpdate = (updates: Partial<{
    retention_days: number;
    raw_quota_gb: number;
    audio_enabled: boolean;
    speech_enabled: boolean;
    quiet_mode: boolean;
  }>) => {
    api.updateSettings(updates).catch((err) => {
      console.error("Failed to persist settings:", err);
    });
  };

  const handleExportBundle = async (mode: "complete" | "sanitized") => {
    try {
      const bundle = await api.exportReplayBundle({ mode });
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ohmycrypto-replay-${mode}-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setExportMessage(`Exported ${mode} replay bundle successfully!`);
      setTimeout(() => setExportMessage(null), 4000);
    } catch (err: any) {
      setExportMessage(`Export failed: ${err.message || String(err)}`);
      setTimeout(() => setExportMessage(null), 4000);
    }
  };

  return (
    <section aria-labelledby="settings-title">
      <div className="panel-header">
        <h2 id="settings-title" className="panel-title">System Settings, Storage & Privacy</h2>
      </div>

      <div className="grid-2">
        <article className="panel-card">
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <HardDrive size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
            Storage & Retention Quota
          </h3>
          <div className="form-group">
            <label className="form-label" htmlFor="settings-retention-days">Diagnostic Aggregate Retention (Days)</label>
            <input
              id="settings-retention-days"
              type="number"
              className="form-input"
              value={retentionDays}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10) || 7;
                setRetentionDays(val);
                handleUpdate({ retention_days: val });
              }}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="settings-raw-quota">Raw Rolling Capture Quota (GiB)</label>
            <input
              id="settings-raw-quota"
              type="number"
              className="form-input"
              value={rawQuotaGb}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10) || 2;
                setRawQuotaGb(val);
                handleUpdate({ raw_quota_gb: val });
              }}
            />
          </div>
          <p style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Rolling raw capture prunes unpinned files older than 48 hours when quota is approached.
          </p>
        </article>

        <article className="panel-card">
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <Bell size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
            Notification Delivery
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 6 }} htmlFor="settings-audio-enabled">
              <input
                id="settings-audio-enabled"
                type="checkbox"
                checked={audioEnabled && !quietMode}
                disabled={quietMode}
                aria-describedby="quiet-mode-hint"
                onChange={(e) => {
                  const val = e.target.checked;
                  setAudioEnabled(val);
                  handleUpdate({ audio_enabled: val });
                }}
              />
              Audible Chime (macOS afplay)
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 6 }} htmlFor="settings-speech-enabled">
              <input
                id="settings-speech-enabled"
                type="checkbox"
                checked={speechEnabled && !quietMode}
                disabled={quietMode}
                aria-describedby="quiet-mode-hint"
                onChange={(e) => {
                  const val = e.target.checked;
                  setSpeechEnabled(val);
                  handleUpdate({ speech_enabled: val });
                }}
              />
              Voice Announcement (macOS say)
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }} htmlFor="settings-quiet-mode">
              <input
                id="settings-quiet-mode"
                type="checkbox"
                checked={quietMode}
                onChange={(e) => {
                  const val = e.target.checked;
                  setQuietMode(val);
                  handleUpdate({ quiet_mode: val });
                }}
              />
              Quiet Mode (suppress all playback; records explicit suppression)
            </label>
            <span id="quiet-mode-hint" style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Quiet Mode suppresses playback and records an explicit suppression record instead of silencing silently.
            </span>
          </div>
        </article>
      </div>

      <div className="panel-card" style={{ marginTop: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          <FileArchive size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
          Privacy & Bundle Export
        </h3>
        <p style={{ fontSize: 12, marginBottom: 8 }}>
          All database state is stored locally on this machine. No telemetry or automated upload occurs.
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn btn-sm" onClick={() => handleExportBundle("complete")}>
            <Download size={12} /> Export Complete Replay Bundle
          </button>
          <button className="btn btn-sm" onClick={() => handleExportBundle("sanitized")}>
            <Download size={12} /> Export Sanitized Share Bundle (Omit Private Balances)
          </button>
          {exportMessage && (
            <span style={{ fontSize: 12, color: "var(--color-primary)", display: "flex", alignItems: "center", gap: 4 }}>
              <Check size={14} /> {exportMessage}
            </span>
          )}
        </div>
      </div>

      <div className="panel-card" style={{ marginTop: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          <Shield size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
          License & Notices
        </h3>
        <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
          OhMyCrypto is licensed under the GNU General Public License v3.0 (GPL-3.0-only).
          All binary distributions provide access to matching corresponding source code and notices.
        </p>
      </div>
    </section>
  );
};
