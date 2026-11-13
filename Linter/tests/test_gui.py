"""Drives the real tkinter window (no mocking of the analysis). Skipped
where tkinter or a display isn't available."""

import time

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app(monkeypatch):
    from schematic_linter import gui
    from schematic_linter.settings import LintSettings

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    root.withdraw()
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, text, **kw: errors.append((title, text)))
    instance = gui.LinterApp(root, settings=LintSettings(open_report=False), persist=False)
    instance.dialog_errors = errors
    yield instance
    root.destroy()


def _pump_until(app, condition, timeout=60.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "GUI did not finish in time"
        app.root.update()
        time.sleep(0.02)


def test_gui_full_run(app, project1_dir, tmp_path):
    app.project_var.set(str(project1_dir))
    app.output_var.set(str(tmp_path))
    app._refresh_project_info()
    assert app.project_ok
    assert str(app.run_btn.cget("state")) == "normal"

    app.rule_vars["floating_single_pin_net"].set(False)
    app.run_checks()
    assert str(app.run_btn.cget("state")) == "disabled"  # no double runs
    _pump_until(app, lambda: app.last_exit_code is not None)

    assert app.last_exit_code == 1  # Projekt1 has one known Error finding
    assert (tmp_path / "report.html").exists()
    assert not any(f.rule_id == "floating_single_pin_net" for f in app.last_result.findings)
    assert str(app.open_report_btn.cget("state")) == "normal"
    assert not app.dialog_errors


def test_gui_rejects_folder_without_netlist(app, tmp_path):
    app.project_var.set(str(tmp_path))
    app._refresh_project_info()
    assert not app.project_ok
    assert str(app.run_btn.cget("state")) == "disabled"
    assert "No netlist" in app.file_labels["netlist"].cget("text")


def test_gui_invalid_threshold_blocks_run(app, project1_dir):
    app.project_var.set(str(project1_dir))
    app._refresh_project_info()
    app.threshold_vars["SIBLING_GROUP_MIN_SIZE"].set("two")
    app.run_checks()
    assert app.worker is None
    assert app.dialog_errors and app.dialog_errors[0][0] == "Invalid threshold"


def test_gui_settings_reflect_widgets(app):
    app.rule_vars["unloaded_divider"].set(False)
    app.threshold_vars["BULK_CAP_RATIO"].set("25")
    app.threshold_vars["ZERO_OHM_THRESHOLD"].set("0,5")  # comma decimal = default, not stored
    settings = app.current_settings()
    assert settings.disabled_rules == ["unloaded_divider"]
    assert settings.thresholds == {"BULK_CAP_RATIO": 25.0}
