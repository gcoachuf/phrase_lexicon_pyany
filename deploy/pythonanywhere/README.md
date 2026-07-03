# PythonAnywhere — Nik's Deutsch Trainer

Run this Flask app on [PythonAnywhere](https://www.pythonanywhere.com) free tier.  
SQLite and hints live in `DATA_DIR` on your home disk — **survives code updates**.

URL: `https://YOURUSERNAME.pythonanywhere.com`

## 1. Create account

1. Sign up at https://www.pythonanywhere.com (free “Beginner” account is enough).
2. Note your **username** (e.g. `nikdeutsch`).

## 2. Upload the project

### Option A — Git (if this folder is on GitHub)

```bash
cd ~
git clone https://github.com/YOURUSER/phrase_lexicon_pyany.git
cd phrase_lexicon_pyany
```

### Option B — Upload ZIP

1. Zip `phrase_lexicon_pyany` on your PC (without `.git`, `cards.db`, `__pycache__`).
2. PythonAnywhere **Files** tab → upload ZIP to `/home/YOURUSERNAME/`.
3. Bash console:

```bash
cd ~
unzip phrase_lexicon_pyany.zip
# ensure the app files are at ~/phrase_lexicon_pyany/app.py
```

## 3. Virtualenv + dependencies

```bash
cd ~/phrase_lexicon_pyany
mkvirtualenv --python=/usr/bin/python3.10 phrase-lexicon-pyany
pip install -r requirements.txt
```

If `mkvirtualenv` is missing:

```bash
python3.10 -m venv ~/.virtualenvs/phrase-lexicon-pyany
source ~/.virtualenvs/phrase-lexicon-pyany/bin/activate
pip install -r requirements.txt
```

## 4. Persistent data directory

Keep the database **outside** the code folder:

```bash
mkdir -p ~/data/phrase_lexicon_pyany/hints
```

`wsgi.py` sets `DATA_DIR` to this path automatically.

## 5. Allow Google Doc access (required on free tier)

**Web** tab → **Allow listed external sites** → add:

- `docs.google.com`
- `googleusercontent.com` (image hints from the doc export, if used)

Save. Without this, **Sync from Doc** fails on the free plan.

## 6. Configure the web app

**Web** tab → **Add a new web app** → **Manual configuration** → **Python 3.10**
(or the newest Python version available).

| Setting | Value |
|---------|--------|
| **Source code** | `/home/YOURUSERNAME/phrase_lexicon_pyany` |
| **Working directory** | `/home/YOURUSERNAME/phrase_lexicon_pyany` |
| **Virtualenv** | `/home/YOURUSERNAME/.virtualenvs/phrase-lexicon-pyany` |
| **Static files** | URL `/static/` → Directory `/home/YOURUSERNAME/phrase_lexicon_pyany/static/` |

### WSGI file

Click the **WSGI configuration file** link (usually
`/var/www/YOURUSERNAME_pythonanywhere_com_wsgi.py`).

Delete everything in it and paste the full contents of
`~/phrase_lexicon_pyany/wsgi.py` from this project.

That file auto-detects the project path and stores data in
`~/data/phrase_lexicon_pyany/` — no username edit needed.

Click **Reload** on the Web tab.

## 7. First use

1. Open `https://YOURUSERNAME.pythonanywhere.com`
2. Click **Sync from Doc**
3. Cards and progress are stored in `~/data/phrase_lexicon_pyany/cards.db`

## Updates

After changing code locally and uploading / `git pull`:

```bash
cd ~/phrase_lexicon_pyany
git pull   # if using git
# Web tab → Reload
```

Progress is **not** lost (`DATA_DIR` is separate).

## Optional: scheduled sync

Free accounts have limited scheduled tasks. Easiest: open the app occasionally or use **Sync from Doc** manually.

Paid plans can add a scheduled task:

```bash
curl -s "https://YOURUSERNAME.pythonanywhere.com/api/cron/sync?key=YOUR_CRON_SECRET"
```

Set `CRON_SECRET` in `wsgi.py` to match.

## Troubleshooting

**Error log** (Web tab → Log files → error log).

Check data folder:

```bash
ls -la ~/data/phrase_lexicon_pyany/
```

**Import errors** — virtualenv path on the Web tab must match `~/.virtualenvs/phrase-lexicon-pyany`.

**Sync fails / URL fetch blocked** — confirm `docs.google.com` is on the allow list.

**Empty after setup** — normal; run **Sync from Doc** once.

**Static CSS missing** — add the Static files mapping for `/static/`.

## Free tier limits

- Subdomain only (`*.pythonanywhere.com`)
- CPU time per day (enough for one learner)
- External HTTP only to **whitelisted** domains
- One web app

## Restore progress from Render / another host

Use **Import Progress** in the app footer with a JSON backup from **Export Progress** on the old host.
