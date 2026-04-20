# Mulberry E-Scooter Tours — Deployment Guide

## Quick Start (Local Development)

### Prerequisites
- Python 3.10+ installed
- A Stripe account (free to create at stripe.com)
- A Gmail account (for sending confirmation emails)

### Step 1: Set Up the Project

```bash
# Navigate to the project folder
cd escooter-tours

# Create a virtual environment
python -m venv venv

# Activate it
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Open .env in your text editor and fill in your values
```

**Required settings to change:**

| Variable | Where to Get It |
|----------|----------------|
| `SECRET_KEY` | Generate a random string (e.g., run `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `STRIPE_PUBLISHABLE_KEY` | Stripe Dashboard → Developers → API Keys |
| `STRIPE_SECRET_KEY` | Stripe Dashboard → Developers → API Keys |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Developers → Webhooks (after creating endpoint) |
| `MAIL_USERNAME` | Your Gmail address |
| `MAIL_PASSWORD` | Gmail App Password (not your regular password — see below) |

**Getting a Gmail App Password:**
1. Go to myaccount.google.com → Security
2. Enable 2-Step Verification if not already on
3. Search for "App passwords"
4. Create one for "Mail" — copy the 16-character password into `.env`

### Step 3: Initialize the Database

```bash
# Seed with sample data (tours, scooters, guides, time slots)
python seed_data.py
```

This creates:
- Admin account: `admin` / `MSTadmin2026!`
- 10 scooters (MST-001 through MST-010)
- 2 tour guides
- 3 sample tours with 14 days of time slots
- Waiver template

### Step 4: Run the App

```bash
# Development mode
flask run --debug

# Or with gunicorn (production-like)
gunicorn --bind 0.0.0.0:5000 app:app
```

Visit: **http://localhost:5000**
Admin: **http://localhost:5000/admin**

---

## Production Deployment

### Option A: Railway (Recommended — Easiest)

1. Create an account at [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub and select the repo
4. Add environment variables (from your `.env` file)
5. Railway auto-detects Python and deploys
6. Get your public URL from the dashboard

**Cost:** ~$5/month for a small app

### Option B: Render

1. Create account at [render.com](https://render.com)
2. New → Web Service → Connect GitHub repo
3. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Add environment variables
5. Deploy

**Cost:** Free tier available (spins down after inactivity)

### Option C: DigitalOcean App Platform

1. Create account at [digitalocean.com](https://digitalocean.com)
2. Apps → Create App → GitHub
3. Configure build & run commands
4. Add environment variables
5. Deploy

**Cost:** ~$5/month

### Option D: Docker (Any VPS)

```bash
# Build the image
docker build -t mst-app .

# Run it
docker run -d -p 5000:5000 --env-file .env mst-app
```

### Production Database

For production, switch from SQLite to PostgreSQL:

1. Create a PostgreSQL database (included free on Railway/Render)
2. Update `DATABASE_URL` in your env:
   ```
   DATABASE_URL=postgresql://user:password@host:5432/dbname
   ```
3. Install the PostgreSQL driver:
   ```bash
   pip install psycopg2-binary
   ```

### Custom Domain

1. Purchase a domain (e.g., `mulberryscootertours.com`)
2. In your hosting dashboard, add the custom domain
3. Update DNS records as instructed by your host
4. Enable HTTPS (usually automatic)

---

## Stripe Setup

### 1. Create a Stripe Account
- Go to [stripe.com](https://stripe.com) and sign up
- Complete identity verification

### 2. Get API Keys
- Dashboard → Developers → API Keys
- Copy **Publishable key** and **Secret key** to your `.env`
- Use **test keys** (starting with `pk_test_` / `sk_test_`) for development
- Switch to **live keys** when ready to accept real payments

### 3. Set Up Webhooks
- Dashboard → Developers → Webhooks → Add endpoint
- URL: `https://yourdomain.com/webhook/stripe`
- Events to listen for:
  - `payment_intent.succeeded`
  - `charge.refunded`
- Copy the **Signing secret** to `STRIPE_WEBHOOK_SECRET`

### 4. Enable Payment Methods
- Dashboard → Settings → Payment Methods
- Enable: Cards, Apple Pay, Google Pay

### 5. Go Live Checklist
- [ ] Complete Stripe account verification
- [ ] Switch from test keys to live keys
- [ ] Test a real payment (then refund it)
- [ ] Set up webhook for production URL
- [ ] Configure payout schedule and bank account

---

## Email Configuration

### Gmail SMTP
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
```

### SendGrid (Higher Volume)
```
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
```

### Mailgun
```
MAIL_SERVER=smtp.mailgun.org
MAIL_PORT=587
MAIL_USERNAME=postmaster@your-domain.mailgun.org
MAIL_PASSWORD=your-mailgun-password
```

---

## Embedding the Booking Widget

To add the booking widget to any external website:

```html
<div id="mst-booking-widget"></div>
<script>
  window.MST_BASE_URL = 'https://yourdomain.com';
</script>
<script src="https://yourdomain.com/widget/embed.js"></script>
```

The widget is responsive and works on mobile. It opens your tour page in a new tab when submitted.

---

## Maintenance

### Daily Checks
- Review new bookings in the admin dashboard
- Check for unread contact messages
- Verify scooter availability matches physical fleet

### Weekly
- Export booking CSV for records
- Review Stripe dashboard for payment issues
- Check for unsigned waivers

### Monthly
- Update time slots for the coming month
- Review and update tour descriptions/pricing
- Check scooter maintenance schedules
- Back up the database

### Database Backup (SQLite)
```bash
cp instance/escooter_tours.db backups/escooter_tours_$(date +%Y%m%d).db
```

### Database Backup (PostgreSQL)
```bash
pg_dump $DATABASE_URL > backups/backup_$(date +%Y%m%d).sql
```
