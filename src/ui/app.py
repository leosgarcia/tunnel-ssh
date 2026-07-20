import customtkinter as ctk
import datetime
import os
import sys
from tkinter import filedialog, messagebox
from typing import Dict, Any, Optional

from src.tunnel import TunnelManager, load_config, save_config
from src.ui.port_manager import PortManagerWindow
from src.ui.host_manager import HostManagerWindow

APP_VERSION = "1.2.1"
APP_NAME = "WL Tech SSH Tunnel Manager"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"

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
        self.title(APP_TITLE)
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
        # Cabeçalho Superior (Header com Menu)
        hdr = ctk.CTkFrame(self, fg_color="#1f2430", corner_radius=0)
        hdr.pack(fill="x")
        
        ctk.CTkLabel(hdr, text="⚡ wltech", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="#8be9fd").pack(side="left", padx=20, pady=15)
        ctk.CTkLabel(hdr, text="SSH Tunnel Manager", font=ctk.CTkFont(family="Consolas", size=12), text_color="#8be9fd").pack(side="left")
        ctk.CTkLabel(hdr, text=f"v{APP_VERSION}", font=ctk.CTkFont(family="Consolas", size=10), text_color="#50fa7b").pack(side="left", padx=(8, 0))
        
        # Menu Sanduíche no cabeçalho
        self._menu_btn = ctk.CTkButton(
            hdr,
            text="☰ Menu",
            command=self._show_popup_menu,
            width=80,
            fg_color="transparent",
            text_color="#f8f8f2",
            hover_color="#313147",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold")
        )
        self._menu_btn.pack(side="right", padx=10)

        # Bloco de Conexão Global
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.pack(fill="x", padx=20, pady=(15, 5))
        
        # container para indicador + textos (usa grid para alinhamento preciso)
        status_frame = ctk.CTkFrame(sf, fg_color="transparent")
        status_frame.pack(side="left", padx=0)

        # bolinha indicador (tamanho reduzido para proporção melhor)
        self._dot = ctk.CTkLabel(status_frame, text="●", font=ctk.CTkFont(family="Consolas", size=18), text_color="#ff5555")
        self._dot.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        # labels de status alinhados ao centro vertical da bolinha
        self._status_label = ctk.CTkLabel(status_frame, text="Desconectado",
                          font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
                          text_color="#ff5555", anchor="w")
        self._status_label.grid(row=0, column=1, sticky="w")

        self._uptime_label = ctk.CTkLabel(status_frame, text="",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color="#6272a4", anchor="w")
        self._uptime_label.grid(row=1, column=1, sticky="w")

        # botão principal com tamanho e padding equilibrados
        self._btn = ctk.CTkButton(sf, text="▶ CONECTAR",
                      font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                      fg_color="#50fa7b", text_color="#1e1e2e", hover_color="#3de05a",
                      command=self._toggle, width=160, height=40, corner_radius=8)
        self._btn.pack(side="right", padx=(10, 0))

        # Bloco do Host (Perfil)
        host_frame = ctk.CTkFrame(self, fg_color="#21222c", corner_radius=10, border_width=1, border_color="#44475a")
        host_frame.pack(fill="x", padx=20, pady=10)
        
        host_hdr = ctk.CTkFrame(host_frame, fg_color="transparent")
        host_hdr.pack(fill="x", padx=15, pady=(10, 0))
        
        ctk.CTkLabel(host_hdr, text="🖥 Host Atual:", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color="#bd93f9").pack(side="left")
        
        saved_hosts_list = list(self._config.get("saved_hosts", {}).keys())
        if not saved_hosts_list and self._config.get("ssh_host"):
            saved_hosts_list = [self._config["ssh_host"]]
            
        self._host_var = ctk.StringVar(value=self._config.get("ssh_host", ""))
        self._host_selector = ctk.CTkOptionMenu(
            host_hdr,
            variable=self._host_var,
            values=saved_hosts_list,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#2a2a3e",
            text_color="#f8f8f2",
            button_color="#2a2a3e",
            button_hover_color="#313147",
            command=self._on_main_host_change
        )
        self._host_selector.pack(side="left", padx=10)
        
        ports_hdr = ctk.CTkFrame(host_frame, fg_color="transparent")
        ports_hdr.pack(fill="x", padx=15, pady=(10, 0))
        
        ctk.CTkLabel(ports_hdr, text="Portas mapeadas neste host:", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#6272a4").pack(side="left")
        ctk.CTkButton(ports_hdr, text="⚙ Editar Portas", font=ctk.CTkFont(size=11, weight="bold"), command=self._open_port_manager, fg_color="transparent", border_width=1, border_color="#6272a4", text_color="#f8f8f2", hover_color="#313147", height=24, width=100).pack(side="right")
        
        self._ports_container = ctk.CTkFrame(host_frame, fg_color="transparent")
        self._ports_container.pack(fill="x", padx=15, pady=(5, 10))
        self._port_dots: Dict[str, ctk.CTkLabel] = {}
        self._rebuild_ports_ui()

        # Log Console
        log_hdr = ctk.CTkFrame(self, fg_color="transparent")
        log_hdr.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(log_hdr, text="LOG DA CONEXÃO", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#6272a4").pack(side="left")
        ctk.CTkButton(log_hdr, text="Limpar", font=ctk.CTkFont(size=10), command=self._clear_log, fg_color="transparent", text_color="#8be9fd", width=60, height=24, hover_color="#313147").pack(side="right")
        
        self._log_box = ctk.CTkTextbox(self, height=120, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#1e1e2e", text_color="#f8f8f2", border_width=1, border_color="#44475a")
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

    def _on_main_host_change(self, selected_host: str) -> None:
        if self._status not in ("disconnected", "error"):
            # Se estiver conectado, reverte visualmente e avisa
            self._host_var.set(self._config.get("ssh_host", ""))
            messagebox.showwarning("Túnel ativo", "Desconecte o túnel antes de trocar o servidor.")
            return
            
        old_host = self._config.get("ssh_host", "")
        if selected_host == old_host: return
        
        # Salva o atual
        if "saved_hosts" not in self._config: self._config["saved_hosts"] = {}
        if old_host:
            if old_host not in self._config["saved_hosts"]: self._config["saved_hosts"][old_host] = {}
            self._config["saved_hosts"][old_host]["key"] = self._config.get("ssh_key", "")
            self._config["saved_hosts"][old_host]["ports"] = self._config.get("ports", [])
            
        # Carrega o novo
        if selected_host in self._config["saved_hosts"]:
            self._config["ssh_key"] = self._config["saved_hosts"][selected_host].get("key", "")
            self._config["ports"] = self._config["saved_hosts"][selected_host].get("ports", [])
        
        self._config["ssh_host"] = selected_host
        save_config(self._config)
        self._rebuild_ports_ui()
        self._append_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Servidor alterado para {selected_host}.", "INFO")

    def _on_ports_saved(self, new_config: Dict[str, Any]) -> None:
        self._config = new_config
        # Salvar portas no host atual no dicionário
        current_host = self._config.get("ssh_host", "")
        if current_host:
            if "saved_hosts" not in self._config:
                self._config["saved_hosts"] = {}
            if current_host not in self._config["saved_hosts"]:
                self._config["saved_hosts"][current_host] = {"key": self._config.get("ssh_key", "")}
            self._config["saved_hosts"][current_host]["ports"] = self._config.get("ports", [])
            
        save_config(self._config)
        self._rebuild_ports_ui()
        self._append_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Configuração de portas salva.", "INFO")

    def _show_popup_menu(self) -> None:
        import tkinter as tk
        m = tk.Menu(self, tearoff=0, bg="#2a2a3e", fg="#f8f8f2", activebackground="#bd93f9", activeforeground="#282a36", font=("Consolas", 10))
        m.add_command(label="🌐 Gerenciar Hosts", command=self._open_host_manager)
        def _show_about():
            about_text = (
                f"{APP_NAME}\nVersão {APP_VERSION}\n\n"
                "Gerencie túneis SSH e múltiplos hosts com facilidade.\n\n"
                "Copyright (c) 2026 leosgarcia\n"
                "License: MIT License\n\n"
                "Project: https://github.com/leosg/tunnel-ssh"
            )
            messagebox.showinfo("Sobre", about_text)

        m.add_command(label="ℹ Sobre", command=_show_about)
        m.add_separator()
        m.add_command(label="✕ Sair", command=self._on_close)
        
        x = self._menu_btn.winfo_rootx()
        y = self._menu_btn.winfo_rooty() + self._menu_btn.winfo_height()
        m.post(x, y)

    def _open_host_manager(self) -> None:
        if self._status not in ("disconnected", "error"):
            messagebox.showwarning("Túnel ativo", "Desconecte o túnel antes de gerenciar os hosts.")
            return

        HostManagerWindow(self, self._config, self._on_hosts_saved)

    def _on_hosts_saved(self, new_config: Dict[str, Any]) -> None:
        self._config = dict(new_config)
        self._config.setdefault("ssh_key", "")
        self._config.setdefault("ports", [])
        self._config.setdefault("saved_hosts", {})

        if not self._config.get("saved_hosts"):
            self._config["ssh_host"] = ""
            self._config["ssh_key"] = ""
            self._config["ports"] = []
        elif self._config.get("ssh_host") not in self._config.get("saved_hosts", {}):
            self._config["ssh_host"] = list(self._config["saved_hosts"].keys())[0]
            host_data = self._config["saved_hosts"][self._config["ssh_host"]]
            self._config["ssh_key"] = host_data.get("key", "")
            self._config["ports"] = host_data.get("ports", [])

        save_config(self._config)

        # Atualiza o OptionMenu principal com a nova lista
        saved_hosts_list = list(self._config.get("saved_hosts", {}).keys())
        if not saved_hosts_list:
            saved_hosts_list = [""]
            self._host_var.set("")
            self._config["ssh_host"] = ""
            
        self._host_selector.configure(values=saved_hosts_list)
        if self._config.get("ssh_host"):
            self._host_var.set(self._config["ssh_host"])
            
        self._rebuild_ports_ui()
        self._append_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Configurações de hosts atualizadas.", "INFO")

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
        # status_color, texto_status, texto_botao, bool_desligado, cor_botao, hover_botao
        cfg = {
            "connected":    ("#50fa7b", "Conectado",     "▪ DESCONECTAR",  False,  "#ff5555", "#cc4444"),
            "connecting":   ("#f1fa8c", "Conectando...", "▪ CANCELAR",     False, "#ff5555", "#cc4444"),
            "reconnecting": ("#f1fa8c", "Reconectando...","▪ CANCELAR",     False, "#ff5555", "#cc4444"),
            "disconnected": ("#ff5555", "Desconectado",  "▶ CONECTAR",     True,  "#50fa7b", "#3de05a"),
            "error":        ("#ff5555", "Erro",          "▶ TENTAR NOVAMENTE", True, "#50fa7b", "#3de05a"),
        }.get(status, ("#6272a4", status, "▶ CONECTAR", True, "#50fa7b", "#3de05a"))

        status_color, text, btn_text, is_off, btn_color, btn_hover = cfg
        
        if is_off:
            self._host_selector.configure(state="normal")
        else:
            self._host_selector.configure(state="disabled")

        self._dot.configure(text_color=status_color)
        self._status_label.configure(text=text, text_color=status_color)
        
        if extra:
            self._uptime_label.configure(text=extra, text_color="#ff5555")
        elif status != "connected":
            self._uptime_label.configure(text="", text_color="#6272a4")
        
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
