"""
Database models for Mulberry E-Scooter Tours
"""
from datetime import datetime, date, time
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()


def generate_uuid():
    return str(uuid.uuid4())


def generate_booking_ref():
    return f"MST-{uuid.uuid4().hex[:8].upper()}"


class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='admin')
    is_active_admin = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Scooter(db.Model):
    __tablename__ = 'scooters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    scooter_id = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='available')
    model = db.Column(db.String(80), default='Standard E-Scooter')
    notes = db.Column(db.Text)
    last_maintenance = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Scooter {self.scooter_id}>'


class Guide(db.Model):
    __tablename__ = 'guides'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    bio = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    max_group_size = db.Column(db.Integer, default=6)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assigned_tours = db.relationship('TimeSlot', backref='guide', lazy=True)


class Tour(db.Model):
    __tablename__ = 'tours'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(250))
    duration_minutes = db.Column(db.Integer, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    max_riders = db.Column(db.Integer, default=6)
    min_riders = db.Column(db.Integer, default=1)
    difficulty = db.Column(db.String(20), default='easy')
    distance_miles = db.Column(db.Float)
    highlights = db.Column(db.Text)
    what_to_bring = db.Column(db.Text)
    meeting_point = db.Column(db.String(250))
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    time_slots = db.relationship('TimeSlot', backref='tour', lazy=True)

    @property
    def price_dollars(self):
        return self.price_cents / 100

    @property
    def formatted_price(self):
        return f"${self.price_dollars:.2f}"

    @property
    def formatted_duration(self):
        hours = self.duration_minutes // 60
        mins = self.duration_minutes % 60
        if hours and mins:
            return f"{hours}h {mins}min"
        elif hours:
            return f"{hours}h"
        return f"{mins}min"


class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, db.ForeignKey('tours.id'), nullable=False)
    guide_id = db.Column(db.Integer, db.ForeignKey('guides.id'), nullable=True)
    slot_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_riders = db.Column(db.Integer, default=6)
    status = db.Column(db.String(20), default='open')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='time_slot', lazy=True)

    @property
    def booked_count(self):
        return sum(b.num_riders for b in self.bookings if b.status in ['confirmed', 'pending'])

    @property
    def available_spots(self):
        return max(0, self.max_riders - self.booked_count)

    @property
    def is_available(self):
        return self.status == 'open' and self.available_spots > 0

    @property
    def formatted_time(self):
        return self.start_time.strftime('%I:%M %p')

    @property
    def formatted_date(self):
        return self.slot_date.strftime('%B %d, %Y')


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    booking_ref = db.Column(db.String(20), unique=True, default=generate_booking_ref)
    time_slot_id = db.Column(db.Integer, db.ForeignKey('time_slots.id'), nullable=False)

    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    num_riders = db.Column(db.Integer, nullable=False)

    total_cents = db.Column(db.Integer, nullable=False)
    stripe_payment_intent_id = db.Column(db.String(250))
    stripe_charge_id = db.Column(db.String(250))
    payment_status = db.Column(db.String(20), default='pending')
    refund_amount_cents = db.Column(db.Integer, default=0)

    status = db.Column(db.String(20), default='pending')
    waiver_signed = db.Column(db.Boolean, default=False)
    waiver_signed_at = db.Column(db.DateTime)
    waiver_signer_name = db.Column(db.String(120))

    special_requests = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)

    participants = db.relationship('Participant', backref='booking', lazy=True, cascade='all, delete-orphan')

    @property
    def total_dollars(self):
        return self.total_cents / 100

    @property
    def formatted_total(self):
        return f"${self.total_dollars:.2f}"

    @property
    def tour_name(self):
        return self.time_slot.tour.name if self.time_slot else "Unknown"


class Participant(db.Model):
    __tablename__ = 'participants'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer)
    waiver_signed = db.Column(db.Boolean, default=False)
    waiver_signed_at = db.Column(db.DateTime)
    emergency_contact_name = db.Column(db.String(120))
    emergency_contact_phone = db.Column(db.String(20))


class WaiverTemplate(db.Model):
    __tablename__ = 'waiver_templates'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.String(10), default='1.0')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
