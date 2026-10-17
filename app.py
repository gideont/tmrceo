"""TMRCEO static pages and opt-in newsletter storage. No email is sent here."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, jsonify, request, send_from_directory
from snake_rules import replay_result, MAX_MOVES
from game_storage import attach_games
from news_quiz import create_tables as create_quiz_tables, register_quiz
from google_auth import register_auth, create_tables as create_auth_tables

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('DATA_DIR', '/data'))
DATA.mkdir(parents=True, exist_ok=True)
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 32768
BOOKS = {book['id'] for book in json.loads((ROOT / 'books/books.json').read_text())}
OPEN_ROLES = {role['id'] for role in json.loads((ROOT / 'leadership/members.json').read_text())['open_roles']}

def db():
    connection = sqlite3.connect(DATA / 'newsletter.sqlite3', timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('CREATE TABLE IF NOT EXISTS subscribers (email TEXT PRIMARY KEY, consent_at INTEGER NOT NULL, consent_text TEXT NOT NULL, token TEXT UNIQUE NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS attempts (source TEXT, at INTEGER)')
    connection.execute('CREATE TABLE IF NOT EXISTS book_likes (book TEXT NOT NULL, visitor TEXT NOT NULL, PRIMARY KEY (book, visitor))')
    connection.execute('CREATE TABLE IF NOT EXISTS team_interest (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, email TEXT NOT NULL, idea TEXT NOT NULL, submitted_at INTEGER NOT NULL, consent_text TEXT NOT NULL, status TEXT NOT NULL DEFAULT "pending")')
    attach_games(connection, DATA)
    create_auth_tables(connection)
    create_quiz_tables(connection)
    return connection

register_auth(app, db)
register_quiz(app, db)

@app.before_request
def protect():
    if request.method == 'POST':
        if request.path in {'/api/subscribe', '/api/team-interest'} and (request.content_length or 0) > 4096:
            return jsonify(error='The request is too large.'), 413
        # Browser forms from other sites cannot post JSON or use this API.
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error='Please use the form on tmrceo.com.'), 403
        if not request.is_json:
            return jsonify(error='Send a JSON request.'), 415

@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/')
def home():
    return send_from_directory(ROOT, 'index.html')

@app.get('/styles.css')
@app.get('/snake.js')
@app.get('/community.js')
@app.get('/arcade.js')
@app.get('/auth.js')
@app.get('/news-quiz.js')
def asset():
    return send_from_directory(ROOT, request.path[1:])


def snake_identity():
    token = request.cookies.get('tmrceo-player', '')
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        token = secrets.token_hex(32)
    session = app.extensions['tmrceo_auth_session']()
    return token, session['player_id'] if session else hashlib.sha256(token.encode()).hexdigest()


def snake_response(payload, token):
    response = jsonify(payload)
    if request.cookies.get('tmrceo-player') != token:
        response.set_cookie('tmrceo-player', token, max_age=365*86400, httponly=True,
                            secure=request.host.split(':')[0] not in {'127.0.0.1', 'localhost'}, samesite='Lax')
    return response


@app.route('/api/snake/player', methods=['GET', 'POST'])
def snake_player():
    token, player = snake_identity()
    data = request.get_json(silent=True) if request.method == 'POST' else None
    if request.method == 'POST':
        name = data.get('name') if isinstance(data, dict) else None
        if not isinstance(name, str):
            return jsonify(error='Choose a gamer nickname.'), 400
        name = ' '.join(unicodedata.normalize('NFKC', name).split())
        if not 2 <= len(name) <= 20 or not any(unicodedata.category(char)[0] in 'LN' for char in name) or any(unicodedata.category(char)[0] not in 'LN' and char not in ' ._-' for char in name):
            return jsonify(error='Use 2–20 letters or numbers, with spaces, dots, underscores or dashes.'), 400
    connection = db()
    try:
        if request.method == 'POST':
            with connection:
                connection.execute('INSERT INTO snake_players (id, name) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name', (player, name))
                connection.execute('UPDATE snake_play_log SET username=? WHERE player=? AND username IS NULL', (name, player))
        row = connection.execute('SELECT name, best_score FROM snake_players WHERE id = ?', (player,)).fetchone()
        return snake_response({'name': row['name'] if row else None, 'best_score': row['best_score'] if row else None}, token)
    finally:
        connection.close()


@app.get('/api/snake/leaderboard')
def snake_leaderboard():
    connection = db()
    try:
        rows = connection.execute('SELECT p.name, s.score FROM snake_scores s JOIN snake_players p ON s.player = p.id ORDER BY s.score DESC, s.achieved_at ASC, s.run_id ASC LIMIT 10').fetchall()
        return jsonify(players=[dict(row) for row in rows])
    finally:
        connection.close()


@app.get('/api/snake/leaderboard/details')
def snake_leaderboard_details():
    connection = db()
    try:
        rows = connection.execute('SELECT p.name,s.score,s.achieved_at FROM snake_scores s JOIN snake_players p ON s.player=p.id ORDER BY s.score DESC,s.achieved_at ASC,s.run_id ASC LIMIT 10').fetchall()
        players = [{'rank': index + 1, 'name': row['name'], 'score': row['score'],
                    'achieved_at': row['achieved_at'] if row['achieved_at'] and row['achieved_at'] > 0 else None}
                   for index, row in enumerate(rows)]
        now = time.time()
        since = players[0]['achieved_at'] if players else None
        return jsonify(players=players, record_since=since, unbeaten_seconds=max(0,now-since) if since else None, server_time=now)
    finally:
        connection.close()


@app.get('/api/snake/stats')
def snake_stats():
    connection = db()
    try:
        row = connection.execute("SELECT COUNT(*) AS plays, COUNT(DISTINCT player) AS players FROM snake_play_log WHERE source != 'legacy_best'").fetchone()
        return jsonify(dict(row))
    finally:
        connection.close()


@app.post('/api/snake/runs')
def snake_start_run():
    token, player = snake_identity()
    now = time.time()
    connection = db()
    try:
        with connection:
            connection.execute('DELETE FROM snake_runs WHERE created_at < ?', (now - 7200,))
            if connection.execute('SELECT COUNT(*) FROM snake_runs WHERE player = ? AND created_at > ?', (player, now - 60)).fetchone()[0] >= 30:
                return jsonify(error='Take a tiny breather, then try again.'), 429
            run_id = secrets.token_urlsafe(32)
            seed = secrets.randbits(32)
            connection.execute('INSERT INTO snake_runs (id, player, seed, created_at) VALUES (?, ?, ?, ?)', (run_id, player, seed, now))
            profile = connection.execute('SELECT name FROM snake_players WHERE id=?', (player,)).fetchone()
            session = app.extensions['tmrceo_auth_session']()
            connection.execute('INSERT INTO snake_play_log (run_id,player,username,email,play_starttime_epoch) VALUES (?,?,?,?,?)', (run_id,player,profile['name'] if profile else None,session['email'] if session else None,now))
        return snake_response({'run_id': run_id, 'seed': seed}, token)
    finally:
        connection.close()


def snake_score_receipt(connection, run_id, best_score):
    """Rank this exact round using the public board's ordering, including ties."""
    saved = connection.execute('SELECT score, achieved_at FROM snake_scores WHERE run_id = ?', (run_id,)).fetchone()
    if not saved:
        return {'ok': True, 'score': None, 'best_score': best_score, 'rank': None}
    rank = connection.execute(
        'SELECT COUNT(*) + 1 FROM snake_scores s JOIN snake_players p ON s.player = p.id '
        'WHERE s.score > ? OR (s.score = ? AND (s.achieved_at < ? OR (s.achieved_at = ? AND s.run_id < ?)))',
        (saved['score'], saved['score'], saved['achieved_at'], saved['achieved_at'], run_id)).fetchone()[0]
    return {'ok': True, 'score': saved['score'], 'best_score': best_score, 'rank': rank}


