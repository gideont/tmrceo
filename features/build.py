"""Build compact task tables and a Gantt timeline with sample dates."""
from datetime import date
from html import escape as e
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMELINE_START = date(2026, 10, 1)


def display_dates(feature):
    """Keep imagined presentation dates separate from recorded release dates."""
    sample = feature.get('timeline_date_basis') == 'sample'
    requested = date.fromisoformat(feature['timeline_requested_on'] if sample else feature['requested_on'])
    raw_completed = feature.get('timeline_completed_on') if sample else feature.get('completed_on')
    completed = date.fromisoformat(raw_completed) if raw_completed else None
    if completed and completed < requested:
        raise ValueError('Completion cannot be before request')
    if (feature['status'] == 'shipped') != bool(completed):
        raise ValueError('Completed dates must match shipped status')
    if requested < TIMELINE_START:
        raise ValueError('Task starts before timeline kickoff')
    return requested, completed


def short_date(value):
    return f'<time datetime="{value.isoformat()}">{value.strftime("%b %d").replace(" 0", " ")}</time>'


def render_table(features, section_id, timeline_end):
    days = (timeline_end - TIMELINE_START).days + 1
    rows = []
    for feature in features:
        requested, completed = display_dates(feature)
        left = (requested - TIMELINE_START).days / days * 100
        if completed:
            width = ((completed - requested).days + 1) / days * 100
            bar = f'<span class="gantt-bar" style="left:{left:.3f}%;width:{width:.3f}%"></span>'
            interval = f'Sample dates: requested {requested.isoformat()}, completed {completed.isoformat()}'
        else:
            bar = f'<span class="gantt-queued" style="left:{left:.3f}%"></span>'
            interval = f'Sample request date {requested.isoformat()}; not completed or scheduled'
        state = 'queued' if feature['status'] == 'queued' else 'shipped'
        label = 'To do' if state == 'queued' else 'Done'
        rows.append(f'''<tr><th scope="row"><span class="feature-state {state}">{label}</span><span class="task-name">{e(feature['title'])}</span></th><td class="task-description">{e(feature['description'])}</td><td>{short_date(requested)}</td><td>{short_date(completed) if completed else '<span class="not-yet">Not yet</span>'}</td><td><div class="gantt-track" role="img" aria-label="{e(interval)}" style="--days:{days}">{bar}</div></td></tr>''')
    ticks = ''.join(f'<span style="left:{offset / days * 100:.3f}%">{offset+1}</span>' for offset in range(days) if offset == 0 or (offset+1) % 4 == 0 or offset == days-1)
    return f'''<p class="table-scroll-hint">On small screens, scroll across to see the timeline →</p><div class="task-scroll" tabindex="0" role="region" aria-label="{section_id} tasks and sample timeline"><table class="task-table"><caption class="sr-only">{section_id}: one task per row. Dates shown are sample dates.</caption><colgroup><col class="task-col"><col class="description-col"><col class="date-col"><col class="date-col"><col class="timeline-col"></colgroup><thead><tr><th scope="col">Task</th><th scope="col">Short description</th><th scope="col">Requested</th><th scope="col">Completed</th><th scope="col"><span class="timeline-month">October 2026 · Sample dates</span><div class="gantt-axis" aria-label="October 1 to {timeline_end.day}">{ticks}</div></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>'''


def build():
    features = json.loads((ROOT / 'features/features.json').read_text())
    if len({feature['id'] for feature in features}) != len(features):
        raise ValueError('Feature IDs must be unique')
    for feature in features:
        if feature['status'] not in {'queued', 'shipped'}:
            raise ValueError('Feature status must be queued or shipped')
        # Validate and preserve recorded dates as well as sample ones.
        if feature.get('requested_on'):
            date.fromisoformat(feature['requested_on'])
        if feature.get('completed_on'):
            date.fromisoformat(feature['completed_on'])
        display_dates(feature)
    timeline_end = max([TIMELINE_START] + [end or start for start, end in map(display_dates, features)])
    queued = sorted((feature for feature in features if feature['status'] == 'queued'), key=lambda feature: display_dates(feature)[0])
    shipped = sorted((feature for feature in features if feature['status'] == 'shipped'), key=lambda feature: display_dates(feature)[1])
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><meta name="description" content="Our to-do list, completed work and an October project timeline with sample dates."><meta name="theme-color" content="#f6f3e9"><title>Feature tracker · Tomorrow CEO</title><link rel="stylesheet" href="/styles.css"></head>
<body><header class="header wrap"><a class="logo" href="/" aria-label="Tomorrow CEO home">tmr<span>CEO</span><i aria-hidden="true">✳</i></a><a class="text-link" href="/">Back to Tomorrow CEO ↗</a></header>
<main class="features-page wrap"><header class="features-intro"><span class="eyebrow">THE TOMORROW BUILD LOG</span><h1>Small steps.<br><span>Waves of kid power.</span></h1><p>Ideas become games, stories and shared adventures. Here’s what’s next, and what our growing crew has already made.</p><nav class="feature-jumps" aria-label="Feature tracker sections"><a href="#queue">To do <span>{len(queued)}</span> ↓</a><a href="#history">Accomplished <span>{len(shipped)}</span> ↓</a></nav></header>
<section class="feature-section" id="queue" aria-labelledby="queue-title"><div class="feature-section-heading"><div><span class="eyebrow">NEXT WAVE OF IDEAS</span><h2 id="queue-title">Features in queue</h2></div><p>Our to-do list comes first. No completion dates or delivery promises yet.</p></div>{render_table(queued, 'To-do', timeline_end)}</section>
<section class="feature-section" id="history" aria-labelledby="history-title"><div class="feature-section-heading"><div><span class="eyebrow">LOOK WHAT WE’VE MADE TOGETHER</span><h2 id="history-title">Built so far</h2></div><p>Games, stories and little wins from our growing crew. Look what we’re making together!</p></div>{render_table(shipped, 'Completed', timeline_end)}</section>
<aside class="kid-power-invite"><span class="eyebrow">THE NEXT WAVE COULD BE YOU</span><h2>More kids. More ideas.<br>More “we made that!”</h2><p>Design a game, discover a story, explore a book or lead your own project. Bring a friend and your curiosity. Let’s build something great together.</p><a class="button dark" href="/#team">Join the next wave ↗</a></aside></main>
<footer class="footer wrap"><a class="logo" href="/">tmr<span>CEO</span><i aria-hidden="true">✳</i></a><span>Little team. Big tomorrow.</span><div><a href="/">Back to the fun ↗</a><a href="/firststone">Firststone ↗</a><a href="/terms">Terms of Use</a><a href="/privacy">Privacy &amp; email preferences</a></div></footer></body></html>'''
    (ROOT / 'features/index.html').write_text(page + '\n')
    print(f'Built compact Gantt tracker: {len(queued)} queued, {len(shipped)} completed; sample dates captioned.')


if __name__ == '__main__':
    build()
