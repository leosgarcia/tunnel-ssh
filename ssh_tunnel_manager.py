"""
wltech · SSH Tunnel Manager
Gerencia túnel SSH com reconexão automática e gerenciamento dinâmico de portas.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import time
import datetime
import sys
import json
import os

# ─── Arquivo de configuração persistente ──────────────────────────────────────
# Quando empacotado com PyInstaller, sys.executable aponta para o .exe.
# __file__ aponta para a pasta temporária _MEIPASS — não serve para persistência.
# Usamos sempre a pasta do executável (.exe) ou do script (.py).
def _get_config_path():
    if getattr(sys, "frozen", False):
        # rodando como .exe gerado pelo PyInstaller
        base = os.path.dirname(sys.executable)
    else:
        # rodando como script .py
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "tunnel_config.json")

CONFIG_FILE = _get_config_path()

DEFAULT_CONFIG = {
    "ssh_host": "ubuntu@144.22.177.153",
    "ssh_key": "",
    "reconnect_delay": 5,
    "ports": [
        {"local": "8443",  "remote_host": "127.0.0.1", "remote_port": "443",  "label": "CoPilot HTTPS",       "group": "CoPilot",  "enabled": True},
        {"local": "8080",  "remote_host": "127.0.0.1", "remote_port": "80",   "label": "CoPilot HTTP",        "group": "CoPilot",  "enabled": True},
        {"local": "18443", "remote_host": "127.0.0.1", "remote_port": "8443", "label": "Wazuh Dashboard",     "group": "Wazuh",    "enabled": True},
        {"local": "1514",  "remote_host": "127.0.0.1", "remote_port": "1514", "label": "Wazuh Syslog",        "group": "Wazuh",    "enabled": True},
        {"local": "1515",  "remote_host": "127.0.0.1", "remote_port": "1515", "label": "Wazuh Agent Reg.",    "group": "Wazuh",    "enabled": True},
        {"local": "9001",  "remote_host": "127.0.0.1", "remote_port": "9001", "label": "Graylog",             "group": "Graylog",  "enabled": True},
        {"local": "3000",  "remote_host": "127.0.0.1", "remote_port": "3000", "label": "Grafana",             "group": "Grafana",  "enabled": True},
        {"local": "9000",  "remote_host": "127.0.0.1", "remote_port": "9000", "label": "MinIO",               "group": "MinIO",    "enabled": True},
    ]
}

# ─── Paleta de cores ──────────────────────────────────────────────────────────
BG        = "#1e1e2e"
SURFACE   = "#2a2a3e"
SURFACE2  = "#313147"
BORDER    = "#3a3a5e"
GREEN     = "#50fa7b"
RED       = "#ff5555"
YELLOW    = "#f1fa8c"
BLUE      = "#8be9fd"
PURPLE    = "#bd93f9"
ORANGE    = "#ffb86c"
FG        = "#f8f8f2"
FG_DIM    = "#6272a4"

GROUP_COLORS = {
    "CoPilot": "#bd93f9",
    "Wazuh":   "#50fa7b",
    "Graylog": "#8be9fd",
    "Grafana": "#ffb86c",
    "MinIO":   "#ff79c6",
}


# ─── Persistência ─────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # garante campos novos
                if "ssh_host" not in data:
                    data["ssh_host"] = DEFAULT_CONFIG["ssh_host"]
                if "reconnect_delay" not in data:
                    data["reconnect_delay"] = DEFAULT_CONFIG["reconnect_delay"]
                if "ssh_key" not in data:
                    data["ssh_key"] = DEFAULT_CONFIG["ssh_key"]
                return data
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_CONFIG))

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")


# ─── TunnelManager ────────────────────────────────────────────────────────────
class TunnelManager:
    def __init__(self, on_status_change, on_log, get_config):
        self.on_status_change = on_status_change
        self.on_log           = on_log
        self.get_config       = get_config   # callable → dict config atual
        self._proc            = None
        self._lock            = threading.Lock()
        self._monitor_thread  = None
        self._stop_event      = threading.Event()
        self._user_stopped    = False
        self.retry_count      = 0
        self.connected_since  = None

    def _build_cmd(self):
        cfg = self.get_config()
        cmd = ["ssh",
               "-o", "StrictHostKeyChecking=no",
               "-o", "ServerAliveInterval=10",
               "-o", "ServerAliveCountMax=3",
               "-o", "ExitOnForwardFailure=yes"]
        key = cfg.get("ssh_key", "").strip()
        if key:
            cmd += ["-i", os.path.expandvars(os.path.expanduser(key))]
        for p in cfg["ports"]:
            if p.get("enabled", True):
                cmd += ["-L", f"{p['local']}:{p['remote_host']}:{p['remote_port']}"]
        cmd += [cfg["ssh_host"], "-N"]
        return cmd

    def _log(self, msg, level="INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.on_log(f"[{ts}] [{level}] {msg}")

    def _set_status(self, status, extra=""):
        self.on_status_change(status, extra)

    def start(self):
        self._user_stopped = False
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        self._user_stopped = True
        self._stop_event.set()
        self._kill_proc()
        self._set_status("disconnected")
        self._log("Túnel encerrado pelo usuário.", "INFO")
        self.connected_since = None
        self.retry_count     = 0

    def is_running(self):
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def _kill_proc(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            self._proc = None

    def _launch(self):
        cmd = self._build_cmd()
        self._log("Iniciando: " + " ".join(cmd))
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        with self._lock:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=flags)
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stderr(self):
        proc = self._proc
        if not proc:
            return
        for line in proc.stderr:
            text = line.decode(errors="replace").strip()
            if text:
                self._log(text, "SSH")

    def _monitor_loop(self):
        cfg = self.get_config()
        delay = cfg.get("reconnect_delay", 5)
        while not self._stop_event.is_set():
            self._set_status("connecting")
            self._log("Conectando ao servidor…")
            try:
                self._launch()
            except FileNotFoundError:
                self._log("Executável 'ssh' não encontrado. Instale OpenSSH ou Git for Windows.", "ERROR")
                self._set_status("error", "ssh não encontrado")
                break
            except Exception as e:
                self._log(f"Falha ao iniciar processo: {e}", "ERROR")
                self._set_status("error", str(e))

            time.sleep(2)
            if self._stop_event.is_set():
                break

            if self.is_running():
                self.retry_count     = 0
                self.connected_since = datetime.datetime.now()
                self._set_status("connected")
                self._log("Túnel estabelecido com sucesso.", "OK")
                self._proc.wait()
                if self._stop_event.is_set() or self._user_stopped:
                    break
                rc = self._proc.returncode
                self._log(f"Processo SSH encerrou (código {rc}).", "WARN")
                self._set_status("reconnecting")
                self.connected_since = None
            else:
                rc = self._proc.returncode if self._proc else "?"
                self._log(f"Processo SSH não iniciou (código {rc}).", "ERROR")
                self._set_status("reconnecting")

            self.retry_count += 1
            cfg   = self.get_config()
            delay = cfg.get("reconnect_delay", 5)
            self._log(f"Reconectando em {delay}s… (tentativa #{self.retry_count})", "WARN")
            self._stop_event.wait(delay)

        self._kill_proc()


# ─── Janela de Gerenciamento de Portas ────────────────────────────────────────
class PortManagerWindow(tk.Toplevel):
    def __init__(self, parent, config, on_save):
        super().__init__(parent)
        self.title("Gerenciar Portas")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()  # modal

        self._config  = json.loads(json.dumps(config))  # cópia
        self._on_save = on_save
        self._rows    = []  # list of dicts com StringVars e BooleanVar

        self._build()
        self._populate()

    def _lbl(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=BG, fg=FG_DIM,
                        font=("Consolas", 8), **kw)

    def _entry(self, parent, var, w=8):
        return tk.Entry(parent, textvariable=var, width=w,
                        bg=SURFACE2, fg=FG, insertbackground=FG,
                        relief="flat", bd=4, font=("Consolas", 9))

    def _build(self):
        # ── cabeçalho ─────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ wltech  ·  Gerenciar Portas",
                 font=("Consolas", 11, "bold"), bg=SURFACE, fg=PURPLE,
                 padx=16, pady=10).pack(side="left")

        # ── aviso ──────────────────────────────────────────────────────────
        tk.Label(self,
                 text="Alterações entram em vigor na próxima conexão.",
                 font=("Consolas", 8), bg=BG, fg=YELLOW
                 ).pack(anchor="w", padx=16, pady=(10, 0))

        # ── cabeçalho da tabela ────────────────────────────────────────────
        cols_frame = tk.Frame(self, bg=BG)
        cols_frame.pack(fill="x", padx=16, pady=(8, 2))
        for text, w in [("Ativo", 5), ("Porta Local", 10), ("Host Remoto", 14),
                        ("Porta Remota", 10), ("Label", 18), ("Grupo", 10), ("", 4)]:
            tk.Label(cols_frame, text=text, width=w, anchor="w",
                     font=("Consolas", 8, "bold"), bg=BG, fg=FG_DIM
                     ).pack(side="left", padx=2)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=2)

        # ── área rolável de linhas ─────────────────────────────────────────
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", padx=16, pady=4)

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0, height=300)
        sb     = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._rows_frame = tk.Frame(canvas, bg=BG)
        self._rows_win   = canvas.create_window((0, 0), window=self._rows_frame,
                                                anchor="nw")
        self._rows_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._canvas = canvas

        # ── botões inferiores ──────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=6)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        def _btn(parent, text, cmd, color=SURFACE2, fg=FG):
            return tk.Button(parent, text=text, command=cmd,
                             bg=color, fg=fg, activebackground=color,
                             font=("Consolas", 9), relief="flat", cursor="hand2",
                             padx=10, pady=6)

        _btn(btn_row, "+ Adicionar Porta", self._add_row,
             color=SURFACE2, fg=BLUE).pack(side="left", padx=(0, 6))
        _btn(btn_row, "✔  Salvar", self._save,
             color=GREEN, fg=BG).pack(side="right")
        _btn(btn_row, "Cancelar", self.destroy,
             color=SURFACE2, fg=FG_DIM).pack(side="right", padx=(0, 6))

    def _populate(self):
        for p in self._config["ports"]:
            self._add_row(p)

    def _add_row(self, port_data=None):
        d = port_data or {
            "local": "", "remote_host": "127.0.0.1",
            "remote_port": "", "label": "", "group": "", "enabled": True
        }
        row = {
            "enabled":     tk.BooleanVar(value=d.get("enabled", True)),
            "local":       tk.StringVar(value=d.get("local", "")),
            "remote_host": tk.StringVar(value=d.get("remote_host", "127.0.0.1")),
            "remote_port": tk.StringVar(value=d.get("remote_port", "")),
            "label":       tk.StringVar(value=d.get("label", "")),
            "group":       tk.StringVar(value=d.get("group", "")),
            "frame":       None,
        }
        f = tk.Frame(self._rows_frame, bg=BG)
        f.pack(fill="x", pady=1)
        row["frame"] = f

        tk.Checkbutton(f, variable=row["enabled"], bg=BG,
                       activebackground=BG, selectcolor=SURFACE2,
                       fg=GREEN, width=3).pack(side="left", padx=2)

        for key, w in [("local", 10), ("remote_host", 14),
                       ("remote_port", 10), ("label", 18), ("group", 10)]:
            self._entry(f, row[key], w).pack(side="left", padx=2)

        def _del(r=row):
            r["frame"].destroy()
            self._rows.remove(r)

        tk.Button(f, text="✕", command=_del,
                  bg=BG, fg=RED, activebackground=BG,
                  font=("Consolas", 9), relief="flat", cursor="hand2",
                  width=2).pack(side="left", padx=2)

        self._rows.append(row)

    def _save(self):
        ports = []
        for r in self._rows:
            local = r["local"].get().strip()
            rhost = r["remote_host"].get().strip()
            rport = r["remote_port"].get().strip()
            if not local or not rport:
                continue
            ports.append({
                "local":       local,
                "remote_host": rhost or "127.0.0.1",
                "remote_port": rport,
                "label":       r["label"].get().strip() or f":{local}",
                "group":       r["group"].get().strip() or "Outros",
                "enabled":     r["enabled"].get(),
            })
        self._config["ports"] = ports
        self._on_save(self._config)
        self.destroy()


# ─── App principal ────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("wltech · SSH Tunnel Manager")
        self.resizable(False, False)
        self.configure(bg=BG)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self._config     = load_config()
        self._status     = "disconnected"
        self._uptime_job = None

        self.manager = TunnelManager(
            on_status_change=self._on_status_change,
            on_log=self._on_log,
            get_config=lambda: self._config,
        )

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # cabeçalho
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ wltech", font=("Consolas", 13, "bold"),
                 bg=SURFACE, fg=PURPLE).pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text="SSH Tunnel Manager", font=("Consolas", 10),
                 bg=SURFACE, fg=FG_DIM).pack(side="left")
        tk.Button(hdr, text="⚙ Portas", font=("Consolas", 8),
                  bg=SURFACE, fg=BLUE, activebackground=SURFACE2,
                  relief="flat", cursor="hand2", padx=8, pady=6,
                  command=self._open_port_manager).pack(side="right", padx=8)
        tk.Button(hdr, text="🔑 Chave SSH", font=("Consolas", 8),
                  bg=SURFACE, fg=ORANGE, activebackground=SURFACE2,
                  relief="flat", cursor="hand2", padx=8, pady=6,
                  command=self._open_key_config).pack(side="right", padx=(0, 0))

        # status
        sf = tk.Frame(self, bg=BG)
        sf.pack(fill="x", padx=16, pady=(14, 4))
        self._dot = tk.Label(sf, text="●", font=("Consolas", 28), bg=BG, fg=RED)
        self._dot.pack(side="left")
        ic = tk.Frame(sf, bg=BG)
        ic.pack(side="left", padx=10)
        self._status_label = tk.Label(ic, text="Desconectado",
                                      font=("Consolas", 14, "bold"), bg=BG, fg=RED, anchor="w")
        self._status_label.pack(anchor="w")
        self._sub_label = tk.Label(ic, text=self._config["ssh_host"],
                                   font=("Consolas", 9), bg=BG, fg=FG_DIM, anchor="w")
        self._sub_label.pack(anchor="w")
        self._uptime_label = tk.Label(ic, text="",
                                      font=("Consolas", 9), bg=BG, fg=FG_DIM, anchor="w")
        self._uptime_label.pack(anchor="w")

        # botão principal
        self._btn = tk.Button(self, text="▶  CONECTAR",
                              font=("Consolas", 11, "bold"),
                              bg=GREEN, fg=BG, activebackground="#3de05a",
                              relief="flat", cursor="hand2", bd=0,
                              padx=20, pady=10, command=self._toggle)
        self._btn.pack(fill="x", padx=16, pady=(6, 2))

        # separador + portas
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=8)
        ports_hdr = tk.Frame(self, bg=BG)
        ports_hdr.pack(fill="x", padx=16)
        tk.Label(ports_hdr, text="PORTAS ATIVAS", font=("Consolas", 8, "bold"),
                 bg=BG, fg=FG_DIM).pack(side="left")

        self._ports_container = tk.Frame(self, bg=BG)
        self._ports_container.pack(fill="x", padx=16, pady=(4, 0))
        self._port_dots = {}
        self._rebuild_ports_ui()

        # log
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=16, pady=8)
        log_hdr = tk.Frame(self, bg=BG)
        log_hdr.pack(fill="x", padx=16)
        tk.Label(log_hdr, text="LOG", font=("Consolas", 8, "bold"),
                 bg=BG, fg=FG_DIM).pack(side="left")
        tk.Button(log_hdr, text="Limpar", font=("Consolas", 8),
                  bg=SURFACE, fg=FG_DIM, relief="flat", cursor="hand2",
                  command=self._clear_log).pack(side="right")
        self._log_box = scrolledtext.ScrolledText(
            self, height=10, width=68,
            font=("Consolas", 8), bg=SURFACE, fg=FG,
            insertbackground=FG, relief="flat", bd=0,
            state="disabled", wrap="word")
        self._log_box.pack(padx=16, pady=(4, 14))
        self._log_box.tag_config("OK",    foreground=GREEN)
        self._log_box.tag_config("ERROR", foreground=RED)
        self._log_box.tag_config("WARN",  foreground=YELLOW)
        self._log_box.tag_config("SSH",   foreground=FG_DIM)
        self._log_box.tag_config("INFO",  foreground=FG)

    def _rebuild_ports_ui(self):
        # limpa widgets existentes
        for w in self._ports_container.winfo_children():
            w.destroy()
        self._port_dots.clear()

        enabled_ports = [p for p in self._config["ports"] if p.get("enabled", True)]

        # agrupa por group
        groups = {}
        for p in enabled_ports:
            g = p.get("group", "Outros")
            groups.setdefault(g, []).append(p)

        col = 0
        for g_name, ports in groups.items():
            color = GROUP_COLORS.get(g_name, FG_DIM)
            gf = tk.Frame(self._ports_container, bg=SURFACE, padx=8, pady=6)
            gf.grid(row=0, column=col, sticky="nw", padx=(0, 8), pady=2)

            tk.Label(gf, text=g_name, font=("Consolas", 8, "bold"),
                     bg=SURFACE, fg=color).pack(anchor="w")

            for p in ports:
                pf = tk.Frame(gf, bg=SURFACE)
                pf.pack(anchor="w", pady=1)
                d = tk.Label(pf, text="●", font=("Consolas", 9),
                             bg=SURFACE, fg=FG_DIM)
                d.pack(side="left")
                tk.Label(pf, text=f":{p['local']} ",
                         font=("Consolas", 8, "bold"), bg=SURFACE, fg=BLUE
                         ).pack(side="left")
                tk.Label(pf, text=p.get("label", ""),
                         font=("Consolas", 8), bg=SURFACE, fg=FG_DIM
                         ).pack(side="left")
                self._port_dots[p["local"]] = d
            col += 1

    # ── gerenciador de portas ─────────────────────────────────────────────────
    def _open_port_manager(self):
        if self._status not in ("disconnected", "error"):
            messagebox.showwarning(
                "Túnel ativo",
                "Desconecte o túnel antes de editar as portas.",
                parent=self)
            return
        PortManagerWindow(self, self._config, self._on_ports_saved)

    def _on_ports_saved(self, new_config):
        self._config = new_config
        save_config(self._config)
        self._rebuild_ports_ui()
        self._on_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Configuração de portas salva.")

    # ── configuração de chave SSH ─────────────────────────────────────────────
    def _open_key_config(self):
        win = tk.Toplevel(self)
        win.title("Chave SSH")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Frame(win, bg=SURFACE).pack(fill="x")
        tk.Label(win, text="⚡ wltech  ·  Chave SSH",
                 font=("Consolas", 11, "bold"), bg=SURFACE, fg=PURPLE,
                 padx=16, pady=10).pack(fill="x")

        body = tk.Frame(win, bg=BG)
        body.pack(fill="x", padx=16, pady=14)

        tk.Label(body, text="Caminho da chave privada (deixe vazio para usar o ssh-agent):",
                 font=("Consolas", 8), bg=BG, fg=FG_DIM, anchor="w").pack(anchor="w")

        key_var = tk.StringVar(value=self._config.get("ssh_key", ""))
        entry = tk.Entry(body, textvariable=key_var, width=52,
                         bg=SURFACE2, fg=FG, insertbackground=FG,
                         relief="flat", bd=6, font=("Consolas", 9))
        entry.pack(fill="x", pady=(4, 2))

        tk.Label(body, text="Exemplo: %USERPROFILE%\\.ssh\\id_ed25519_wltech_pve",
                 font=("Consolas", 8), bg=BG, fg=FG_DIM, anchor="w").pack(anchor="w")

        def _browse():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=win, title="Selecionar chave SSH privada",
                initialdir=os.path.expanduser("~/.ssh"),
                filetypes=[("Chaves SSH", "id_* *.pem *.key"), ("Todos", "*.*")])
            if path:
                key_var.set(path)

        browse_btn = tk.Button(body, text="📂 Procurar…", command=_browse,
                               bg=SURFACE2, fg=BLUE, activebackground=BORDER,
                               font=("Consolas", 8), relief="flat", cursor="hand2",
                               padx=8, pady=4)
        browse_btn.pack(anchor="w", pady=(6, 0))

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=16, pady=8)

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        def _save():
            self._config["ssh_key"] = key_var.get().strip()
            save_config(self._config)
            self._on_log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [INFO] Chave SSH salva: {self._config['ssh_key'] or '(ssh-agent)'}")
            win.destroy()

        tk.Button(btn_row, text="✔  Salvar", command=_save,
                  bg=GREEN, fg=BG, activebackground="#3de05a",
                  font=("Consolas", 9), relief="flat", cursor="hand2",
                  padx=10, pady=6).pack(side="right")
        tk.Button(btn_row, text="Cancelar", command=win.destroy,
                  bg=SURFACE2, fg=FG_DIM, activebackground=BORDER,
                  font=("Consolas", 9), relief="flat", cursor="hand2",
                  padx=10, pady=6).pack(side="right", padx=(0, 6))

    # ── toggle connect ────────────────────────────────────────────────────────
    def _toggle(self):
        if self._status in ("disconnected", "error"):
            self.manager.start()
        else:
            self.manager.stop()

    def _on_close(self):
        self.manager.stop()
        self.destroy()

    # ── callbacks do manager ──────────────────────────────────────────────────
    def _on_status_change(self, status, extra=""):
        self.after(0, self._apply_status, status, extra)

    def _on_log(self, msg):
        self.after(0, self._append_log, msg)

    # ── update UI ─────────────────────────────────────────────────────────────
    def _apply_status(self, status, extra=""):
        self._status = status
        cfg = {
            "connected":    (GREEN,  "● Conectado",     "▪  DESCONECTAR",  False),
            "connecting":   (YELLOW, "◌ Conectando…",   "▪  CANCELAR",     False),
            "reconnecting": (YELLOW, "↻ Reconectando…", "▪  CANCELAR",     False),
            "disconnected": (RED,    "● Desconectado",  "▶  CONECTAR",     True),
            "error":        (RED,    "✕ Erro",           "▶  TENTAR NOVAMENTE", True),
        }.get(status, (FG_DIM, status, "▶  CONECTAR", True))

        color, text, btn_text, is_off = cfg
        self._dot.config(fg=color)
        self._status_label.config(text=text, fg=color)
        self._sub_label.config(text=extra if extra else self._config["ssh_host"])
        self._btn.config(
            text=btn_text,
            bg=(GREEN if is_off else RED),
            activebackground=("#3de05a" if is_off else "#cc4444"))

        dot_color = GREEN if status == "connected" else FG_DIM
        for d in self._port_dots.values():
            d.config(fg=dot_color)

        if status == "connected":
            self._tick_uptime()
        else:
            if self._uptime_job:
                self.after_cancel(self._uptime_job)
                self._uptime_job = None
            self._uptime_label.config(text="")

    def _tick_uptime(self):
        if self.manager.connected_since:
            d = datetime.datetime.now() - self.manager.connected_since
            h, r = divmod(int(d.total_seconds()), 3600)
            m, s = divmod(r, 60)
            self._uptime_label.config(text=f"conectado há {h:02d}:{m:02d}:{s:02d}")
        self._uptime_job = self.after(1000, self._tick_uptime)

    def _append_log(self, msg):
        tag = "INFO"
        for t in ("OK", "ERROR", "WARN", "SSH"):
            if f"[{t}]" in msg:
                tag = t
                break
        self._log_box.config(state="normal")
        self._log_box.insert("end", msg + "\n", tag)
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