@app.post('/api/snake/runs/<run_id>/finish')
def snake_finish_run(run_id):
    _, player = snake_identity()
    data = request.get_json(silent=True)
    moves = data.get('moves') if isinstance(data, dict) else None
    if not isinstance(moves, str) or not 1 <= len(moves) <= MAX_MOVES:
        return jsonify(error='That game could not be checked. Please play another round.'), 400
    connection = db()
    try:
        now = time.time()
        run = connection.execute('SELECT * FROM snake_runs WHERE id = ? AND player = ?', (run_id, player)).fetchone()
        if not run or now - run['created_at'] > 7200:
            return jsonify(error='That round has expired. Play again to join the scoreboard.'), 404
        profile = connection.execute('SELECT * FROM snake_players WHERE id = ?', (player,)).fetchone()
        logged = connection.execute('SELECT * FROM snake_play_log WHERE run_id=?', (run_id,)).fetchone()
        if logged and logged['score'] is not None:
            score, finished_at = logged['score'], logged['finished_at']
        elif run['finished']:
            return jsonify(snake_score_receipt(connection, run_id, profile['best_score'] if profile else None))
        else:
            try:
                score, duration = replay_result(run['seed'], moves)
            except ValueError as error:
                return jsonify(error=str(error)), 400
            if now - run['created_at'] + 0.5 < duration:
                return jsonify(error='That round finished too quickly. Please play another game.'), 400
            finished_at = now
        with connection:
            connection.execute('UPDATE snake_play_log SET score=?,finished_at=? WHERE run_id=? AND score IS NULL', (score,finished_at,run_id))
            logged = connection.execute('SELECT score,finished_at FROM snake_play_log WHERE run_id=?', (run_id,)).fetchone()
            if logged and logged['score'] is not None:
                score, finished_at = logged['score'], logged['finished_at']
            if profile:
                inserted = connection.execute('INSERT OR IGNORE INTO snake_scores VALUES (?, ?, ?, ?)', (run_id, player, score, finished_at)).rowcount
                if inserted:
                    connection.execute('UPDATE snake_players SET best_score = ?, best_at = ? WHERE id = ? AND (best_score IS NULL OR best_score < ?)', (score, finished_at, player, score))
            connection.execute('UPDATE snake_runs SET finished = 1 WHERE id = ?', (run_id,))
        if not profile:
            return jsonify(ok=True, score=score, best_score=None, rank=None, needs_name=True)
        best = connection.execute('SELECT best_score FROM snake_players WHERE id = ?', (player,)).fetchone()[0]
        receipt = snake_score_receipt(connection, run_id, best)
        receipt['needs_name'] = False
        return jsonify(receipt)
    finally:
        connection.close()


