import pytest

from schematic_linter.parsers.flatten_check import NonFlattenedNetlistError, check_flattened
from schematic_linter.parsers.netlist_parser import parse_netlist


def test_flatten_check_passes_on_known_good_sample(project1_netlist_path):
    records = parse_netlist(project1_netlist_path)
    result = check_flattened(records)
    assert result.is_flattened is True


def test_flatten_check_rejects_empty_record_list():
    with pytest.raises(NonFlattenedNetlistError):
        check_flattened([])


def test_flatten_check_does_not_false_positive_on_multi_gate_ic(project1_netlist_path):
    """Regression guard: a naive "ref-des maps to >1 instance id" heuristic
    was considered and rejected during design because it misfires on this
    very sample (the dual op-amp / connectors have per-gate/per-pin
    instance ids). This test documents that the real sample must keep
    passing, whatever the eventual heuristic looks like.
    """

    records = parse_netlist(project1_netlist_path)
    result = check_flattened(records)
    assert result.is_flattened is True
