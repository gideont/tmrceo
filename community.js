// Reader likes and expressions of interest use the existing private server storage.
(() => {
  const status = document.getElementById('books-status');
  const buttons = [...document.querySelectorAll('.book-like')];
  function updateButton(button, book) {
    button.setAttribute('aria-pressed', String(book.liked));
    button.querySelector('[aria-hidden]').textContent = book.liked ? '♥' : '♡';
    button.querySelector('.like-word').textContent = book.liked ? 'Liked' : 'Like';
    button.querySelector('.like-count').textContent = book.likes.toLocaleString();
  }
  async function loadLikes() {
    try {
      const response = await fetch('/api/books');
      if (!response.ok) throw Error('Reader likes are unavailable. You can still explore every book.');
      const books = await response.json();
      for (const button of buttons) {
        updateButton(button, books[button.dataset.book]);
        button.disabled = false;
      }
      status.textContent = 'Reader likes are shared. You can like each book once per browser and tap again to undo.';
    } catch (error) { status.textContent = error.message; }
  }
  if (status) loadLikes();
  for (const button of buttons) button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const response = await fetch(`/api/books/${button.dataset.book}/like`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({liked: button.getAttribute('aria-pressed') !== 'true'})
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'Could not save your like. Please try again.');
      updateButton(button, result);
      status.textContent = result.liked ? 'Your like is saved. A good book is even better shared!' : 'Your like has been removed.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });

  function openJoinPanel() {
    const panel = document.getElementById('join-team');
    if (panel && location.hash === '#join-team') panel.open = true;
  }
  window.addEventListener('hashchange', openJoinPanel);
  openJoinPanel();
  document.querySelectorAll('.role-interest[href="#join-team"]').forEach(link => link.addEventListener('click', () => {
    document.getElementById('join-team').open = true;
    document.querySelector('#join-form select').value = link.dataset.role;
  }));
  const form = document.getElementById('join-form');
  if (form) form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    const message = document.getElementById('join-status');
    button.disabled = true;
    message.textContent = 'Sending your interest…';
    try {
      const payload = Object.fromEntries(new FormData(form));
      payload.consent = form.consent.checked;
      const response = await fetch('/api/team-interest', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'Please try again.');
      message.textContent = 'Thank you! Your interest is saved privately for the team to review. No role has been assigned yet.';
      form.reset();
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
