"""Real RSA-signed ID-token fixtures, browser-bound login and revocable sessions."""
import base64
import datetime
import importlib
import json
import tempfile
import shutil
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

import google_auth as auth

CLIENT_ID = '123456-test.apps.googleusercontent.com'
ORIGIN = 'https://tmrceo.com'


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


class GoogleAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module('app')
        cls.app = cls.module.app
        cls.old_data = cls.module.DATA
        cls.storage = tempfile.TemporaryDirectory(prefix='tmrceo-auth-tests-')
        cls.module.DATA = Path(cls.storage.name)
        cls.old_client_id = cls.app.config['GOOGLE_CLIENT_ID']
        cls.app.config.update(TESTING=True, GOOGLE_CLIENT_ID=CLIENT_ID)
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Isolated test certificate')])
        now = datetime.datetime.now(datetime.timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(cls.key.public_key()).serial_number(1)
                       .not_valid_before(now - datetime.timedelta(days=1))
                       .not_valid_after(now + datetime.timedelta(days=1)).sign(cls.key, hashes.SHA256()))
        cls.certificate = certificate.public_bytes(serialization.Encoding.PEM).decode()

    @classmethod
    def tearDownClass(cls):
        cls.app.config['GOOGLE_CLIENT_ID'] = cls.old_client_id
        cls.module.DATA = cls.old_data
        cls.storage.cleanup()

    def setUp(self):
        shutil.rmtree(self.module.DATA / 'games', ignore_errors=True)
        path = self.module.DATA / 'newsletter.sqlite3'
        path.unlink(missing_ok=True)
        self.client = self.app.test_client()
        class CertificateResponse:
            status = 200
            data = json.dumps({'test-key': self.certificate}).encode()
        self.transport = patch.object(auth._transport, 'request', create=True, new=lambda *a, **k: CertificateResponse())
        self.transport.start()
        self.addCleanup(self.transport.stop)

    def request(self, path, method='get', client=None, **kwargs):
        return getattr(client or self.client, method)(path, base_url=ORIGIN, **kwargs)

    def challenge(self, client=None):
        response = self.request('/api/auth/session', client=client)
        self.assertEqual(response.status_code, 200)
        return response.json

    def credential(self, browser_nonce, **overrides):
        claims = dict(sub='google-subject-1', aud=CLIENT_ID, iss='https://accounts.google.com',
                      iat=int(time.time()), exp=int(time.time()) + 300, nonce=browser_nonce,
                      email='private@example.com', email_verified=True, name='Private Google Name')
        claims.update(overrides)
        data = b64(b'{"alg":"RS256","kid":"test-key"}') + '.' + b64(json.dumps(claims).encode())
        return data + '.' + b64(self.key.sign(data.encode(), padding.PKCS1v15(), hashes.SHA256()))

    def login(self, client=None, challenge=None, **claims):
        challenge = challenge or self.challenge(client)
        return self.request('/api/auth/google', 'post', client=client,
                            json={'credential': self.credential(challenge['nonce'], **claims)},
                            headers={'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token']})

    def test_real_signature_and_claim_validation(self):
        self.assertEqual(self.login().status_code, 200)
        self.assertNotIn('private@example.com', self.request('/api/auth/session').text)
        for claims in ({'aud': 'other-client'}, {'iss': 'https://evil.example'}, {'exp': 1},
                       {'iat': int(time.time()) + 3600}, {'nonce': 'wrong-nonce'}, {'azp': 'other'}, {'sub': ''}):
            client = self.app.test_client()
            self.assertEqual(self.login(client, **claims).status_code, 401, claims)
        client = self.app.test_client()
        challenge = self.challenge(client)
        token = self.credential(challenge['nonce'])
        parts = token.split('.')
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        payload['sub'] = 'tampered'
        parts[1] = b64(json.dumps(payload).encode())
        response = self.request('/api/auth/google', 'post', client=client,
                                json={'credential': '.'.join(parts)},
                                headers={'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token']})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(token, response.text)

    def test_csrf_origin_challenge_binding_and_replay(self):
        challenge = self.challenge()
        body = {'credential': self.credential(challenge['nonce'])}
        for headers in ({}, {'Origin': ORIGIN}, {'Origin': 'https://evil.example', 'X-CSRF-Token': challenge['csrf_token']},
                        {'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token'], 'Sec-Fetch-Site': 'same-site'}):
            self.assertEqual(self.request('/api/auth/google', 'post', json=body, headers=headers).status_code, 403)
        other = self.app.test_client()
        self.challenge(other)
        self.assertEqual(self.request('/api/auth/google', 'post', client=other, json=body,
                                     headers={'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token']}).status_code, 403)
        self.assertEqual(self.login(challenge=challenge).status_code, 200)
        self.assertEqual(self.login(challenge=challenge).status_code, 409)

    def test_session_cookie_storage_expiry_and_logout_revocation(self):
        result = self.login()
        cookie = self.client.get_cookie(auth.SESSION_COOKIE, domain='tmrceo.com')
        session_header = next(h for h in result.headers.getlist('Set-Cookie') if h.startswith(auth.SESSION_COOKIE + '='))
        for attribute in ('HttpOnly', 'Secure', 'SameSite=Lax', 'Path=/'):
            self.assertIn(attribute, session_header)
        self.assertNotIn('Domain=', session_header)
        with self.module.db() as connection:
            row = connection.execute('SELECT * FROM auth_sessions').fetchone()
            self.assertEqual(row['id_hash'], auth.digest(cookie.value))
            self.assertNotIn(cookie.value, str(tuple(row)))
            columns = [r[1] for r in connection.execute('PRAGMA table_info(auth_users)')]
            self.assertIn('email', columns)
            self.assertNotIn('name', columns)
        self.assertEqual(self.request('/api/auth/logout', 'post', json={}, headers={'Origin': ORIGIN}).status_code, 403)
        self.assertEqual(self.request('/api/auth/logout', 'post', json={}, headers={'Origin': ORIGIN, 'X-CSRF-Token': result.json['csrf_token']}).status_code, 200)
        self.client.set_cookie(auth.SESSION_COOKIE, cookie.value, domain='tmrceo.com')
        self.assertFalse(self.challenge()['authenticated'])
        self.login()
        with self.module.db() as connection:
            connection.execute('UPDATE auth_sessions SET expires_at = 1')
        self.assertFalse(self.challenge()['authenticated'])

    def test_guest_progress_merges_across_browsers_without_duplicate_players(self):
        self.request('/api/snake/player', 'post', json={'name': 'CapyCaptain'})
        token = self.client.get_cookie('tmrceo-player', domain='tmrceo.com').value
        guest_id = auth.digest(token)
        with self.module.db() as connection:
            connection.execute('UPDATE snake_players SET best_score = 40, best_at = 100 WHERE id = ?', (guest_id,))
            connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', ('first-guest-score', guest_id, 40, 100))
            connection.execute('INSERT INTO snake_runs VALUES (?, ?, ?, ?, ?)', ('pending-run', guest_id, 1, time.time(), 0))
        result = self.login()
        self.assertEqual(result.json['user'], {'display_name': 'CapyCaptain', 'needs_name': False})
        self.assertEqual(self.request('/api/snake/player').json['best_score'], 40)
        other = self.app.test_client()
        self.request('/api/snake/player', 'post', client=other, json={'name': 'Different Guest'})
        other_id = auth.digest(other.get_cookie('tmrceo-player', domain='tmrceo.com').value)
        with self.module.db() as connection:
            connection.execute('UPDATE snake_players SET best_score = 60, best_at = 200 WHERE id = ?', (other_id,))
            connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', ('second-guest-score', other_id, 60, 200))
        self.assertEqual(self.login(other).json['user']['display_name'], 'CapyCaptain')
        self.assertEqual(self.request('/api/snake/player', client=other).json['best_score'], 60)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM auth_users').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT count(*) FROM snake_players').fetchone()[0], 1)
            player_id = connection.execute('SELECT player_id FROM auth_users').fetchone()[0]
            self.assertEqual(connection.execute('SELECT player FROM snake_runs WHERE id = ?', ('pending-run',)).fetchone()[0], player_id)
        self.assertEqual(self.request('/api/snake/leaderboard').json['players'], [{'name': 'CapyCaptain', 'score': 60}, {'name': 'CapyCaptain', 'score': 40}])
        third = self.app.test_client()
        self.assertEqual(self.login(third, sub='different-google-subject').json['user']['needs_name'], True)
        self.assertIsNone(self.request('/api/snake/player', client=third).json['name'])

    def test_bad_tokens_attempt_limit_expired_challenges_and_unavailable_google(self):
        challenge = self.challenge()
        headers = {'Origin': ORIGIN, 'X-CSRF-Token': challenge['csrf_token']}
        for _ in range(5):
            self.assertEqual(self.request('/api/auth/google', 'post', json={'credential': 'invalid'}, headers=headers).status_code, 401)
        self.assertEqual(self.login(challenge=challenge).status_code, 403)
        challenge = self.challenge()
        with patch('google_auth.verify_google_credential', side_effect=auth.TransportError('private upstream error')):
            response = self.login(challenge=challenge)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private upstream error', response.text)
        with self.module.db() as connection:
            connection.execute('UPDATE auth_challenges SET expires_at = 1')
        self.assertEqual(self.login(challenge=challenge).status_code, 403)

    def test_public_assets_and_no_environment_exposure(self):
        with self.request('/auth.js') as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.request('/.env').status_code, 404)
        self.assertEqual(self.request('/api/auth/session').headers['Cache-Control'], 'no-store')
        with self.request('/') as response:
            self.assertEqual(response.headers['Cross-Origin-Opener-Policy'], 'same-origin-allow-popups')

    def test_quiz_guests_can_learn_without_earning_or_persisting_rewards(self):
        wrong = self.request('/api/news-quiz/mudroom-v1', 'post', json={'choice': 0}, headers={'Origin': ORIGIN})
        self.assertFalse(wrong.json['correct'])
        correct = self.request('/api/news-quiz/mudroom-v1', 'post', json={'choice': 1, 'points': 9999}, headers={'Origin': ORIGIN})
        self.assertFalse(correct.json['correct'])
        self.assertTrue(correct.json['already_answered'])
        self.assertEqual(correct.json['awarded'], 0)
        self.assertEqual(correct.json['points'], 0)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM quiz_rewards').fetchone()[0], 0)

    def test_quiz_rewards_are_once_per_account_private_and_separate_from_snake(self):
        login = self.login()
        headers = {'Origin': ORIGIN, 'X-CSRF-Token': login.json['csrf_token']}
        for expected in (10, 0, 0):
            response = self.request('/api/news-quiz/mudroom-v1', 'post', json={'choice': 1, 'points': 9999}, headers=headers)
            self.assertEqual(response.json['awarded'], expected)
            self.assertEqual(response.json['points'], 10)
        self.assertFalse(self.request('/api/news-quiz/firefly-v1', 'post', json={'choice': 0}, headers=headers).json['correct'])
        response = self.request('/api/news-quiz/firefly-v1', 'post', json={'choice': 1}, headers=headers)
        self.assertEqual(response.json['points'], 10)
        self.assertEqual(len(response.json['completed']), 2)
        self.assertEqual(self.request('/api/snake/leaderboard').json, {'players': []})
        same = self.app.test_client()
        self.login(same)
        self.assertEqual(self.request('/api/news-quiz', client=same).json['points'], 10)
        other = self.app.test_client()
        self.login(other, sub='another-quiz-user')
        self.assertEqual(self.request('/api/news-quiz', client=other).json['points'], 0)
        self.assertEqual(self.request('/api/news-quiz', client=self.app.test_client()).json['completed'], {})

    def test_guest_first_attempt_survives_signin_and_email_stays_private(self):
        self.request('/api/news-quiz')
        wrong = self.request('/api/news-quiz/mudroom-v1', 'post', json={'choice': 0}, headers={'Origin': ORIGIN})
        self.assertFalse(wrong.json['correct'])
        self.request('/api/snake/player', 'post', json={'name': 'Private Capy'})
        run = self.request('/api/snake/runs', 'post', json={}).json['run_id']
        login = self.login()
        self.assertNotIn('private@example.com', login.text)
        headers = {'Origin': ORIGIN, 'X-CSRF-Token': login.json['csrf_token']}
        retry = self.request('/api/news-quiz/mudroom-v1', 'post', json={'choice': 1}, headers=headers)
        self.assertTrue(retry.json['already_answered'])
        self.assertFalse(retry.json['correct'])
        self.assertEqual(retry.json['points'], 0)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT email FROM snake_play_log WHERE run_id=?', (run,)).fetchone()[0], 'private@example.com')
        self.assertNotIn('private@example.com', self.request('/api/snake/stats').text)
        self.assertNotIn('private@example.com', self.request('/api/snake/leaderboard').text)
        # A new browser for the same account still cannot change the first answer.
        other = self.app.test_client()
        self.login(other)
        progress = self.request('/api/news-quiz', client=other).json
        self.assertFalse(progress['completed']['mudroom-v1']['correct'])

    def test_guest_correct_attempt_awards_points_once_on_signin(self):
        answer = self.request('/api/news-quiz/firefly-v1', 'post', json={'choice': 1}, headers={'Origin': ORIGIN})
        self.assertTrue(answer.json['correct'])
        self.assertEqual(answer.json['points'], 0)
        self.login()
        self.assertEqual(self.request('/api/news-quiz').json['points'], 10)
        other = self.app.test_client()
        self.login(other)
        self.assertEqual(self.request('/api/news-quiz', client=other).json['points'], 10)

    def test_quiz_rejects_forgery_and_invalid_answers(self):
        login = self.login()
        path = '/api/news-quiz/mudroom-v1'
        for headers in ({}, {'Origin': ORIGIN}, {'Origin': 'https://evil.example', 'X-CSRF-Token': login.json['csrf_token']}):
            self.assertEqual(self.request(path, 'post', json={'choice': 1}, headers=headers).status_code, 403)
        headers = {'Origin': ORIGIN, 'X-CSRF-Token': login.json['csrf_token']}
        for value in (True, -1, 2, '1', None):
            self.assertEqual(self.request(path, 'post', json={'choice': value}, headers=headers).status_code, 400)
        self.assertEqual(self.request('/api/news-quiz/missing', 'post', json={'choice': 1}, headers=headers).status_code, 404)
        response = self.request('/api/news-quiz')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['points'], 0)


if __name__ == '__main__':
    unittest.main()
