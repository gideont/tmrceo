"""Guest identity, ordering and server-side Snake score validation."""
import importlib
import os
import sqlite3
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from snake_rules import replay_score, replay_result, tick_seconds

# Seed 1 places the first apple at (13, 4): go up six, right five,
# then continue right into the wall. The second apple is not on this path.
TEN_POINTS = '0' * 6 + '1' * 12
ZERO_POINTS = '1' * 12
FOUR_CANDIES = '00000011111222333222333333222233333'


class ArcadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix='tmrceo-arcade-tests-')
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

    def start(self, client=None, at=1000):
        with patch('app.time.time', return_value=at), patch('app.secrets.randbits', return_value=1):
            response = (client or self.client).post('/api/snake/runs', json={})
        self.assertEqual(response.status_code, 200)
        return response.json['run_id']

    def finish(self, run, moves=TEN_POINTS, client=None, at=1005, **extra):
        with patch('app.time.time', return_value=at):
            return (client or self.client).post(f'/api/snake/runs/{run}/finish', json={'moves': moves, **extra})

    def test_rules_known_food_and_finished_round(self):
        self.assertEqual(replay_score(1, TEN_POINTS), 10)
        self.assertEqual(replay_score(1, ZERO_POINTS), 0)
        for moves in ('', '111', '3', ZERO_POINTS + '1', 'x', '1' * 20001):
            with self.assertRaises(ValueError):
                replay_score(1, moves)

    def test_acceleration_replay_duration_and_score_acceptance(self):
        self.assertEqual(tick_seconds(0), 0.135)
        self.assertLess(tick_seconds(1), tick_seconds(0))
        self.assertLess(tick_seconds(4), tick_seconds(3))
        score, duration = replay_result(1, FOUR_CANDIES)
        self.assertEqual(score, 40)
        self.assertLess(duration, len(FOUR_CANDIES) * tick_seconds(0) - 0.5)
        self.client.post('/api/snake/player', json={'name': 'Candy Capy'})
        run = self.start()
        self.assertEqual(self.finish(run, FOUR_CANDIES, at=1000 + duration - 0.6).status_code, 400)
        result = self.finish(run, FOUR_CANDIES, at=1000 + duration)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['score'], 40)

    def test_unnamed_round_is_private_until_name_is_chosen(self):
        run = self.start()
        self.assertTrue(self.finish(run).json['needs_name'])
        self.assertEqual(self.client.get('/api/snake/leaderboard').json, {'players': []})
        self.assertEqual(self.client.post('/api/snake/player', json={'name': 'Pixel Capy'}).status_code, 200)
        response = self.finish(run, score=999999)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['score'], 10)
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], [{'name': 'Pixel Capy', 'score': 10}])

    def test_best_only_rename_and_repeat_finish(self):
        self.client.post('/api/snake/player', json={'name': 'BeaverByte'})
        run = self.start()
        self.assertEqual(self.finish(run).json['best_score'], 10)
        self.assertEqual(self.finish(run).status_code, 200)
        weaker = self.start(at=1010)
        self.assertEqual(self.finish(weaker, ZERO_POINTS, at=1015).json['best_score'], 10)
        renamed = self.client.post('/api/snake/player', json={'name': 'CapyCaptain'})
        self.assertEqual(renamed.json, {'name': 'CapyCaptain', 'best_score': 10})
        board = self.client.get('/api/snake/leaderboard').json['players']
        self.assertEqual(board, [{'name': 'CapyCaptain', 'score': 10}, {'name': 'CapyCaptain', 'score': 0}])
        self.assertEqual(self.client.get('/api/snake/player').json['name'], 'CapyCaptain')

    def test_saved_round_rank_uses_exact_round_and_earlier_ties(self):
        self.client.post('/api/snake/player', json={'name': 'Champion Capy'})
        first = self.start()
        self.assertEqual(self.finish(first).json['rank'], 1)
        self.assertEqual(self.finish(first).json['rank'], 1)
        second = self.start(at=1010)
        self.assertEqual(self.finish(second, at=1015).json['rank'], 2)
        lower = self.start(at=1020)
        result = self.finish(lower, ZERO_POINTS, at=1025).json
        self.assertEqual(result['rank'], 3)
        self.assertEqual(result['best_score'], 10)
        self.assertEqual(result['score'], 0)
        # Another player's higher rounds push this exact round out of the top 10.
        with self.module.db() as connection:
            connection.execute('INSERT INTO snake_players VALUES (?, ?, ?, ?)', ('other', 'Other Capy', 20, 900))
            for index in range(9):
                connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', (f'other-{index}', 'other', 20, 900 + index))
        self.assertEqual(self.finish(lower, ZERO_POINTS, at=1026).json['rank'], 12)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM snake_scores').fetchone()[0], 12)

    def test_record_details_dates_ties_and_new_record(self):
        empty = self.client.get('/api/snake/leaderboard/details')
        self.assertEqual(empty.json['players'], [])
        self.assertIsNone(empty.json['record_since'])
        self.assertIsNone(empty.json['unbeaten_seconds'])
        self.client.post('/api/snake/player', json={'name': 'Record Capy'})
        first = self.start()
        self.finish(first)
        second = self.start(at=1010)
        self.finish(second, at=1015)
        with patch('app.time.time', return_value=1125):
            response = self.client.get('/api/snake/leaderboard/details')
        details = response.json
        self.assertEqual(details['record_since'], 1005)
        self.assertEqual(details['unbeaten_seconds'], 120)
        self.assertEqual(details['players'][0], {'rank': 1, 'name': 'Record Capy', 'score': 10, 'achieved_at': 1005})
        self.assertEqual(details['players'][1]['rank'], 2)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('email', response.text)
        self.assertNotIn('player_id', response.text)
        higher = self.start(at=1020)
        self.finish(higher, FOUR_CANDIES, at=1025)
        with patch('app.time.time', return_value=1125):
            details = self.client.get('/api/snake/leaderboard/details').json
        self.assertEqual(details['record_since'], 1025)
        self.assertEqual(details['unbeaten_seconds'], 100)
        self.assertEqual(details['players'][0]['score'], 40)

    def test_record_details_keep_start_times_private(self):
        with self.module.db() as connection:
            connection.execute('INSERT INTO snake_players VALUES (?, ?, ?, ?)', ('legacy', 'Original Champion', 80, 100))
            connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', ('legacy-round', 'legacy', 80, 100))
        details = self.client.get('/api/snake/leaderboard/details').json
        self.assertNotIn('started_at', details['players'][0])
        self.assertEqual(details['players'][0]['achieved_at'], 100)

    def test_round_ownership_speed_expiry_and_invalid_moves(self):
        self.client.post('/api/snake/player', json={'name': 'Player One'})
        run = self.start()
        other = self.app.test_client()
        self.assertEqual(self.finish(run, client=other).status_code, 404)
        self.assertEqual(self.finish(run, at=1000).status_code, 400)
        self.assertEqual(self.finish(run, moves='333').status_code, 400)
        self.assertEqual(self.finish(run, at=8300).status_code, 404)
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], [])

    def test_top_ten_order_and_ties_no_private_ids(self):
        with self.module.db() as connection:
            for index in range(12):
                connection.execute('INSERT INTO snake_players VALUES (?, ?, ?, ?)', (f'guest-{index}', f'Player {index}', index * 10, 1000 + index))
                connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', (f'run-{index}', f'guest-{index}', index * 10, 1000 + index))
            connection.execute('INSERT INTO snake_players VALUES (?, ?, ?, ?)', ('tie', 'Earlier tie', 110, 900))
            connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', ('tie-run', 'tie', 110, 900))
        response = self.client.get('/api/snake/leaderboard')
        players = response.json['players']
        self.assertEqual(len(players), 10)
        self.assertEqual(players[0], {'name': 'Earlier tie', 'score': 110})
        self.assertEqual(players[1], {'name': 'Player 11', 'score': 110})
        self.assertTrue(all(players[i]['score'] >= players[i+1]['score'] for i in range(9)))
        self.assertNotIn('id', players[0])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_same_player_can_hold_all_ten_spots_without_duplicate_submissions(self):
        self.client.post('/api/snake/player', json={'name': 'Arcade Capy'})
        for index in range(12):
            run = self.start(at=1000 + index * 10)
            moves = TEN_POINTS if index < 8 else ZERO_POINTS
            self.assertEqual(self.finish(run, moves, at=1005 + index * 10).status_code, 200)
        self.assertEqual(self.finish(run, ZERO_POINTS, at=1120).status_code, 200)
        players = self.client.get('/api/snake/leaderboard').json['players']
        self.assertEqual(len(players), 10)
        self.assertTrue(all(p['name'] == 'Arcade Capy' for p in players))
        self.assertEqual([p['score'] for p in players], [10] * 8 + [0] * 2)
        with self.module.db() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM snake_scores').fetchone()[0], 12)
        self.start(at=10000)  # Temporary replay cleanup must not erase high scores.
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], players)
        self.assertEqual(self.client.get('/api/snake/player').json['best_score'], 10)

    def test_existing_best_is_migrated_once_without_inventing_old_rounds(self):
        with sqlite3.connect(self.module.DATA / 'newsletter.sqlite3') as connection:
            connection.execute('CREATE TABLE snake_players (id TEXT PRIMARY KEY, name TEXT NOT NULL, best_score INTEGER, best_at REAL)')
            connection.execute('INSERT INTO snake_players VALUES (?, ?, ?, ?)', ('old-player', 'Old Champion', 80, 100))
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], [{'name': 'Old Champion', 'score': 80}])
        with self.module.db() as connection:
            connection.execute('UPDATE snake_players SET best_score = 90 WHERE id = ?', ('old-player',))
            connection.execute('INSERT INTO snake_scores VALUES (?, ?, ?, ?)', ('new-round', 'old-player', 90, 200))
        expected = [{'name': 'Old Champion', 'score': 90}, {'name': 'Old Champion', 'score': 80}]
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], expected)
        self.assertEqual(self.client.get('/api/snake/leaderboard').json['players'], expected)

    def test_nickname_validation_unicode_and_origin(self):
        for name in ('', 'A', 'A' * 21, '<script>', 'person@example.com', '---'):
            self.assertEqual(self.client.post('/api/snake/player', json={'name': name}).status_code, 400)
        self.assertEqual(self.client.post('/api/snake/player', json={'name': '水豚队长'}).status_code, 200)
        self.assertEqual(self.client.post('/api/snake/player', json={'name': 'Other'}, headers={'Origin': 'https://other.example'}).status_code, 403)
        self.assertEqual(self.client.get('/api/snake/player').json['name'], '水豚队长')

    def test_guest_cookie_and_start_rate_limit(self):
        response = self.client.get('/api/snake/player', base_url='https://tmrceo.com')
        for attribute in ('HttpOnly', 'Secure', 'SameSite=Lax'):
            self.assertIn(attribute, response.headers['Set-Cookie'])
        with patch('app.time.time', return_value=1000):
            for _ in range(30):
                self.assertEqual(self.client.post('/api/snake/runs', json={}).status_code, 200)
            self.assertEqual(self.client.post('/api/snake/runs', json={}).status_code, 429)


if __name__ == '__main__':
    unittest.main()
