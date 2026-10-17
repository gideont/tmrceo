'use strict';
(() => {
  const section = document.getElementById('do-you-know');
  if (!section) return;
  const cards = [...section.querySelectorAll('[data-question]')];
  const points = document.getElementById('quiz-points');
  const signin = document.getElementById('quiz-signin');
  let progress = {authenticated: false, points: 0, completed: {}};
  let generation = 0;
  let loaded = false;

  async function api(path, choice) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path, {
        method: choice === undefined ? 'GET' : 'POST',
        headers: choice === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRF-Token': window.tmrceoAuth?.csrfToken || ''},
        body: choice === undefined ? undefined : JSON.stringify({choice}), signal: controller.signal
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'Couldn’t check that answer. Try again in a moment.');
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw Error('The questions are taking a little break. Try again shortly.');
      throw error;
    } finally { clearTimeout(timer); }
  }

  function render() {
    points.textContent = progress.authenticated
      ? `Your curiosity points: ${progress.points.toLocaleString()}`
      : 'Try a question. Sign in to save your curiosity points.';
    signin.hidden = progress.authenticated;
    for (const card of cards) {
      const completed = progress.completed[card.dataset.question];
      card.classList.toggle('quiz-unlocked', Boolean(completed?.correct));
      for (const button of card.querySelectorAll('[data-choice]')) {
        const selected = completed && Number(button.dataset.choice) === completed.choice;
        button.disabled = !loaded || Boolean(completed) || card.dataset.busy === 'true';
        button.setAttribute('aria-pressed', String(Boolean(selected)));
        button.classList.toggle('quiz-correct', Boolean(selected && completed.correct));
        button.classList.toggle('quiz-wrong', Boolean(selected && !completed.correct));
        button.setAttribute('aria-label', button.textContent + (selected ? (completed.correct ? ' — Correct answer' : ' — Incorrect answer') : ''));
      }
      if (completed) card.querySelector('.quiz-feedback').textContent = (completed.correct ? 'Correct! ' : 'Not quite! ') + completed.explanation + (completed.correct ? (progress.authenticated ? ' +10 points saved.' : ' Sign in to save your 10 points.') : ' Your answer is locked. Keep exploring!');
    }
  }

  async function load() {
    const version = ++generation;
    loaded = false;
    progress = {authenticated: false, points: 0, completed: {}};
    for (const card of cards) {card.dataset.busy = '';card.querySelector('.quiz-feedback').textContent = '';}
    render();
    try {
      const result = await api('/api/news-quiz');
      if (version !== generation) return;
      progress = result;
      loaded = true;
      render();
    } catch {
      if (version === generation) points.textContent = 'Points couldn’t load. The story clues are still here—try again shortly.';
    }
  }

  const ready = (async () => {await window.tmrceoAuth?.ready; await load();})();
  for (const card of cards) card.addEventListener('click', async event => {
    const button = event.target.closest('[data-choice]');
    if (!button || button.disabled || card.dataset.busy === 'true') return;
    card.dataset.busy = 'true';
    await ready;
    if (progress.completed[card.dataset.question]) {card.dataset.busy = '';render();return;}
    const version = generation;
    const choice = Number(button.dataset.choice);
    const feedback = card.querySelector('.quiz-feedback');
    card.dataset.busy = 'true';
    render();
    feedback.textContent = 'Checking your discovery…';
    try {
      const result = await api(`/api/news-quiz/${encodeURIComponent(card.dataset.question)}`, choice);
      if (version !== generation) return;
      progress = {...result, points: Math.max(progress.points, result.points), completed: {...progress.completed, ...result.completed}};
      render();
    } catch (error) {
      if (version === generation) feedback.textContent = error.message + ' Reload to check whether your answer was saved.';
    } finally {
      if (version === generation && progress.completed[card.dataset.question]) {card.dataset.busy = '';render();}
    }
  });
  document.addEventListener('tmrceo:auth-change', load);
  document.querySelector('a.quiz-clue[href="#word-mudroom"]')?.addEventListener('click', () => {
    document.getElementById('mudroom-clue').open = true;
  });
})();
