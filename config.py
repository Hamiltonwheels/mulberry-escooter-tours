"""
Configuration for Mulberry E-Scooter Tours
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # App
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production-abc123')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///escooter_tours.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Business
    BUSINESS_NAME = "Mulberry E-Scooter Tours"
    BUSINESS_TAGLINE = "Explore Mulberry, GA on Two Wheels"
    BUSINESS_EMAIL = os.getenv('BUSINESS_EMAIL', 'info@mulberryscootertours.com')
    BUSINESS_PHONE = os.getenv('BUSINESS_PHONE', '(706) 555-0199')
    BUSINESS_ADDRESS = "Mulberry, GA 30260"
    TIMEZONE = "US/Eastern"
    MAX_GROUP_SIZE = 6
    FLEET_SIZE = 10

    # Stripe
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_placeholder')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', 'sk_test_placeholder')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_placeholder')

    # Email (SMTP)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@mulberryscootertours.com')

    # Booking
    BOOKING_ADVANCE_DAYS = 60       # How far ahead customers can book
    BOOKING_CUTOFF_HOURS = 2        # Minimum hours before tour to book
    CANCELLATION_HOURS = 24         # Free cancellation window
    DEPOSIT_PERCENT = 100           # Full payment at booking
