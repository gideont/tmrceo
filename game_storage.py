"""Separate game databases attached for atomic account/game transactions."""
from pathlib import Path


def attach_games(connection, data):
    directory = Path(data) / 'games'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection.execute('ATTACH DATABASE ? AS snake', (str(directory / 'snake.sqlite3'),))
    connection.execute('ATTACH DATABASE ? AS quiz', (str(directory / 'curiosity.sqlite3'),))
    connection.execute('CREATE TABLE IF NOT EXISTS snake.snake_players (id TEXT PRIMARY KEY, name TEXT NOT NULL, best_score INTEGER, best_at REAL)')
    connection.execute('CREATE TABLE IF NOT EXISTS snake.snake_runs (id TEXT PRIMARY KEY, player TEXT NOT NULL, seed INTEGER NOT NULL, created_at REAL NOT NULL, finished INTEGER NOT NULL DEFAULT 0)')
    connection.execute('CREATE INDEX IF NOT EXISTS snake.snake_runs_player_time ON snake_runs (player, created_at)')
    connection.execute('CREATE TABLE IF NOT EXISTS snake.snake_scores (run_id TEXT PRIMARY KEY, player TEXT NOT NULL, score INTEGER NOT NULL, achieved_at REAL NOT NULL)')
    connection.execute('CREATE INDEX IF NOT EXISTS snake.snake_scores_ranking ON snake_scores (score DESC, achieved_at ASC, run_id ASC)')
    connection.execute('CREATE INDEX IF NOT EXISTS snake.snake_scores_player ON snake_scores (player)')
    connection.execute('CREATE TABLE IF NOT EXISTS snake.snake_play_log (run_id TEXT PRIMARY KEY, player TEXT NOT NULL, username TEXT, email TEXT, play_starttime_epoch REAL, score INTEGER, finished_at REAL, source TEXT NOT NULL DEFAULT "live")')
    connection.execute('CREATE INDEX IF NOT EXISTS snake.snake_log_player ON snake_play_log (player)')
    connection.execute('CREATE TABLE IF NOT EXISTS snake.schema_migrations (name TEXT PRIMARY KEY)')
    connection.execute('CREATE TABLE IF NOT EXISTS quiz.quiz_rewards (user_id TEXT NOT NULL, question_id TEXT NOT NULL, points INTEGER NOT NULL, answered_at REAL NOT NULL, PRIMARY KEY (user_id, question_id))')
    connection.execute('CREATE TABLE IF NOT EXISTS quiz.quiz_attempts (identity TEXT NOT NULL, question_id TEXT NOT NULL, choice INTEGER NOT NULL, correct INTEGER NOT NULL, answered_at REAL NOT NULL, PRIMARY KEY (identity, question_id))')
    connection.execute('CREATE TABLE IF NOT EXISTS quiz.schema_migrations (name TEXT PRIMARY KEY)')
    main_tables = {r[0] for r in connection.execute("SELECT name FROM main.sqlite_master WHERE type='table'")}
    if not connection.execute('SELECT 1 FROM snake.schema_migrations WHERE name=?', ('separate-games-v1',)).fetchone():
        with connection:
            inserted = connection.execute('INSERT OR IGNORE INTO snake.schema_migrations VALUES (?)', ('separate-games-v1',)).rowcount
            if inserted:
                for table in ('snake_players', 'snake_runs', 'snake_scores'):
                    if table in main_tables:
                        connection.execute(f'INSERT OR IGNORE INTO snake.{table} SELECT * FROM main.{table}')
                if 'snake_players' in main_tables and 'snake_scores' not in main_tables:
                    connection.execute("INSERT OR IGNORE INTO snake.snake_scores SELECT 'legacy_' || id, id, best_score, COALESCE(best_at,0) FROM snake.snake_players WHERE best_score IS NOT NULL")
                connection.execute("INSERT OR IGNORE INTO snake.snake_play_log SELECT r.id,r.player,p.name,NULL,r.created_at,s.score,s.achieved_at,'legacy_run' FROM snake.snake_runs r LEFT JOIN snake.snake_players p ON r.player=p.id LEFT JOIN snake.snake_scores s ON s.run_id=r.id")
                connection.execute("INSERT OR IGNORE INTO snake.snake_play_log SELECT s.run_id,s.player,p.name,NULL,NULL,s.score,s.achieved_at,CASE WHEN s.run_id LIKE 'legacy_%' THEN 'legacy_best' ELSE 'legacy_round' END FROM snake.snake_scores s LEFT JOIN snake.snake_players p ON s.player=p.id")
                for table in ('snake_scores', 'snake_runs', 'snake_players'):
                    if table in main_tables:
                        connection.execute(f'DROP TABLE main.{table}')
    if not connection.execute('SELECT 1 FROM quiz.schema_migrations WHERE name=?', ('separate-games-v1',)).fetchone():
        with connection:
            inserted = connection.execute('INSERT OR IGNORE INTO quiz.schema_migrations VALUES (?)', ('separate-games-v1',)).rowcount
            if inserted and 'quiz_rewards' in main_tables:
                connection.execute('INSERT OR IGNORE INTO quiz.quiz_rewards SELECT * FROM main.quiz_rewards')
                connection.execute('DROP TABLE main.quiz_rewards')