@app.get('/features')
@app.get('/features/')
def features():
    return send_from_directory(ROOT / 'features', 'index.html')

@app.get('/firststone')
@app.get('/firststone/')
@app.get('/firststone/index.html')
def firststone():
    return send_from_directory(ROOT / 'firststone', 'index.html')

@app.get('/articles/<slug>')
@app.get('/articles/<slug>/')
def article(slug):
    if slug not in {'ouroboros', 'maquech', 'fireflies', 'ladybirds'}:
        from flask import abort
        abort(404)
    return send_from_directory(ROOT / 'articles', slug + '.html')

@app.get('/assets/team/<filename>')
def team_image(filename):
    if not filename.endswith(('.svg', '.png')):
        from flask import abort
        abort(404)
    return send_from_directory(ROOT / 'assets/team', filename)

@app.get('/assets/news/<filename>')
def news_image(filename):
    if filename not in {'ouroboros.jpg', 'maquech.jpg', 'firefly.jpg', 'ladybird.jpg'}:
        from flask import abort
        abort(404)
    response = send_from_directory(ROOT / 'assets/news', filename)
    response.cache_control.max_age = 86400
    return response


@app.get('/assets/books/<filename>')
def book_cover(filename):
    if not filename.endswith('.jpg') or filename[:-4] not in BOOKS:
        from flask import abort
        abort(404)
    response = send_from_directory(ROOT / 'assets/books', filename)
    response.cache_control.max_age = 86400
    return response


