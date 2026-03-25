# FinSmart

FinSmart is a Django web application for students to track expenses, manage monthly budgets, and generate AI-powered personal finance advice.

## Features

- User signup, login, and logout
- Expense add, edit, and delete
- Monthly budget management
- Dashboard with totals, category breakdown, budget status, alerts, and Chart.js graph
- AI advice generation with a safe fallback when `OPENAI_API_KEY` is missing or the API call fails

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

4. Start the development server:

```bash
python manage.py runserver
```

## OpenAI Setup

FinSmart can load the API key either from the process environment or from a local `.env` file in the project root.

Example `.env`:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

If you set or change the key after the Django server is already running, restart the server so Django reloads the environment.

PowerShell example:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
python manage.py runserver
```

When the API is unavailable, the app logs the real exception in the terminal and still saves a graceful fallback message instead of crashing.
