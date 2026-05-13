# Horizon Cinemas Booking System (HCBS

HCBS is a comprehensive Python-based cinema booking system designed to streamline movie scheduling, seat reservations, and staff management. The system features a graphical user interface built with Tkinter and a persistent SQLite database.

## Setup Instructions

Follow these steps to set up and run the project locally. The steps cover Windows (PowerShell) and macOS/Linux.

### Prerequisites
- Python 3.10+ installed (3.13 tested in development).
- Git to clone the repository.
- Optional: system package manager to install system-level libraries for Pillow/matplotlib if needed.

### 1) Clone the repository
```bash
git clone https://github.com/shritika28/ASD--Horizon-Cinemas-Booking-System.git
cd ASD--Horizon-Cinemas-Booking-System
```

### 2) Create & activate a virtual environment (recommended)
Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Windows (cmd.exe):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```
macOS / Linux:
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3) Install Python dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4) Initialize the database (SQLite)
The project uses an SQLite database file `hcbs.db` stored in the project root. Create and seed the DB with the provided script:

```bash
python src/database/setup_db.py
```

This will create `hcbs.db` and insert demo cinemas, screens, films, showings, prices, users, and a few bookings.

If you prefer an empty database or want to re-run the setup, delete `hcbs.db` first.

### 5) Run the application
```bash
python main.py
```

The login screen appears first. Use one of the demo accounts listed below.

### Demo credentials (seeded by `setup_db.py`)
| Role    | Username | Password   |
| :------ | :------- | :--------- |
| Manager | manager1 | password123 |
| Admin   | admin1   | password123 |
| Admin   | admin2   | password123 |
| Staff   | staff1   | password123 |
| Staff   | staff2   | password123 |
| Staff   | staff3   | password123 |

---

## Running tests
If you want to run unit tests (requires `pytest`):
```bash
pip install pytest
pytest -q
```

## Troubleshooting
- "SyntaxError: invalid decimal literal" or leftover merge markers: run a file search for `<<<<<<<`, `=======`, `>>>>>>>` and remove any conflict text. This repo had merge artifacts previously — ensure files are clean.
- If Python imports still show errors after fix, remove stale bytecode caches:
```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Include *.pyc | Remove-Item -Force
```
- Windows DPI / low-resolution UI: the app tries to enable DPI awareness in `main.py`. If UI looks tiny/large, try adjusting scaling in `main.py` or your OS display settings.
- Git push/pull issues: if `MERGE_HEAD` exists, either finish the merge message in your editor and `git commit`, or abort with `git merge --abort`.

## Developer notes
- Database file: `hcbs.db` (SQLite) at project root.
- Seed script: `src/database/setup_db.py` (idempotent for development re-seeds — delete `hcbs.db` to start fresh).
- GUI: `src/gui/` (Tkinter + ttk). Styles and palette constants are defined at the top of each window module.

## Additional tips
- To run a single window for manual UI tests, you can run the module directly, for example:
```bash
python src/gui/film_listing_window.py
```
- To clear and re-seed the database in one line:
```bash
rm hcbs.db 2>nul || del hcbs.db
python src/database/setup_db.py
```

---

## CI/CD Pipeline

[![CI](https://github.com/shritika28/ASD--Horizon-Cinemas-Booking-System/actions/workflows/ci.yml/badge.svg)](https://github.com/shritika28/ASD--Horizon-Cinemas-Booking-System/actions/workflows/ci.yml)

This project strictly follows an automated Continuous Integration and Continuous Deployment (CI/CD) pipeline powered by GitHub Actions.

### Branch Strategy
- **`feature/*` branches**: Used by developers to build isolated features.
- **`develop` branch (Staging)**: When features are pushed or PR'd to `develop`, the **CI Pipeline** runs automatically. It lints code, runs all unit/integration tests with an in-memory SQLite database, enforces 70% coverage, and scans for security vulnerabilities.
- **`main` branch (Production)**: When code is merged into `main`, the **CD Pipeline** initiates. It requires a manual review step. Once approved, it executes database migrations (if applicable for MySQL), tags the Git release, and builds the deployable `.zip` artifact.

### Running the Pipeline Locally
You can mirror the CI pipeline exactly on your local machine using the provided `Makefile`. Make sure you have activated your `.venv` and installed the tools via `pip install flake8 pylint pytest pytest-cov bandit safety`.

```bash
# Run linting + testing + security scanning in sequence:
make ci

# Or run individual stages:
make lint
make test
make security
make build
```

---

(If you want I can add a short `CONTRIBUTING.md` with branch/PR rules, or add a `make`/`invoke` script to automate setup.)
