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


class TrayConfigDialog:
    """Tkinter-based GUI configuration dialog for GhostPush tray app."""

    def __init__(self, helper: Optional[TrayConfigHelper] = None, parent: Optional[Any] = None):
        if not HAS_TKINTER:
            raise RuntimeError("Tkinter is not installed or unavailable in this environment.")
        self.helper = helper or TrayConfigHelper()
        self.parent = parent
        self.window: Optional[tk.Toplevel] = None

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
        self.window.geometry("450x480")

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
        tk.Label(self.window, text="AI API Key (Optional):").pack(anchor="w", padx=10, pady=(10, 2))
        apikey_var = tk.StringVar()
        apikey_entry = tk.Entry(self.window, textvariable=apikey_var, show="*")
        apikey_entry.pack(fill="x", padx=10)

        key_status_label = tk.Label(self.window, text="", font=("Arial", 8, "italic"))
        key_status_label.pack(anchor="w", padx=10, pady=(2, 0))

        def update_key_status(*args):
            current_provider = provider_var.get().strip()
            existing_key = self.helper.get_api_key(current_provider)
            if existing_key:
                key_status_label.config(text=f"✓ API key configured for {current_provider}", fg="#10b981")
            else:
                key_status_label.config(text=f"No API key configured for {current_provider}", fg="#6b7280")

        provider_cb.bind("<<ComboboxSelected>>", update_key_status)
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

        # Save Action
        def on_save():
            selected_provider = provider_var.get().strip()
            typed_api_key = apikey_var.get().strip()

            updates = {
                "repository_path": repo_var.get().strip(),
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

