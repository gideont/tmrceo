"""Render the bookshelf from the editable, source-backed book registry."""
from html import escape as e
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent


def build():
    books = json.loads((ROOT / 'books/books.json').read_text())
    cards = []
    for i, book in enumerate(books, 1):
        book_id = e(book['id'])
        cards.append(f'''<article class="book-card" aria-labelledby="book-{book_id}"><div class="book-cover"><span class="book-number">{i:02}</span><img src="/assets/books/{book_id}.jpg" alt="Cover of {e(book['title'])} by {e(book['author'])}" width="300" height="450" loading="lazy"></div><div class="book-info"><span class="book-theme">{e(book['theme'])}</span><h3 id="book-{book_id}">{e(book['title'])}</h3><p class="book-author">By {e(book['author'])}</p><p class="book-description">{e(book['description'])}</p><div class="book-actions"><button class="book-like" type="button" data-book="{book_id}" aria-pressed="false" aria-label="Like {e(book['title'])}" disabled><span aria-hidden="true">♡</span> <span class="like-word">Like</span> <span class="like-count">—</span></button><span class="book-borrow-note">Borrow · Read · Share</span></div></div></article>''')
    section = '''<!-- bookshelf:start -->
<section class="books-section wrap" id="books" aria-labelledby="books-title"><header class="books-heading"><div><span class="eyebrow">THE TOMORROW BOOKSHELF</span><h2 id="books-title">Big adventures.<br>Between two covers.</h2></div><div><p>Six books for curious minds. Find one at your local library, borrow from a friend, or share a copy you’ve enjoyed. Which adventure will you read together?</p><p class="books-small">Read it, love it, pass it on. Like your favourites and help other kids find their next read.</p></div></header><div class="books-grid">'''+''.join(cards)+'''</div><p id="books-status" class="books-status" role="status" aria-live="polite">Loading reader likes…</p><noscript><p>Browse our six books above. Enable JavaScript to like your favourites.</p></noscript><p class="book-credits">Cover thumbnails via <a href="https://openlibrary.org/dev/docs/api/covers" target="_blank" rel="noopener noreferrer">Open Library</a>. Cover art belongs to its respective rights holders.</p></section>
<!-- bookshelf:end -->'''
    path = ROOT / 'index.html'
    home = path.read_text()
    if '<!-- bookshelf:start -->' in home:
        start = home.index('<!-- bookshelf:start -->')
        end = home.index('<!-- bookshelf:end -->') + len('<!-- bookshelf:end -->')
        home = home[:start] + section + home[end:]
    else:
        home = home.replace('<!-- newspaper:end -->', '<!-- newspaper:end -->\n' + section, 1)
    path.write_text(home)
    credits = ['# Book-cover provenance', '', 'Downloaded from Open Library Covers API for book identification and recommendation.', 'Copyright remains with the respective cover artists and publishers. No ownership or open licence is claimed.', '']
    for book in books:
        credits.extend([f'## {book["title"]}', f'- Author: {book["author"]}', f'- ISBN for cover: {book["isbn"]}', f'- Cover: https://covers.openlibrary.org/b/isbn/{book["isbn"]}-L.jpg', f'- Book details: {book["source_url"]}', ''])
    (ROOT / 'assets/books/CREDITS.md').write_text('\n'.join(credits))
    print(f'Built {len(books)}-book library-and-sharing shelf and cover provenance.')


if __name__ == '__main__':
    build()
