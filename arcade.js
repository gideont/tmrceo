'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const NAME_KEY = 'tmrceo-snake-name';
  const form = $('player-name-form');
  const panel = $('player-name-panel');
  const message = $('player-name-status');
  const scoreboardStatus = $('leaderboard-status');
  let nickname = '';
  let pending = [];
  let flushing = false;
  const celebrated = new Set();
  const celebration = $('score-celebration');
  let celebrationRank = null;
  let confettiTimer = null;

  function celebrate(result, runId) {
    if (!Number.isInteger(result.rank) || result.rank < 1 || result.rank > 10 || celebrated.has(runId)) return;
    celebrated.add(runId);
    celebrationRank = result.rank;
    const champion = result.rank === 1;
    celebration.classList.toggle('is-champion', champion);
    $('celebration-badge').innerHTML = champion ? '<svg viewBox="0 0 80 80" width="88" height="88" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M23 18H10v9q0 17 19 17m28-26h13v9q0 17-19 17" stroke="#bd8432" stroke-width="6"/><path d="M22 12h36v20q0 22-18 22T22 32Z" fill="#edbd61" stroke="#aa742a" stroke-width="3"/><path d="M28 17v14q0 12 7 16" stroke="#ffedb0" stroke-width="4" stroke-linecap="round"/><path d="M35 53h10v14H35z" fill="#bd8432"/><path d="M25 67h30v9H25z" fill="#edbd61" stroke="#aa742a" stroke-width="3"/><path d="m40 22 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z" fill="#fff4c9"/></svg>' : '<svg viewBox="0 0 80 80" width="72" height="72" xmlns="http://www.w3.org/2000/svg"><path d="m40 6 10 22 24 3-18 17 5 25-21-12-21 12 5-25L6 31l24-3Z" fill="#edbd61" stroke="#aa742a" stroke-width="3" stroke-linejoin="round"/><path d="m40 17-7 16-16 2" fill="none" stroke="#fff4c9" stroke-width="4" stroke-linecap="round"/></svg>';
    $('celebration-kicker').textContent = champion ? 'A HUGE ROUND OF APPLAUSE!' : `HALL OF SNAKE · NUMBER ${result.rank}`;
    $('celebration-title').textContent = champion ? 'You’re number one!' : 'You made the top 10!';
    $('celebration-copy').textContent = champion
      ? `Congratulations, ${nickname}! You made it to the very top! ${result.score} points. The best score on the board!`
      : `High five, ${nickname}! Your ${result.score}-point round landed at #${result.rank}. That’s a spot in the Hall of Snake!`;
    $('celebration-applause').hidden = $('sound').getAttribute('aria-pressed') === 'true';
    const particles = celebration.querySelector('.celebration-confetti');
    particles.replaceChildren();
    clearTimeout(confettiTimer);
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const colours = ['#edbd61', '#779462', '#e986a3', '#3d8ec9', '#b765ad'];
      for (let i = 0; i < (champion ? 70 : 28); i++) {
        const piece = document.createElement('i');
        piece.style.cssText = `--x:${Math.random()*100}%;--drift:${(Math.random()-.5)*260}px;--delay:${Math.random()*.7}s;--spin:${Math.random()*1000-500}deg;background:${colours[i%colours.length]}`;
        particles.appendChild(piece);
      }
      confettiTimer = setTimeout(() => particles.replaceChildren(), 4300);
    }
    document.dispatchEvent(new Event('snake:name-edit'));
    if (!celebration.open) celebration.showModal();
    document.dispatchEvent(new CustomEvent('snake:celebrate', {detail: {rank: result.rank}}));
  }
  celebration.addEventListener('close', () => {
    clearTimeout(confettiTimer);
    celebration.querySelector('.celebration-confetti').replaceChildren();
    document.dispatchEvent(new Event('snake:celebration-stop'));
    $('start').focus({preventScroll: true});
  });
  $('celebration-quit').addEventListener('click', () => celebration.close());
  $('celebration-play').addEventListener('click', () => {
    celebration.close();
    $('start').click();
  });
  $('celebration-applause').addEventListener('click', () => {
    if ($('sound').getAttribute('aria-pressed') !== 'true') $('sound').click();
    $('celebration-applause').hidden = true;
    document.dispatchEvent(new CustomEvent('snake:celebrate', {detail: {rank: celebrationRank}}));
  });
  try { nickname = localStorage.getItem(NAME_KEY) || ''; } catch {}
  if (!/^[\p{L}\p{N} ._-]{2,20}$/u.test(nickname)) nickname = '';

  async function api(path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(path, {
        method: payload === undefined ? 'GET' : 'POST',
        headers: payload === undefined ? {} : {'Content-Type': 'application/json'},
        body: payload === undefined ? undefined : JSON.stringify(payload),
        signal: controller.signal
      });
      const result = await response.json();
      if (!response.ok) {const error = Error(result.error || 'Please try again in a moment.'); error.status = response.status; throw error;}
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw Error('The scoreboard is taking a break. Please try again.');
      throw error;
    } finally { clearTimeout(timer); }
  }

  function welcome(returning = true) {
    $('player-welcome').textContent = nickname
      ? `${returning ? 'Welcome back' : 'You’re up'}, ${nickname}!`
      : 'Ready, future high scorer?';
    $('change-player-name').hidden = !nickname;
  }
  function remember(name) {
    nickname = name;
    try { localStorage.setItem(NAME_KEY, name); } catch {
      message.textContent = 'Nickname saved for this visit. This browser is not allowing local storage.';
    }
  }

  async function refreshStats() {
    const label = $('snake-play-stats');
    try {
      const stats = await api('/api/snake/stats');
      label.textContent = `${stats.players.toLocaleString()} ${stats.players === 1 ? 'player' : 'players'} · ${stats.plays.toLocaleString()} recorded ${stats.plays === 1 ? 'play' : 'plays'}`;
    } catch {label.textContent = 'Play count is taking a little break.';}
  }

  const details = $('leaderboard-details');
  let recordClock = null;
  let detailsVersion = 0;
  function dateCell(epoch) {
    const cell = document.createElement('td');
    if (!Number.isFinite(epoch) || epoch <= 0) {cell.textContent = 'Not recorded';return cell;}
    const date = new Date(epoch * 1000);
    const stamp = document.createElement('time');
    stamp.dateTime = date.toISOString();
    stamp.textContent = new Intl.DateTimeFormat(undefined, {year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'}).format(date);
    cell.appendChild(stamp);
    return cell;
  }
  function standingDuration(total) {
    const seconds = Math.max(0, Math.floor(total));
    const days = Math.floor(seconds/86400), hours = Math.floor(seconds%86400/3600), minutes = Math.floor(seconds%3600/60), rest = seconds%60;
    if (days) return `${days}d ${hours}h ${minutes}m`;
    if (hours) return `${hours}h ${minutes}m ${rest}s`;
    if (minutes) return `${minutes}m ${rest}s`;
    return `${rest}s`;
  }
  async function loadRecordDetails() {
    const version = ++detailsVersion;
    clearInterval(recordClock);
    $('record-details-status').textContent = 'Opening the record book…';
    $('record-summary').hidden = true;
    $('record-details-rows').replaceChildren();
    $('record-timezone').textContent = '';
    try {
      const result = await api('/api/snake/leaderboard/details');
      if (version !== detailsVersion || !details.open) return;
      const rows = document.createDocumentFragment();
      for (const player of result.players) {
        const row = document.createElement('tr');
        for (const value of [String(player.rank).padStart(2,'0'),player.name,String(player.score).padStart(3,'0')]) {
          const cell = document.createElement('td');cell.textContent=value;row.appendChild(cell);
        }
        row.appendChild(dateCell(player.achieved_at));rows.appendChild(row);
      }
      $('record-details-rows').replaceChildren(rows);
      $('record-timezone').textContent = `Times shown in your local time (${Intl.DateTimeFormat().resolvedOptions().timeZone}).`;
      $('record-summary').hidden = !result.players.length;
      if (result.players.length) {
        const leader = result.players[0];
        $('record-holder').textContent = `${leader.name} · ${leader.score} points`;
        const date = dateCell(result.record_since).firstChild;
        $('record-set-at').replaceChildren(document.createTextNode('Record set: '),date);
        if (Number.isFinite(result.unbeaten_seconds)) {
          const received = performance.now();
          const update = () => {$('record-standing').textContent = `Unbeaten for ${standingDuration(result.unbeaten_seconds + (performance.now()-received)/1000)}`;};
          update();recordClock=setInterval(update,1000);
        } else $('record-standing').textContent = 'Record date was not recorded.';
      }
      $('record-details-status').textContent = result.players.length ? 'The record below reflects the latest refresh.' : 'No scores yet. Could yours be the first record?';
    } catch (error) {
      if (version === detailsVersion) $('record-details-status').textContent = error.message || 'The record book couldn’t load. Please try again.';
    }
  }
  $('leaderboard-more').addEventListener('click', () => {
    document.dispatchEvent(new Event('snake:name-edit'));
    details.showModal();loadRecordDetails();
  });
  $('leaderboard-details-close').addEventListener('click', () => details.close());
  $('record-details-refresh').addEventListener('click', loadRecordDetails);
  details.addEventListener('close', () => {detailsVersion++;clearInterval(recordClock);});

  async function refreshLeaderboard() {
    try {
      const {players} = await api('/api/snake/leaderboard');
      const rows = document.createDocumentFragment();
      for (let index = 0; index < 10; index++) {
        const row = document.createElement('tr');
        const player = players[index];
        for (const value of [String(index + 1).padStart(2, '0'), player ? player.name : 'OPEN SPOT', player ? String(player.score).padStart(3, '0') : '—']) {
          const cell = document.createElement('td');
          cell.textContent = value;
          row.appendChild(cell);
        }
        if (!player) row.className = 'arcade-empty';
        rows.appendChild(row);
      }
      $('leaderboard-rows').replaceChildren(rows);
      scoreboardStatus.textContent = players.length ? 'Top 10 rounds. Same name, many spots! Ties go to the earlier score.' : 'No scores yet. Play a round and claim the first spot!';
    } catch {
      scoreboardStatus.textContent = 'The high-score board is resting. Refresh to try again; you can still play.';
    }
  }

  async function flushScores() {
    if (flushing || !pending.length) return;
    flushing = true;
    let saved = false;
    let awaitingName = false;
    let moment = null;
    $('retry-score').hidden = true;
    try {
      for (const game of [...pending]) {
        try {
          const result = await api(`/api/snake/runs/${encodeURIComponent(game.run_id)}/finish`, {moves: game.moves});
          if (Number.isInteger(result.rank) && result.rank >= 1 && result.rank <= 10 && !celebrated.has(game.run_id) && (!moment || result.rank < moment.result.rank)) moment = {result, runId: game.run_id};
          if (result.needs_name) {awaitingName = true;continue;}
          saved = true;
        } catch (error) {
          if (error.status !== 404) throw error;
          // An expired round must not block newer scores in this visit.
        }
        pending = pending.filter(item => item.run_id !== game.run_id);
      }
      $('score-submit-status').textContent = saved ? 'Score saved! Every round can earn a spot in the top 10.' : awaitingName ? 'Round recorded. Save a gamer name to add it to the high-score board.' : 'That round expired. Play again to share a fresh score.';
      await refreshLeaderboard();
    } catch (error) {
      $('score-submit-status').textContent = error.message || 'Couldn’t save your score. Your device best is still safe.';
      $('retry-score').hidden = false;
    } finally { flushing = false; if (moment) celebrate(moment.result, moment.runId); }
  }

  welcome();
  const ready = (async () => {
    try {
      await window.tmrceoAuth?.ready;
      let player = await api('/api/snake/player');
      if (!player.name && nickname && !window.tmrceoAuth?.authenticated) player = await api('/api/snake/player', {name: nickname});
      if (player.name) { remember(player.name); welcome(); }
      else if (window.tmrceoAuth?.authenticated) {
        nickname = '';
        try { localStorage.removeItem(NAME_KEY); } catch {}
        welcome();
        showNameForm();
      }
    } catch { /* Local names and the game remain available if the server is offline. */ }
  })();
  refreshLeaderboard();
  refreshStats();

  function showNameForm() {
    panel.hidden = false;
    $('gamer-name').value = nickname;
    $('gamer-name').focus({preventScroll: true});
    panel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
  $('change-player-name').addEventListener('click', () => {
    document.dispatchEvent(new Event('snake:name-edit'));
    showNameForm();
  });
  $('skip-player-name').addEventListener('click', () => {
    panel.hidden = true;
    $('start').focus({preventScroll: true});
  });
  $('retry-score').addEventListener('click', flushScores);
  $('refresh-leaderboard').addEventListener('click', refreshLeaderboard);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    message.textContent = 'Saving your gamer name…';
    try {
      await ready;
      const player = await api('/api/snake/player', {name: $('gamer-name').value});
      remember(player.name);
      welcome(false);
      panel.hidden = true;
      message.textContent = '';
      await flushScores();
      await refreshLeaderboard();
    } catch (error) {
      message.textContent = error.message || 'Couldn’t save your name. Please try again.';
    } finally { button.disabled = false; }
  });

  document.addEventListener('tmrceo:auth-change', async event => {
    await ready;
    const {action, authenticated} = event.detail;
    if (action === 'logout') {
      nickname = '';
      pending = [];
      panel.hidden = true;
      try {localStorage.removeItem(NAME_KEY);} catch {}
      welcome();
    }
    try {
      const player = await api('/api/snake/player');
      nickname = '';
      if (player.name) remember(player.name);
      else { try { localStorage.removeItem(NAME_KEY); } catch {} }
      welcome();
      if (authenticated && !player.name) showNameForm();
      if (authenticated) await flushScores();
      await refreshLeaderboard();
    } catch {
      $('score-submit-status').textContent = 'Your sign-in changed. Refresh to update your gamer profile.';
    }
  });

  window.tmrceoArcade = {
    async startRun() {
      panel.hidden = true;
      $('score-submit-status').textContent = '';
      await ready;
      try { const run = await api('/api/snake/runs', {}); refreshStats(); return run; }
      catch {
        $('score-submit-status').textContent = 'Playing without the scoreboard for now. Your device best still counts.';
        return null;
      }
    },
    gameOver(run, moves) {
      if (run && moves.length <= 20000) {
        pending.push({run_id: run.run_id, moves});
        if (pending.length > 5) pending.shift();
      }
      if (!nickname) showNameForm();
      flushScores();
    }
  };
})();
