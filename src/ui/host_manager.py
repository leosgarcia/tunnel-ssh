import customtkinter as ctk
import json
import os
from tkinter import filedialog, messagebox
from typing import Dict, Any, Callable, List


def validate_host_rows(rows: List[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    seen: set[str] = set()

    for row in rows:
        host = (row.get("host") or "").strip()
        if not host:
            errors.append("Preencha todos os nomes de host antes de salvar.")
            continue

        if host in seen:
            errors.append(f"Host duplicado: {host}")
        else:
            seen.add(host)

    return errors


class HostManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, config: Dict[str, Any], on_save: Callable[[Dict[str, Any]], None]):
        super().__init__(parent)
        self.title("Gerenciar Hosts")
        self.geometry("700x450")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        self._config = json.loads(json.dumps(config))
        self._on_save = on_save
        
        self._rows: List[Dict[str, Any]] = []
        for host, data in self._config.get("saved_hosts", {}).items():
            self._rows.append({
                "original_host": host,
                "host": host,
                "key": data.get("key", ""),
                "ports": data.get("ports", [])
            })
            
        self._build()
        self._populate()

    def _build(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(hdr, text="🌐 Gerenciar Hosts", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="#bd93f9").pack(side="left")

        cols_frame = ctk.CTkFrame(self, fg_color="transparent")
        cols_frame.pack(fill="x", padx=20, pady=(0, 5))
        
        ctk.CTkLabel(cols_frame, text="Host", width=250, anchor="w", font=ctk.CTkFont(family="Consolas", size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(cols_frame, text="Chave Privada", width=200, anchor="w", font=ctk.CTkFont(family="Consolas", size=12, weight="bold")).pack(side="left", padx=5)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(btn_row, text="+ Novo Host", command=self._add_row, fg_color="transparent", border_width=1, border_color="#6272a4", text_color="#f8f8f2", hover_color="#313147").pack(side="left")
        
        ctk.CTkButton(btn_row, text="✔ Salvar", command=self._save, fg_color="#50fa7b", text_color="#1e1e2e", hover_color="#3de05a").pack(side="right")
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy, fg_color="transparent", border_width=1, border_color="#6272a4", text_color="#f8f8f2", hover_color="#313147").pack(side="right", padx=(0, 10))

        self._error_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Consolas", size=10), text_color="#ff5555")
        self._error_label.pack(fill="x", padx=20, pady=(0, 10))

    def _populate(self) -> None:
        for w in self.scroll_frame.winfo_children():
            w.destroy()
            
        for i, row in enumerate(self._rows):
            f = ctk.CTkFrame(self.scroll_frame, fg_color="#2a2a3e", corner_radius=5)
            f.pack(fill="x", pady=2)
            
            host_var = ctk.StringVar(value=row["host"])
            key_var = ctk.StringVar(value=row["key"])
            
            def make_cmd(idx=i, hv=host_var, kv=key_var):
                def cb(*args):
                    self._rows[idx]["host"] = hv.get().strip()
                    self._rows[idx]["key"] = kv.get().strip()
                return cb
                
            cb = make_cmd()
            host_var.trace_add("write", cb)
            key_var.trace_add("write", cb)
            
            ctk.CTkEntry(f, textvariable=host_var, width=250, font=ctk.CTkFont(family="Consolas", size=11)).pack(side="left", padx=5, pady=5)
            ctk.CTkEntry(f, textvariable=key_var, width=200, font=ctk.CTkFont(family="Consolas", size=11)).pack(side="left", padx=5, pady=5)
            
            def browse(kv=key_var):
                path = filedialog.askopenfilename(title="Selecionar chave", initialdir=os.path.expanduser("~/.ssh"), filetypes=[("Chaves SSH", "id_* *.pem *.key"), ("Todos", "*.*")])
                if path: kv.set(path)
                
            ctk.CTkButton(f, text="📂", width=30, command=browse, fg_color="transparent", hover_color="#313147").pack(side="left")
            
            def delete(idx=i):
                if messagebox.askyesno("Confirmar", "Remover este host?"):
                    self._rows.pop(idx)
                    self._populate()
            
            ctk.CTkButton(f, text="🗑", width=30, command=delete, fg_color="transparent", text_color="#ff5555", hover_color="#552222").pack(side="right", padx=5)

    def _add_row(self) -> None:
        self._rows.append({"original_host": None, "host": "", "key": "", "ports": []})
        self._populate()

    def _save(self) -> None:
        errors = validate_host_rows(self._rows)
        if errors:
            self._error_label.configure(text="\n".join(errors))
            return

        new_hosts = {}
        for row in self._rows:
            host = row["host"].strip()
            new_hosts[host] = {
                "key": row["key"],
                "ports": row["ports"]
            }
        
        self._config["saved_hosts"] = new_hosts
        
        if self._config.get("ssh_host") not in new_hosts:
            if new_hosts:
                self._config["ssh_host"] = list(new_hosts.keys())[0]
            else:
                self._config["ssh_host"] = ""
                
        if self._config["ssh_host"]:
            self._config["ssh_key"] = new_hosts[self._config["ssh_host"]]["key"]
            self._config["ports"] = new_hosts[self._config["ssh_host"]]["ports"]
        else:
            self._config["ssh_key"] = ""
            self._config["ports"] = []

        self._error_label.configure(text="")
        self._on_save(self._config)
        self.destroy()
