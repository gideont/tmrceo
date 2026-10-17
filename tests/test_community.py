"""Regression checks for shared reader likes and private role-interest submissions."""
import importlib
import os
from pathlib import Path
import sqlite3
import tempfile
import shutil
import unittest


class CommunityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix='tmrceo-community-tests-')
        os.environ['DATA_DIR'] = cls.storage.name
        cls.module = importlib.import_module('app')
        cls.module.DATA = Path(cls.storage.name)
        cls.app = cls.module.app
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def setUp(self):
        shutil.rmtree(self.module.DATA / 'games', ignore_errors=True)
        path = self.module.DATA / 'newsletter.sqlite3'
        if path.exists():
            path.unlink()
        self.client = self.app.test_client()

    def test_likes_are_shared_idempotent_and_reversible(self):
        other = self.app.test_client()
        self.assertEqual(self.client.get('/api/books').json['wild-robot'], {'likes': 0, 'liked': False})
        self.assertEqual(self.client.post('/api/books/wild-robot/like', json={'liked': True}).json['likes'], 1)
        self.assertEqual(self.client.post('/api/books/wild-robot/like', json={'liked': True}).json['likes'], 1)
        self.assertEqual(other.get('/api/books').json['wild-robot'], {'likes': 1, 'liked': False})
        self.assertEqual(other.post('/api/books/wild-robot/like', json={'liked': True}).json['likes'], 2)
        self.assertEqual(self.client.post('/api/books/wild-robot/like', json={'liked': False}).json, {'likes': 1, 'liked': False})
        self.assertEqual(other.get('/api/books').json['wild-robot'], {'likes': 1, 'liked': True})

    def test_unknown_book_invalid_likes_and_cross_origin_are_rejected(self):
        for payload in ({}, {'liked': 'yes'}, [], {'liked': 1}):
            self.assertEqual(self.client.post('/api/books/wild-robot/like', json=payload).status_code, 400)
        self.assertEqual(self.client.post('/api/books/unknown/like', json={'liked': True}).status_code, 404)
        self.assertEqual(self.client.post('/api/books/wild-robot/like', json={'liked': True}, headers={'Origin': 'https://other.example'}).status_code, 403)
        self.assertEqual(self.client.get('/api/books').json['wild-robot']['likes'], 0)

    def test_reader_cookie_and_no_cache(self):
        response = self.client.get('/api/books', base_url='https://tmrceo.com')
        cookie = response.headers['Set-Cookie']
        for attribute in ('Secure', 'HttpOnly', 'SameSite=Lax'):
            self.assertIn(attribute, cookie)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('Set-Cookie', self.client.get('/api/books', base_url='https://tmrceo.com').headers)

    def interest(self, **changes):
        payload = dict(name='Future leader', role='ceo', email='parent@example.com', idea='Make a game and learn to lead.', consent=True)
        payload.update(changes)
        return self.client.post('/api/team-interest', json=payload)

    def test_interest_is_private_pending_and_does_not_subscribe(self):
        self.assertEqual(self.interest().status_code, 200)
        with self.module.db() as connection:
            row = connection.execute('SELECT * FROM team_interest').fetchone()
            self.assertEqual(row['status'], 'pending')
            self.assertEqual(row['role'], 'ceo')
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM subscribers').fetchone()[0], 0)
        self.assertNotIn('parent@example.com', self.client.get('/', buffered=True).text)

    def test_interest_requires_consent_valid_role_and_contact(self):
        for change in ({'consent': False}, {'role': 'adult-ceo'}, {'role': 'cfo'}, {'role': 'fpa'}, {'email': 'invalid'}, {'idea': ''}, {'idea': 'x'*1501}, {'name': ['invalid']}):
            self.assertEqual(self.interest(**change).status_code, 400)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM team_interest').fetchone()[0], 0)

    def test_honeypot_and_rate_limit(self):
        self.assertEqual(self.interest(website='spam').status_code, 200)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM team_interest').fetchone()[0], 0)
        for _ in range(20):
            self.assertEqual(self.interest().status_code, 200)
        self.assertEqual(self.interest().status_code, 429)

    def test_existing_subscriber_survives_schema_additions(self):
        shutil.rmtree(self.module.DATA / 'games', ignore_errors=True)
        path = self.module.DATA / 'newsletter.sqlite3'
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE subscribers (email TEXT PRIMARY KEY, consent_at INTEGER NOT NULL, consent_text TEXT NOT NULL, token TEXT UNIQUE NOT NULL)')
            connection.execute('INSERT INTO subscribers VALUES (?, ?, ?, ?)', ('existing@example.com', 1, 'Existing consent', 'existing-token'))
        self.assertEqual(self.client.get('/api/books').status_code, 200)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT email FROM subscribers').fetchone()[0], 'existing@example.com')

    def test_pages_assets_and_content(self):
        for route in ('/', '/community.js', '/arcade.js', '/snake.js', '/styles.css', '/privacy', '/terms', '/terms/', '/health', '/features', '/features/', '/firststone', '/articles/ouroboros', '/articles/maquech', '/articles/fireflies', '/articles/ladybirds'):
            self.assertEqual(self.client.get(route, buffered=True).status_code, 200, route)
        for book in self.module.BOOKS:
            self.assertEqual(self.client.get(f'/assets/books/{book}.jpg', buffered=True).status_code, 200)
        for route in ('/assets/books/unknown.jpg', '/assets/books/lemonade-war.jpg', '/books/books.json', '/leadership/members.json'):
            self.assertEqual(self.client.get(route, buffered=True).status_code, 404)
        home = self.client.get('/', buffered=True).text
        self.assertNotIn('Senior', home)
        self.assertIn('href="/terms"', home)
        terms = self.client.get('/terms', buffered=True).text
        self.assertIn('Terms of Use', terms)
        self.assertIn('mailto:gideon@gmail.com', terms)
        self.assertIn('href="/privacy"', terms)
        self.assertEqual(home.count('class="book-card"'), 6)
        shelf = home.split('<!-- bookshelf:start -->')[1].split('<!-- bookshelf:end -->')[0]
        self.assertIn('local library', shelf)
        self.assertIn('share a copy', shelf)
        self.assertNotIn('scholastic', shelf.lower())
        self.assertNotIn('About the book', shelf)
        self.assertNotIn('The Lemonade War', shelf)
        self.assertNotIn('Frindle', shelf)
        self.assertNotIn('A Boy Called Bat', shelf)
        self.assertNotIn('The Phantom Tollbooth', shelf)
        self.assertEqual(home.count('class="hiring-card"'), 7)
        self.assertLess(home.index('id="news"'), home.index('id="books"'))
        self.assertLess(home.index('id="books"'), home.index('id="team"'))
        self.assertIn('Chief Imagination Officer', home)
        self.assertIn('Chief Game Designer', home)
        self.assertIn('Chief Engineer', home)
        self.assertIn('Anyone want to step up to be the CEO?', home)
        self.assertNotIn('Head of FP&amp;A', home)
        self.assertNotIn('Chief Financial Officer', home)
        for title in ('Chief Game Editor', 'Chief News Editor', 'Book Explorer', 'Chief Buzz Maker', 'Chief Story Sharer', 'Curiosity Reporter'):
            self.assertIn(title, home)
        self.assertIn('more than one CEO', home)
        self.assertIn('href="/features"', home)
        self.assertNotIn('Features in queue', home)
        tracker = self.client.get('/features', buffered=True).text
        self.assertIn('Features in queue', tracker)
        self.assertIn('Built so far', tracker)
        for task in ('What could tmrCEO be?', 'Register tmrceo.com', 'Set up web hosting', 'Project email'):
            self.assertIn(task, tracker)
        self.assertNotIn('timeline-notice', tracker)
        self.assertNotIn('imagined', tracker)
        self.assertIn('Sample dates', tracker)
        self.assertIn('Google sign-in + your own gamer name', tracker)
        self.assertEqual(tracker.count('feature-state queued'), 2)
        self.assertIn('<time datetime="2026-10-16">', tracker)
        self.assertIn('By tmrCEO curiosity desk', home)
        self.assertIn('By tmrCEO curiosity desk', self.client.get('/articles/ouroboros', buffered=True).text)


if __name__ == '__main__':
    unittest.main()
