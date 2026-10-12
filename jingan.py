"""Platform-specific single-account client based on observed requests and installed client."""
import argparse
import base64
import json
import math
import os
import sys
import fcntl
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from claim import load_request, target_time, wait_until

ROOT = Path(__file__).resolve().parent
CN = ZoneInfo('Asia/Shanghai')
BASE = 'https://shgypsapi.linkingfit.club/api'
IV = b'wealdger-shgyps0'


def make_signature(token, key, rule_id, at):
    key_bytes = key.encode('utf-8')
    if len(key_bytes) not in {16, 24, 32}:
        raise ValueError('Unexpected signing key length')
    value = (token + at.astimezone(CN).strftime('%Y-%m-%d %H') + str(rule_id)).encode('utf-8')
    padder = padding.PKCS7(128).padder()
    padded = padder.update(value) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key_bytes), modes.CBC(IV)).encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()


def parse_location(value):
    if not value.get('confirmed_actual_location'):
        raise ValueError('Actual location must be confirmed locally')
    lat, lng = float(value['latitude']), float(value['longitude'])
    if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise ValueError('Invalid actual location')
    return f'{lat},{lng}'


class JinganClient:
    def __init__(self, headers, proxy=None, transport=None):
        self.headers = dict(headers)
        self.client = httpx.Client(headers=self.headers, proxy=proxy, transport=transport, trust_env=False,
                                   follow_redirects=False, timeout=httpx.Timeout(8, connect=5))

    @property
    def token(self):
        return next((v for k,v in self.headers.items() if k.lower() == 'token'), '')

    def close(self):
        self.client.close()

    def get(self, path, params=None):
        response = self.client.get(BASE + path, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 20000:
            raise ValueError('Business response rejected; refresh login in mini-program')
        return data['data']

    def coupons(self):
        data = self.get('/v1/home/coupons', {'area_code': 5})
        return [dict(c, group=group) for group, items in data.items() if isinstance(items, list) for c in items]

    def profile(self):
        if not self.token:
            raise ValueError('Missing account token; manually log in and import an authenticated capture')
        return self.get('/v1/user/info')

    def signing_key(self):
        return self.get('/v1/app/sign')

    def submit(self, rule_id, actual_location, signing_key, now=None):
        now = now or datetime.now(CN)
        payload = {'rule_id': rule_id, 'l': actual_location,
                   'sign': make_signature(self.token, signing_key, rule_id, now)}
        try:
            response = self.client.post(BASE + '/v1/coupon', json=payload)
        except httpx.HTTPError:
            return {'state': 'transport_error_result_unknown', 'retry': False}
        if response.status_code == 429:
            return {'state': 'rate_limited', 'retry_after': response.headers.get('retry-after'), 'retry': False}
        if not 200 <= response.status_code < 300:
            return {'state': 'http_error', 'http_status': response.status_code, 'retry': False}
        try:
            result = response.json()
        except ValueError:
            return {'state': 'unknown', 'retry': False}
        code = result.get('code')
        data = result.get('data')
        message = str(result.get('message', ''))[:160]
        if self.token:
            message = message.replace(self.token, '<token>')
        message = message.replace(actual_location, '<location>')
        success = code == 20000 and isinstance(data, dict) and bool(data.get('end_time'))
        return {'state': 'success' if success else 'business_rejected' if code != 20000 else 'unknown',
                'code': code, 'message': message, 'retry': False}


def read_headers():
    session = ROOT / 'private/session.json'
    path = session if session.exists() else ROOT / 'private/flows/home-coupons/request.json'
    _, _, headers, _ = load_request(path)
    return headers


def import_session(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not data['url'].startswith(BASE + '/'):
        raise ValueError('Only this platform account capture is accepted')
    headers = data['headers']
    if isinstance(headers, dict):
        headers = list(headers.items())
    if not any(k.lower() == 'token' and bool(v) for k,v in headers):
        raise ValueError('This capture has no logged-in account token')
    target = ROOT / 'private/session.json'
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(target, 0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy', default='http://127.0.0.1:7897')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('doctor')
    importer = commands.add_parser('import-session')
    importer.add_argument('request_file')
    claim = commands.add_parser('claim')
    claim.add_argument('--coupon', type=int, required=True, help='Rule ID from list')
    claim.add_argument('--at', help='ISO time, or use coupon next_time')
    claim.add_argument('--location', default=str(ROOT / 'private/location.json'))
    claim.add_argument('--send', action='store_true')
    args = parser.parse_args()
    if args.command == 'import-session':
        import_session(args.request_file)
        print(json.dumps({'session_imported': True, 'token_printed': False}))
        return 0
    lock = None
    if args.command == 'claim' and args.send:
        lock = open(ROOT / 'private/claim.lock', 'a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            print(json.dumps({'state': 'another_claim_process_is_running'}))
            return 3
    client = None
    try:
        client = JinganClient(read_headers(), proxy=args.proxy)
        if args.command == 'list':
            coupons = client.coupons()
            print(json.dumps([{k:c.get(k) for k in ['id','name','money','lower_money','group','next_time','next_number']}
                              for c in coupons], ensure_ascii=False, indent=2))
            return 0
        profile = client.profile()
        eligible = bool(profile.get('is_address')) and bool(profile.get('is_certification'))
        # Preserve the same server-provided user delay used by the official client.
        if 'user_type_time' not in profile:
            raise ValueError('Account delay field missing; inspect profile schema before submitting')
        delay = max(0, float(profile['user_type_time']))
        if args.command == 'doctor':
            print(json.dumps({'logged_in': True, 'address_complete': bool(profile.get('is_address')),
                              'real_name_complete': bool(profile.get('is_certification')), 'delay_seconds': delay}))
            return 0
        if not eligible:
            raise ValueError('Complete real name and address in official mini-program first')
        coupon = next((c for c in client.coupons() if c['id'] == args.coupon), None)
        if not coupon:
            raise ValueError('Coupon rule does not exist in current official list')
        release = target_time(args.at or coupon['next_time'])
        target = release + timedelta(seconds=delay)
        if release.timestamp() < datetime.now(CN).timestamp() - 1:
            raise ValueError('Release time has passed')
        location = parse_location(json.loads(Path(args.location).read_text(encoding='utf-8')))
        # Dry run validates signing without transmitting a claim.
        key = client.signing_key()
        make_signature(client.token, key, args.coupon, datetime.now(CN))
        print(json.dumps({'mode': 'send' if args.send else 'dry_run', 'coupon_id': args.coupon,
                          'amount': coupon['money'], 'at': target.isoformat(), 'delay_seconds': delay,
                          'signature_validated': True, 'actual_location_configured': True}, ensure_ascii=False))
        if not args.send:
            return 0
        # Refresh key/profile shortly before launch. No claim retries.
        preparation = target - timedelta(seconds=20)
        if preparation > datetime.now(CN):
            wait_until(preparation)
            latest = client.profile()
            if not latest.get('is_address') or not latest.get('is_certification') or float(latest.get('user_type_time', -1)) != delay:
                raise ValueError('Account eligibility changed; cancel submission')
            key = client.signing_key()
        wait_until(target)
        result = client.submit(args.coupon, location, key)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['state'] == 'success' else 2
    finally:
        if client:
            client.close()
        if lock:
            lock.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, httpx.HTTPError, StopIteration):
        print(json.dumps({'state': 'configuration_or_login_required', 'hint': 'Check login, eligibility, location and schedule locally'}), file=sys.stderr)
        sys.exit(1)
