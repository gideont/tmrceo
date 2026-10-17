"""Deterministic Snake replay used to check guest leaderboard submissions."""
import math

N = 20
BASE_TICK_MS = 135
MIN_TICK_MS = 45
SPEED_GAIN = 0.18


def tick_seconds(candies):
    """Match browser delays: a gentle start, faster candy by candy."""
    return math.ceil(MIN_TICK_MS + (BASE_TICK_MS - MIN_TICK_MS) / (1 + SPEED_GAIN * candies)) / 1000


TICK_SECONDS = tick_seconds(0)
MAX_MOVES = 20000


def replay_result(seed, moves):
    """Return score and minimum duration for a legal, completed replay."""
    if not isinstance(moves, str) or not 1 <= len(moves) <= MAX_MOVES or any(move not in '0123' for move in moves):
        raise ValueError('Invalid game moves.')
    snake = [(8, 10), (7, 10), (6, 10)]
    direction = 1
    score = 0
    duration = 0
    random_state = seed

    def food():
        nonlocal random_state
        empty = [(x, y) for y in range(N) for x in range(N) if (x, y) not in snake]
        if not empty:
            return None
        random_state = (random_state * 1664525 + 1013904223) & 0xffffffff
        return empty[(random_state * len(empty)) // 4294967296]

    apple = food()
    vectors = [(0, -1), (1, 0), (0, 1), (-1, 0)]
    for step, move in enumerate(moves):
        duration += tick_seconds(score // 10)
        next_direction = int(move)
        if next_direction == (direction + 2) % 4:
            raise ValueError('The snake cannot turn backwards.')
        direction = next_direction
        vx, vy = vectors[direction]
        head = (snake[0][0] + vx, snake[0][1] + vy)
        eating = head == apple
        body = snake if eating else snake[:-1]
        collided = not (0 <= head[0] < N and 0 <= head[1] < N) or head in body
        if collided:
            if step != len(moves) - 1:
                raise ValueError('Moves continued after game over.')
            return score, duration
        snake.insert(0, head)
        if eating:
            score += 10
            apple = food()
        else:
            snake.pop()
        if apple is None:
            if step != len(moves) - 1:
                raise ValueError('Moves continued after winning.')
            return score, duration
    raise ValueError('The game has not finished.')


def replay_score(seed, moves):
    """Compatibility helper for callers interested only in the score."""
    return replay_result(seed, moves)[0]
