"""
Mulberry E-Scooter Tours — Main Application
"""
import os
import json
import stripe
from datetime import datetime, timedelta, date, time
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, send_from_directory)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message as MailMessage

from config import Config
from models import (db, Admin, Scooter, Guide, Tour, TimeSlot, Booking,
                    Participant, WaiverTemplate, ContactMessage, SiteSettings,
                    generate_booking_ref)

import pytz

# ─── App Factory ────────────────────────────────────────────────────
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'admin_login'

    stripe.api_key = app.config['STRIPE_SECRET_KEY']

    with app.app_context():
        db.create_all()

    return app

mail = Mail()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

app = create_app()
eastern = pytz.timezone(app.config['TIMEZONE'])


# ─── Helpers ───────────────────────────────────────────────────────
def now_eastern():
    return datetime.now(eastern)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_active_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

def send_confirmation_email(booking):
    """Send booking confirmation email."""
    try:
        ts = booking.time_slot
        msg = MailMessage(
            subject=f"Booking Confirmed — {ts.tour.name} | {booking.booking_ref}",
            recipients=[booking.customer_email],
            html=render_template('emails/confirmation.html', booking=booking)
        )
        mail.send(msg)
    except Exception as e:

# ════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    tours = Tour.query.filter_by(is_active=True).order_by(Tour.is_featured.desc()).all()
    return render_template('public/index.html', tours=tours)


@app.route('/tours')
def tours_list():
    tours = Tour.query.filter_by(is_active=True).all()
    return render_template('public/tours.html', tours=tours)


@app.route('/tour/<slug>')
def tour_detail(slug):
    tour = Tour.query.filter_by(slug=slug, is_active=True).first_or_404()
    today = now_eastern().date()
    max_date = today + timedelta(days=app.config['BOOKING_ADVANCE_DAYS'])
    slots = TimeSlot.query.filter(
        TimeSlot.tour_id == tour.id,
        TimeSlot.slot_date >= today,
        TimeSlot.slot_date <= max_date,
        TimeSlot.status == 'open'
    ).order_by(TimeSlot.slot_date, TimeSlot.start_time).all()
    return render_template('public/tour_detail.html', tour=tour, slots=slots)


@app.route('/api/availability/<int:tour_id>')
def api_availability(tour_id):
    """JSON endpoint for real-time availability checks."""
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date required'}), 400
    try:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    slots = TimeSlot.query.filter(
        TimeSlot.tour_id == tour_id,
        TimeSlot.slot_date == check_date,
        TimeSlot.status == 'open'
    ).order_by(TimeSlot.start_time).all()

    result = []
    for s in slots:
        result.append({
            'id': s.id,
            'time': s.formatted_time,
            'start': s.start_time.strftime('%H:%M'),
            'end': s.end_time.strftime('%H:%M'),
            'available': s.available_spots,
            'max': s.max_riders,
            'guide': s.guide.name if s.guide else 'TBD'
        })
    return jsonify({'date': date_str, 'slots': result})