def reader_identity():
    token = request.cookies.get('tmrceo-reader', '')
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        token = secrets.token_hex(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def reader_response(payload, token):
    response = jsonify(payload)
    if request.cookies.get('tmrceo-reader') != token:
        response.set_cookie('tmrceo-reader', token, max_age=180*86400, httponly=True,
                            secure=request.host.split(':')[0] not in {'127.0.0.1', 'localhost'},
                            samesite='Lax')
    return response


@app.get('/api/books')
def book_likes():
    token, visitor = reader_identity()
    connection = db()
    try:
        rows = connection.execute('SELECT book, COUNT(*) AS likes, MAX(visitor = ?) AS liked FROM book_likes GROUP BY book', (visitor,)).fetchall()
        result = {book: {'likes': 0, 'liked': False} for book in BOOKS}
        for row in rows:
            if row['book'] in result:
                result[row['book']] = {'likes': row['likes'], 'liked': bool(row['liked'])}
        return reader_response(result, token)
    finally:
        connection.close()


@app.post('/api/books/<book>/like')
def like_book(book):
    data = request.get_json(silent=True)
    if book not in BOOKS:
        return jsonify(error='That book is not on our shelf.'), 404
    if not isinstance(data, dict) or not isinstance(data.get('liked'), bool):
        return jsonify(error='Please choose whether to like this book.'), 400
    token, visitor = reader_identity()
    connection = db()
    try:
        with connection:
            if data['liked']:
                connection.execute('INSERT OR IGNORE INTO book_likes (book, visitor) VALUES (?, ?)', (book, visitor))
            else:
                connection.execute('DELETE FROM book_likes WHERE book = ? AND visitor = ?', (book, visitor))
            count = connection.execute('SELECT COUNT(*) FROM book_likes WHERE book = ?', (book,)).fetchone()[0]
        return reader_response({'likes': count, 'liked': data['liked']}, token)
    finally:
        connection.close()


@app.post('/api/team-interest')
def team_interest():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Please check the form.'), 400
    if data.get('website'):
        return jsonify(ok=True)
    values = {}
    for key, limit in [('name', 60), ('role', 64), ('email', 254), ('idea', 1500)]:
        value = data.get(key, '')
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            return jsonify(error='Please complete the form and check the length of your answers.'), 400
        values[key] = value.strip()
    if values['role'] not in OPEN_ROLES or data.get('consent') is not True:
        return jsonify(error='Choose an open role and confirm parent or guardian permission.'), 400
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", values['email']):
        return jsonify(error='Please include a valid parent or guardian contact email.'), 400
    now = int(time.time())
    source = hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
    connection = db()
    try:
        with connection:
            connection.execute('DELETE FROM attempts WHERE at < ?', (now-3600,))
            if connection.execute('SELECT COUNT(*) FROM attempts WHERE source = ?', (source,)).fetchone()[0] >= 20:
                return jsonify(error='We have received several messages. Please try again later.'), 429
            connection.execute('INSERT INTO attempts VALUES (?, ?)', (source, now))
            connection.execute('INSERT INTO team_interest (name, role, email, idea, submitted_at, consent_text) VALUES (?, ?, ?, ?, ?, ?)',
                               (values['name'], values['role'], values['email'].lower(), values['idea'], now,
                                'Parent or guardian agrees to information being saved privately for team review.'))
        return jsonify(ok=True)
    finally:
        connection.close()


@app.post('/api/discoveries')
def discovery():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Please check the form.'), 400
    if data.get('website'):
        return jsonify(ok=True)
    values = {}
    for key, limit in [('name', 60), ('title', 140), ('fact', 3000), ('source', 1000)]:
        value = data.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            return jsonify(error='Please check the length of your submission.'), 400
        values[key] = value.strip()
    if not all(values[key] for key in ['title', 'fact', 'source']) or data.get('consent') is not True:
        return jsonify(error='Add your headline, discovery, source link, and permission to review.'), 400
    try:
        url = urlsplit(values['source'])
        valid_source = url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
    except ValueError:
        valid_source = False
    if not valid_source:
        return jsonify(error='Please include a valid http or https source link.'), 400
    now = int(time.time())
    source = hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
    connection = db()
    try:
        with connection:
            connection.execute('CREATE TABLE IF NOT EXISTS discoveries (id INTEGER PRIMARY KEY, name TEXT, title TEXT NOT NULL, fact TEXT NOT NULL, source TEXT NOT NULL, submitted_at INTEGER NOT NULL, consent_text TEXT NOT NULL, status TEXT NOT NULL DEFAULT "pending")')
            connection.execute('DELETE FROM attempts WHERE at < ?', (now-3600,))
            count = connection.execute('SELECT COUNT(*) FROM attempts WHERE source = ?', (source,)).fetchone()[0]
            if count >= 60:
                return jsonify(error='The newsroom is busy. Please try again later.'), 429
            connection.execute('INSERT INTO attempts VALUES (?, ?)', (source, now))
            connection.execute('INSERT INTO discoveries (name, title, fact, source, submitted_at, consent_text) VALUES (?, ?, ?, ?, ?, ?)', (values['name'], values['title'], values['fact'], values['source'], now, 'Permission to review and, if selected, publish with the supplied name.'))
        return jsonify(ok=True)
    finally:
        connection.close()

@app.get('/terms')
@app.get('/terms/')
def terms():
    return send_from_directory(ROOT, 'terms.html')

@app.get('/privacy')
def privacy():
    return send_from_directory(ROOT, 'privacy.html')

@app.get('/health')
def health():
    return jsonify(ok=True)

@app.post('/api/subscribe')
def subscribe():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Please check the form.'), 400
    if data.get('website'):
        return jsonify(ok=True)
    email = data.get('email', '')
    if not isinstance(email, str):
        return jsonify(error='Enter a valid email address.'), 400
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", email):
        return jsonify(error='Enter a valid email address.'), 400
    if data.get('consent') is not True:
        return jsonify(error='Please tick the box to opt in to updates.'), 400
    now = int(time.time())
    # Store only a short-lived hash for abuse throttling, never raw IP addresses.
    source = hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
    connection = db()
    try:
        with connection:
            connection.execute('DELETE FROM attempts WHERE at < ?', (now-3600,))
            count = connection.execute('SELECT COUNT(*) FROM attempts WHERE source = ?', (source,)).fetchone()[0]
            if count >= 60:
                return jsonify(error='A lot of signups just came in. Please try again later.'), 429
            connection.execute('INSERT INTO attempts VALUES (?, ?)', (source, now))
            token = secrets.token_urlsafe(32)
            cursor = connection.execute('INSERT OR IGNORE INTO subscribers VALUES (?, ?, ?, ?)', (email, now, 'Yes, email me tmrCEO updates. I can unsubscribe anytime.', token))
            # Never reveal an existing subscriber’s management token.
            return jsonify(ok=True, unsubscribe='/privacy#unsubscribe='+token if cursor.rowcount else None)
    finally:
        connection.close()

@app.post('/api/unsubscribe')
def unsubscribe():
    data = request.get_json(silent=True)
    token = data.get('token') if isinstance(data, dict) else None
    if not isinstance(token, str) or not 20 <= len(token) <= 100:
        return jsonify(error='Use your private unsubscribe link.'), 400
    connection = db()
    try:
        with connection:
            connection.execute('DELETE FROM subscribers WHERE token = ?', (token,))
        return jsonify(ok=True)
    finally:
        connection.close()

@app.errorhandler(413)
def too_large(error):
    return jsonify(error='The request is too large.'), 413
