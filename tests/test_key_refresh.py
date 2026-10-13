import httpx

from jingan import JinganClient


def test_signing_key_rejection_refreshes_once_without_infinite_loop():
    requests=[]
    def handler(req):
        requests.append((req.method, req.url.path))
        if req.method=='GET':
            return httpx.Response(200,json={'code':20000,'data':'fedcba9876543210'})
        return httpx.Response(200,json={'code':40013,'data':None})
    client=JinganClient({'Token':'TEST'},transport=httpx.MockTransport(handler))
    try:
        result=client.submit_with_key_refresh(4,'31.0,121.0','0123456789abcdef')
    finally:client.close()
    assert requests==[('POST','/api/v1/coupon'),('GET','/api/v1/app/sign'),('POST','/api/v1/coupon')]
    assert result['attempts']==2 and result['state']=='signature_rejected'


def test_sold_out_or_unknown_busy_code_does_not_trigger_key_retry():
    for code, message in [(40000,'消费券已经被领取完'),(59999,'太多人抢了，请重试')]:
        requests=[]
        def handler(req):
            requests.append(req)
            return httpx.Response(200,json={'code':code,'message':message,'data':None})
        client=JinganClient({'Token':'TEST'},transport=httpx.MockTransport(handler))
        try:
            result=client.submit_with_key_refresh(4,'31.0,121.0','0123456789abcdef')
        finally:client.close()
        assert len(requests)==1 and result['attempts']==1