@app.route('/book/<int:slot_id>', methods=['GET', 'POST'])
def book_tour(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    tour = slot.tour

    if not slot.is_available:
        flash('This time slot is no longer available.', 'error')
        return redirect(url_for('tour_detail', slug=tour.slug))

    if request.method == 'POST':
        name = request.form.get('customer_name', '').strip()
        email = request.form.get('customer_email', '').strip()
        phone = request.form.get('customer_phone', '').strip()
        num_riders = int(request.form.get('num_riders', 1))
        special = request.form.get('special_requests', '').strip()

        # Validate
        errors = []
        if not name:
            errors.append('Name is required.')
        if not email:
            errors.append('Email is required.')
        if not phone:
            errors.append('Phone number is required.')
        if num_riders < 1 or num_riders > slot.available_spots:
            errors.append(f'Invalid number of riders. Max available: {slot.available_spots}')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('public/book.html', slot=slot, tour=tour)

        total = tour.price_cents * num_riders

        # Create Stripe Payment Intent
        try:
            intent = stripe.PaymentIntent.create(
                amount=total,
                currency='usd',
                metadata={

        # Create pending booking
        booking = Booking(
            time_slot_id=slot.id,
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            num_riders=num_riders,
            total_cents=total,
            stripe_payment_intent_id=intent.id,
            special_requests=special,
            status='pending',
            payment_status='pending'
        )
        db.session.add(booking)
        db.session.commit()

        return render_template('public/payment.html',
                               booking=booking,
                               tour=tour,
                               slot=slot,
                               client_secret=intent.client_secret,
                               stripe_key=app.config['STRIPE_PUBLISHABLE_KEY'])

    return render_template('public/book.html', slot=slot, tour=tour)


@app.route('/booking/confirm/<int:booking_id>', methods=['POST'])
def confirm_booking(booking_id):
    """Called after Stripe payment succeeds (client-side)."""
    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json() or {}

    payment_intent_id = data.get('payment_intent_id', booking.stripe_payment_intent_id)

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        if intent.status == 'succeeded':
            booking.status = 'confirmed'
            booking.payment_status = 'paid'
            booking.stripe_charge_id = intent.latest_charge
            db.session.commit()
            send_confirmation_email(booking)
            return jsonify({'success': True, 'booking_ref': booking.booking_ref})
        else:
            return jsonify({'success': False, 'error': 'Payment not completed'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/booking/success/<booking_ref>')
def booking_success(booking_ref):
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    return render_template('public/booking_success.html', booking=booking)


@app.route('/booking/lookup', methods=['GET', 'POST'])
def booking_lookup():
    if request.method == 'POST':
        ref = request.form.get('booking_ref', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        booking = Booking.query.filter_by(booking_ref=ref, customer_email=email).first()
        if booking:
            return render_template('public/booking_detail.html', booking=booking)
        flash('Booking not found. Please check your reference and email.', 'error')
    return render_template('public/booking_lookup.html')


@app.route('/booking/cancel/<booking_ref>', methods=['POST'])
def cancel_booking(booking_ref):
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    email = request.form.get('email', '').strip().lower()

    if booking.customer_email.lower() != email:
        flash('Email does not match booking.', 'error')
        return redirect(url_for('booking_lookup'))

    if booking.status == 'cancelled':
        flash('This booking is already cancelled.', 'info')
        return redirect(url_for('booking_lookup'))

    # Check cancellation window
    slot_dt = datetime.combine(booking.time_slot.slot_date, booking.time_slot.start_time)
    slot_aware = eastern.localize(slot_dt)
    hours_until = (slot_aware - now_eastern()).total_seconds() / 3600

    if hours_until < app.config['CANCELLATION_HOURS']:
        flash(f'Cancellations must be made at least {app.config["CANCELLATION_HOURS"]} hours before the tour.', 'error')
        return redirect(url_for('booking_lookup'))

    # Process Stripe refund
    if booking.payment_status == 'paid' and booking.stripe_payment_intent_id:
        try:
            refund = stripe.Refund.create(payment_intent=booking.stripe_payment_intent_id)
            booking.payment_status = 'refunded'

# ─── Waiver ─────────────────────────────────────────────────────────
@app.route('/waiver/<booking_ref>', methods=['GET', 'POST'])
def sign_waiver(booking_ref):
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    waiver = WaiverTemplate.query.filter_by(is_active=True).first()

    if request.method == 'POST':
        signer_name = request.form.get('signer_name', '').strip()
        agreed = request.form.get('agree_waiver')

        if not signer_name or not agreed:
            flash('You must enter your name and agree to the waiver.', 'error')
            return render_template('public/waiver.html', booking=booking, waiver=waiver)

        booking.waiver_signed = True
        booking.waiver_signed_at = datetime.utcnow()
        booking.waiver_signer_name = signer_name

        # Handle participant waivers
        participants_json = request.form.get('participants', '[]')
        try:
            participants = json.loads(participants_json)
            for p in participants:
                part = Participant(
                    booking_id=booking.id,
                    name=p.get('name', ''),
                    age=p.get('age'),
                    waiver_signed=True,
                    waiver_signed_at=datetime.utcnow(),
                    emergency_contact_name=p.get('emergency_name', ''),
                    emergency_contact_phone=p.get('emergency_phone', '')
                )
                db.session.add(part)
        except (json.JSONDecodeError, TypeError):
            pass

        db.session.commit()
        flash('Waiver signed successfully!', 'success')
        return redirect(url_for('booking_success', booking_ref=booking.booking_ref))

    return render_template('public/waiver.html', booking=booking, waiver=waiver)


# ─── Contact ────────────────────────────────────────────────────────
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        msg = ContactMessage(
            name=request.form.get('name', '').strip(),
            email=request.form.get('email', '').strip(),
            phone=request.form.get('phone', '').strip(),
            subject=request.form.get('subject', '').strip(),
            message=request.form.get('message', '').strip()
        )
        db.session.add(msg)
        db.session.commit()
        flash('Message sent! We\'ll get back to you soon.', 'success')
        return redirect(url_for('contact'))

# ─── Stripe Webhook ─────────────────────────────────────────────────
@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, app.config['STRIPE_WEBHOOK_SECRET']
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'payment_intent.succeeded':
        pi = event['data']['object']
        booking = Booking.query.filter_by(stripe_payment_intent_id=pi['id']).first()
        if booking and booking.status == 'pending':
            booking.status = 'confirmed'
            booking.payment_status = 'paid'
            booking.stripe_charge_id = pi.get('latest_charge')
            db.session.commit()
            send_confirmation_email(booking)

    elif event['type'] == 'charge.refunded':
        charge = event['data']['object']
        booking = Booking.query.filter_by(stripe_charge_id=charge['id']).first()
        if booking:
            booking.payment_status = 'refunded'
            booking.refund_amount_cents = charge.get('amount_refunded', 0)
            db.session.commit()

    return jsonify({'received': True}), 200


# ─── Calendar Export ───────────────────────────────────────────────
@app.route('/booking/calendar/<booking_ref>')
def download_calendar(booking_ref):
    from icalendar import Calendar, Event as CalEvent
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    ts = booking.time_slot
    tour = ts.tour

    cal = Calendar()
    cal.add('prodid', '-//Mulberry E-Scooter Tours//EN')
    cal.add('version', '2.0')

    event = CalEvent()
    event.add('summary', f'{tour.name} — Mulberry E-Scooter Tours')
    start_dt = eastern.localize(datetime.combine(ts.slot_date, ts.start_time))
    end_dt = eastern.localize(datetime.combine(ts.slot_date, ts.end_time))
    event.add('dtstart', start_dt)
    event.add('dtend', end_dt)
    event.add('location', tour.meeting_point or app.config['BUSINESS_ADDRESS'])
    event.add('description',
              f'Booking: {booking.booking_ref}\nRiders: {booking.num_riders}\n'
              f'Tour: {tour.name}\nMeeting Point: {tour.meeting_point or "TBD"}')
    cal.add_component(event)

    from flask import Response
    return Response(
        cal.to_ical(),
        mimetype='text/calendar',
        headers={'Content-Disposition': f'attachment; filename=tour-{booking.booking_ref}.ics'}
    )

# ════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = Admin.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    today = now_eastern().date()
    stats = {
        'today_bookings': Booking.query.join(TimeSlot).filter(
            TimeSlot.slot_date == today, Booking.status == 'confirmed').count(),
        'total_bookings': Booking.query.filter(Booking.status == 'confirmed').count(),
        'revenue_today': sum(b.total_cents for b in Booking.query.join(TimeSlot).filter(
            TimeSlot.slot_date == today, Booking.payment_status == 'paid').all()) / 100,
        'revenue_month': sum(b.total_cents for b in Booking.query.join(TimeSlot).filter(
            TimeSlot.slot_date >= today.replace(day=1), Booking.payment_status == 'paid').all()) / 100,
        'active_scooters': Scooter.query.filter_by(status='available').count(),
        'total_scooters': Scooter.query.count(),
        'upcoming_tours': TimeSlot.query.filter(
            TimeSlot.slot_date >= today, TimeSlot.status == 'open').count(),
        'unread_messages': ContactMessage.query.filter_by(is_read=False).count(),
        'pending_waivers': Booking.query.filter(


# ─── Admin: Bookings ────────────────────────────────────────────────
@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    status_filter = request.args.get('status', 'all')
    q = Booking.query.order_by(Booking.created_at.desc())
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    bookings = q.all()
    return render_template('admin/bookings.html', bookings=bookings, status_filter=status_filter)


@app.route('/admin/booking/<int:booking_id>')
@admin_required
def admin_booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template('admin/booking_detail.html', booking=booking)


@app.route('/admin/booking/<int:booking_id>/status', methods=['POST'])
@admin_required
def admin_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    if new_status in ['confirmed', 'cancelled', 'completed', 'no_show']:
        booking.status = new_status
        if new_status == 'cancelled':
            booking.cancelled_at = datetime.utcnow()
        db.session.commit()
        flash(f'Booking status updated to {new_status}.', 'success')
    return redirect(url_for('admin_booking_detail', booking_id=booking_id))


@app.route('/admin/booking/<int:booking_id>/refund', methods=['POST'])
@admin_required
def admin_refund_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    amount_str = request.form.get('refund_amount', '')

    try:
        amount_dollars = float(amount_str)
        amount_cents = int(amount_dollars * 100)
    except (ValueError, TypeError):
        flash('Invalid refund amount.', 'error')
        return redirect(url_for('admin_booking_detail', booking_id=booking_id))

    if amount_cents > booking.total_cents - booking.refund_amount_cents:
        flash('Refund amount exceeds remaining balance.', 'error')
        return redirect(url_for('admin_booking_detail', booking_id=booking_id))

    try:
        refund = stripe.Refund.create(
            payment_intent=booking.stripe_payment_intent_id,
            amount=amount_cents
        )


# ─── Admin: Tours ──────────────────────────────────────────────────
@app.route('/admin/tours')
@admin_required
def admin_tours():
    tours = Tour.query.all()
    return render_template('admin/tours.html', tours=tours)


@app.route('/admin/tour/new', methods=['GET', 'POST'])
@admin_required
def admin_tour_new():
    if request.method == 'POST':
        tour = Tour(
            name=request.form['name'],
            slug=request.form['name'].lower().replace(' ', '-').replace("'", ''),
            description=request.form['description'],
            short_description=request.form.get('short_description', ''),
            duration_minutes=int(request.form['duration_minutes']),
            price_cents=int(float(request.form['price']) * 100),
            max_riders=int(request.form.get('max_riders', 6)),
            difficulty=request.form.get('difficulty', 'easy'),
            distance_miles=float(request.form.get('distance_miles', 0)) or None,
            highlights=request.form.get('highlights', ''),
            what_to_bring=request.form.get('what_to_bring', ''),
            meeting_point=request.form.get('meeting_point', ''),
            is_active=bool(request.form.get('is_active')),
            is_featured=bool(request.form.get('is_featured'))
        )
        db.session.add(tour)
        db.session.commit()
        flash('Tour created!', 'success')
        return redirect(url_for('admin_tours'))
    return render_template('admin/tour_form.html', tour=None)


@app.route('/admin/tour/<int:tour_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_tour_edit(tour_id):
    tour = Tour.query.get_or_404(tour_id)
    if request.method == 'POST':
        tour.name = request.form['name']
        tour.slug = request.form['name'].lower().replace(' ', '-').replace("'", '')
        tour.description = request.form['description']
        tour.short_description = request.form.get('short_description', '')
        tour.duration_minutes = int(request.form['duration_minutes'])
        tour.price_cents = int(float(request.form['price']) * 100)
        tour.max_riders = int(request.form.get('max_ride


# ─── Admin: Time Slots ──────────────────────────────────────────────
@app.route('/admin/slots')
@admin_required
def admin_slots():
    today = now_eastern().date()
    date_filter = request.args.get('date', today.isoformat())
    try:
        filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
    except ValueError:
        filter_date = today

    slots = TimeSlot.query.filter(
        TimeSlot.slot_date >= filter_date
    ).order_by(TimeSlot.slot_date, TimeSlot.start_time).limit(50).all()

    tours = Tour.query.filter_by(is_active=True).all()
    guides = Guide.query.filter_by(is_active=True).all()
    return render_template('admin/slots.html', slots=slots, tours=tours,
                           guides=guides, filter_date=filter_date)


@app.route('/admin/slots/generate', methods=['POST'])
@admin_required
def admin_generate_slots():
    """Bulk-generate time slots for a date range."""
    tour_id = int(request.form['tour_id'])
    guide_id = request.form.get('guide_id')
    guide_id = int(guide_id) if guide_id else None
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    times_raw = request.form.get('times', '09:00,11:00,14:00,16:00')

    tour = Tour.query.get_or_404(tour_id)
    times = [t.strip() for t in times_raw.split(',')]
    count = 0
    current = start_date

    while current <= end_date:
        for t_str in times:
            h, m = map(int, t_str.split(':'))
            start_t = time(h, m)
            end_minutes = h * 60 + m + tour.duration_minutes
            end_t = time(end_minutes // 60, end_minutes % 60)

            existing = TimeSlot.query.filter_by(
                tour_id=tour_id, slot_date=current, start_time=start_t
            ).first()
            if not existing:
                slot = TimeSlot(
                    tour_id=tour_id,
                    guide_id=guide_id,
                    slot_date=current,
                    start_time=start_t,
                    end_time=end_t,
                    max_riders=tour.max_riders
                )
                db.session.add(slot)
                count += 1
        current += timedelta(days=1)

    db.session.commit()
    flash(f'{count} time slots generated.', 'success')
    return redirect(url_for('admin_slots'))


@app.route('/admin/slot/<int:slot_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_slot(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    slot.status = 'cancelled'
    for booking in slot.bookings:
        if booking.status in ['pending', 'confirmed']:
            booking.status = 'cancelled'
            booking.cancelled_at = datetime.utcnow()


# ─── Admin: Scooters ────────────────────────────────────────────
@app.route('/admin/scooters')
@admin_required
def admin_scooters():
    scooters = Scooter.query.order_by(Scooter.scooter_id).all()
    return render_template('admin/scooters.html', scooters=scooters)


@app.route('/admin/scooter/new', methods=['GET', 'POST'])
@admin_required
def admin_scooter_new():
    if request.method == 'POST':
        scooter = Scooter(
            name=request.form['name'],
            scooter_id=request.form['scooter_id'],
            model=request.form.get('model', 'Standard E-Scooter'),
            status=request.form.get('status', 'available'),
            notes=request.form.get('notes', '')
        )
        db.session.add(scooter)
        db.session.commit()
        flash('Scooter added!', 'success')
        return redirect(url_for('admin_scooters'))
    return render_template('admin/scooter_form.html', scooter=None)


@app.route('/admin/scooter/<int:scooter_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_scooter_edit(scooter_id):
    scooter = Scooter.query.get_or_404(scooter_id)
    if request.method == 'POST':
        scooter.name = request.form['name']
        scooter.scooter_id = request.form['scooter_id']
        scooter.model = request.form.get('model', '')
        scooter.status = request.form.get('status', 'available')
        scooter.notes = request.form.get('notes', '')
        db.session.commit()
        flash('Scooter updated!', 'success')
        return redirect(url_for('admin_scooters'))
    return render_template('admin/scooter_form.html', scooter=scooter)


# ─── Admin: Guides ───────────────────────────────────────────────
@app.route('/admin/guides')
@admin_required
def admin_guides():
    guides = Guide.query.all()
    return render_template('admin/guides.html', guides=guides)


@app.route('/admin/guide/new', methods=['GET', 'POST'])
@admin_required
def admin_guide_new():
    if request.method == 'POST':
        guide = Guide(
            name=request.form['name'],
            email=request.form['email'],
            phone=request.form.get('phone', ''),
            bio=request.form.get('bio', ''),
            is_active=bool(request.form.get('is_active')),
            max_group_size=int(request.form.get('max_group_size', 6))
        )
        db.session.add(guide)
        db.session.commit()
        flash('Guide added!', 'success')
        return redirect(url_for('admin_guides'))
    return render_template('admin/guide_form.html', guide=None)


@app.route('/admin/guide/<int:guide_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_guide_edit(guide_id):
    guide = Guide.query.get_or_404(guide_id)


# ─── Admin: Messages ──────────────────────────────────────────────
@app.route('/admin/messages')
@admin_required
def admin_messages():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)


@app.route('/admin/message/<int:msg_id>/read', methods=['POST'])
@admin_required
def admin_mark_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return jsonify({'success': True})


# ─── Admin: Reports / Export ───────────────────────────────────────
@app.route('/admin/reports')
@admin_required
def admin_reports():
    return render_template('admin/reports.html')


@app.route('/admin/reports/export')
@admin_required
def admin_export_bookings():
    """Export bookings to CSV."""
    import csv
    import io

    start = request.args.get('start', (now_eastern().date() - timedelta(days=30)).isoformat())
    end = request.args.get('end', now_eastern().date().isoformat())

    start_date = datetime.strptime(start, '%Y-%m-%d').date()
    end_date = datetime.strptime(end, '%Y-%m-%d').date()

    bookings = Booking.query.join(TimeSlot).filter(
        TimeSlot.slot_date >= start_date,
        TimeSlot.slot_date <= end_date
    ).order_by(TimeSlot.slot_date).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Booking Ref', 'Date', 'Time', 'Tour', 'Customer',
                     'Email', 'Phone', 'Riders', 'Total', 'Status',
                     'Payment', 'Waiver', 'Created'])
    for b in bookings:
        writer.writerow([
            b.booking_ref,
            b.time_slot.slot_date.isoformat(),
            b.time_slot.formatted_time,
            b.tour_name,
            b.customer_name,
            b.customer_email,
            b.customer_phone,
            b.num_riders,
            b.formatted_total,
            b.status,


# ─── Admin: Settings ──────────────────────────────────────────────
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        for key in ['business_name', 'business_email', 'business_phone',
                     'cancellation_hours', 'booking_advance_days', 'booking_cutoff_hours']:
            val = request.form.get(key, '')
            setting = SiteSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = val
            else:
                db.session.add(SiteSettings(key=key, value=val))
        db.session.commit()
        flash('Settings saved!', 'success')
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    return render_template('admin/settings.html', settings=settings)


# ─── Admin: Waiver Template ───────────────────────────────────────
@app.route('/admin/waivers')
@admin_required
def admin_waivers():
    waivers = WaiverTemplate.query.all()
    return render_template('admin/waivers.html', waivers=waivers)


@app.route('/admin/waiver/edit', methods=['GET', 'POST'])
@admin_required
def admin_waiver_edit():
    waiver = WaiverTemplate.query.filter_by(is_active=True).first()
    if request.method == 'POST':
        if waiver:
            waiver.title = request.form['title']
            waiver.content = request.form['content']
            waiver.version = request.form.get('version',


# ════════════════════════════════════════════════════════════════
#  API ENDPOINTS (for widget & AJAX)
# ════════════════════════════════════════════════════════════════

@app.route('/api/tours')
def api_tours():
    tours = Tour.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'slug': t.slug,
        'short_description': t.short_description,
        'duration': t.formatted_duration,
        'price': t.formatted_price,
        'price_cents': t.price_cents,
        'difficulty': t.difficulty,
        'max_riders': t.max_riders,
        'image_url': t.image_url
    } for t in tours])


@app.route('/api/slots/<int:tour_id>/<date_str>')
def api_slots(tour_id, date_str):
    try:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date'}), 400

    slots = TimeSlot.query.filter(


# ════════════════════════════════════════════════════════════════
#  SEED DATA
# ════════════════════════════════════════════════════════════════

@app.cli.command('seed')
def seed_data():
    """Populate the database with initial data."""
    print("Seeding database...")

    # Admin user
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(
            username='admin',
            email='admin@mulberryscootertours.com',
            full_name='Tour Admin',
            role='admin'
        )
        admin.set_password('MulberryTours2026!')
        db.session.add(admin)
        print("  ✓ Admin user created (admin / MulberryTours2026!)")

    # Scooters
    if Scooter.query.count() == 0:
        for i in range(1, 11):
            db.session.add(Scooter(
                name=f'Scooter {i:02d}',
                scooter_id=f'MST-{i:03d}',
                model='Standard E-Scooter',
                status='available'
            ))
        print("  ✓ 10 scooters created")


    # Tours
    if Tour.query.count() == 0:
        tours_data = [
            {
                'name': 'Downtown Discovery',
                'slug': 'downtown-discovery',
                'description': 'Cruise through the heart of Mulberry on this beginner-friendly tour! '
                               'Glide past historic landmarks, local shops, and scenic parks while your '
                               'guide shares fascinating stories about our town\'s rich history. Perfect '
                               'for first-time riders and families.',
                'short_description': 'A scenic ride through historic downtown Mulberry — perfect for beginners.',
                'duration_minutes': 60,
                'price_cents': 3500,
                'max_riders': 6,
                'difficulty': 'easy',
                'distance_miles': 4.5,
                'highlights': 'Historic Town Square, Mulberry Park, Local Art Murals, Scenic Creek Trail',
                'what_to_bring': 'Comfortable shoes, sunscreen, water bottle, phone for photos',
                'meeting_point': 'Mulberry Town Square, Main Street, Mulberry, GA 30260',
                'is_active': True,
                'is_featured': True,
            },
            {
                'name': 'Sunset & Scenic Route',
                'slug': 'sunset-scenic-route',
                'description': 'Experience Mulberry bathed in golden light on our most popular evening tour. '
                               'Wind through tree-lined paths, cross picturesque bridges, and catch breathtaking '
                               'sunset views from the best vantage points in town. Includes a stop for local '
                               'refreshments.',
                'short_description': 'Golden hour magic — glide through Mulberry\'s most scenic spots at sunset.',
                'duration_minutes': 90,
                'price_cents': 4900,
                'max_riders': 6,
                'difficulty': 'easy',
                'distance_miles': 6.0,
                'highlights': 'Sunset Overlook, Heritage Bridge, Peach Tree Lane, Refreshment Stop',
                'what_to_bring': 'Light jacket, camera, water bottle, comfortable clothing',
                'meeting_point': 'Mulberry Town Square, Main Street, Mulberry, GA 30260',
                'is_active': True,
                'is_featured': True,
            },
            {
                'name': 'Nature & Trails Adventure',
                'slug': 'nature-trails-adventure',
                'description': 'For riders who want a bit more thrill! Explore Mulberry\'s nature trails, '
                               'wooded paths, and rolling hills on this moderate-difficulty tour. See local '
                               'wildlife, cross scenic creek crossings, and enjoy Georgia\'s natural beauty '
                               'from the seat of your e-scooter.',
                'short_description': 'Explore trails, hills, and Georgia\'s natural beauty on a moderate ride.',
                'duration_minutes': 120,
                'price_cents': 6500,
                'max_riders': 4,
                'difficulty': 'moderate',

    # Generate sample time slots for the next 14 days
    if TimeSlot.query.count() == 0:
        tours = Tour.query.all()
        guides = Guide.query.all()
        today = date.today()
        slot_times = {
            'Downtown Discovery': [(9, 0), (11, 0), (14, 0), (16, 0)],
            'Sunset & Scenic Route': [(17, 30), (18, 30)],
            'Nature & Trails Adventure': [(8, 0), (10, 30), (14, 0)],
        }
        for day_offset in range(1, 15):
            d = today + timedelta(days=day_offset)
            for tour in tours:
                times = slot_times.get(tour.name, [(10, 0)])
                for h, m in times:

    # Waiver Template
    if WaiverTemplate.query.count() == 0:
        db.session.add(WaiverTemplate(
            title='Mulberry E-Scooter Tours — Liability Waiver & Release',
            content='''ASSUMPTION OF RISK AND WAIVER OF LIABILITY

By signing this waiver, I acknowledge and agree to the following:

1. ACKNOWLEDGMENT OF RISKS: I understand that participating in an electric scooter tour involves inherent risks, including but not limited to: falls, collisions, equipment malfunction, road hazards, weather conditions, and interactions with vehicular traffic and pedestrians. These risks may result in injury, property damage, or in extreme cases, death.

2. PHYSICAL FITNESS: I confirm that I am in adequate physical condition to participate in this activity and have no medical conditions that would impair my ability to safely operate an electric scooter. I am at least 16 years of age (or am accompanied by a parent/guardian who has also signed this waiver).

3. EQUIPMENT RESPONSIBILITY: I agree to wear the provided safety helmet at all times during the tour. I will follow all operating instructions provided by the tour guide. I accept financial responsibility for any damage to the e-scooter caused by my negligence or misuse.

4. RULES OF THE ROAD: I agree to obey all traffic laws, follow the designated tour route, and comply with all instructions given by the tour guide. I will not operate the scooter under the influence of alcohol, drugs, or any substance that impairs judgment or coordination.

5. RELEASE OF LIABILITY: In consideration of being permitted to participate in this tour, I hereby release, waive, and discharge Mulberry E-Scooter Tours, its owners, officers, employees, guides, and agents from any and all liability, claims, demands, or causes of action that I may have arising out of or related to any injury, damage, or loss sustained during my participation.

6. PHOTO/VIDEO CONSENT: I grant Mulberry E-Scooter Tours permission to use photographs or video taken during the tour for promotional and marketing purposes.

7. EMERGENCY MEDICAL AUTHORIZATION: In the event of an emergency, I authorize Mulberry E-Scooter Tours to obtain medical treatment on my behalf if I am unable to do so.

I have read this waiver carefully, understand its contents, and sign it voluntarily.''',
            version='1.0',
            is_active=True
        ))
        print("  ✓ Waiver template created")

    db.session.commit()
    print("\n✅ Database seeded successfully!")


# ════════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

                    end_min = h * 60 + m + tour.duration_minutes
                    guide = guides[day_offset % len(guides)] if guides else None
                    db.session.add(TimeSlot(
                        tour_id=tour.id,
                        guide_id=guide.id if guide else None,
                        slot_date=d,
                        start_time=time(h, m),
                        end_time=time(end_min // 60, end_min % 60),
                        max_riders=tour.max_riders
                    ))
        print("  ✓ Time slots generated for next 14 days")
                'distance_miles': 9.0,
                'highlights': 'Nature Trail Loop, Creek Crossing, Hilltop Vista, Wildlife Spotting',
                'what_to_bring': 'Sturdy shoes, water, sunscreen, bug spray, sense of adventure',
                'meeting_point': 'Mulberry Trailhead Parking, County Road 12, Mulberry, GA 30260',
                'is_active': True,
                'is_featured': False,
            },
        ]
        for td in tours_data:
            db.session.add(Tour(**td))
        print("  ✓ 3 tours created")
    # Guides
    if Guide.query.count() == 0:
        guides_data = [
            ('Alex Rivera', 'alex@mulberryscootertours.com', '(706) 555-0101',
             'Born and raised in Mulberry, Alex knows every back road and hidden gem.'),
            ('Jordan Chen', 'jordan@mulberryscootertours.com', '(706) 555-0102',
             'Outdoor enthusiast and certified safety instructor with 5 years of tour experience.'),
        ]
        for name, email, phone, bio in guides_data:
            db.session.add(Guide(name=name, email=email, phone=phone, bio=bio, is_active=True))
        print("  ✓ 2 guides created")
        TimeSlot.tour_id == tour_id,
        TimeSlot.slot_date == check_date,
        TimeSlot.status == 'open'
    ).order_by(TimeSlot.start_time).all()

    return jsonify([{
        'id': s.id,
        'time': s.formatted_time,
        'available': s.available_spots,
        'max': s.max_riders
    } for s in slots]) '1.0')
        else:
            waiver = WaiverTemplate(
                title=request.form['title'],
                content=request.form['content'],
                version=request.form.get('version', '1.0')
            )
            db.session.add(waiver)
        db.session.commit()
        flash('Waiver template saved!', 'success')
        return redirect(url_for('admin_waivers'))
    return render_template('admin/waiver_form.html', waiver=waiver)
            b.payment_status,
            'Yes' if b.waiver_signed else 'No',
            b.created_at.strftime('%Y-%m-%d %H:%M')
        ])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=bookings-{start}-to-{end}.csv'}
    )
    if request.method == 'POST':
        guide.name = request.form['name']
        guide.email = request.form['email']
        guide.phone = request.form.get('phone', '')
        guide.bio = request.form.get('bio', '')
        guide.is_active = bool(request.form.get('is_active'))
        guide.max_group_size = int(request.form.get('max_group_size', 6))
        db.session.commit()
        flash('Guide updated!', 'success')
        return redirect(url_for('admin_guides'))
    return render_template('admin/guide_form.html', guide=guide)
            if booking.payment_status == 'paid' and booking.stripe_payment_intent_id:
                try:
                    stripe.Refund.create(payment_intent=booking.stripe_payment_intent_id)
                    booking.payment_status = 'refunded'
                    booking.refund_amount_cents = booking.total_cents
                except Exception:
                    pass
            send_cancellation_email(booking)
    db.session.commit()
    flash('Slot cancelled. Affected bookings have been refunded.', 'success')
    return redirect(url_for('admin_slots'))rs', 6))
        tour.difficulty = request.form.get('difficulty', 'easy')
        tour.distance_miles = float(request.form.get('distance_miles', 0)) or None
        tour.highlights = request.form.get('highlights', '')
        tour.what_to_bring = request.form.get('what_to_bring', '')
        tour.meeting_point = request.form.get('meeting_point', '')
        tour.is_active = bool(request.form.get('is_active'))
        tour.is_featured = bool(request.form.get('is_featured'))
        db.session.commit()
        flash('Tour updated!', 'success')
        return redirect(url_for('admin_tours'))
    return render_template('admin/tour_form.html', tour=tour)
        booking.refund_amount_cents += amount_cents
        if booking.refund_amount_cents >= booking.total_cents:
            booking.payment_status = 'refunded'
        else:
            booking.payment_status = 'partial_refund'
        db.session.commit()
        flash(f'Refund of ${amount_dollars:.2f} processed.', 'success')
    except stripe.error.StripeError as e:
        flash(f'Refund failed: {str(e)}', 'error')

    return redirect(url_for('admin_booking_detail', booking_id=booking_id))
            Booking.status == 'confirmed', Booking.waiver_signed == False).count(),
    }
    upcoming = TimeSlot.query.filter(
        TimeSlot.slot_date >= today
    ).order_by(TimeSlot.slot_date, TimeSlot.start_time).limit(10).all()

    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           stats=stats, upcoming=upcoming,
                           recent_bookings=recent_bookings)


# ─── Embeddable Widget ──────────────────────────────────────────────
@app.route('/widget')
def booking_widget():
    tours = Tour.query.filter_by(is_active=True).all()
    return render_template('public/widget.html', tours=tours)

@app.route('/widget/embed.js')
def widget_js():
    return send_from_directory('static/js', 'widget-embed.js', mimetype='application/javascript')
    return render_template('public/contact.html')


@app.route('/faq')
def faq():
    return render_template('public/faq.html')


@app.route('/about')
def about():
    return render_template('public/about.html')
            booking.refund_amount_cents = booking.total_cents
        except stripe.error.StripeError as e:
            flash(f'Refund failed: {str(e)}', 'error')
            return redirect(url_for('booking_lookup'))

    booking.status = 'cancelled'
    booking.cancelled_at = datetime.utcnow()
    db.session.commit()
    send_cancellation_email(booking)
    flash('Your booking has been cancelled and a full refund has been issued.', 'success')
    return redirect(url_for('booking_lookup'))
                    'tour_name': tour.name,
                    'slot_id': slot.id,
                    'customer_name': name,
                    'customer_email': email,
                    'num_riders': num_riders
                },
                receipt_email=email
            )
        except stripe.error.StripeError as e:
            flash(f'Payment setup failed: {str(e)}', 'error')
            return render_template('public/book.html', slot=slot, tour=tour)
        app.logger.error(f"Email send failed: {e}")

def send_cancellation_email(booking):
    """Send cancellation email."""
    try:
        msg = MailMessage(
            subject=f"Booking Cancelled — {booking.booking_ref}",
            recipients=[booking.customer_email],
            html=render_template('emails/cancellation.html', booking=booking)
        )
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Email send failed: {e}")
