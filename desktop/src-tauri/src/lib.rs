// OhMyCrypto Tauri shell.
//
// Follows Section 4 of PROJECT_EXECUTION_GUIDE.md: the native shell owns the
// packaged Python sidecar's lifetime and exposes an allowlisted IPC surface.
// The webview never talks to the network or the filesystem directly; every
// engine interaction is a versioned JSON Lines request forwarded verbatim to
// the sidecar over stdin/stdout. Domain numbers remain decimal strings; no
// unauthenticated local listener exists.

use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{Emitter, Manager, RunEvent};

struct PendingMap(HashMap<u64, std::sync::mpsc::SyncSender<Result<Value, String>>>);

struct Sidecar {
    stdin: Mutex<Option<ChildStdin>>,
    child: Mutex<Option<Child>>,
    pending: Mutex<PendingMap>,
    next_id: AtomicU64,
}

impl Sidecar {
    fn spawn(app: &tauri::AppHandle) -> Result<Arc<Sidecar>, String> {
        let exe = std::env::current_exe()
            .map_err(|e| format!("cannot resolve app executable: {e}"))?;
        let parent_dir = exe
            .parent()
            .ok_or("executable has no parent directory")?;
        let mut sidecar_path = parent_dir.join("sidecar/ohmycrypto-sidecar");

        if !sidecar_path.exists() {
            let alt_x86_64 = parent_dir.join("sidecar/ohmycrypto-sidecar-x86_64");
            let alt_arm64 = parent_dir.join("sidecar/ohmycrypto-sidecar-arm64");
            if alt_x86_64.exists() {
                sidecar_path = alt_x86_64;
            } else if alt_arm64.exists() {
                sidecar_path = alt_arm64;
            } else {
                return Err(format!(
                    "sidecar binary not found at {}",
                    sidecar_path.display()
                ));
            }
        }

        let mut child = Command::new(&sidecar_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

        let stdin = child.stdin.take().ok_or("sidecar stdin unavailable")?;
        let stdout = child.stdout.take().ok_or("sidecar stdout unavailable")?;

        let state = Arc::new(Sidecar {
            stdin: Mutex::new(Some(stdin)),
            child: Mutex::new(Some(child)),
            pending: Mutex::new(PendingMap(HashMap::new())),
            next_id: AtomicU64::new(1),
        });

        // Reader thread: responses resolve pending requests; event lines are
        // forwarded to the webview as Tauri events.
        let reader_state = Arc::clone(&state);
        let reader_app = app.clone();
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                let Ok(line) = line else { break };
                if line.trim().is_empty() {
                    continue;
                }
                let Ok(msg) = serde_json::from_str::<Value>(&line) else {
                    continue;
                };
                if let Some(id) = msg.get("id").and_then(|v| v.as_u64()) {
                    let response = if msg.get("status").and_then(|v| v.as_str()) == Some("ok") {
                        Ok(msg.get("payload").cloned().unwrap_or(Value::Null))
                    } else {
                        Err(msg
                            .get("error")
                            .and_then(|v| v.as_str())
                            .unwrap_or("sidecar error")
                            .to_string())
                    };
                    if let Some(sender) = reader_state
                        .pending
                        .lock()
                        .ok()
                        .and_then(|mut p| p.0.remove(&id))
                    {
                        let _ = sender.send(response);
                    }
                } else if let Some(event) = msg.get("event").and_then(|v| v.as_str()) {
                    let payload = msg.get("payload").cloned().unwrap_or(Value::Null);
                    let _ = reader_app.emit(&format!("sidecar-{event}"), payload);
                }
            }
            // stdout closed: the sidecar terminated. Fail every pending request.
            if let Ok(mut pending) = reader_state.pending.lock() {
                for (_, sender) in pending.0.drain() {
                    let _ = sender.send(Err("sidecar terminated unexpectedly".into()));
                }
            }
            let _ = reader_app.emit("sidecar-exited", json!({}));
            if let Ok(mut child_slot) = reader_state.child.lock() {
                if let Some(mut c) = child_slot.take() {
                    let _ = c.wait();
                }
            }
        });

        Ok(state)
    }

    fn request(&self, action: &str, payload: Value) -> Result<Value, String> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let (tx, rx) = std::sync::mpsc::sync_channel::<Result<Value, String>>(1);
        self.pending
            .lock()
            .map_err(|_| "sidecar state poisoned".to_string())?
            .0
            .insert(id, tx);

        let request = json!({ "id": id, "action": action, "payload": payload });
        {
            let mut stdin_slot = self
                .stdin
                .lock()
                .map_err(|_| "sidecar state poisoned".to_string())?;
            match stdin_slot.as_mut() {
                Some(stdin) => {
                    let mut line = request.to_string().into_bytes();
                    line.push(b'\n');
                    if stdin.write_all(&line).is_err() || stdin.flush().is_err() {
                        stdin_slot.take();
                        self.pending.lock().ok().and_then(|mut p| p.0.remove(&id));
                        return Err("failed to write to sidecar (process exited?)".into());
                    }
                }
                None => {
                    self.pending.lock().ok().and_then(|mut p| p.0.remove(&id));
                    return Err("sidecar is not running".into());
                }
            }
        }

        match rx.recv_timeout(Duration::from_secs(120)) {
            Ok(result) => result,
            Err(_) => {
                self.pending.lock().ok().and_then(|mut p| p.0.remove(&id));
                Err(format!("sidecar request {action} timed out"))
            }
        }
    }

    fn shutdown(&self) {
        // Dropping stdin signals EOF: the sidecar exits cleanly (owned child).
        let _ = self.stdin.lock().map(|mut slot| slot.take());
        if let Ok(mut child_slot) = self.child.lock() {
            if let Some(mut child) = child_slot.take() {
                match child.try_wait() {
                    Ok(Some(_)) => {}
                    _ => {
                        std::thread::sleep(Duration::from_millis(300));
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        }
    }
}

#[tauri::command]
fn sidecar_request(
    state: tauri::State<'_, Arc<Sidecar>>,
    action: String,
    payload: Option<Value>,
) -> Result<Value, String> {
    state.request(&action, payload.unwrap_or(Value::Null))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let sidecar =
                Sidecar::spawn(app.handle()).map_err(|e| format!("sidecar startup failed: {e}"))?;
            app.manage(sidecar);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar_request])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                // Parent owns child lifetime: terminate the sidecar on exit.
                if let Some(sidecar) = app_handle.try_state::<Arc<Sidecar>>() {
                    sidecar.shutdown();
                }
            }
        });
}
