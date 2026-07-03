# Nik's Deutsch Trainer — PythonAnywhere

Flask flashcard trainer for [PythonAnywhere](https://www.pythonanywhere.com) free tier.

Progress lives in `~/data/phrase_lexicon_pyany/` and **survives code updates** (unlike Render Free).

URL: `https://YOURUSERNAME.pythonanywhere.com`

Full step-by-step: [deploy/pythonanywhere/README.md](deploy/pythonanywhere/README.md)

## Quick setup

```bash
cd ~
# upload this folder, or clone your repo, so you have:
# ~/phrase_lexicon_pyany/

cd ~/phrase_lexicon_pyany
mkvirtualenv --python=/usr/bin/python3.10 phrase-lexicon-pyany
pip install -r requirements.txt
mkdir -p ~/data/phrase_lexicon_pyany
```

**Web** tab → Manual configuration → Python 3.10:

| Setting | Value |
|---------|--------|
| Source code | `/home/YOURUSERNAME/phrase_lexicon_pyany` |
| Working directory | `/home/YOURUSERNAME/phrase_lexicon_pyany` |
| Virtualenv | `/home/YOURUSERNAME/.virtualenvs/phrase-lexicon-pyany` |
| Static files | URL `/static/` → `/home/YOURUSERNAME/phrase_lexicon_pyany/static/` |
| WSGI file | `/home/YOURUSERNAME/phrase_lexicon_pyany/wsgi.py` |

**Allow listed external sites** (free tier, required for Sync):

- `docs.google.com`
- `googleusercontent.com`

Reload the web app, open the site, click **Sync from Doc**.

## Data & backup

- Database: `~/data/phrase_lexicon_pyany/cards.db`
- Hints: `~/data/phrase_lexicon_pyany/hints/`
- Use **Export Progress** / **Import Progress** in the app footer for backups

## Local run (optional)

```bash
pip install -r requirements.txt
set DATA_DIR=.test_data   # Windows
# export DATA_DIR=.test_data  # Linux/macOS
python app.py
```
