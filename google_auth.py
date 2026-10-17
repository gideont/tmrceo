"""Google ID-token authentication and opaque, revocable server-side sessions."""
import hashlib
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

import requests
from cachecontrol import CacheControl
from flask import g, jsonify, request
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

SESSION_COOKIE = '__Host-tmrceo-session'
CHALLENGE_COOKIE = '__Host-tmrceo-auth'
SESSION_SECONDS = 7 * 86400
CHALLENGE_SECONDS = 20 * 60
_transport = threading.local()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def valid_token(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{64}', value) is not None


class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, *args, **kwargs):
        kwargs['timeout'] = 5
        return super().__call__(*args, **kwargs)


def verify_google_credential(credential, client_id):
    """Use Google's library and cached public certificates; never log the JWT."""
    if not hasattr(_transport, 'request'):
        _transport.request = BoundedGoogleRequest(session=CacheControl(requests.Session()))
    return id_token.verify_oauth2_token(credential, _transport.request, audience=client_id)


def create_tables(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS auth_users (id TEXT PRIMARY KEY, google_sub TEXT UNIQUE NOT NULL, player_id TEXT UNIQUE NOT NULL, created_at REAL NOT NULL, last_login REAL NOT NULL)')
    if 'email' not in {r[1] for r in connection.execute('PRAGMA main.table_info(auth_users)')}:
        try:
            connection.execute('ALTER TABLE auth_users ADD COLUMN email TEXT')
        except sqlite3.OperationalError:
            if 'email' not in {r[1] for r in connection.execute('PRAGMA main.table_info(auth_users)')}:
                raise
    connection.execute('CREATE TABLE IF NOT EXISTS auth_sessions (id_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL)')
    connection.execute('CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON auth_sessions (expires_at)')
    connection.execute('CREATE TABLE IF NOT EXISTS auth_challenges (id_hash TEXT PRIMARY KEY, nonce TEXT NOT NULL, csrf TEXT NOT NULL, expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0)')


def register_auth(app, db):
    client_id = os.environ.get('NEXT_PUBLIC_GOOGLE_CLIENT_ID', '').strip()
    if client_id and not re.fullmatch(r'[A-Za-z0-9-]+\.apps\.googleusercontent\.com', client_id):
        raise ValueError('NEXT_PUBLIC_GOOGLE_CLIENT_ID must be a Google web client ID.')
    origins = {origin.strip() for origin in os.environ.get('AUTH_ALLOWED_ORIGINS', 'https://tmrceo.com,https://www.tmrceo.com').split(',') if origin.strip()}
    if any(urlsplit(origin).scheme != 'https' or not urlsplit(origin).netloc or urlsplit(origin).path or urlsplit(origin).query or urlsplit(origin).fragment for origin in origins):
        raise ValueError('AUTH_ALLOWED_ORIGINS must contain HTTPS origins without paths.')
    app.config['GOOGLE_CLIENT_ID'] = client_id
    app.config['AUTH_ALLOWED_ORIGINS'] = origins

    def current_session():
        if hasattr(g, 'auth_session'):
            return g.auth_session
        g.auth_session = None
        token = request.cookies.get(SESSION_COOKIE)
        if not valid_token(token):
            return None
        connection = db()
        try:
            row = connection.execute('SELECT s.id_hash, s.csrf, s.expires_at, u.id AS user_id, u.player_id, u.email FROM auth_sessions s JOIN auth_users u ON s.user_id = u.id WHERE s.id_hash = ? AND s.expires_at > ?', (digest(token), time.time())).fetchone()
            g.auth_session = dict(row) if row else None
            return g.auth_session
        finally:
            connection.close()

    app.extensions['tmrceo_auth_session'] = current_session

    def set_cookie(response, name, value, age):
        response.set_cookie(name, value, max_age=age, secure=True, httponly=True, samesite='Lax', path='/')

    def clear_cookie(response, name):
        response.delete_cookie(name, secure=True, httponly=True, samesite='Lax', path='/')

    def valid_origin():
        return request.headers.get('Origin') in app.config['AUTH_ALLOWED_ORIGINS'] and request.headers.get('Sec-Fetch-Site') not in {'cross-site', 'same-site'}

    def user_payload(connection, session):
        profile = connection.execute('SELECT name FROM snake_players WHERE id = ?', (session['player_id'],)).fetchone()
        return {'display_name': profile['name'] if profile else None, 'needs_name': profile is None}

    def challenge(connection):
        now = time.time()
        token = request.cookies.get(CHALLENGE_COOKIE)
        row = connection.execute('SELECT * FROM auth_challenges WHERE id_hash = ? AND expires_at > ? AND attempts < 5', (digest(token), now)).fetchone() if valid_token(token) else None
        if row:
            return token, dict(row)
        token = secrets.token_urlsafe(48)
        row = {'nonce': secrets.token_urlsafe(32), 'csrf': secrets.token_urlsafe(32), 'expires_at': now + CHALLENGE_SECONDS}
        connection.execute('INSERT INTO auth_challenges (id_hash, nonce, csrf, expires_at) VALUES (?, ?, ?, ?)', (digest(token), row['nonce'], row['csrf'], row['expires_at']))
        return token, row

    @app.get('/api/auth/session')
    def auth_session():
        session = current_session()
        connection = db()
        try:
            with connection:
                now = time.time()
                connection.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (now,))
                connection.execute('DELETE FROM auth_challenges WHERE expires_at <= ?', (now,))
                if session:
                    return jsonify(authenticated=True, user=user_payload(connection, session), csrf_token=session['csrf'], enabled=bool(app.config['GOOGLE_CLIENT_ID']))
                if not app.config['GOOGLE_CLIENT_ID']:
                    return jsonify(authenticated=False, enabled=False)
                token, row = challenge(connection)
                response = jsonify(authenticated=False, enabled=True, client_id=app.config['GOOGLE_CLIENT_ID'], nonce=row['nonce'], csrf_token=row['csrf'])
                set_cookie(response, CHALLENGE_COOKIE, token, CHALLENGE_SECONDS)
                if request.cookies.get(SESSION_COOKIE):
                    clear_cookie(response, SESSION_COOKIE)
                return response
        finally:
            connection.close()

    @app.post('/api/auth/google')
    def auth_google():
        if not app.config['GOOGLE_CLIENT_ID']:
            return jsonify(error='Google sign-in is not configured yet.'), 503
        if not valid_origin():
            return jsonify(error='Please sign in from this website.'), 403
        if (request.content_length or 0) > 12000:
            return jsonify(error='The sign-in request is too large.'), 413
        if current_session():
            return jsonify(error='You are already signed in. Log out to choose another account.'), 409
        token = request.cookies.get(CHALLENGE_COOKIE)
        csrf = request.headers.get('X-CSRF-Token', '')
        data = request.get_json(silent=True)
        credential = data.get('credential') if isinstance(data, dict) else None
        if not valid_token(token) or not isinstance(credential, str) or not 1 <= len(credential) <= 8192:
            return jsonify(error='Sign-in could not be checked. Refresh and try again.'), 400
        connection = db()
        try:
            now = time.time()
            row = connection.execute('SELECT * FROM auth_challenges WHERE id_hash = ? AND expires_at > ? AND attempts < 5', (digest(token), now)).fetchone()
            if not row or not secrets.compare_digest(row['csrf'].encode(), csrf.encode()):
                return jsonify(error='Sign-in expired. Refresh this page and try again.'), 403
            with connection:
                connection.execute('UPDATE auth_challenges SET attempts = attempts + 1 WHERE id_hash = ?', (digest(token),))
            try:
                claims = verify_google_credential(credential, app.config['GOOGLE_CLIENT_ID'])
            except (TransportError, requests.RequestException):
                return jsonify(error='Google could not be reached. Please try again shortly.'), 503
            except (ValueError, GoogleAuthError):
                return jsonify(error='Google sign-in could not be verified. Please try again.'), 401
            # The library validates signature, audience, expiry and issuer. Keep
            # explicit claim checks here as well, including our browser nonce.
            subject = claims.get('sub')
            expiry = claims.get('exp')
            issued = claims.get('iat')
            if (not isinstance(subject, str) or not 1 <= len(subject) <= 255
                or claims.get('aud') != app.config['GOOGLE_CLIENT_ID']
                or claims.get('iss') not in {'accounts.google.com', 'https://accounts.google.com'}
                or not isinstance(expiry, (int, float)) or isinstance(expiry, bool) or not math.isfinite(expiry) or expiry <= now
                or not isinstance(issued, (int, float)) or isinstance(issued, bool) or not math.isfinite(issued) or issued > now + 60
                or claims.get('azp', app.config['GOOGLE_CLIENT_ID']) != app.config['GOOGLE_CLIENT_ID']
                or not isinstance(claims.get('nonce'), str) or not secrets.compare_digest(claims['nonce'].encode(), row['nonce'].encode())):
                return jsonify(error='Google sign-in could not be verified. Refresh and try again.'), 401
            email = claims.get('email') if claims.get('email_verified') is True and isinstance(claims.get('email'), str) and len(claims['email']) <= 320 else None
            session_token = secrets.token_urlsafe(48)
            session_csrf = secrets.token_urlsafe(32)
            guest_token = request.cookies.get('tmrceo-player', '')
            guest_id = digest(guest_token) if re.fullmatch(r'[a-f0-9]{64}', guest_token) else None
            # Consume the browser-bound challenge and merge guest progress in a
            # single write transaction, including concurrent callbacks/tabs.
            with connection:
                consumed = connection.execute('DELETE FROM auth_challenges WHERE id_hash = ? AND expires_at > ?', (digest(token), time.time())).rowcount
                if consumed != 1:
                    return jsonify(error='This sign-in was already used. Refresh to continue.'), 409
                user = connection.execute('SELECT * FROM auth_users WHERE google_sub = ?', (subject,)).fetchone()
                if not user:
                    user_id = secrets.token_hex(24)
                    player_id = 'account_' + secrets.token_hex(24)
                    connection.execute('INSERT INTO auth_users (id,google_sub,player_id,created_at,last_login,email) VALUES (?, ?, ?, ?, ?, ?)', (user_id, subject, player_id, now, now, email))
                else:
                    user_id, player_id = user['id'], user['player_id']
                    connection.execute('UPDATE auth_users SET last_login = ?,email=COALESCE(?,email) WHERE id = ?', (now, email, user_id))
                guest = connection.execute('SELECT * FROM snake_players WHERE id = ?', (guest_id,)).fetchone() if guest_id else None
                profile = connection.execute('SELECT * FROM snake_players WHERE id = ?', (player_id,)).fetchone()
                if guest:
                    if not profile:
                        connection.execute('INSERT INTO snake_players (id, name, best_score, best_at) VALUES (?, ?, ?, ?)', (player_id, guest['name'], guest['best_score'], guest['best_at']))
                    elif guest['best_score'] is not None and (profile['best_score'] is None or guest['best_score'] > profile['best_score'] or (guest['best_score'] == profile['best_score'] and guest['best_at'] < profile['best_at'])):
                        connection.execute('UPDATE snake_players SET best_score = ?, best_at = ? WHERE id = ?', (guest['best_score'], guest['best_at'], player_id))
                    connection.execute('DELETE FROM snake_players WHERE id = ?', (guest_id,))
                if guest_id:
                    connection.execute('UPDATE snake_runs SET player = ? WHERE player = ?', (player_id, guest_id))
                    connection.execute('UPDATE snake_scores SET player = ? WHERE player = ?', (player_id, guest_id))
                    connection.execute('UPDATE snake_play_log SET player=?,email=COALESCE(?,email) WHERE player=?', (player_id,email,guest_id))
                if email:
                    connection.execute('UPDATE snake_play_log SET email=? WHERE player=? AND email IS NULL', (email,player_id))
                from news_quiz import merge_guest_attempts
                merge_guest_attempts(connection, request.cookies.get('tmrceo-quiz', ''), user_id)
                connection.execute('INSERT INTO auth_sessions VALUES (?, ?, ?, ?, ?)', (digest(session_token), user_id, session_csrf, now, now + SESSION_SECONDS))
                payload = user_payload(connection, {'player_id': player_id})
            response = jsonify(authenticated=True, user=payload, csrf_token=session_csrf)
            set_cookie(response, SESSION_COOKIE, session_token, SESSION_SECONDS)
            clear_cookie(response, CHALLENGE_COOKIE)
            clear_cookie(response, 'tmrceo-player')
            clear_cookie(response, 'tmrceo-quiz')
            return response
        finally:
            connection.close()

    @app.post('/api/auth/logout')
    def auth_logout():
        if not valid_origin():
            return jsonify(error='Please log out from this website.'), 403
        session = current_session()
        if not session:
            return jsonify(error='Your session has expired. Refresh this page.'), 401
        if not secrets.compare_digest(session['csrf'].encode(), request.headers.get('X-CSRF-Token', '').encode()):
            return jsonify(error='Please refresh before logging out.'), 403
        connection = db()
        try:
            with connection:
                connection.execute('DELETE FROM auth_sessions WHERE id_hash = ?', (session['id_hash'],))
            response = jsonify(authenticated=False)
            clear_cookie(response, SESSION_COOKIE)
            clear_cookie(response, CHALLENGE_COOKIE)
            clear_cookie(response, 'tmrceo-player')
            clear_cookie(response, 'tmrceo-quiz')
            return response
        finally:
            connection.close()
