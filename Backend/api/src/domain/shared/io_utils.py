"""Ecriture fichier resiliente.

Le lecteur reseau utilise pour heberger cette application (partage mappe,
scanne en continu par l'antivirus/EDR du poste) provoque occasionnellement
des ``PermissionError``/``OSError`` transitoires sur des fichiers pourtant
tout juste crees. Ces utilitaires reessaient l'ecriture quelques fois avant
d'abandonner, ce qui evite qu'une simple sauvegarde de configuration ou de
KID genere ne fasse planter l'application.
"""

from __future__ import annotations

import time
from pathlib import Path


def write_text_resilient(path: Path, text: str, encoding: str = "utf-8", attempts: int = 5, delay: float = 0.25) -> None:
    last_exc: OSError | None = None
    for attempt in range(attempts):
        try:
            path.write_text(text, encoding=encoding)
            return
        except OSError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(delay * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def write_bytes_resilient(path: Path, data: bytes, attempts: int = 5, delay: float = 0.25) -> None:
    last_exc: OSError | None = None
    for attempt in range(attempts):
        try:
            path.write_bytes(data)
            return
        except OSError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(delay * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def ensure_dir_resilient(path: Path, attempts: int = 5, delay: float = 0.25) -> None:
    """Equivalent de ``path.mkdir(parents=True, exist_ok=True)`` tolerant
    aux ``FileExistsError``/``OSError`` transitoires : sur un partage reseau,
    l'incoherence passagere du cache metadonnees SMB peut faire echouer
    ``exist_ok=True`` alors meme que le dossier existe deja."""
    last_exc: OSError | None = None
    for attempt in range(attempts):
        try:
            path.mkdir(parents=True, exist_ok=True)
            return
        except OSError as exc:
            last_exc = exc
            if path.is_dir():
                return
            if attempt < attempts - 1:
                time.sleep(delay * (attempt + 1))
    assert last_exc is not None
    raise last_exc
