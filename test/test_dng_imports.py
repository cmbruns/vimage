import importlib


def test_dng_state_and_image_data_import_without_cycle():
    dng = importlib.import_module("vmg.dng")
    image_data = importlib.import_module("vmg.image_data")
    state = importlib.import_module("vmg.state")

    assert dng.DngImage is not None
    assert image_data.ImageData is not None
    assert state.ViewState is not None
