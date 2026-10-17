"""Editable news questions and account-bound, once-per-question curiosity rewards."""
from html import escape
import secrets
import hashlib
import re
import time

POINTS = 10
QUESTIONS = [
    {'id': 'mudroom-v1', 'question': 'Do you know what a mudroom is?',
     'options': ['A room full of mud. Squish!', 'An entrance room for muddy boots and wet coats.'],
     'answer': 1, 'clue': '#word-mudroom', 'clue_label': 'Read our little word story',
     'explanation': 'A mudroom is an entrance space where you can leave muddy boots and wet coats. The mud stays by the door!'},
    {'id': 'firefly-v1', 'question': 'A firefly lights up. But what kind of insect is it?',
     'options': ['A tiny fly with a torch.', 'A beetle with a natural glow.'],
     'answer': 1, 'clue': '/articles/fireflies', 'clue_label': 'Find a clue in our firefly story',
     'explanation': 'Fireflies are beetles! Their glow is called bioluminescence: light made by a living thing.'},
    {'id': 'ouroboros-v1', 'question': 'What makes an ouroboros a circle?',
     'options': ['Its mouth meets its own tail.', 'Two snakes holding hands. Wait… hands?'],
     'answer': 0, 'clue': '/articles/ouroboros', 'clue_label': 'Find a clue in our snake story',
     'explanation': 'An ouroboros curves around to meet its own tail. People have used it to think about cycles and renewal.'},
]
BY_ID = {q['id']: q for q in QUESTIONS}


def render_news_questions():
    cards = []
    for index, question in enumerate(QUESTIONS, 1):
        qid = question['id']
        options = ''.join(f'<button type="button" class="quiz-option" data-choice="{i}" aria-pressed="false">{escape(text)}</button>' for i, text in enumerate(question['options']))
        cards.append(f'''<article class="quiz-card" data-question="{qid}" aria-labelledby="{qid}-title"><div class="quiz-kicker"><span>CURIOUS QUESTION {index:02}</span><span>+{POINTS} POINTS</span></div><h3 id="{qid}-title">{escape(question['question'])}</h3><div class="quiz-options" role="group" aria-label="{escape(question['question'], quote=True)}">{options}</div><a class="quiz-clue" href="{escape(question['clue'], quote=True)}">{escape(question['clue_label'])} ↗</a><p class="quiz-feedback" role="status" aria-live="polite"></p></article>''')
    return '''<aside class="word-story" id="word-mudroom" aria-labelledby="word-mudroom-title"><span class="eyebrow">A LITTLE WORD STORY</span><h3 id="word-mudroom-title">Mudroom. A room made of mud?</h3><details id="mudroom-clue"><summary>Open this tiny story for a clue ↗</summary><p>Picture coming home in soggy boots. Before you trail muddy footprints through the house, there’s a place to take them off. That entrance space is a <strong>mudroom</strong>. Wet coats and muddy shoes can stay there while you head inside. Mud is welcome on the boots. All over the floor? Maybe less so.</p><p class="word-credit">By tmrCEO curiosity desk · <time datetime="2026-10-16">October 16, 2026</time> · Word checked with <a href="https://www.collinsdictionary.com/dictionary/english/mudroom" target="_blank" rel="noopener noreferrer">Collins Dictionary ↗</a></p></details></aside>''' + f'''<span id="did-you-know" aria-hidden="true"></span><section class="news-quiz" id="do-you-know" aria-labelledby="quiz-title"><header class="quiz-heading"><div><span class="eyebrow">FOLLOW YOUR CURIOSITY</span><h2 id="quiz-title">Do you know?</h2><p>The clues are hiding in our stories. Read, wonder, then have a go!</p></div><div class="quiz-progress"><p id="quiz-points" role="status" aria-live="polite">Sign in to save your curiosity points.</p><span>+{POINTS} for each new discovery. One answer per question. Choose carefully!</span><a href="#auth-controls" id="quiz-signin">Sign in to collect points ↗</a></div></header><div class="quiz-grid">{''.join(cards)}</div><noscript><p>Enable JavaScript to answer the questions. You can still read every clue.</p></noscript></section>'''


def create_tables(connection):
    # Existing correct answers remain locked and retain their points.
    if not connection.execute('SELECT 1 FROM quiz.schema_migrations WHERE name=?', ('one-chance-v1',)).fetchone():
        with connection:
            inserted = connection.execute('INSERT OR IGNORE INTO quiz.schema_migrations VALUES (?)', ('one-chance-v1',)).rowcount
            if inserted:
                for question in QUESTIONS:
                    connection.execute("INSERT OR IGNORE INTO quiz_attempts SELECT 'account_' || user_id, question_id, ?, 1, answered_at FROM quiz_rewards WHERE question_id=?", (question['answer'],question['id']))


