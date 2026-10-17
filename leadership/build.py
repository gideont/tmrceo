"""Render editable leadership data into the static homepage; no runtime JS needed."""
from html import escape as e
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def portrait(member, css_class):
    filename = member['portrait']
    if Path(filename).name != filename or not (ROOT / 'assets/team' / filename).is_file():
        raise ValueError('Portrait must name an existing file in assets/team')
    return f'<img class="{css_class}" src="/assets/team/{e(filename)}" alt="" loading="lazy" width="240" height="190">'


def render_leader(member):
    return f'''<article class="person" aria-labelledby="leader-{e(member['id'])}">
<div class="person-top"><span class="tag">{e(member['tag'])}</span><span aria-hidden="true">✷</span></div>
<div class="portrait">{portrait(member, 'leader-portrait')}</div>
<div class="person-info"><h3 id="leader-{e(member['id'])}">{e(member['name'])} <span aria-hidden="true">✦</span></h3><span class="role">{e(member['role'])}</span><p>{e(member['bio'])}</p></div>
<div class="person-foot">{e(member['footer'])}<span aria-hidden="true">♡</span></div></article>'''


def render_board_member(member):
    return f'''<details class="board-member"><summary>{portrait(member, 'board-portrait')}<span class="board-identity"><strong>{e(member['name'])}</strong><span>{e(member['role'])}</span></span><span class="board-toggle">Profile <span aria-hidden="true">+</span></span></summary><div class="board-bio"><p>{e(member['bio'])}</p></div></details>'''


def render_fundraising(data):
    """Reusable component: pass a dict from JSON now or a database query later.

    Monetary values are in the major unit of an explicit ISO currency code.
    None means unavailable, never zero. No database or public metrics API yet.
    """
    metrics = (
        ('total_funds_raised', 'Total Funds Raised', 'Total investment committed', True),
        ('available_funding', 'Available Funding', 'Funds available for projects', True),
        ('active_investors', 'Active Investors', 'Number of participating investors', False),
        ('projects_funded', 'Projects Funded', 'Children’s projects receiving support', False),
    )
    cards = []
    for key, title, description, money in metrics:
        value = data.get(key)
        if value is None:
            display = '—'
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f'{key} must be a nonnegative number or None')
            if money:
                currency = data.get('currency')
                if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
                    raise ValueError('Monetary values require a three-letter currency code')
                display = f'{currency.upper()} {value:,.2f}'
            else:
                if int(value) != value:
                    raise ValueError(f'{key} must be a whole number')
                display = f'{value:,.0f}'
        cards.append(f'<div class="funding-metric"><dt>{title}</dt><dd><span>{e(display)}</span><p>{description}</p></dd></div>')
    is_demo = data.get('is_demo', True)
    badge = 'Demonstration data · Preview only' if is_demo else 'Project funding'
    note = ('All values are placeholders, not actual financial results. A dash means data is not yet available.'
            if is_demo else 'A dash means data is not yet available.')
    return f'''<details class="fundraising-preview"><summary>Future fundraising dashboard <span aria-hidden="true">+</span></summary><div class="fundraising-content"><span class="demo-label">{badge}</span><h3>Backing their next big idea.</h3><p class="fundraising-note">{note}</p><dl class="funding-grid">{''.join(cards)}</dl></div></details>'''



