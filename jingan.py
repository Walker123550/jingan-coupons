"""Platform-specific single-account client based on observed requests and installed client."""
import argparse
import base64
import json
import math
import os
import sys
import fcntl
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from claim import load_request, target_time, wait_until

ROOT = Path(__file__).resolve().parent
CN = ZoneInfo('Asia/Shanghai')
BASE = 'https://shgypsapi.linkingfit.club/api'
IV = b'wealdger-shgyps0'
RUN_LOG = None


class RunLog:
    def __init__(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / (datetime.now(CN).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.jsonl')
        self.path.touch(mode=0o600)

    def record(self, event, **fields):
        # Callers supply only operational metadata, never headers or request bodies.
        row = {'time': datetime.now(CN).isoformat(timespec='milliseconds'), 'event': event, **fields}
        with self.path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
            output.flush()


def audit(event, **fields):
    if RUN_LOG:
        RUN_LOG.record(event, **fields)


def validate_schedule(release, now, send, explicit_time):
    if release.timestamp() < now.timestamp() - 1:
        raise ValueError('Release time has passed')
    if send and not explicit_time and release.astimezone(CN).date() != now.astimezone(CN).date():
        raise ValueError('Next release is not today; refusing to silently wait for another day')


def resolve_proxy(explicit=None):
    config_path = ROOT / 'private/config.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError('Invalid local network configuration')
    value = explicit if explicit is not None else os.environ.get('JINGAN_PROXY', config.get('proxy'))
    if not value or str(value).lower() == 'direct':
        return None
    if not isinstance(value, str):
        raise ValueError('Invalid local network configuration')
    parts = urlsplit(value)
    if parts.scheme not in {'http', 'https'} or not parts.hostname:
        raise ValueError('Proxy must be an HTTP/HTTPS URL or direct')
    return value


def account_delay(value):
    delay = float(value)
    if not math.isfinite(delay) or delay < 0:
        raise ValueError('Invalid account delay returned by platform')
    return delay


def latest_run_log(folder):
    files = sorted(folder.glob('*.jsonl'), key=lambda path:path.stat().st_mtime_ns, reverse=True)
    for path in files:
        try:
            with path.open(encoding='utf-8') as source:
                first = json.loads(source.readline())
            if first.get('command') == 'claim' and first.get('send'):
                return path
        except (ValueError, OSError):
            continue
    return files[0] if files else None


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
        audit('api_started', method='GET', path=path)
        response = self.client.get(BASE + path, params=params)
        audit('api_http_received', method='GET', path=path, http_status=response.status_code)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('Unexpected API response shape')
        audit('api_received', method='GET', path=path, http_status=response.status_code, code=data.get('code'))
        if data.get('code') != 20000:
            raise ValueError('Business response rejected; refresh login in mini-program')
        return data['data']

    def coupons(self):
        data = self.get('/v1/home/coupons', {'area_code': 5})
        if not isinstance(data, dict):
            raise ValueError('Unexpected API response shape')
        return [dict(c, group=group) for group, items in data.items() if isinstance(items, list) for c in items]

    def profile(self):
        if not self.token:
            raise ValueError('Missing account token; manually log in and import an authenticated capture')
        result = self.get('/v1/user/info')
        if not isinstance(result, dict):
            raise ValueError('Unexpected API response shape')
        return result

    def bag(self):
        if not self.token:
            raise ValueError('Missing account token; manually log in and import an authenticated capture')
        data = self.get('/v1/user/coupon')
        fields = ['rule_id', 'name', 'money', 'lower_money', 'status', 'start_time', 'end_time']
        return {'total': data.get('pagination', {}).get('total'),
                'coupons': [{k:c[k] for k in fields if k in c} for c in (data.get('list') or [])]}

    def signing_key(self):
        key = self.get('/v1/app/sign')
        if not isinstance(key, str) or len(key.encode('utf-8')) not in {16, 24, 32}:
            raise ValueError('Unexpected API response shape')
        return key

    def submit(self, rule_id, actual_location, signing_key, now=None, attempt=1):
        now = now or datetime.now(CN)
        payload = {'rule_id': rule_id, 'l': actual_location,
                   'sign': make_signature(self.token, signing_key, rule_id, now)}
        started = time.monotonic()
        audit('claim_submitted', coupon_id=rule_id, attempt=attempt)
        try:
            response = self.client.post(BASE + '/v1/coupon', json=payload)
        except httpx.HTTPError:
            audit('claim_transport_error', coupon_id=rule_id, elapsed_ms=round((time.monotonic()-started)*1000), result_unknown=True)
            return {'state': 'transport_error_result_unknown', 'retry': False}
        audit('claim_received', coupon_id=rule_id, attempt=attempt, http_status=response.status_code, elapsed_ms=round((time.monotonic()-started)*1000))
        if response.status_code == 429:
            return {'state': 'rate_limited', 'retry_after': response.headers.get('retry-after'), 'retry': False}
        if not 200 <= response.status_code < 300:
            return {'state': 'http_error', 'http_status': response.status_code, 'retry': False}
        try:
            result = response.json()
        except ValueError:
            return {'state': 'unknown', 'retry': False}
        if not isinstance(result, dict):
            return {'state': 'unknown', 'retry': False}
        code = result.get('code')
        data = result.get('data')
        message = str(result.get('message', ''))[:160]
        if self.token:
            message = message.replace(self.token, '<token>')
        message = message.replace(actual_location, '<location>')
        for value in [*actual_location.split(','), signing_key, payload['sign']]:
            if value:
                message = message.replace(value, '<private>')
        success = code == 20000 and isinstance(data, dict) and bool(data.get('end_time'))
        rejected = 'signature_rejected' if code == 40013 else 'sold_out' if code == 40000 and '领取完' in message else 'business_rejected'
        return {'state': 'success' if success else rejected if code != 20000 else 'unknown',
                'code': code, 'message': message, 'retry': False}

    def submit_with_key_refresh(self, rule_id, actual_location, key):
        result = self.submit(rule_id, actual_location, key)
        result['attempts'] = 1
        if result.get('code') == 40013:
            # Match the installed official client's one-time signing-key refresh.
            audit('signing_key_refresh_required', coupon_id=rule_id, code=40013)
            fresh_key = self.signing_key()
            result = self.submit(rule_id, actual_location, fresh_key, attempt=2)
            result['attempts'] = 2
        return result


def read_headers():
    session = ROOT / 'private/session.json'
    path = session if session.exists() else ROOT / 'private/flows/home-coupons/request.json'
    if not path.exists():
        return [('WeChatAppId', '5'), ('Content-Type', 'application/json'), ('Token', '')]
    _, _, headers, _ = load_request(path)
    return headers


def import_session(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    parts = urlsplit(data['url'])
    if parts.scheme != 'https' or parts.hostname != 'shgypsapi.linkingfit.club' or parts.username or parts.password or not parts.path.startswith('/api/'):
        raise ValueError('Only this platform account capture is accepted')
    headers = data['headers']
    if isinstance(headers, dict):
        headers = list(headers.items())
    if not any(k.lower() == 'token' and bool(v) for k,v in headers):
        raise ValueError('This capture has no logged-in account token')
    target = ROOT / 'private/session.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    allowed = {'token', 'wechatappid', 'user-agent', 'referer', 'content-type', 'accept', 'accept-language'}
    normalized = {'url': BASE + '/v1/user/info', 'method': 'GET',
                  'headers': [[k,v] for k,v in headers if k.lower() in allowed], 'body_base64': ''}
    target.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(target, 0o600)


def main():
    global RUN_LOG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy', default=None, help='HTTP/HTTPS proxy or direct; otherwise use JINGAN_PROXY/local config')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    commands.add_parser('doctor')
    commands.add_parser('bag')
    logs = commands.add_parser('logs')
    logs.add_argument('--last', type=int, default=20)
    importer = commands.add_parser('import-session')
    importer.add_argument('request_file')
    claim = commands.add_parser('claim')
    claim.add_argument('--coupon', type=int, required=True, help='Rule ID from list')
    claim.add_argument('--at', help='ISO time, or use coupon next_time')
    claim.add_argument('--location', default=str(ROOT / 'private/location.json'))
    claim.add_argument('--send', action='store_true')
    args = parser.parse_args()
    if args.command == 'logs':
        latest = latest_run_log(ROOT / 'private/runs')
        if not latest:
            print(json.dumps({'state': 'no_saved_run_logs'}))
            return 0
        print(json.dumps({'log_file':str(latest)}, ensure_ascii=False))
        for line in latest.read_text(encoding='utf-8').splitlines()[-max(1, args.last):]:
            print(line)
        return 0
    RUN_LOG = RunLog(ROOT / 'private/runs')
    audit('run_started', command=args.command, send=bool(getattr(args, 'send', False)), coupon_id=getattr(args, 'coupon', None))
    print(json.dumps({'log_file': str(RUN_LOG.path)}, ensure_ascii=False))
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
            audit('run_rejected', reason='another_claim_process_is_running')
            return 3
    client = None
    try:
        client = JinganClient(read_headers(), proxy=resolve_proxy(args.proxy))
        if args.command == 'list':
            coupons = client.coupons()
            print(json.dumps([{k:c.get(k) for k in ['id','name','money','lower_money','group','next_time','next_number']}
                              for c in coupons], ensure_ascii=False, indent=2))
            return 0
        if args.command == 'bag':
            print(json.dumps(client.bag(), ensure_ascii=False, indent=2))
            audit('bag_checked')
            return 0
        profile = client.profile()
        eligible = bool(profile.get('is_address')) and bool(profile.get('is_certification'))
        # Preserve the same server-provided user delay used by the official client.
        if 'user_type_time' not in profile:
            raise ValueError('Account delay field missing; inspect profile schema before submitting')
        delay = account_delay(profile['user_type_time'])
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
        validate_schedule(release, datetime.now(CN), args.send, args.at is not None)
        audit('schedule_selected', release=release.isoformat(), target=target.isoformat(), delay_seconds=delay)
        location = parse_location(json.loads(Path(args.location).read_text(encoding='utf-8')))
        # Dry run validates signing without transmitting a claim.
        key = client.signing_key()
        make_signature(client.token, key, args.coupon, datetime.now(CN))
        print(json.dumps({'mode': 'send' if args.send else 'dry_run', 'coupon_id': args.coupon,
                          'amount': coupon['money'], 'at': target.isoformat(), 'delay_seconds': delay,
                          'signature_validated': True, 'actual_location_configured': True}, ensure_ascii=False))
        if not args.send:
            audit('dry_run_completed')
            return 0
        # Refresh key/profile shortly before launch. No claim retries.
        preparation = target - timedelta(seconds=20)
        if preparation > datetime.now(CN):
            audit('waiting_for_preflight', at=preparation.isoformat())
            wait_until(preparation)
            latest = client.profile()
            if not latest.get('is_address') or not latest.get('is_certification') or account_delay(latest.get('user_type_time', -1)) != delay:
                raise ValueError('Account eligibility changed; cancel submission')
            key = client.signing_key()
        audit('waiting_for_release', at=target.isoformat())
        wait_until(target)
        result = client.submit_with_key_refresh(args.coupon, location, key)
        audit('claim_result', **result)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['state'] == 'success' else 2
    finally:
        if client:
            client.close()
        if lock:
            lock.close()


def report_error(exc):
    known = {
        'Release time has passed',
        'Next release is not today; refusing to silently wait for another day',
        'Business response rejected; refresh login in mini-program',
        'Missing account token; manually log in and import an authenticated capture',
        'Account delay field missing; inspect profile schema before submitting',
        'Complete real name and address in official mini-program first',
        'Coupon rule does not exist in current official list',
        'Actual location must be confirmed locally',
        'Invalid actual location',
        'Account eligibility changed; cancel submission',
        'Proxy must be an HTTP/HTTPS URL or direct',
        'Invalid account delay returned by platform',
        'Unexpected API response shape',
        'Invalid local network configuration',
    }
    reason = str(exc) if isinstance(exc, ValueError) and str(exc) in known else type(exc).__name__
    result = {'state': 'configuration_or_login_required', 'reason': reason,
              'hint': 'Check local run log for timing, API status and business code'}
    audit('run_failed', **result)
    print(json.dumps(result, ensure_ascii=False), file=sys.stderr)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, httpx.HTTPError, StopIteration) as exc:
        report_error(exc)
        sys.exit(1)
    except KeyboardInterrupt:
        audit('run_cancelled')
        sys.exit(130)
