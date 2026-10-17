"""Persistent per-game files, legacy migration, play logs and one-shot attempts."""
from concurrent.futures import ThreadPoolExecutor
import importlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

ORIGIN = 'https://tmrceo.com'


class GameStorageTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('app')
        self.old_data = self.module.DATA
        self.storage = tempfile.TemporaryDirectory(prefix='tmrceo-game-storage-')
        self.module.DATA = Path(self.storage.name)
        self.app = self.module.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.module.DATA = self.old_data
        self.storage.cleanup()

    def test_each_game_is_separate_and_play_log_survives_cleanup_and_reopen(self):
        self.client.post('/api/snake/player', json={'name': 'Log Capy'})
        with patch('app.time.time', return_value=1000), patch('app.secrets.randbits', return_value=1):
            run = self.client.post('/api/snake/runs', json={}).json['run_id']
        with patch('app.time.time', return_value=1005):
            self.assertEqual(self.client.post('/api/snake/runs/'+run+'/finish', json={'moves': '1'*12}).status_code, 200)
        for _ in range(3):
            self.assertEqual(self.client.get('/api/snake/stats').json, {'players': 1, 'plays': 1})
        # This directly reopens the disk file; it does not use app connection state.
        with sqlite3.connect(self.module.DATA/'games/snake.sqlite3') as connection:
            row = connection.execute('SELECT username,email,play_starttime_epoch,score FROM snake_play_log WHERE run_id=?', (run,)).fetchone()
            self.assertEqual(row, ('Log Capy', None, 1000, 0))
        with sqlite3.connect(self.module.DATA/'newsletter.sqlite3') as connection:
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('snake_play_log', tables)
            self.assertNotIn('snake_scores', tables)
            self.assertNotIn('quiz_rewards', tables)
        self.assertTrue((self.module.DATA/'games/curiosity.sqlite3').is_file())
        with patch('app.time.time', return_value=10000):
            self.client.post('/api/snake/runs', json={})
        self.assertEqual(self.client.get('/api/snake/stats').json, {'players': 1, 'plays': 2})
        with self.module.db() as connection:
            self.assertIsNotNone(connection.execute('SELECT score FROM snake_play_log WHERE run_id=?', (run,)).fetchone())

    def test_unnamed_round_is_logged_but_not_public_until_name_saved(self):
        with patch('app.time.time', return_value=1000), patch('app.secrets.randbits', return_value=1):
            run = self.client.post('/api/snake/runs', json={}).json['run_id']
        with patch('app.time.time', return_value=1005):
            result = self.client.post('/api/snake/runs/'+run+'/finish', json={'moves': '1'*12})
        self.assertTrue(result.json['needs_name'])
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], [])
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT username,score FROM snake_play_log').fetchone()[:], (None,0))
        self.client.post('/api/snake/player', json={'name':'Now Named'})
        with patch('app.time.time', return_value=1006):
            self.client.post('/api/snake/runs/'+run+'/finish', json={'moves': '1'*12})
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], [{'name':'Now Named','score':0}])

    def test_legacy_scores_rewards_and_sessions_are_migrated_once(self):
        with sqlite3.connect(self.module.DATA/'newsletter.sqlite3') as c:
            c.execute('CREATE TABLE snake_players (id TEXT PRIMARY KEY,name TEXT,best_score INTEGER,best_at REAL)')
            c.execute('INSERT INTO snake_players VALUES ("p","Legacy Capy",80,100)')
            c.execute('CREATE TABLE snake_runs (id TEXT PRIMARY KEY,player TEXT,seed INTEGER,created_at REAL,finished INTEGER)')
            c.execute('INSERT INTO snake_runs VALUES ("run","p",1,90,1)')
            c.execute('CREATE TABLE snake_scores (run_id TEXT PRIMARY KEY,player TEXT,score INTEGER,achieved_at REAL)')
            c.execute('INSERT INTO snake_scores VALUES ("run","p",80,100)')
            c.execute('CREATE TABLE quiz_rewards (user_id TEXT,question_id TEXT,points INTEGER,answered_at REAL,PRIMARY KEY(user_id,question_id))')
            c.execute('INSERT INTO quiz_rewards VALUES ("u","mudroom-v1",10,100)')
        for _ in range(3):
            with self.module.db() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM snake_scores').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT score,play_starttime_epoch FROM snake_play_log').fetchone()[:],(80,90))
                self.assertEqual(c.execute('SELECT SUM(points) FROM quiz_rewards').fetchone()[0],10)
                self.assertEqual(c.execute('SELECT choice,correct FROM quiz_attempts WHERE identity="account_u"').fetchone()[:],(1,1))
                for schema in ('main','snake','quiz'):
                    self.assertEqual(c.execute(f'PRAGMA {schema}.integrity_check').fetchone()[0],'ok')

    def test_guest_cannot_retry_even_after_new_connection_or_concurrent_answers(self):
        self.client.get('/api/news-quiz', base_url=ORIGIN)
        token = self.client.get_cookie('tmrceo-quiz', domain='tmrceo.com').value
        barrier = threading.Barrier(2)
        def answer(choice):
            client = self.app.test_client()
            client.set_cookie('tmrceo-quiz',token,domain='tmrceo.com')
            barrier.wait()
            return client.post('/api/news-quiz/mudroom-v1', base_url=ORIGIN,json={'choice':choice},headers={'Origin':ORIGIN}).json
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(answer,[0,1]))
        self.assertEqual(sum(not r['already_answered'] for r in results),1)
        self.assertEqual(results[0]['correct'],results[1]['correct'])
        progress = self.client.get('/api/news-quiz',base_url=ORIGIN).json
        chosen = progress['completed']['mudroom-v1']['choice']
        retry = self.client.post('/api/news-quiz/mudroom-v1',base_url=ORIGIN,json={'choice':1-chosen},headers={'Origin':ORIGIN}).json
        self.assertEqual(retry['completed']['mudroom-v1']['choice'],chosen)
        with sqlite3.connect(self.module.DATA/'games/curiosity.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM quiz_attempts').fetchone()[0],1)


if __name__ == '__main__':
    unittest.main()
