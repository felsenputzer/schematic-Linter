from schematic_linter.graph.model import ComponentKind


def test_graph_component_and_net_counts(project1_graph):
    assert len(project1_graph.components) == 107
    assert len(project1_graph.nets) == 78


def test_graph_classifies_known_refs(project1_graph):
    assert project1_graph.get_component("051405R1").kind == ComponentKind.RESISTOR
    assert project1_graph.get_component("051405C1").kind == ComponentKind.CAPACITOR
    assert project1_graph.get_component("U01").kind == ComponentKind.IC
    assert project1_graph.get_component("081708U01").kind == ComponentKind.IC  # multi-gate op-amp
    assert project1_graph.get_component("Y0001").kind == ComponentKind.CRYSTAL
    assert project1_graph.get_component("J01").kind == ComponentKind.CONNECTOR
    assert project1_graph.get_component("Q01").kind == ComponentKind.TRANSISTOR
    assert project1_graph.get_component("051405TP1").kind == ComponentKind.TESTPOINT
    assert project1_graph.get_component("051405FL1").kind == ComponentKind.INDUCTOR
    # BLK0002 has no useful ref-des prefix or comp_type keyword; must fall
    # back to the eBOM description ("IR LED ...") to be classified.
    assert project1_graph.get_component("BLK0002").kind == ComponentKind.DIODE


def test_graph_anchor_nets_from_explicit_netlist_tags(project1_graph):
    assert project1_graph.get_net("GND").is_ground
    assert project1_graph.get_net("IPSU_5V").is_power
    assert not project1_graph.get_net("GND").is_power


def test_graph_does_not_guess_anchors_from_net_name(project1_graph):
    # "RAW_1"/"RAW_2" look like supply rail names but are NOT tagged POWER
    # by the exporter -- they're actually feedback/base-drive nodes between
    # an op-amp output and a transistor base (see 081708R12/08R09). Only
    # the netlist's own NET_TYPE tag should ever set the anchor flags.
    assert not project1_graph.get_net("RAW_1").is_power
    assert not project1_graph.get_net("RAW_2").is_power


def test_component_values_parsed_from_ebom(project1_graph):
    r1 = project1_graph.get_component("051405R1")
    assert r1.value_source == "ebom"
    assert r1.value.magnitude == 5600.0

    zero_ohm = project1_graph.get_component("051405R8")
    assert zero_ohm.value.magnitude == 0.0


def test_component_without_meaningful_bom_value_is_not_applicable(project1_graph):
    # Diodes/ICs have a BOM "VALUE" column that holds a part variant
    # string, not an engineering quantity -- should not be treated as a
    # parse failure.
    diode = project1_graph.get_component("051405D1")
    assert diode.value_source == "not_applicable"
    assert diode.value is None


def test_unconnected_pin_tracked_on_component(project1_graph):
    u04 = project1_graph.get_component("U04")
    unconnected_names = {p.pin_name for p in u04.unconnected_pins}
    assert "GND" in unconnected_names
