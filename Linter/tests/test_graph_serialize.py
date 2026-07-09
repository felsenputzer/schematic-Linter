from schematic_linter.graph.serialize import load_graph, save_graph


def test_graph_round_trips_through_json(project1_graph, tmp_path):
    out_path = tmp_path / "graph.json"
    save_graph(project1_graph, out_path, metadata={"project_name": "Projekt1"})
    assert out_path.exists()

    reloaded = load_graph(out_path)
    assert len(reloaded.components) == len(project1_graph.components)
    assert len(reloaded.nets) == len(project1_graph.nets)

    original = project1_graph.get_component("051405R1")
    restored = reloaded.get_component("051405R1")
    assert restored.kind == original.kind
    assert restored.value.magnitude == original.value.magnitude

    # connectivity must be preserved, not just node lists
    assert sorted(reloaded.nets_of("051405R1")) == sorted(project1_graph.nets_of("051405R1"))
