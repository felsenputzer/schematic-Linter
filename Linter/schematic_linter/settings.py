"""User settings: which checks are on, threshold overrides, and the GUI's
last-used folders.

Saved as JSON in the per-user config folder (``%APPDATA%\\SchematicLinter``
on Windows) so the GUI remembers them between sessions. The same JSON
format doubles as a shareable "check profile" (GUI: *Save profile...* /
*Load profile...*; CLI: ``--profile FILE``), so a team can agree on one
set of checks and thresholds.

Disabled checks are stored (rather than enabled ones) so a check added in a
later version of the tool is on by default for everyone.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from . import config

SETTINGS_FILENAME = "settings.json"

Number = Union[int, float]


@dataclass
class LintSettings:
    disabled_rules: List[str] = field(default_factory=list)
    thresholds: Dict[str, Number] = field(default_factory=dict)
    # GUI-only conveniences (ignored when loading a profile):
    project_dir: str = ""
    output_dir: str = ""
    open_report: bool = True

    def enabled_rules(self, all_rule_ids: List[str]) -> Set[str]:
        disabled = set(self.disabled_rules)
        return {rule_id for rule_id in all_rule_ids if rule_id not in disabled}

    @classmethod
    def from_dict(cls, data: dict) -> "LintSettings":
        """Builds settings from (possibly hand-edited / older) JSON, dropping
        anything unknown or invalid instead of failing."""

        settings = cls()
        if not isinstance(data, dict):
            return settings
        rules = data.get("disabled_rules")
        if isinstance(rules, list):
            settings.disabled_rules = [r for r in rules if isinstance(r, str)]
        thresholds = data.get("thresholds")
        if isinstance(thresholds, dict):
            for key, value in thresholds.items():
                try:
                    settings.thresholds.update(config.validate_thresholds({key: value}))
                except ValueError:
                    pass
        for key in ("project_dir", "output_dir"):
            if isinstance(data.get(key), str):
                setattr(settings, key, data[key])
        if isinstance(data.get("open_report"), bool):
            settings.open_report = data["open_report"]
        return settings

    def to_dict(self) -> dict:
        return asdict(self)

    def profile_dict(self) -> dict:
        """Only the check configuration -- what's worth sharing with others."""

        return {"disabled_rules": sorted(self.disabled_rules), "thresholds": dict(self.thresholds)}


def settings_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "SchematicLinter"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SchematicLinter"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "schematic-linter"


def _read_json(path: Path) -> Optional[dict]:
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_settings(path: Optional[Path] = None) -> LintSettings:
    """Loads the saved settings; returns defaults if there are none yet or
    the file is unreadable/corrupt."""

    data = _read_json(path or settings_dir() / SETTINGS_FILENAME)
    return LintSettings.from_dict(data) if data is not None else LintSettings()


def save_settings(settings: LintSettings, path: Optional[Path] = None) -> None:
    """Best effort: a read-only profile folder must not break the tool."""

    path = Path(path or settings_dir() / SETTINGS_FILENAME)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)
    except OSError:
        pass


def load_profile(path: Path) -> LintSettings:
    """Reads a shared check profile; raises ``ValueError`` if it's not one."""

    data = _read_json(path)
    if not isinstance(data, dict) or not ({"disabled_rules", "thresholds"} & data.keys()):
        raise ValueError(f"'{path}' is not a schematic-linter profile (expected 'disabled_rules'/'thresholds').")
    profile = LintSettings.from_dict(data)
    return LintSettings(disabled_rules=profile.disabled_rules, thresholds=profile.thresholds)


def save_profile(settings: LintSettings, path: Path) -> None:
    """Writes the check configuration only; raises ``OSError`` on failure."""

    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(settings.profile_dict(), f, indent=2)