def merge_guest_attempts(connection, token, user_id):
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        return
    guest = 'guest_' + hashlib.sha256(token.encode()).hexdigest()
    account = 'account_' + user_id
    for row in connection.execute('SELECT * FROM quiz_attempts WHERE identity=?', (guest,)).fetchall():
        inserted = connection.execute('INSERT OR IGNORE INTO quiz_attempts VALUES (?,?,?,?,?)', (account,row['question_id'],row['choice'],row['correct'],row['answered_at'])).rowcount
        if inserted and row['correct']:
            connection.execute('INSERT OR IGNORE INTO quiz_rewards VALUES (?,?,?,?)', (user_id,row['question_id'],POINTS,row['answered_at']))
    connection.execute('DELETE FROM quiz_attempts WHERE identity=?', (guest,))


def register_quiz(app, db):
    from flask import jsonify, request

    def identity():
        session = app.extensions['tmrceo_auth_session']()
        token = request.cookies.get('tmrceo-quiz', '')
        if not re.fullmatch(r'[a-f0-9]{64}', token):
            token = secrets.token_hex(32)
        key = 'account_' + session['user_id'] if session else 'guest_' + hashlib.sha256(token.encode()).hexdigest()
        return session, token, key

    def response(payload, session, token):
        result = jsonify(payload)
        if not session and request.cookies.get('tmrceo-quiz') != token:
            result.set_cookie('tmrceo-quiz',token,max_age=365*86400,httponly=True,secure=request.host.split(':')[0] not in {'localhost','127.0.0.1'},samesite='Lax',path='/')
        return result

    def progress(connection, session, key):
        rows = connection.execute('SELECT question_id,choice,correct FROM quiz_attempts WHERE identity=?', (key,)).fetchall()
        total = connection.execute('SELECT COALESCE(SUM(points),0) FROM quiz_rewards WHERE user_id=?', (session['user_id'],)).fetchone()[0] if session else 0
        return {'authenticated': bool(session), 'points': total,
                'completed': {r['question_id']: {'choice': r['choice'], 'correct': bool(r['correct']), 'explanation': BY_ID[r['question_id']]['explanation']} for r in rows if r['question_id'] in BY_ID}}

    @app.get('/api/news-quiz')
    def quiz_progress():
        session,token,key = identity()
        connection = db()
        try:
            return response(progress(connection,session,key),session,token)
        finally:
            connection.close()

    @app.post('/api/news-quiz/<question_id>')
    def quiz_answer(question_id):
        if request.headers.get('Origin') not in app.config['AUTH_ALLOWED_ORIGINS'] or request.headers.get('Sec-Fetch-Site') in {'cross-site', 'same-site'}:
            return jsonify(error='Please answer from this website.'), 403
        question = BY_ID.get(question_id)
        if not question:
            return jsonify(error='That question is not available.'), 404
        data = request.get_json(silent=True)
        choice = data.get('choice') if isinstance(data, dict) else None
        if type(choice) is not int or not 0 <= choice < len(question['options']):
            return jsonify(error='Pick one of the answers.'), 400
        session,token,key = identity()
        if session and not secrets.compare_digest(session['csrf'].encode(), request.headers.get('X-CSRF-Token', '').encode()):
            return jsonify(error='Refresh the page to continue collecting points.'), 403
        connection = db()
        try:
            awarded = 0
            with connection:
                inserted = connection.execute('INSERT OR IGNORE INTO quiz_attempts VALUES (?,?,?,?,?)', (key,question_id,choice,int(choice==question['answer']),time.time())).rowcount
                attempt = connection.execute('SELECT * FROM quiz_attempts WHERE identity=? AND question_id=?', (key,question_id)).fetchone()
                if session and inserted and attempt['correct']:
                    awarded = POINTS if connection.execute('INSERT OR IGNORE INTO quiz_rewards VALUES (?,?,?,?)', (session['user_id'],question_id,POINTS,attempt['answered_at'])).rowcount else 0
            payload = progress(connection,session,key)
            payload.update(correct=bool(attempt['correct']),awarded=awarded,already_answered=not bool(inserted),explanation=question['explanation'])
            return response(payload,session,token)
        finally:
            connection.close()
