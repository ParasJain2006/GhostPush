"""Configuration UI helper and tkinter dialog for GhostPush system tray application.

Integrates with ConfigManager and AppSettings for validation and non-secret persistence.
Fails gracefully if tkinter is unavailable.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from backend.config.manager import ConfigManager
from backend.config.models import AppSettings

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


import threading


class TrayConfigHelper:
    """Headless controller for managing configuration loads and updates for the tray application."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()

    def get_current_settings(self) -> AppSettings:
        """Return the current validated AppSettings model."""
        return self.config_manager.load_config()

    def update_settings(self, updates: Dict[str, Any]) -> AppSettings:
        """Apply non-secret updates via ConfigManager, enforcing AppSettings validation."""
        return self.config_manager.update_config(updates)

    def get_api_key(self, provider: str) -> Optional[str]:
        """Resolve current API key for a provider via ConfigManager."""
        return self.config_manager.get_api_key(provider)

    def set_api_key(self, provider: str, api_key: str) -> None:
        """Save API key for a provider to %APPDATA%/GhostPush/.env via ConfigManager."""
        self.config_manager.set_api_key(provider, api_key)

    def has_api_key(self, provider: str) -> bool:
        """Return True only when a real (non-placeholder) credential is stored for provider."""
        return self.config_manager.has_api_key(provider)

    def remove_api_key(self, provider: str) -> None:
        """Remove the stored API key for a provider."""
        self.config_manager.remove_api_key(provider)

    def check_provider_health(self, provider: str, model: Optional[str] = None) -> "AIHealthStatus":
        """Perform a real provider health check and return status."""
        from backend.config.health import check_provider_health
        return check_provider_health(self.config_manager, provider, model)