def render_hiring(roles):
    cards = ''.join(f'<article class="hiring-card"><span class="open-badge">JOIN THE CREW</span><h4>{e(role["title"])}</h4><strong>{e(role["tagline"])}</strong><p>{e(role["description"])}</p><a class="text-link role-interest" href="{("#share-discovery" if role["id"] == "journalist" else "#join-team")}" data-role="{e(role["id"])}">{("Share a discovery" if role["id"] == "journalist" else "Let’s try it!")} ↗</a></article>' for role in roles)
    options = ''.join(f'<option value="{e(role["id"])}">{e(role["title"])}</option>' for role in roles)
    return f'''<section class="hiring-section" aria-labelledby="hiring-title"><div class="hiring-heading"><div><span class="eyebrow">YOUR IDEAS BELONG HERE</span><h3 id="hiring-title">We’re hiring curious minds!</h3></div><p>Pick an adventure, bring your ideas and learn as you go. Bring your curiosity! We can have more than one CEO, each leading a project, with adults nearby to help.</p></div><div class="hiring-grid">{cards}</div><details class="join-panel" id="join-team"><summary>Find your adventure on the team <span aria-hidden="true">+</span></summary><div class="join-inner"><h4>What’s your next big idea?</h4><p>Tell us a little about your idea. For young applicants, please ask a parent or guardian to help. This is an expression of interest in a learning project; submitting doesn’t assign a role.</p><form id="join-form" method="post" action="/api/team-interest"><noscript><p>Please enable JavaScript to send your interest through this form.</p></noscript><div class="join-fields"><label>Your first name or nickname<input name="name" maxlength="60" required autocomplete="nickname"></label><label>I’m curious about<select name="role" required>{options}</select></label></div><label>Parent or guardian’s contact email<input name="email" type="email" maxlength="254" required autocomplete="email"></label><label>What would you like to help make or learn?<textarea name="idea" rows="3" maxlength="1500" required></textarea></label><div class="honey" aria-hidden="true"><label>Leave blank<input name="website" tabindex="-1" autocomplete="off"></label></div><label class="consent"><input name="consent" type="checkbox" required><span>I’m the parent or guardian and agree to this information being saved privately for the team to review. Please don’t include school names, addresses or other private details.</span></label><button class="button dark" type="submit">Count me in ↗</button><p id="join-status" role="status" aria-live="polite"></p></form><p>Have a story instead? <a class="text-link" href="#share-discovery">Everyone can send a discovery ↗</a></p></div></details></section>'''


def build():
    members = json.loads((ROOT / 'leadership/members.json').read_text())
    funding = json.loads((ROOT / 'leadership/fundraising-demo.json').read_text())
    leaders = ''.join(render_leader(member) for member in members['leadership'])
    board = ''.join(render_board_member(member) for member in members['board'])
    hiring = render_hiring(members['open_roles'])
    section = f'''<!-- leadership:start -->
<section class="team-section wrap" id="team" aria-labelledby="leadership-title">
<div class="section-heading"><div><span class="eyebrow">YOUNG LEADERS. REAL POSSIBILITIES.</span><h2 id="leadership-title">Leadership Team</h2></div><p>At Tomorrow CEO, <strong>the children are the leaders.</strong> Our young leaders set the direction and learn entrepreneurship by running their own projects and businesses, with adults supporting them along the way.</p></div>
<div class="leadership-layout"><div class="team-grid">{leaders}</div><aside class="leadership-note"><span class="eyebrow">THEIR IDEAS. THEIR DIRECTION.</span><h3>Small leaders.<br>Big tomorrow.</h3><p>From “what if?” to “we made it,” our young entrepreneurs make decisions, try things out and learn along the way.</p><p>Adults bring encouragement, experience and resources. The children lead.</p><a class="text-link" href="#board">Meet the people behind them ↗</a></aside></div>
{hiring}
</section>
<section class="board-section wrap" id="board" aria-labelledby="board-title"><header class="board-heading"><span class="eyebrow">INVESTING IN THEIR POTENTIAL</span><h2 id="board-title">Board of Directors &amp; Investors</h2><p>Behind every young CEO is a network of people who believe in their potential. Our Board of Directors and Investors provides the funding, experience and resources to help young entrepreneurs turn their ideas into reality.</p><p>Parents and supporting adults empower the children through mentorship, technical and operational resources, business connections, governance and guidance. They support the young leaders as they run their businesses.</p></header>
<div class="board-list">{board}</div><p class="board-growth">A growing circle of support, with room for more parents, mentors and investors to help our young entrepreneurs thrive.</p>
{render_fundraising(funding)}
</section>
<!-- leadership:end -->'''
    path = ROOT / 'index.html'
    home = path.read_text()
    start = home.index('<!-- leadership:start -->')
    end = home.index('<!-- leadership:end -->') + len('<!-- leadership:end -->')
    path.write_text(home[:start] + section + home[end:])
    print('Built leadership, board profiles and demonstration fundraising preview.')


if __name__ == '__main__':
    build()
