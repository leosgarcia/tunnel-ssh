import subprocess
import threading
import time
import datetime
import sys
import json
import os
import logging
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)

def _get_config_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # Quando dentro de src/, a raiz é um nível acima
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "tunnel_config.json")

CONFIG_FILE = _get_config_path()


def ensure_config_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

DEFAULT_CONFIG: Dict[str, Any] = {
    "ssh_host": "usuario@host",
    "ssh_key": "",
    "reconnect_delay": 5,
    "ports": [],
    "saved_hosts": {}
}

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "ssh_host" not in data: data["ssh_host"] = DEFAULT_CONFIG["ssh_host"]
                if "reconnect_delay" not in data: data["reconnect_delay"] = DEFAULT_CONFIG["reconnect_delay"]
                if "ssh_key" not in data: data["ssh_key"] = DEFAULT_CONFIG["ssh_key"]
                if "ports" not in data: data["ports"] = DEFAULT_CONFIG["ports"]
                if "saved_hosts" not in data: data["saved_hosts"] = {}
                
                # Migração inicial para garantir que o host atual exista no dicionário
                current = data["ssh_host"]
                if current not in data["saved_hosts"]:
                    data["saved_hosts"][current] = {
                        "key": data.get("ssh_key", ""),
                        "ports": data.get("ports", [])
                    }
                return data
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de configuração: {e}")
    data = json.loads(json.dumps(DEFAULT_CONFIG))
    # Inicializa com o padrão no dict também
    data["saved_hosts"][data["ssh_host"]] = {"key": data["ssh_key"], "ports": data["ports"]}
    return data

def save_config(cfg: Dict[str, Any]) -> None:
    try:
        ensure_config_dir(CONFIG_FILE)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info("Configuração salva com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao salvar configuração: {e}")

class TunnelManager:
    def __init__(self, on_status_change: Callable[[str, str], None], on_log: Callable[[str, str], None], get_config: Callable[[], Dict[str, Any]]):
        self.on_status_change = on_status_change
        self.on_log = on_log
        self.get_config = get_config
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._user_stopped = False
        self.retry_count = 0
        self.connected_since: Optional[datetime.datetime] = None

    def _build_cmd(self) -> list[str]:
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

    def _log(self, msg: str, level: str = "INFO") -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        logger.info(f"[{level}] {msg}")
        self.on_log(f"[{ts}] [{level}] {msg}", level)

    def _set_status(self, status: str, extra: str = "") -> None:
        self.on_status_change(status, extra)

    def start(self) -> None:
        self._user_stopped = False
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self) -> None:
        self._user_stopped = True
        self._stop_event.set()
        self._kill_proc()
        self._set_status("disconnected")
        self._log("Túnel encerrado pelo usuário.", "INFO")
        self.connected_since = None
        self.retry_count = 0

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def _kill_proc(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            self._proc = None

    def _launch(self) -> None:
        cmd = self._build_cmd()
        self._log("Iniciando: " + " ".join(cmd), "INFO")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        with self._lock:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=flags)
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stderr(self) -> None:
        proc = self._proc
        if not proc or not proc.stderr:
            return
        for line in proc.stderr:
            text = line.decode(errors="replace").strip()
            if text:
                self._log(text, "SSH")

    def _monitor_loop(self) -> None:
        cfg = self.get_config()
        while not self._stop_event.is_set():
            self._set_status("connecting")
            self._log("Conectando ao servidor…", "INFO")
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
                self.retry_count = 0
                self.connected_since = datetime.datetime.now()
                self._set_status("connected")
                self._log("Túnel estabelecido com sucesso.", "OK")
                
                # Aguarda o processo terminar
                if self._proc:
                    self._proc.wait()
                
                if self._stop_event.is_set() or self._user_stopped:
                    break
                
                rc = self._proc.returncode if self._proc else "?"
                self._log(f"Processo SSH encerrou (código {rc}).", "WARN")
                self._set_status("reconnecting")
                self.connected_since = None
            else:
                rc = self._proc.returncode if self._proc else "?"
                self._log(f"Processo SSH não iniciou (código {rc}).", "ERROR")
                self._set_status("reconnecting")

            self.retry_count += 1
            cfg = self.get_config()
            delay = cfg.get("reconnect_delay", 5)
            self._log(f"Reconectando em {delay}s… (tentativa #{self.retry_count})", "WARN")
            self._stop_event.wait(delay)

        self._kill_proc()
