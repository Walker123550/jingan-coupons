from types import SimpleNamespace

import capture_addon


def test_unrelated_app_traffic_is_not_retained(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_addon, 'ROOT', tmp_path)
    addon=capture_addon.Capture()
    addon.response(SimpleNamespace(request=SimpleNamespace(pretty_url='https://unrelated.test/profile')))
    assert not addon.flows
    assert not (tmp_path/'index.json').exists()
