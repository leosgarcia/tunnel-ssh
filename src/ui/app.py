import customtkinter as ctk
import datetime
import os
import sys
from tkinter import filedialog, messagebox
from typing import Dict, Any, Optional

from src.tunnel import TunnelManager, load_config, save_config
from src.ui.port_manager import PortManagerWindow

# Configura o tema do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

GROUP_COLORS = {
    "CoPilot": "#bd93f9",
    "Wazuh":   "#50fa7b",
    "Graylog": "#8be9fd",
    "Grafana": "#ffb86c",
    "MinIO":   "#ff79c6",
}

def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)

class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("wltech · SSH Tunnel Manager")
        self.geometry("700x550")
        self.resizable(False, False)
        
        try:
            icon_path = resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self._config = load_config()
        self._status = "disconnected"
        self._uptime_job: Optional[str] = None
        
        self.manager = TunnelManager(
            on_status_change=self._on_status_change,
            on_log=self._on_log,
            get_config=lambda: self._config,
        )

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color="#2a2a3e", corner_radius=0)
        hdr.pack(fill="x")
        
        ctk.CTkLabel(hdr, text="⚡ wltech", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="#bd93f9").pack(side="left", padx=20, pady=15)
        ctk.CTkLabel(hdr, text="SSH Tunnel Manager", font=ctk.CTkFont(family="Consolas", size=12), text_color="#6272a4").pack(side="left")
        
        ctk.CTkButton(hdr, text="⚙ Servidor", command=self._open_server_config, fg_color="transparent", border_width=1, text_color="#ffb86c", hover_color="#313147").pack(side="right", padx=10)
        ctk.CTkButton(hdr, text="⚙ Portas", command=self._open_port_manager, fg_color="transparent", border_width=1, text_color="#8be9fd", hover_color="#313147").pack(side="right", padx=10)

        # Status Panel
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.pack(fill="x", padx=20, pady=(20, 10))
        
        self._dot = ctk.CTkLabel(sf, text="●", font=ctk.CTkFont(family="Consolas", size=36), text_color="#ff5555")
        self._dot.pack(side="left")
        
        ic = ctk.CTkFrame(sf, fg_color="transparent")
        ic.pack(side="left", padx=15)
        
        self._status_label = ctk.CTkLabel(ic, text="Desconectado", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="#ff5555", anchor="w")
        self._status_label.pack(anchor="w")
        
        self._sub_label = ctk.CTkLabel(ic, text=self._config.get("ssh_host", ""), font=ctk.CTkFont(family="Consolas", size=12), text_color="#6272a4", anchor="w")
        self._sub_label.pack(anchor="w")
        
        self._uptime_label = ctk.CTkLabel(ic, text="", font=ctk.CTkFont(family="Consolas", size=12), text_color="#6272a4", anchor="w")
        self._uptime_label.pack(anchor="w")

        # Botão Conectar
        self._btn = ctk.CTkButton(self, text="▶ CONECTAR", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                  fg_color="#50fa7b", text_color="#1e1e2e", hover_color="#3de05a", command=self._toggle)
        self._btn.pack(fill="x", padx=20, pady=10)

        # Portas Ativas
        ports_hdr = ctk.CTkFrame(self, fg_color="transparent")
        ports_hdr.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(ports_hdr, text="PORTAS ATIVAS", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#6272a4").pack(side="left")

        self._ports_container = ctk.CTkFrame(self, fg_color="transparent")
        self._ports_container.pack(fill="x", padx=20, pady=(5, 10))
        self._port_dots: Dict[str, ctk.CTkLabel] = {}
        self._rebuild_ports_ui()

        # Log Console
        log_hdr = ctk.CTkFrame(self, fg_color="transparent")
        log_hdr.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(log_hdr, text="LOG", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#6272a4").pack(side="left")
        ctk.CTkButton(log_hdr, text="Limpar", font=ctk.CTkFont(size=10), command=self._clear_log, fg_color="transparent", text_color="#6272a4", width=50, height=20, hover_color="#313147").pack(side="right")
        
        self._log_box = ctk.CTkTextbox(self, height=120, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#2a2a3e", text_color="#f8f8f2")
        self._log_box.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        self._log_box.configure(state="disabled")

        # Configura tags no textbox subjacente
        self._log_box.tag_config("OK", foreground="#50fa7b")
        self._log_box.tag_config("ERROR", foreground="#ff5555")
        self._log_box.tag_config("WARN", foreground="#f1fa8c")
        self._log_box.tag_config("SSH", foreground="#6272a4")
        self._log_box.tag_config("INFO", foreground="#f8f8f2")

    def _rebuild_ports_ui(self) -> None:
        for w in self._ports_container.winfo_children():
            w.destroy()
        self._port_dots.clear()

        enabled_ports = [p for p in self._config.get("ports", []) if p.get("enabled", True)]
        
        groups: Dict[str, list] = {}
        for p in enabled_ports:
            g = p.get("group", "Outros")
            groups.setdefault(g, []).append(p)

        col = 0
        for g_name, ports in groups.items():
            color = GROUP_COLORS.get(g_name, "#f8f8f2")
            gf = ctk.CTkFrame(self._ports_container, fg_color="#2a2a3e", corner_radius=8)
            gf.grid(row=0, column=col, sticky="nw", padx=(0, 10), pady=2)

            ctk.CTkLabel(gf, text=g_name, font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color=color).pack(anchor="w", padx=10, pady=(5, 0))

            for p in ports:
                pf = ctk.CTkFrame(gf, fg_color="transparent")
                pf.pack(anchor="w", padx=10, pady=2)
                
                d = ctk.CTkLabel(pf, text="●", font=ctk.CTkFont(family="Consolas", size=12), text_color="#6272a4")
                d.pack(side="left")
                
                ctk.CTkLabel(pf, text=f":{p['local']} ", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#8be9fd").pack(side="left")
                ctk.CTkLabel(pf, text=p.get("label", ""), font=ctk.CTkFont(family="Consolas", size=10), text_color="#6272a4").pack(side="left")
                
                self._port_dots[p["local"]] = d
            col += 1

    def _open_port_manager(self) -> None:
        if self._status not in ("disconnected", "error"):
            # fallback for standard tk messagebox
            messagebox.showwarning("Túnel ativo", "Desconecte o túnel antes de editar as portas.")
            return
        PortManagerWindow(self, self._config, self._on_ports_saved)

    def _on_ports_saved(self, new_config: Dict[str, Any]) -> None:
        self._config = new_config
        save_config(self._config)
        self._rebuild_ports_ui()
        self._append_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Configuração de portas salva.", "INFO")

    def _open_server_config(self) -> None:
        if self._status not in ("disconnected", "error"):
            messagebox.showwarning("Túnel ativo", "Desconecte o túnel antes de editar as configurações do servidor.")
            return

        win = ctk.CTkToplevel(self)
        win.title("Servidor & Chave")
        win.geometry("500x320")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="⚙ Servidor SSH", font=ctk.CTkFont(family="Consolas", size=16, weight="bold"), text_color="#bd93f9").pack(pady=15)
        
        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)
        
        # Campo Host
        ctk.CTkLabel(body, text="Host (ex: usuario@192.168.0.1):", font=ctk.CTkFont(size=12), text_color="#6272a4").pack(anchor="w")
        host_var = ctk.StringVar(value=self._config.get("ssh_host", ""))
        host_entry = ctk.CTkEntry(body, textvariable=host_var, font=ctk.CTkFont(family="Consolas", size=12))
        host_entry.pack(fill="x", pady=(0, 15))

        # Campo Chave
        ctk.CTkLabel(body, text="Caminho da chave privada (vazio para ssh-agent):", font=ctk.CTkFont(size=12), text_color="#6272a4").pack(anchor="w")
        key_var = ctk.StringVar(value=self._config.get("ssh_key", ""))
        key_entry = ctk.CTkEntry(body, textvariable=key_var, font=ctk.CTkFont(family="Consolas", size=12))
        key_entry.pack(fill="x", pady=(0, 5))
        
        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Selecionar chave SSH privada",
                initialdir=os.path.expanduser("~/.ssh"),
                filetypes=[("Chaves SSH", "id_* *.pem *.key"), ("Todos", "*.*")]
            )
            if path:
                key_var.set(path)
                
        ctk.CTkButton(body, text="📂 Procurar...", command=_browse, fg_color="transparent", border_width=1, text_color="#8be9fd", hover_color="#313147").pack(anchor="w")
        
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=20)
        
        def _save() -> None:
            self._config["ssh_host"] = host_var.get().strip()
            self._config["ssh_key"] = key_var.get().strip()
            save_config(self._config)
            self._sub_label.configure(text=self._config.get("ssh_host", ""))
            self._append_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Configurações de servidor salvas.", "INFO")
            win.destroy()
            
        ctk.CTkButton(btn_row, text="✔ Salvar", command=_save, fg_color="#50fa7b", text_color="#1e1e2e", hover_color="#3de05a").pack(side="right")
        ctk.CTkButton(btn_row, text="Cancelar", command=win.destroy, fg_color="transparent", border_width=1, text_color="#f8f8f2", hover_color="#313147").pack(side="right", padx=(0, 10))

    def _toggle(self) -> None:
        if self._status in ("disconnected", "error"):
            self.manager.start()
        else:
            self.manager.stop()

    def _on_close(self) -> None:
        self.manager.stop()
        self.destroy()

    def _on_status_change(self, status: str, extra: str = "") -> None:
        self.after(0, self._apply_status, status, extra)

    def _on_log(self, msg: str, level: str = "INFO") -> None:
        self.after(0, self._append_log, msg, level)

    def _apply_status(self, status: str, extra: str = "") -> None:
        self._status = status
        # (cor_status, texto_status, texto_botao, bool_desligado, cor_botao, hover_botao)
        cfg = {
            "connected":    ("#50fa7b", "● Conectado",     "▪ DESCONECTAR",  False, "#ff5555", "#cc4444"),
            "connecting":   ("#f1fa8c", "◌ Conectando...", "▪ CANCELAR",     False, "#ff5555", "#cc4444"),
            "reconnecting": ("#f1fa8c", "↻ Reconectando...","▪ CANCELAR",     False, "#ff5555", "#cc4444"),
            "disconnected": ("#ff5555", "● Desconectado",  "▶ CONECTAR",     True,  "#50fa7b", "#3de05a"),
            "error":        ("#ff5555", "✕ Erro",          "▶ TENTAR NOVAMENTE", True, "#50fa7b", "#3de05a"),
        }.get(status, ("#6272a4", status, "▶ CONECTAR", True, "#50fa7b", "#3de05a"))

        status_color, text, btn_text, is_off, btn_color, btn_hover = cfg
        
        self._dot.configure(text_color=status_color)
        self._status_label.configure(text=text, text_color=status_color)
        self._sub_label.configure(text=extra if extra else self._config.get("ssh_host", ""))
        
        self._btn.configure(
            text=btn_text,
            fg_color=btn_color,
            hover_color=btn_hover
        )

        dot_color = "#50fa7b" if status == "connected" else "#6272a4"
        for d in self._port_dots.values():
            d.configure(text_color=dot_color)

        if status == "connected":
            self._tick_uptime()
        else:
            if self._uptime_job:
                self.after_cancel(self._uptime_job)
                self._uptime_job = None
            self._uptime_label.configure(text="")

    def _tick_uptime(self) -> None:
        if self.manager.connected_since:
            d = datetime.datetime.now() - self.manager.connected_since
            h, r = divmod(int(d.total_seconds()), 3600)
            m, s = divmod(r, 60)
            self._uptime_label.configure(text=f"conectado há {h:02d}:{m:02d}:{s:02d}")
        self._uptime_job = self.after(1000, self._tick_uptime)

    def _append_log(self, msg: str, level: str) -> None:
        tag = level if level in ("OK", "ERROR", "WARN", "SSH", "INFO") else "INFO"
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n", tag)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("0.0", "end")
        self._log_box.configure(state="disabled")
