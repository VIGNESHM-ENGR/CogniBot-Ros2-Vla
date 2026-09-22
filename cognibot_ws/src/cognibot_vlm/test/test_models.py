from cognibot_vlm.models import LOADED, LOADING, UNLOADED, UNLOADING, vlm_state


def test_nothing_running_is_unloaded():
    assert vlm_state({"running": []}) == (UNLOADED, "")
    assert vlm_state({}) == (UNLOADED, "")


def test_llama_swap_states_map_to_model_states():
    entry = {"model": "qwen3-vl-4b-gpu", "name": "Qwen3-VL-4B (all layers on GPU)"}
    assert vlm_state({"running": [{**entry, "state": "starting"}]}) == (LOADING, entry["name"])
    assert vlm_state({"running": [{**entry, "state": "ready"}]})[0] == LOADED
    assert vlm_state({"running": [{**entry, "state": "stopping"}]})[0] == UNLOADING
