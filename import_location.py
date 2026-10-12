"""Import actual wx.getLocation coordinates from its observed nearby-venue request."""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / 'private/flows/businesses/request.json'
    request = json.loads(path.read_text(encoding='utf-8'))
    parts = urlsplit(request['url'])
    if parts.hostname != 'shgypsapi.linkingfit.club' or parts.path != '/api/v1/businesses':
        raise ValueError('Wrong platform location source')
    query = parse_qs(parts.query)
    lat, lng = float(query['latitude'][0]), float(query['longitude'][0])
    captured_at = request.get('captured_at_unix')
    location = {'latitude':lat,'longitude':lng,'confirmed_actual_location':True,
                'source':'Observed nearby-venue request; installed home client assigns successful wx.getLocation coordinates',
                'captured_at':datetime.fromtimestamp(captured_at, ZoneInfo('Asia/Shanghai')).isoformat() if captured_at else None}
    from jingan import parse_location
    parse_location(location)
    output = ROOT / 'private/location.json'
    output.write_text(json.dumps(location,ensure_ascii=False,indent=2),encoding='utf-8')
    os.chmod(output,0o600)
    print(json.dumps({'actual_location_imported':True,'coordinates_printed':False}))


if __name__ == '__main__':
    main()
