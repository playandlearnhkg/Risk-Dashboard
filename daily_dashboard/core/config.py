"""
core/config.py — Configuration and secrets loading.
===================================================

One rule: nothing else in the codebase reads config.yaml or os.environ
directly. Everything goes through `load_config()` and the `Config` wrapper, so
there is exactly one place where a missing key or a bad path is diagnosed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env(path: Path = ENV_PATH) -> dict[str, str]:
    """
    Minimal .env reader.

    Deliberately not python-dotenv: this needs to parse five lines of
    KEY=value, and a dependency that must be installed before the program can
    tell you what is misconfigured is a bad trade. Real environment variables
    win over the file, so containers and CI can override without editing it.
    """
    values: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")

    for key in list(values):
        if key in os.environ:
            values[key] = os.environ[key]
    for key, value in os.environ.items():
        values.setdefault(key, value)
    return values


@dataclass
class Config:
    """Dict-backed config with dotted-path access and resolved paths."""

    raw: dict[str, Any]
    env: dict[str, str] = field(default_factory=dict)
    root: Path = PROJECT_ROOT

    # -- lookup ------------------------------------------------------------

    def get(self, dotted: str, default: Any = None) -> Any:
        """
        Fetch a nested value by dotted path.

            cfg.get("regime.capital_status.high_above")
        """
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted: str) -> Any:
        """Same as get(), but a missing key is a startup error, not a None."""
        sentinel = object()
        value = self.get(dotted, sentinel)
        if value is sentinel:
            raise KeyError(f"Required config key missing from config.yaml: {dotted}")
        return value

    # -- secrets -----------------------------------------------------------

    def secret(self, name: str, default: str | None = None) -> str | None:
        """Read a secret from .env / environment. Never logged by callers."""
        return self.env.get(name, default)

    def has_secret(self, name: str) -> bool:
        value = self.env.get(name)
        return bool(value and not value.startswith("your_"))

    # -- paths -------------------------------------------------------------

    def path(self, dotted: str) -> Path:
        """
        Resolve a configured path relative to the project root.

        Paths in config.yaml are written relative to daily_dashboard/ so the
        project can be cloned anywhere; this turns them absolute exactly once.
        """
        value = self.require(dotted)
        p = Path(value)
        return p if p.is_absolute() else (self.root / p).resolve()

    def ensure_dirs(self) -> None:
        """Create the writable directories the run needs."""
        for key in ("paths.cache_dir", "paths.output_dir"):
            self.path(key).mkdir(parents=True, exist_ok=True)
        self.path("paths.database").parent.mkdir(parents=True, exist_ok=True)

    # -- SEC compliance ----------------------------------------------------

    def sec_user_agent(self) -> str:
        """
        SEC requires a User-Agent identifying the requester with a real email.
        Requests without one get blocked, so this fails loudly at startup
        rather than producing a confusing 403 deep inside a fetch loop.
        """
        ua = self.secret("SEC_USER_AGENT")
        if not ua or "@" not in ua:
            raise RuntimeError(
                "SEC_USER_AGENT must be set in .env and contain a contact email.\n"
                '  Example: SEC_USER_AGENT="Meridian Research you@example.com"\n'
                "SEC blocks requests that do not identify the caller. Run with "
                "--no-filings to skip EDGAR entirely."
            )
        return ua


_cached: Config | None = None


def load_config(path: Path = CONFIG_PATH, reload: bool = False) -> Config:
    """Load and cache config.yaml plus .env."""
    global _cached
    if _cached is not None and not reload:
        return _cached

    if not path.exists():
        raise FileNotFoundError(f"config.yaml not found at {path}")

    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}

    _cached = Config(raw=raw, env=_load_env(), root=path.parent)
    return _cached
