# HashAI Lead Manager

Run
- venv
  - Windows PowerShell:
    - python -m venv .venv
    - .venv\Scripts\pip install -r requirements.txt
- start
  - .venv\Scripts\python app.py
- open
  - http://127.0.0.1:5000/login
  - test@example.com / password123

Notes
- SQLite DB: app.db (ignored by git)
- JWT stored in localStorage
- Tailwind via CDN
