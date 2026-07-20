"""Janela de confirmação e acompanhamento de atualização."""

from __future__ import annotations

import os
import queue
import threading
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from src.updater import ReleaseInfo, UpdateError, download_release


class UpdateDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        release: ReleaseInfo,
        current_version: str,
        ignored: bool,
        on_ignore: Callable[[str, bool], None],
        on_install: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._release = release
        self._on_ignore = on_ignore
        self._on_install = on_install
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._downloading = False
        self._downloaded_path = ""

        self.title("Atualização disponível")
        self.geometry("580x480")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=20)

        ctk.CTkLabel(
            container,
            text=f"Nova versão {release.version}",
            font=ctk.CTkFont(family="Consolas", size=21, weight="bold"),
            text_color="#50fa7b",
        ).pack(anchor="w")
        ctk.CTkLabel(
            container,
            text=f"Versão instalada: {current_version}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#6272a4",
        ).pack(anchor="w", pady=(2, 14))

        ctk.CTkLabel(
            container,
            text="NOTAS DA VERSÃO",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color="#8be9fd",
        ).pack(anchor="w", pady=(0, 5))

        notes = ctk.CTkTextbox(
            container,
            height=230,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#1e1e2e",
            text_color="#f8f8f2",
            border_width=1,
            border_color="#44475a",
            wrap="word",
        )
        notes.pack(fill="both", expand=True)
        notes.insert("0.0", release.notes)
        notes.configure(state="disabled")

        self._ignore_var = ctk.BooleanVar(value=ignored)
        self._ignore_checkbox = ctk.CTkCheckBox(
            container,
            text="Não avisar novamente sobre esta versão",
            variable=self._ignore_var,
            command=self._toggle_ignore,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#f8f8f2",
            fg_color="#bd93f9",
            hover_color="#9f78d9",
        )
        self._ignore_checkbox.pack(anchor="w", pady=(12, 8))

        self._progress = ctk.CTkProgressBar(
            container,
            height=10,
            progress_color="#50fa7b",
            fg_color="#44475a",
        )
        self._progress.set(0)

        self._status_label = ctk.CTkLabel(
            container,
            text="",
            height=20,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#8be9fd",
        )

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", pady=(6, 0))
        self._later_button = ctk.CTkButton(
            actions,
            text="AGORA NÃO",
            width=126,
            height=34,
            corner_radius=6,
            command=self._close,
            fg_color="transparent",
            border_width=1,
            border_color="#6272a4",
            text_color="#f8f8f2",
            hover_color="#313147",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self._later_button.pack(side="left")
        self._install_button = ctk.CTkButton(
            actions,
            text="BAIXAR E INSTALAR",
            width=174,
            height=34,
            corner_radius=6,
            command=self._start_download,
            fg_color="#50fa7b",
            text_color="#1e1e2e",
            hover_color="#3de05a",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        self._install_button.pack(side="right")

        self.after(100, self._center_on_parent)
        self.grab_set()

    def _center_on_parent(self) -> None:
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _toggle_ignore(self) -> None:
        self._on_ignore(self._release.version, bool(self._ignore_var.get()))

    def _start_download(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        self._install_button.configure(state="disabled", text="BAIXANDO...")
        self._later_button.configure(state="disabled")
        self._ignore_checkbox.configure(state="disabled")
        self._progress.pack(fill="x", pady=(4, 2), before=self._ignore_checkbox)
        self._status_label.configure(text="Preparando download seguro...")
        self._status_label.pack(fill="x", before=self._ignore_checkbox)

        threading.Thread(target=self._download_worker, daemon=True).start()
        self.after(100, self._poll_events)

    def _download_worker(self) -> None:
        try:
            path = download_release(
                self._release,
                progress=lambda value: self._events.put(("progress", value)),
            )
            self._events.put(("complete", path))
        except Exception as exc:
            self._events.put(("error", exc))

    def _poll_events(self) -> None:
        try:
            while True:
                event, value = self._events.get_nowait()
                if event == "progress":
                    progress = float(value)
                    self._progress.set(progress)
                    self._status_label.configure(text=f"Baixando... {round(progress * 100)}%")
                elif event == "complete":
                    self._downloaded_path = str(value)
                    self._progress.set(1)
                    self._status_label.configure(text="Download verificado. Instalando...")
                    self.after(250, self._install)
                    return
                elif event == "error":
                    self._show_error(value)
                    return
        except queue.Empty:
            pass
        if self._downloading:
            self.after(100, self._poll_events)

    def _install(self) -> None:
        try:
            self._on_install(self._downloaded_path)
        except Exception as exc:
            self._show_error(exc)

    def _show_error(self, error: object) -> None:
        self._downloading = False
        if self._downloaded_path:
            try:
                os.unlink(self._downloaded_path)
            except OSError:
                pass
            self._downloaded_path = ""
        self._install_button.configure(state="normal", text="TENTAR NOVAMENTE")
        self._later_button.configure(state="normal")
        self._ignore_checkbox.configure(state="normal")
        self._status_label.configure(text="Não foi possível concluir a atualização.", text_color="#ff5555")
        message = str(error) if isinstance(error, (UpdateError, OSError)) else "Erro inesperado ao atualizar."
        messagebox.showerror("Falha na atualização", message, parent=self)

    def _close(self) -> None:
        if self._downloading:
            return
        if self._downloaded_path:
            try:
                os.unlink(self._downloaded_path)
            except OSError:
                pass
        self.grab_release()
        self.destroy()
