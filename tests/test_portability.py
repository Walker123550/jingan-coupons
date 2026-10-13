import json

import httpx
import pytest

import jingan


def test_fresh_checkout_can_list_without_private_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(jingan, 'ROOT', tmp_path)
    headers = dict(jingan.read_headers())
    assert headers['WeChatAppId'] == '5' and headers['Token'] == ''
    assert jingan.resolve_proxy() is None


def test_proxy_precedence_and_explicit_direct(tmp_path, monkeypatch):
    monkeypatch.setattr(jingan, 'ROOT', tmp_path)
    monkeypatch.delenv('JINGAN_PROXY', raising=False)
    (tmp_path/'private').mkdir()
    (tmp_path/'private/config.json').write_text(json.dumps({'proxy':'http://127.0.0.1:8888'}))
    assert jingan.resolve_proxy() == 'http://127.0.0.1:8888'
    monkeypatch.setenv('JINGAN_PROXY','http://127.0.0.1:9999')
    assert jingan.resolve_proxy() == 'http://127.0.0.1:9999'
    assert jingan.resolve_proxy('direct') is None


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1])
def test_invalid_account_delay_cannot_skip_platform_rule(value):
    with pytest.raises(ValueError):
        jingan.account_delay(value)


def test_malformed_success_response_is_unknown():
    client=jingan.JinganClient({'Token':'TEST'},transport=httpx.MockTransport(lambda req:httpx.Response(200,json=[])))
    try:
        assert client.submit(4,'31.0,121.0','0123456789abcdef')['state']=='unknown'
    finally:client.close()


def test_empty_coupon_bag_is_supported():
    client=jingan.JinganClient({'Token':'TEST'},transport=httpx.MockTransport(lambda req:
        httpx.Response(200,json={'code':20000,'data':{'list':None,'pagination':{'total':0}}})))
    try:
        assert client.bag()=={'total':0,'coupons':[]}
    finally:client.close()
