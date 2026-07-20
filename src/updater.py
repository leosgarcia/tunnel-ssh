"""Atualização segura do executável a partir do GitHub Releases oficial."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple


REPOSITORY = "leosgarcia/tunnel-ssh"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ASSET_API_PREFIX = f"https://api.github.com/repos/{REPOSITORY}/releases/assets/"
EXECUTABLE_ASSET_NAME = "wltech-tunnel.exe"
API_VERSION = "2022-11-28"
MAX_RELEASE_RESPONSE_SIZE = 2 * 1024 * 1024


class UpdateError(RuntimeError):
    """Falha esperada durante a consulta, download ou instalação."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    title: str
    notes: str
    page_url: str
    asset_api_url: str
    asset_size: int
    asset_sha256: str


def parse_version(value: str) -> Tuple[int, int, int]:
    """Converte uma versão SemVer simples (com ou sem prefixo ``v``)."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?", value.strip())
    if not match:
        raise UpdateError(f"Versão inválida recebida do GitHub: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer_version(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _request(url: str, accept: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "wltech-tunnel-updater",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )


def _validated_asset_url(value: object) -> str:
    url = str(value or "")
    asset_id = url.removeprefix(ASSET_API_PREFIX)
    if not url.startswith(ASSET_API_PREFIX) or not asset_id.isdigit():
        raise UpdateError("A release retornou um endereço de download não autorizado.")
    return url


def _validated_digest(value: object) -> str:
    digest = str(value or "").lower()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise UpdateError("O executável da release não possui um digest SHA-256 válido.")
    return digest.split(":", 1)[1]


def parse_release(payload: object) -> ReleaseInfo:
    if not isinstance(payload, dict):
        raise UpdateError("Resposta inválida recebida do GitHub.")

    version = str(payload.get("tag_name", "")).removeprefix("v")
    parse_version(version)

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("A release não contém uma lista de arquivos válida.")

    matching_assets = [
        asset for asset in assets
        if isinstance(asset, dict) and asset.get("name") == EXECUTABLE_ASSET_NAME
    ]
    if len(matching_assets) != 1:
        raise UpdateError(
            f'A release deve conter exatamente um executável chamado "{EXECUTABLE_ASSET_NAME}".'
        )

    asset = matching_assets[0]
    size = asset.get("size")
    if not isinstance(size, int) or size <= 0:
        raise UpdateError("O executável da release possui tamanho inválido.")

    page_url = str(payload.get("html_url", ""))
    expected_page_prefix = f"https://github.com/{REPOSITORY}/releases/"
    if not page_url.startswith(expected_page_prefix):
        raise UpdateError("A release não pertence ao repositório oficial.")

    return ReleaseInfo(
        version=version,
        title=str(payload.get("name") or f"Versão {version}"),
        notes=str(payload.get("body") or "Nenhuma nota de versão foi publicada."),
        page_url=page_url,
        asset_api_url=_validated_asset_url(asset.get("url")),
        asset_size=size,
        asset_sha256=_validated_digest(asset.get("digest")),
    )


def fetch_latest_release(
    timeout: int = 10,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> ReleaseInfo:
    """Consulta apenas a última release publicada do repositório oficial."""
    try:
        with opener(_request(LATEST_RELEASE_URL, "application/vnd.github+json"), timeout=timeout) as response:  # type: ignore[attr-defined]
            raw = response.read(MAX_RELEASE_RESPONSE_SIZE + 1)
    except Exception as exc:
        raise UpdateError(f"Não foi possível consultar o GitHub: {exc}") from exc

    if len(raw) > MAX_RELEASE_RESPONSE_SIZE:
        raise UpdateError("A resposta do GitHub excedeu o tamanho permitido.")
    try:
        return parse_release(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("O GitHub retornou uma resposta inválida.") from exc


def download_release(
    release: ReleaseInfo,
    progress: Optional[Callable[[float], None]] = None,
    timeout: int = 30,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> str:
    """Baixa e valida o executável; retorna o caminho temporário."""
    asset_url = _validated_asset_url(release.asset_api_url)
    temp_handle, temp_path = tempfile.mkstemp(prefix="wltech-tunnel-", suffix=".exe")
    os.close(temp_handle)
    digest = hashlib.sha256()
    downloaded = 0

    try:
        request = _request(asset_url, "application/octet-stream")
        with opener(request, timeout=timeout) as response, open(temp_path, "wb") as output:  # type: ignore[attr-defined]
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > release.asset_size:
                    raise UpdateError("O download excedeu o tamanho informado pela release.")
                output.write(chunk)
                digest.update(chunk)
                if progress:
                    progress(min(downloaded / release.asset_size, 1.0))

        if downloaded != release.asset_size:
            raise UpdateError("O download terminou incompleto.")
        if digest.hexdigest().lower() != release.asset_sha256.lower():
            raise UpdateError("A verificação SHA-256 falhou. O arquivo foi descartado.")
        with open(temp_path, "rb") as downloaded_file:
            if downloaded_file.read(2) != b"MZ":
                raise UpdateError("O arquivo baixado não é um executável válido do Windows.")
        if progress:
            progress(1.0)
        return temp_path
    except Exception as exc:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"Não foi possível baixar a atualização: {exc}") from exc


POWERSHELL_UPDATER = r'''param(
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$TargetPath,
    [Parameter(Mandatory=$true)][string]$NewPath
)
$ErrorActionPreference = 'Stop'
$backupPath = "$TargetPath.bak"
$logPath = Join-Path ([IO.Path]::GetDirectoryName($TargetPath)) 'update-error.log'
$script:restored = $false

function Restore-PreviousVersion {
    if (Test-Path -LiteralPath $TargetPath) {
        Remove-Item -LiteralPath $TargetPath -Force
    }
    if (Test-Path -LiteralPath $backupPath) {
        Move-Item -LiteralPath $backupPath -Destination $TargetPath -Force
        Start-Process -FilePath $TargetPath
        $script:restored = $true
    }
}

try {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if (-not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 500
    }
    if (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue) {
        throw 'O aplicativo não encerrou dentro do tempo esperado.'
    }

    if (Test-Path -LiteralPath $backupPath) {
        Remove-Item -LiteralPath $backupPath -Force
    }
    Move-Item -LiteralPath $TargetPath -Destination $backupPath -Force

    try {
        Move-Item -LiteralPath $NewPath -Destination $TargetPath -Force
        $newProcess = Start-Process -FilePath $TargetPath -PassThru
        Start-Sleep -Seconds 5
        if ($newProcess.HasExited) {
            throw 'A nova versão encerrou durante a inicialização.'
        }
        Remove-Item -LiteralPath $backupPath -Force
        if (Test-Path -LiteralPath $logPath) {
            Remove-Item -LiteralPath $logPath -Force
        }
    }
    catch {
        Restore-PreviousVersion
        throw
    }
}
catch {
    $message = "$(Get-Date -Format o) - $($_.Exception.Message)"
    if (-not $script:restored -and -not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) {
        if (-not (Test-Path -LiteralPath $TargetPath) -and (Test-Path -LiteralPath $backupPath)) {
            Restore-PreviousVersion
        }
        elseif (Test-Path -LiteralPath $TargetPath) {
            Start-Process -FilePath $TargetPath
        }
    }
    Set-Content -LiteralPath $logPath -Value $message -Encoding UTF8 -ErrorAction SilentlyContinue
}
finally {
    if (Test-Path -LiteralPath $NewPath) {
        Remove-Item -LiteralPath $NewPath -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''


def can_self_update() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def launch_update(downloaded_executable: str) -> None:
    """Inicia o auxiliar independente que substituirá o processo atual."""
    if not can_self_update():
        raise UpdateError("A instalação automática só funciona no executável compilado para Windows.")

    target = Path(sys.executable).resolve()
    downloaded = Path(downloaded_executable).resolve()
    if not target.is_file() or not downloaded.is_file():
        raise UpdateError("Não foi possível localizar os arquivos necessários para atualizar.")
    try:
        write_test_handle, write_test_path = tempfile.mkstemp(
            prefix=".wltech-write-test-",
            dir=str(target.parent),
        )
        os.close(write_test_handle)
        os.unlink(write_test_path)
    except OSError as exc:
        raise UpdateError("A pasta do aplicativo não permite substituir o executável.") from exc

    script_handle, script_path = tempfile.mkstemp(prefix="wltech-updater-", suffix=".ps1")
    os.close(script_handle)
    Path(script_path).write_text(POWERSHELL_UPDATER, encoding="utf-8-sig")

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
                "-ParentProcessId",
                str(os.getpid()),
                "-TargetPath",
                str(target),
                "-NewPath",
                str(downloaded),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
    except Exception as exc:
        try:
            os.unlink(script_path)
        except OSError:
            pass
        raise UpdateError(f"Não foi possível iniciar o instalador: {exc}") from exc
