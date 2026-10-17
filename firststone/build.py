from pathlib import Path
import base64

root = Path(__file__).resolve().parent
hero = root / 'assets' / 'firststone-workshop.png'
source = (root / 'article.html').read_text(encoding='utf-8')
encoded = base64.b64encode(hero.read_bytes()).decode('ascii')
output = source.replace('__HERO_IMAGE__', 'data:image/png;base64,' + encoded)
assert '__HERO_IMAGE__' not in output
(root / 'index.html').write_text(output, encoding='utf-8')
print(f'Built standalone article: {len(output):,} characters')
