import customtkinter as ctk
import json
from typing import Dict, Any, Callable, List

class PortManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, config: Dict[str, Any], on_save: Callable[[Dict[str, Any]], None]):
        super().__init__(parent)
        self.title("Gerenciar Portas")
        self.geometry("780x500")
        self.resizable(False, False)
        
        # Faz a janela ficar por cima (modal)
        self.transient(parent)
        self.grab_set()

        self._config = json.loads(json.dumps(config))
        self._on_save = on_save
        self._rows: List[Dict[str, Any]] = []

        self._build()
        self._populate()

    def _build(self) -> None:
        # Cabeçalho
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(hdr, text="⚡ Gerenciar Portas", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="#bd93f9").pack(side="left")
        
        ctk.CTkLabel(self, text="Alterações entram em vigor na próxima conexão.", font=ctk.CTkFont(size=12), text_color="#f1fa8c").pack(anchor="w", padx=20, pady=(0, 10))

        # Cabeçalho da Tabela
        cols_frame = ctk.CTkFrame(self, fg_color="transparent")
        cols_frame.pack(fill="x", padx=20, pady=(0, 5))
        
        headers = [("Ativo", 50), ("Porta Local", 90), ("Host Remoto", 120), ("Porta Remota", 100), ("Label", 150), ("Grupo", 100), ("", 30)]
        for text, w in headers:
            ctk.CTkLabel(cols_frame, text=text, width=w, anchor="w", font=ctk.CTkFont(family="Consolas", size=12, weight="bold")).pack(side="left", padx=5)

        # Área de rolagem
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Botões inferiores
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(btn_row, text="+ Adicionar Porta", command=self._add_row, fg_color="transparent", border_width=1, border_color="#6272a4", text_color="#f8f8f2", hover_color="#313147").pack(side="left")
        
        ctk.CTkButton(btn_row, text="✔ Salvar", command=self._save, fg_color="#50fa7b", text_color="#1e1e2e", hover_color="#3de05a").pack(side="right")
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy, fg_color="transparent", border_width=1, border_color="#6272a4", text_color="#f8f8f2", hover_color="#313147").pack(side="right", padx=(0, 10))

    def _populate(self) -> None:
        for p in self._config.get("ports", []):
            self._add_row(p)

    def _add_row(self, port_data: Dict[str, Any] = None) -> None:
        d = port_data or {
            "local": "", "remote_host": "127.0.0.1",
            "remote_port": "", "label": "", "group": "", "enabled": True
        }
        
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        
        row_vars = {
            "enabled": ctk.BooleanVar(value=d.get("enabled", True)),
            "local": ctk.StringVar(value=d.get("local", "")),
            "remote_host": ctk.StringVar(value=d.get("remote_host", "127.0.0.1")),
            "remote_port": ctk.StringVar(value=d.get("remote_port", "")),
            "label": ctk.StringVar(value=d.get("label", "")),
            "group": ctk.StringVar(value=d.get("group", "")),
            "frame": row_frame
        }
        
        ctk.CTkSwitch(row_frame, text="", variable=row_vars["enabled"], width=50, progress_color="#50fa7b").pack(side="left", padx=5)
        
        ctk.CTkEntry(row_frame, textvariable=row_vars["local"], width=90, font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left", padx=5)
        ctk.CTkEntry(row_frame, textvariable=row_vars["remote_host"], width=120, font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left", padx=5)
        ctk.CTkEntry(row_frame, textvariable=row_vars["remote_port"], width=100, font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left", padx=5)
        ctk.CTkEntry(row_frame, textvariable=row_vars["label"], width=150, font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left", padx=5)
        ctk.CTkEntry(row_frame, textvariable=row_vars["group"], width=100, font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left", padx=5)
        
        def _del() -> None:
            row_frame.destroy()
            self._rows.remove(row_vars)
            
        ctk.CTkButton(row_frame, text="✕", width=30, command=_del, fg_color="#ff5555", hover_color="#cc4444", text_color="#1e1e2e").pack(side="left", padx=5)
        
        self._rows.append(row_vars)

    def _save(self) -> None:
        ports = []
        for r in self._rows:
            local = r["local"].get().strip()
            rhost = r["remote_host"].get().strip()
            rport = r["remote_port"].get().strip()
            if not local or not rport:
                continue
            ports.append({
                "local": local,
                "remote_host": rhost or "127.0.0.1",
                "remote_port": rport,
                "label": r["label"].get().strip() or f":{local}",
                "group": r["group"].get().strip() or "Outros",
                "enabled": r["enabled"].get(),
            })
        self._config["ports"] = ports
        self._on_save(self._config)
        self.destroy()
