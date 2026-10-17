"""Run inside the container; write a newsletter CSV to stdout."""
import csv
import os
import sqlite3
import sys
from pathlib import Path
connection = sqlite3.connect(Path(os.environ.get('DATA_DIR', '/data')) / 'newsletter.sqlite3')
writer = csv.writer(sys.stdout)
writer.writerow(['email', 'consent_at_unix', 'consent_text', 'unsubscribe_url'])
try:
    for email, at, consent, token in connection.execute('SELECT email, consent_at, consent_text, token FROM subscribers ORDER BY consent_at'):
        # Prefix CSV formula characters for safe spreadsheet imports.
        safe_email = "'" + email if email.startswith(('=', '+', '-', '@')) else email
        writer.writerow([safe_email, at, consent, 'https://tmrceo.com/privacy#unsubscribe='+token])
except sqlite3.OperationalError:
    pass
finally:
    connection.close()