class TrayConfigDialog:
    """Tkinter-based GUI configuration dialog for GhostPush tray app."""

    def __init__(self, helper: Optional[TrayConfigHelper] = None, parent: Optional[Any] = None):
        if not HAS_TKINTER:
            raise RuntimeError("Tkinter is not installed or unavailable in this environment.")
        self.helper = helper or TrayConfigHelper()
        self.parent = parent
        self.window: Optional[tk.Toplevel] = None
        self._is_testing: bool = False

    def open(self) -> None:
        """Open the modal configuration dialog window."""
        if not HAS_TKINTER:
            raise RuntimeError("Tkinter is unavailable.")

        settings = self.helper.get_current_settings()

        if self.parent:
            self.window = tk.Toplevel(self.parent)
        else:
            self.window = tk.Tk()

        self.window.title("GhostPush Configuration")
        self.window.geometry("450x600")

        # Repository Path
        tk.Label(self.window, text="Local Repository Path:").pack(anchor="w", padx=10, pady=(10, 2))
        repo_frame = tk.Frame(self.window)
        repo_frame.pack(fill="x", padx=10)
        repo_var = tk.StringVar(value=settings.repository_path)
        repo_entry = tk.Entry(repo_frame, textvariable=repo_var)
        repo_entry.pack(side="left", fill="x", expand=True)

        def browse_repo():
            chosen = filedialog.askdirectory(initialdir=repo_var.get())
            if chosen:
                repo_var.set(chosen)

        tk.Button(repo_frame, text="Browse...", command=browse_repo).pack(side="right", padx=(5, 0))

        # Remote Repository URL
        tk.Label(self.window, text="Remote Repository URL (Optional):").pack(anchor="w", padx=10, pady=(10, 2))
        remote_url_var = tk.StringVar(value=settings.remote_repo_url)
        remote_url_entry = tk.Entry(self.window, textvariable=remote_url_var)
        remote_url_entry.pack(fill="x", padx=10)

        # AI Provider
        tk.Label(self.window, text="AI Provider:").pack(anchor="w", padx=10, pady=(10, 2))
        provider_var = tk.StringVar(value=settings.ai_provider)
        provider_cb = ttk.Combobox(
            self.window,
            textvariable=provider_var,
            values=["gemini", "openai", "anthropic", "groq", "openrouter"],
        )
        provider_cb.pack(fill="x", padx=10)

        # AI API Key (Masked)
        tk.Label(self.window, text="AI API Key:").pack(anchor="w", padx=10, pady=(10, 2))
        apikey_frame = tk.Frame(self.window)
        apikey_frame.pack(fill="x", padx=10)
        apikey_var = tk.StringVar()
        apikey_entry = tk.Entry(apikey_frame, textvariable=apikey_var, show="*")
        apikey_entry.pack(side="left", fill="x", expand=True)

        # Show/Hide toggle
        show_key_var = tk.BooleanVar(value=False)

        def toggle_key_visibility():
            if show_key_var.get():
                apikey_entry.config(show="")
                show_hide_btn.config(text="Hide")
            else:
                apikey_entry.config(show="*")
                show_hide_btn.config(text="Show")

        show_hide_btn = tk.Button(apikey_frame, text="Show", width=5,
                                  command=lambda: (show_key_var.set(not show_key_var.get()), toggle_key_visibility()))
        show_hide_btn.pack(side="right", padx=(5, 0))

        key_status_label = tk.Label(self.window, text="", font=("Arial", 8, "italic"))
        key_status_label.pack(anchor="w", padx=10, pady=(2, 0))

        # API Key action buttons frame
        key_btn_frame = tk.Frame(self.window)
        key_btn_frame.pack(fill="x", padx=10, pady=(5, 0))

        save_key_btn = tk.Button(key_btn_frame, text="Save API Key", bg="#10b981", fg="white")
        remove_key_btn = tk.Button(key_btn_frame, text="Remove API Key", bg="#ef4444", fg="white")
        test_conn_btn = tk.Button(key_btn_frame, text="Test AI Connection", bg="#3b82f6", fg="white")

        save_key_btn.pack(side="left", padx=(0, 5))
        remove_key_btn.pack(side="left", padx=(0, 5))
        test_conn_btn.pack(side="left")

        def update_key_status(*args):
            if self._is_testing:
                return
            current_provider = provider_var.get().strip()
            if self.helper.has_api_key(current_provider):
                key_status_label.config(
                    text=f"● {current_provider.capitalize()} API key saved — connection not tested",
                    fg="#3b82f6"
                )
                save_key_btn.config(state="normal")
                remove_key_btn.config(state="normal")
                test_conn_btn.config(state="normal")
            else:
                key_status_label.config(
                    text=f"⚠ {current_provider.capitalize()} API key not configured",
                    fg="#f59e0b"
                )
                save_key_btn.config(state="normal")
                remove_key_btn.config(state="disabled")
                test_conn_btn.config(state="disabled")

        provider_cb.bind("<<ComboboxSelected>>", update_key_status)

        def _run_async_health_check(provider: str, model: Optional[str]):
            if self._is_testing:
                return
            self._is_testing = True
            save_key_btn.config(state="disabled")
            test_conn_btn.config(state="disabled")
            key_status_label.config(text=f"● Testing {provider.capitalize()} connection...", fg="#3b82f6")

            def _worker():
                health = self.helper.check_provider_health(provider, model)
                if self.window and self.window.winfo_exists():
                    self.window.after(0, lambda: _on_complete(health))

            def _on_complete(health_status):
                self._is_testing = False
                has_key = self.helper.has_api_key(provider)
                save_key_btn.config(state="normal")
                remove_key_btn.config(state="normal" if has_key else "disabled")
                test_conn_btn.config(state="normal" if has_key else "disabled")

                val = health_status.value if hasattr(health_status, "value") else str(health_status)

                if val == "CONNECTED":
                    key_status_label.config(
                        text=f"✓ {provider.capitalize()} connection successful", fg="#10b981"
                    )
                elif val == "NOT_CONFIGURED":
                    key_status_label.config(
                        text=f"⚠ {provider.capitalize()} API key not configured", fg="#f59e0b"
                    )
                elif val == "INVALID_API_KEY":
                    key_status_label.config(
                        text=f"✗ {provider.capitalize()} API key is invalid", fg="#ef4444"
                    )
                elif val == "NETWORK_ERROR":
                    key_status_label.config(
                        text=f"⚠ Unable to connect to {provider.capitalize()}", fg="#f59e0b"
                    )
                elif val == "TIMEOUT":
                    key_status_label.config(
                        text=f"⚠ {provider.capitalize()} connection timed out", fg="#f59e0b"
                    )
                else:
                    key_status_label.config(
                        text=f"⚠ Provider error for {provider.capitalize()}", fg="#f59e0b"
                    )

            threading.Thread(target=_worker, name="GhostPushUIHealthThread", daemon=True).start()

        def on_save_key():
            typed_key = apikey_var.get().strip()
            current_provider = provider_var.get().strip()
            if not typed_key:
                messagebox.showwarning("Warning", "Please enter an API key.")
                return
            try:
                self.helper.set_api_key(current_provider, typed_key)
                apikey_var.set("")
                key_status_label.config(text="✓ API key saved. Testing connection...", fg="#3b82f6")
                _run_async_health_check(current_provider, model_var.get().strip() or None)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save API key:\n{e}")

        def on_remove_key():
            current_provider = provider_var.get().strip()
            self.helper.remove_api_key(current_provider)
            apikey_var.set("")
            update_key_status()
            messagebox.showinfo("Removed", f"API key removed for {current_provider.capitalize()}.")

        def on_test_connection():
            current_provider = provider_var.get().strip()
            _run_async_health_check(current_provider, model_var.get().strip() or None)

        save_key_btn.config(command=on_save_key)
        remove_key_btn.config(command=on_remove_key)
        test_conn_btn.config(command=on_test_connection)

        update_key_status()

        # AI Model
        tk.Label(self.window, text="AI Model (Optional):").pack(anchor="w", padx=10, pady=(10, 2))
        model_var = tk.StringVar(value=settings.ai_model)
        tk.Entry(self.window, textvariable=model_var).pack(fill="x", padx=10)

        # Log Level
        tk.Label(self.window, text="Log Level:").pack(anchor="w", padx=10, pady=(10, 2))
        log_var = tk.StringVar(value=settings.log_level)
        log_cb = ttk.Combobox(
            self.window,
            textvariable=log_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        )
        log_cb.pack(fill="x", padx=10)

        # Auto Push & Auto Commit Checkboxes
        auto_commit_var = tk.BooleanVar(value=settings.auto_commit)
        tk.Checkbutton(self.window, text="Auto-commit new solutions", variable=auto_commit_var).pack(anchor="w", padx=10, pady=(10, 0))

        auto_push_var = tk.BooleanVar(value=settings.auto_push)
        tk.Checkbutton(self.window, text="Auto-push commits to remote", variable=auto_push_var).pack(anchor="w", padx=10, pady=(2, 10))

        # Save Settings Action
        def on_save():
            selected_provider = provider_var.get().strip()
            typed_api_key = apikey_var.get().strip()

            updates = {
                "repository_path": repo_var.get().strip(),
                "remote_repo_url": remote_url_var.get().strip(),
                "ai_provider": selected_provider,
                "ai_model": model_var.get().strip(),
                "log_level": log_var.get().strip(),
                "auto_commit": auto_commit_var.get(),
                "auto_push": auto_push_var.get(),
            }
            try:
                # Save API key first if non-empty
                if typed_api_key:
                    self.helper.set_api_key(selected_provider, typed_api_key)
                    apikey_var.set("")

                # Save non-secret AppSettings to config.json
                self.helper.update_settings(updates)
                messagebox.showinfo("Success", "Configuration saved successfully!")
                if self.window:
                    self.window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration:\n{e}")

        tk.Button(self.window, text="Save Settings", command=on_save, bg="#6366f1", fg="white").pack(pady=15)

        if not self.parent:
            self.window.mainloop()
