from datetime import datetime

import httpx
import pytest

from jingan import CN, JinganClient, make_signature, parse_location


def test_signature_matches_independent_crypto_fixture():
    # AES-CBC result independently verified with Node crypto.
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    import base64
    token='TEST_TOKEN'
    at=datetime(2026,10,13,7,30,tzinfo=CN)
    signature=make_signature(token,'0123456789abcdef',22,at)
    assert signature=='W4a769RTc3Em9mApPgfLhtj4l4uQf6Lo8datarmbFbE='
    decryptor=Cipher(algorithms.AES(b'0123456789abcdef'),modes.CBC(b'wealdger-shgyps0')).decryptor()
    padded=decryptor.update(base64.b64decode(signature))+decryptor.finalize()
    unpad=padding.PKCS7(128).unpadder()
    assert unpad.update(padded)+unpad.finalize()==b'TEST_TOKEN2026-10-13 0722'


@pytest.mark.parametrize('value',[{'latitude':31,'longitude':121},
    {'confirmed_actual_location':True,'latitude':float('nan'),'longitude':121},
    {'confirmed_actual_location':True,'latitude':91,'longitude':121}])
def test_location_cannot_use_unconfirmed_or_invalid_values(value):
    with pytest.raises(ValueError):
        parse_location(value)


def test_claim_one_request_and_payload_schema():
    calls=[]
    def handler(req):
        import json
        calls.append(req)
        body=json.loads(req.content)
        assert set(body)=={'rule_id','l','sign'}
        assert body['rule_id']==22
        return httpx.Response(200,json={'code':20000,'data':{'end_time':'2026-10-27 23:59:59'}})
    client=JinganClient({'Token':'SYNTHETIC_TEST'},transport=httpx.MockTransport(handler))
    try:
        result=client.submit(22,'31.0,121.0','0123456789abcdef',datetime(2026,10,13,7,30,tzinfo=CN))
    finally:
        client.close()
    assert len(calls)==1
    assert result['state']=='success'


def test_200_business_failure_is_not_success():
    client=JinganClient({'Token':'SYNTHETIC_TEST'},transport=httpx.MockTransport(lambda req:
        httpx.Response(200,json={'code':40013,'data':None})))
    try:
        result=client.submit(22,'31.0,121.0','0123456789abcdef')
    finally:
        client.close()
    assert result['state']=='signature_rejected'
    assert result['retry'] is False
