# Mulberry E-Scooter Tours

Booking website for Mulberry E-Scooter Tours  Mulberry, GA.

Built with Flask, Stripe, and SQLite. Features online booking, digital waivers, Stripe payments, admin dashboard, and embeddable booking widget.

## Quick Start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your keys
python seed_data.py
flask run --debug
```

Visit http://localhost:5000 (site) or http://localhost:5000/admin (admin panel).
