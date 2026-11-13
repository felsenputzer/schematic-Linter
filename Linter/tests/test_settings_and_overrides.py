import json

import pytest

from schematic_linter import config
from schematic_linter.pipeline import run_pipeline
from schematic_linter.rules import available_rules
from schematic_linter.settings import LintSettings, load_profile, load_settings, save_profile, save_settings


def test_every_rule_has_gui_metadata():
    rules = available_rules()
    assert len(rules) >= 13
    for rule in rules:
        assert rule.name and rule.name != rule.rule_id, rule.rule_id
        assert rule.description, rule.rule_id
    assert [r.rule_id for r in rules if r.requires_bom] == ["missing_decoupling"]


def test_every_threshold_names_existing_rules():
    rule_ids = {r.rule_id for r in available_rules()}
    for spec in config.TUNABLE_THRESHOLDS:
        assert set(spec.used_by) <= rule_ids, spec.key
        assert spec.minimum <= spec.default <= spec.maximum


def test_override_applies_and_restores():
    before = config.SIBLING_GROUP_MIN_SIZE
    with config.override({"SIBLING_GROUP_MIN_SIZE": "7"}):
        assert config.SIBLING_GROUP_MIN_SIZE == 7
    assert config.SIBLING_GROUP_MIN_SIZE == before


@pytest.mark.parametrize(
    "values",
    [{"NOPE": 1}, {"SIBLING_GROUP_MIN_SIZE": "abc"}, {"SIBLING_GROUP_MIN_SIZE": 2.5}, {"ZERO_OHM_THRESHOLD": -1}],
)
def test_invalid_thresholds_rejected(values):
    with pytest.raises(ValueError):
        config.validate_thresholds(values)


def test_pipeline_threshold_override_changes_findings(project1_dir, tmp_path):
    default = run_pipeline(project1_dir, tmp_path / "a")
    assert any(f.rule_id == "sibling_pin_mismatch" for f in default.findings)

    strict = run_pipeline(project1_dir, tmp_path / "b", thresholds={"SIBLING_GROUP_MIN_SIZE": 50})
    assert not any(f.rule_id == "sibling_pin_mismatch" for f in strict.findings)
    assert "Non-default thresholds" in strict.report_path.read_text(encoding="utf-8")
    assert config.SIBLING_GROUP_MIN_SIZE == 3  # restored after the run


def test_pipeline_runs_only_enabled_rules(project1_dir, tmp_path):
    result = run_pipeline(project1_dir, tmp_path, enabled_rules={"power_pin_miswire"})
    assert result.findings and {f.rule_id for f in result.findings} == {"power_pin_miswire"}
    html = result.report_path.read_text(encoding="utf-8")
    assert "Checks disabled for this run" in html


def test_settings_roundtrip_and_corrupt_file(tmp_path):
    path = tmp_path / "settings.json"
    settings = LintSettings(
        disabled_rules=["floating_single_pin_net"], thresholds={"BULK_CAP_RATIO": 20.0},
        project_dir="C:\\Designs\\Board", output_dir="", open_report=False,
    )
    save_settings(settings, path)
    assert load_settings(path) == settings

    path.write_text("{ not json", encoding="utf-8")
    assert load_settings(path) == LintSettings()


def test_settings_drop_invalid_entries():
    loaded = LintSettings.from_dict(
        {"disabled_rules": ["a", 3], "thresholds": {"BULK_CAP_RATIO": "x", "ZERO_OHM_THRESHOLD": 1}, "open_report": "yes"}
    )
    assert loaded.disabled_rules == ["a"]
    assert loaded.thresholds == {"ZERO_OHM_THRESHOLD": 1.0}
    assert loaded.open_report is True


def test_profile_contains_only_check_configuration(tmp_path):
    path = tmp_path / "team.json"
    save_profile(LintSettings(disabled_rules=["b", "a"], thresholds={"BULK_CAP_RATIO": 5}, project_dir="secret"), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"disabled_rules": ["a", "b"], "thresholds": {"BULK_CAP_RATIO": 5}}
    assert load_profile(path).disabled_rules == ["a", "b"]

    other = tmp_path / "other.json"
    other.write_text('{"foo": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(other)
