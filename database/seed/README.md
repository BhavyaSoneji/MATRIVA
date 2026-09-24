# Synthetic seed data

Run from the repository root after the API dependencies are installed:

```bash
cd backend
python ../database/seed/seed.py
```

The script is idempotent and creates three clearly marked demo users, staff accounts, synthetic
ANC/nutrition/traditional source cards, and a few food/lifestyle records. It is for local
development only. Replace every demo source with current, clinically reviewed material before
using the application for real users.
