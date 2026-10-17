FROM python:3.12-alpine
WORKDIR /site
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && adduser -D -u 10001 site && mkdir /data && chown site:site /data
COPY export_subscribers.py app.py game_storage.py snake_rules.py google_auth.py news_quiz.py index.html styles.css snake.js arcade.js auth.js news-quiz.js community.js privacy.html terms.html ./
COPY articles/*.html ./articles/
COPY assets/news/*.jpg ./assets/news/
COPY assets/team/*.svg assets/team/*.png ./assets/team/
COPY assets/books/*.jpg ./assets/books/
COPY books/books.json ./books/books.json
COPY leadership/members.json ./leadership/members.json
COPY firststone/index.html ./firststone/index.html
COPY features/index.html ./features/index.html
USER site
ENV DATA_DIR=/data
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--access-logfile", "-", "app:app"]
