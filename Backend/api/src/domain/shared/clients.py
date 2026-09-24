"""Client Management Engine for PRIIPs KID configurations."""

import json
from pathlib import Path
from typing import Any

import yaml
from domain.shared.io_utils import ensure_dir_resilient, write_bytes_resilient, write_text_resilient

from utils.paths import org_config_dir


def _clients_dir() -> Path:
    """An organisation's client records are its own."""
    return org_config_dir() / "clients_info"


def _ensure_clients_dir() -> None:
    ensure_dir_resilient(_clients_dir())


def get_all_clients() -> list[dict[str, Any]]:
    """Returns a list of all clients found in the clients_info directory."""
    _ensure_clients_dir()
    clients = []
    for f in _clients_dir().glob("*.yaml"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                client_data = yaml.safe_load(file) or {}
                if isinstance(client_data, dict):
                    client_data["client_id"] = f.stem
                    clients.append(client_data)
        except Exception:
            pass
    return sorted(clients, key=lambda c: c.get("organisation_name", c.get("client_id", "")))


def get_client(client_id: str) -> dict[str, Any] | None:
    """Returns a single client's configuration or None if not found."""
    if not client_id:
        return None
    _ensure_clients_dir()
    f = _clients_dir() / f"{client_id}.yaml"
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as file:
                client_data = yaml.safe_load(file) or {}
                client_data["client_id"] = client_id
                return client_data
        except Exception:
            pass
    return None


def save_client(client_id: str, client_data: dict[str, Any]) -> None:
    """Saves or creates a client configuration."""
    if not client_id:
        raise ValueError("Client ID is required.")
    _ensure_clients_dir()
    
    # Remove client_id from the data before saving
    data_to_save = dict(client_data)
    data_to_save.pop("client_id", None)
    
    f = _clients_dir() / f"{client_id}.yaml"
    yaml_str = yaml.dump(data_to_save, allow_unicode=True, default_flow_style=False, sort_keys=False)
    write_text_resilient(f, yaml_str)


def delete_client(client_id: str) -> None:
    """Deletes a client configuration and its logo."""
    if not client_id:
        return
    f = _clients_dir() / f"{client_id}.yaml"
    if f.exists():
        f.unlink()
    # also remove logo
    logo_path = get_client_logo_path(client_id)
    if logo_path and logo_path.exists():
        logo_path.unlink()


def get_client_logo_path(client_id: str) -> Path | None:
    """Finds the logo associated with a client (PNG, JPG, JPEG)."""
    if not client_id:
        return None
    _ensure_clients_dir()
    for ext in [".png", ".jpg", ".jpeg"]:
        p = _clients_dir() / f"{client_id}_logo{ext}"
        if p.exists():
            return p
    return None


def get_client_logo_bytes(client_id: str) -> tuple[bytes, str] | None:
    """Returns the logo bytes and filename if it exists."""
    p = get_client_logo_path(client_id)
    if p:
        try:
            with open(p, "rb") as file:
                return file.read(), p.name
        except Exception:
            pass
    return None


def save_client_logo(client_id: str, content: bytes, filename: str) -> None:
    """Saves a logo for a specific client."""
    if not client_id:
        raise ValueError("Client ID is required.")
    
    # Remove existing logos first
    existing = get_client_logo_path(client_id)
    if existing:
        existing.unlink()
        
    ext = Path(filename).suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg"]:
        raise ValueError("Only PNG and JPG/JPEG files are supported.")
        
    p = _clients_dir() / f"{client_id}_logo{ext}"
    write_bytes_resilient(p, content)


def remove_client_logo(client_id: str) -> None:
    """Removes the logo for a specific client."""
    existing = get_client_logo_path(client_id)
    if existing:
        existing.unlink()
