import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tunnel import DEFAULT_CONFIG, load_config, save_config
from src.ui.app import App


def test_save_config_persists_host_removals(tmp_path, monkeypatch):
    config_path = tmp_path / "tunnel_config.json"
    monkeypatch.setattr("src.tunnel.CONFIG_FILE", str(config_path))

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["ssh_host"] = "host-a"
    cfg["saved_hosts"] = {
        "host-a": {"key": "", "ports": []},
        "host-b": {"key": "", "ports": []},
    }
    save_config(cfg)

    loaded = load_config()
    assert set(loaded["saved_hosts"].keys()) == {"host-a", "host-b"}

    cfg["saved_hosts"] = {"host-a": {"key": "", "ports": []}}
    cfg["ssh_host"] = "host-a"
    save_config(cfg)

    reloaded = load_config()
    assert reloaded["saved_hosts"] == {"host-a": {"key": "", "ports": []}}


def test_app_persists_hosts_when_host_manager_saves(monkeypatch):
    app = App.__new__(App)
    app._config = {
        "ssh_host": "host-a",
        "ssh_key": "",
        "ports": [],
        "saved_hosts": {
            "host-a": {"key": "", "ports": []},
            "host-b": {"key": "", "ports": []},
        },
    }
    app._host_var = SimpleNamespace(set=lambda *args, **kwargs: None)
    app._host_selector = SimpleNamespace(configure=lambda *args, **kwargs: None)
    app._rebuild_ports_ui = lambda: None
    app._append_log = lambda *args, **kwargs: None

    saved = []

    def fake_save_config(cfg):
        saved.append(cfg)

    monkeypatch.setattr("src.ui.app.save_config", fake_save_config)

    app._on_hosts_saved({
        "ssh_host": "host-a",
        "ssh_key": "",
        "ports": [],
        "saved_hosts": {"host-a": {"key": "", "ports": []}},
    })

    assert saved and saved[0]["saved_hosts"] == {"host-a": {"key": "", "ports": []}}
