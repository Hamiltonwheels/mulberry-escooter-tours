"""
Mulberry E-Scooter Tours - Main Application
Full-featured booking system with Stripe payments and admin dashboard.
"""
import os
import json
import stripe
from datetime import datetime, date, time, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, abort, session
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_mail import Mail, Message as MailMessage

from config import Config
from models import (
    db, Admin, Scooter, Guide, Tour, TimeSlot,
    Booking, Participant, WaiverTemplate, ContactMessage,
    SiteSettings, generate_booking_ref
)

# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

# Fix Postgres URI for SQLAlchemy (Railway uses postgres:// but SA needs postgresql://)
uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
if uri.startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = uri.replace('postgres://', 'postgresql://', 1)

db.init_app(app)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message_category = 'warning'

# Flask-Mail (optional - graceful failure if not configured)
mail = Mail(app)

# Stripe
stripe.api_key = app.config.get('STRIPE_SECRET_KEY', '')

# ---------------------------------------------------------------------------
# Create tables on startup
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()

# ---------------------------------------------------------------------------
# Flask-Login loader
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

# ---------------------------------------------------------------------------
# Context Processors - inject into every template
# ---------------------------------------------------------------------------
@app.context_processor
def inject_config():
    return dict(
        business_name=app.config.get('BUSINESS_NAME', 'Mulberry E-Scooter Tours'),
        business_tagline=app.config.get('BUSINESS_TAGLINE', 'Explore Mulberry, GA on Two Wheels'),
        business_email=app.config.get('BUSINESS_EMAIL', ''),
        business_phone=app.config.get('BUSINESS_PHONE', ''),
        business_address=app.config.get('BUSINESS_ADDRESS', ''),
        stripe_publishable_key=app.config.get('STRIPE_PUBLISHABLE_KEY', ''),
        current_year=datetime.utcnow().year,
    )

# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template('public/index.html',
                           error_message='Page not found.'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('public/index.html',
                           error_message='Something went wrong. Please try again.'), 500

# ---------------------------------------------------------------------------
# Helper: send email (graceful failure)
# ---------------------------------------------------------------------------
def send_email(subject, recipients, body_html, body_text=None):
    """Send an email; silently fail if mail is not configured."""
    try:
        msg = MailMessage(
            subject=subject,
            recipients=recipients,
            html=body_html,
            body=body_text or '',
            sender=app.config.get('MAIL_DEFAULT_SENDER')
        )
        mail.send(msg)
        return True
    except Exception:
        app.logger.warning(f'Email send failed: {subject} to {recipients}')
        return False

# =========================================================================
#  PUBLIC ROUTES
# =========================================================================

@app.route('/')
def index():
    """Homepage - featured tours and hero section."""
    featured_tours = Tour.query.filter_by(is_active=True, is_featured=True).all()
    return render_template('public/index.html', featured_tours=featured_tours)


@app.route('/tours')
def tours():
    """All active tours listing."""
    all_tours = Tour.query.filter_by(is_active=True).order_by(Tour.price_cents).all()
    return render_template('public/tours.html', tours=all_tours)


@app.route('/tours/<slug>')
def tour_detail(slug):
    """Individual tour detail page."""
    tour = Tour.query.filter_by(slug=slug, is_active=True).first_or_404()

    # Get available dates for next 60 days
    today = date.today()
    max_date = today + timedelta(days=app.config.get('BOOKING_ADVANCE_DAYS', 60))

    available_slots = TimeSlot.query.filter(
        TimeSlot.tour_id == tour.id,
        TimeSlot.slot_date >= today,
        TimeSlot.slot_date <= max_date,
        TimeSlot.status == 'open'
    ).order_by(TimeSlot.slot_date, TimeSlot.start_time).all()

    # Group slots by date
    slots_by_date = {}
    for slot in available_slots:
        if slot.available_spots > 0:
            date_str = slot.slot_date.isoformat()
            if date_str not in slots_by_date:
                slots_by_date[date_str] = []
            slots_by_date[date_str].append(slot)

    return render_template('public/tour_detail.html',
                           tour=tour,
                           slots_by_date=slots_by_date,
                           today=today,
                           max_date=max_date)


@app.route('/book/<slug>', methods=['GET', 'POST'])
def book_tour(slug):
    """Booking form - select date, time slot, number of riders."""
    tour = Tour.query.filter_by(slug=slug, is_active=True).first_or_404()

    if request.method == 'POST':
        slot_id = request.form.get('slot_id', type=int)
        num_riders = request.form.get('num_riders', type=int)
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        special_requests = request.form.get('special_requests', '').strip()

        # Validation
        errors = []
        if not slot_id:
            errors.append('Please select a time slot.')
        if not num_riders or num_riders < 1:
            errors.append('Please select the number of riders.')
        if not customer_name:
            errors.append('Name is required.')
        if not customer_email:
            errors.append('Email is required.')
        if not customer_phone:
            errors.append('Phone number is required.')

        slot = TimeSlot.query.get(slot_id) if slot_id else None
        if slot and num_riders:
            if num_riders > slot.available_spots:
                errors.append(f'Only {slot.available_spots} spots available for this time slot.')
            if slot.status != 'open':
                errors.append('This time slot is no longer available.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('book_tour', slug=slug))

        # Calculate total
        total_cents = tour.price_cents * num_riders

        # Create booking
        booking = Booking(
            time_slot_id=slot.id,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            num_riders=num_riders,
            total_cents=total_cents,
            special_requests=special_requests,
            status='pending',
            payment_status='pending'
        )
        db.session.add(booking)
        db.session.commit()

        # Redirect to payment
        return redirect(url_for('payment', booking_ref=booking.booking_ref))

    # GET - show booking form
    today = date.today()
    max_date = today + timedelta(days=app.config.get('BOOKING_ADVANCE_DAYS', 60))

    available_slots = TimeSlot.query.filter(
        TimeSlot.tour_id == tour.id,
        TimeSlot.slot_date >= today,
        TimeSlot.slot_date <= max_date,
        TimeSlot.status == 'open'
    ).order_by(TimeSlot.slot_date, TimeSlot.start_time).all()

    # Filter to slots with availability
    available_slots = [s for s in available_slots if s.available_spots > 0]

    return render_template('public/book.html',
                           tour=tour,
                           available_slots=available_slots,
                           today=today,
                           max_date=max_date)


@app.route('/payment/<booking_ref>', methods=['GET', 'POST'])
def payment(booking_ref):
    """Payment page - Stripe integration."""
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()

    if booking.payment_status == 'paid':
        flash('This booking has already been paid.', 'info')
        return redirect(url_for('booking_success', booking_ref=booking_ref))

    tour = booking.time_slot.tour

    return render_template('public/payment.html',
                           booking=booking,
                           tour=tour,
                           stripe_publishable_key=app.config.get('STRIPE_PUBLISHABLE_KEY', ''))


@app.route('/booking/success/<booking_ref>')
def booking_success(booking_ref):
    """Booking confirmation page."""
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    tour = booking.time_slot.tour
    return render_template('public/booking_success.html',
                           booking=booking, tour=tour)


@app.route('/booking/lookup', methods=['GET', 'POST'])
def booking_lookup():
    """Look up an existing booking by reference number or email."""
    booking = None
    bookings = []

    if request.method == 'POST':
        lookup_value = request.form.get('lookup_value', '').strip()

        if lookup_value:
            # Try booking reference first
            booking = Booking.query.filter_by(booking_ref=lookup_value.upper()).first()

            if not booking:
                # Try email
                bookings = Booking.query.filter_by(
                    customer_email=lookup_value
                ).order_by(Booking.created_at.desc()).all()

            if not booking and not bookings:
                flash('No booking found. Please check your reference number or email.', 'warning')

    return render_template('public/booking_lookup.html',
                           booking=booking, bookings=bookings)


@app.route('/booking/<booking_ref>')
def booking_detail_public(booking_ref):
    """Public booking detail page."""
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    tour = booking.time_slot.tour
    return render_template('public/booking_detail.html',
                           booking=booking, tour=tour)


@app.route('/waiver/<booking_ref>', methods=['GET', 'POST'])
def waiver(booking_ref):
    """Digital waiver signing."""
    booking = Booking.query.filter_by(booking_ref=booking_ref).first_or_404()
    waiver_template = WaiverTemplate.query.filter_by(is_active=True).first()

    if request.method == 'POST':
        signer_name = request.form.get('signer_name', '').strip()

        if not signer_name:
            flash('Please enter your full name to sign the waiver.', 'danger')
            return redirect(url_for('waiver', booking_ref=booking_ref))

        booking.waiver_signed = True
        booking.waiver_signed_at = datetime.utcnow()
        booking.waiver_signer_name = signer_name
        db.session.commit()

        flash('Waiver signed successfully! Thank you.', 'success')
        return redirect(url_for('booking_detail_public', booking_ref=booking_ref))

    return render_template('public/waiver.html',
                           booking=booking,
                           waiver_template=waiver_template)


@app.route('/about')
def about():
    """About page."""
    guides = Guide.query.filter_by(is_active=True).all()
    return render_template('public/about.html', guides=guides)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page with form."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('contact'))

        contact_msg = ContactMessage(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )
        db.session.add(contact_msg)
        db.session.commit()

        flash('Thank you for your message! We\'ll get back to you soon.', 'success')
        return redirect(url_for('contact'))

    return render_template('public/contact.html')


@app.route('/faq')
def faq():
    """FAQ page."""
    return render_template('public/faq.html')


@app.route('/widget')
def widget():
    """Embeddable booking widget."""
    tours = Tour.query.filter_by(is_active=True).all()
    return render_template('public/widget.html', tours=tours)


# =========================================================================
#  API ROUTES
# =========================================================================

@app.route('/api/slots/<int:tour_id>')
def api_get_slots(tour_id):
    """Get available time slots for a tour (optionally filtered by date)."""
    tour = Tour.query.get_or_404(tour_id)
    date_str = request.args.get('date')

    query = TimeSlot.query.filter(
        TimeSlot.tour_id == tour.id,
        TimeSlot.status == 'open',
        TimeSlot.slot_date >= date.today()
    )

    if date_str:
        try:
            filter_date = date.fromisoformat(date_str)
            query = query.filter(TimeSlot.slot_date == filter_date)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    slots = query.order_by(TimeSlot.slot_date, TimeSlot.start_time).all()

    result = []
    for slot in slots:
        if slot.available_spots > 0:
            result.append({
                'id': slot.id,
                'date': slot.slot_date.isoformat(),
                'formatted_date': slot.formatted_date,
                'start_time': slot.start_time.strftime('%H:%M'),
                'formatted_time': slot.formatted_time,
                'end_time': slot.end_time.strftime('%H:%M'),
                'available_spots': slot.available_spots,
                'max_riders': slot.max_riders,
                'guide': slot.guide.name if slot.guide else None
            })

    return jsonify({'slots': result, 'tour_id': tour.id})


@app.route('/api/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create a Stripe PaymentIntent for a booking."""
    try:
        data = request.get_json()
        booking_ref = data.get('booking_ref')

        booking = Booking.query.filter_by(booking_ref=booking_ref).first()
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404

        if booking.payment_status == 'paid':
            return jsonify({'error': 'Already paid'}), 400

        tour = booking.time_slot.tour

        # Create PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=booking.total_cents,
            currency='usd',
            metadata={
                'booking_ref': booking.booking_ref,
                'tour_name': tour.name,
                'customer_email': booking.customer_email
            },
            receipt_email=booking.customer_email,
            description=f'{tour.name} - {booking.num_riders} rider(s)'
        )

        booking.stripe_payment_intent_id = intent.id
        db.session.commit()

        return jsonify({
            'clientSecret': intent.client_secret,
            'amount': booking.total_cents,
            'booking_ref': booking.booking_ref
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Payment processing error'}), 500


@app.route('/api/payment-success', methods=['POST'])
def payment_success():
    """Handle successful payment (called from frontend)."""
    try:
        data = request.get_json()
        booking_ref = data.get('booking_ref')
        payment_intent_id = data.get('payment_intent_id')

        booking = Booking.query.filter_by(booking_ref=booking_ref).first()
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404

        # Verify with Stripe
        if payment_intent_id:
            try:
                intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                if intent.status == 'succeeded':
                    booking.payment_status = 'paid'
                    booking.status = 'confirmed'
                    booking.stripe_payment_intent_id = payment_intent_id
                    if hasattr(intent, 'latest_charge') and intent.latest_charge:
                        booking.stripe_charge_id = intent.latest_charge
                    db.session.commit()

                    # Try to send confirmation email
                    try:
                        send_email(
                            subject=f'Booking Confirmed - {booking.booking_ref}',
                            recipients=[booking.customer_email],
                            body_html=render_template('emails/booking_confirmation.html',
                                                      booking=booking,
                                                      tour=booking.time_slot.tour),
                            body_text=f'Your booking {booking.booking_ref} is confirmed!'
                        )
                    except Exception:
                        pass

                    return jsonify({'success': True, 'booking_ref': booking.booking_ref})
            except stripe.error.StripeError:
                pass

        return jsonify({'error': 'Payment verification failed'}), 400

    except Exception as e:
        return jsonify({'error': 'Error processing payment'}), 500


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = app.config.get('STRIPE_WEBHOOK_SECRET', '')

    try:
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            event = json.loads(payload)
    except (ValueError, stripe.error.SignatureVerificationError):
        return '', 400

    # Handle the event
    if event.get('type') == 'payment_intent.succeeded':
        intent = event['data']['object']
        booking_ref = intent.get('metadata', {}).get('booking_ref')

        if booking_ref:
            booking = Booking.query.filter_by(booking_ref=booking_ref).first()
            if booking and booking.payment_status != 'paid':
                booking.payment_status = 'paid'
                booking.status = 'confirmed'
                booking.stripe_charge_id = intent.get('latest_charge', '')
                db.session.commit()

    elif event.get('type') == 'charge.refunded':
        charge = event['data']['object']
        booking = Booking.query.filter_by(stripe_charge_id=charge['id']).first()
        if booking:
            booking.refund_amount_cents = charge.get('amount_refunded', 0)
            if charge.get('amount_refunded', 0) >= booking.total_cents:
                booking.payment_status = 'refunded'
                booking.status = 'cancelled'
                booking.cancelled_at = datetime.utcnow()
            else:
                booking.payment_status = 'partial_refund'
            db.session.commit()

    return '', 200


@app.route('/api/cancel-booking', methods=['POST'])
def cancel_booking_api():
    """Cancel a booking (public-facing)."""
    try:
        data = request.get_json()
        booking_ref = data.get('booking_ref')
        customer_email = data.get('customer_email')

        booking = Booking.query.filter_by(
            booking_ref=booking_ref,
            customer_email=customer_email
        ).first()

        if not booking:
            return jsonify({'error': 'Booking not found'}), 404

        if booking.status == 'cancelled':
            return jsonify({'error': 'Booking already cancelled'}), 400

        # Check cancellation window
        slot_datetime = datetime.combine(
            booking.time_slot.slot_date,
            booking.time_slot.start_time
        )
        hours_until = (slot_datetime - datetime.now()).total_seconds() / 3600
        cancellation_hours = app.config.get('CANCELLATION_HOURS', 24)

        if hours_until < cancellation_hours:
            return jsonify({
                'error': f'Cancellations must be made at least {cancellation_hours} hours before the tour.'
            }), 400

        # Process refund if paid
        if booking.payment_status == 'paid' and booking.stripe_charge_id:
            try:
                stripe.Refund.create(charge=booking.stripe_charge_id)
                booking.payment_status = 'refunded'
                booking.refund_amount_cents = booking.total_cents
            except stripe.error.StripeError as e:
                return jsonify({'error': f'Refund failed: {str(e)}'}), 400

        booking.status = 'cancelled'
        booking.cancelled_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'message': 'Booking cancelled successfully'})

    except Exception as e:
        return jsonify({'error': 'Error cancelling booking'}), 500


# =========================================================================
#  ADMIN ROUTES
# =========================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password) and admin.is_active_admin:
            login_user(admin)
            flash(f'Welcome back, {admin.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin_dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Admin logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard with stats overview."""
    today = date.today()

    # Today's bookings
    todays_slots = TimeSlot.query.filter_by(slot_date=today).all()
    todays_slot_ids = [s.id for s in todays_slots]
    todays_bookings = Booking.query.filter(
        Booking.time_slot_id.in_(todays_slot_ids),
        Booking.status == 'confirmed'
    ).all() if todays_slot_ids else []

    # Stats
    total_bookings = Booking.query.filter_by(status='confirmed').count()
    pending_bookings = Booking.query.filter_by(status='pending').count()
    total_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Booking.total_cents), 0)
    ).filter_by(status='confirmed', payment_status='paid').scalar()

    # This week's bookings
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_slots = TimeSlot.query.filter(
        TimeSlot.slot_date >= week_start,
        TimeSlot.slot_date <= week_end
    ).all()
    week_slot_ids = [s.id for s in week_slots]
    week_bookings = Booking.query.filter(
        Booking.time_slot_id.in_(week_slot_ids),
        Booking.status == 'confirmed'
    ).count() if week_slot_ids else 0

    # Fleet status
    fleet_available = Scooter.query.filter_by(status='available').count()
    fleet_total = Scooter.query.count()

    # Unread messages
    unread_messages = ContactMessage.query.filter_by(is_read=False).count()

    # Recent bookings
    recent_bookings = Booking.query.order_by(
        Booking.created_at.desc()
    ).limit(10).all()

    # Upcoming tours today
    upcoming_slots = TimeSlot.query.filter(
        TimeSlot.slot_date == today,
        TimeSlot.status == 'open'
    ).order_by(TimeSlot.start_time).all()

    return render_template('admin/dashboard.html',
                           todays_bookings=todays_bookings,
                           total_bookings=total_bookings,
                           pending_bookings=pending_bookings,
                           total_revenue=total_revenue,
                           week_bookings=week_bookings,
                           fleet_available=fleet_available,
                           fleet_total=fleet_total,
                           unread_messages=unread_messages,
                           recent_bookings=recent_bookings,
                           upcoming_slots=upcoming_slots,
                           today=today)


# --- Admin: Bookings ---

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    """List all bookings with filters."""
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)

    query = Booking.query

    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    bookings = query.order_by(Booking.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/bookings.html',
                           bookings=bookings,
                           status_filter=status_filter)


@app.route('/admin/bookings/<int:booking_id>')
@login_required
def admin_booking_detail(booking_id):
    """Booking detail view for admin."""
    booking = Booking.query.get_or_404(booking_id)
    tour = booking.time_slot.tour
    return render_template('admin/booking_detail.html',
                           booking=booking, tour=tour)


@app.route('/admin/bookings/<int:booking_id>/confirm', methods=['POST'])
@login_required
def admin_confirm_booking(booking_id):
    """Manually confirm a booking."""
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'confirmed'
    db.session.commit()
    flash(f'Booking {booking.booking_ref} confirmed.', 'success')
    return redirect(url_for('admin_booking_detail', booking_id=booking.id))


@app.route('/admin/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def admin_cancel_booking(booking_id):
    """Admin cancel a booking with optional refund."""
    booking = Booking.query.get_or_404(booking_id)

    # Process refund if paid
    if booking.payment_status == 'paid' and booking.stripe_charge_id:
        try:
            stripe.Refund.create(charge=booking.stripe_charge_id)
            booking.payment_status = 'refunded'
            booking.refund_amount_cents = booking.total_cents
        except stripe.error.StripeError as e:
            flash(f'Refund failed: {str(e)}', 'danger')

    booking.status = 'cancelled'
    booking.cancelled_at = datetime.utcnow()
    db.session.commit()

    flash(f'Booking {booking.booking_ref} cancelled.', 'warning')
    return redirect(url_for('admin_booking_detail', booking_id=booking.id))


# --- Admin: Tours ---

@app.route('/admin/tours')
@login_required
def admin_tours():
    """List all tours."""
    tours = Tour.query.order_by(Tour.name).all()
    return render_template('admin/tours.html', tours=tours)


@app.route('/admin/tours/new', methods=['GET', 'POST'])
@login_required
def admin_tour_new():
    """Create a new tour."""
    if request.method == 'POST':
        tour = Tour(
            name=request.form.get('name', '').strip(),
            slug=request.form.get('slug', '').strip().lower().replace(' ', '-'),
            description=request.form.get('description', '').strip(),
            short_description=request.form.get('short_description', '').strip(),
            duration_minutes=request.form.get('duration_minutes', type=int) or 60,
            price_cents=int(float(request.form.get('price', 0)) * 100),
            max_riders=request.form.get('max_riders', type=int) or 6,
            min_riders=request.form.get('min_riders', type=int) or 1,
            difficulty=request.form.get('difficulty', 'easy'),
            distance_miles=request.form.get('distance_miles', type=float),
            highlights=request.form.get('highlights', '').strip(),
            what_to_bring=request.form.get('what_to_bring', '').strip(),
            meeting_point=request.form.get('meeting_point', '').strip(),
            image_url=request.form.get('image_url', '').strip(),
            is_active='is_active' in request.form,
            is_featured='is_featured' in request.form,
        )
        db.session.add(tour)
        db.session.commit()
        flash(f'Tour "{tour.name}" created!', 'success')
        return redirect(url_for('admin_tours'))

    return render_template('admin/tour_form.html', tour=None)


@app.route('/admin/tours/<int:tour_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_tour_edit(tour_id):
    """Edit an existing tour."""
    tour = Tour.query.get_or_404(tour_id)

    if request.method == 'POST':
        tour.name = request.form.get('name', '').strip()
        tour.slug = request.form.get('slug', '').strip().lower().replace(' ', '-')
        tour.description = request.form.get('description', '').strip()
        tour.short_description = request.form.get('short_description', '').strip()
        tour.duration_minutes = request.form.get('duration_minutes', type=int) or 60
        tour.price_cents = int(float(request.form.get('price', 0)) * 100)
        tour.max_riders = request.form.get('max_riders', type=int) or 6
        tour.min_riders = request.form.get('min_riders', type=int) or 1
        tour.difficulty = request.form.get('difficulty', 'easy')
        tour.distance_miles = request.form.get('distance_miles', type=float)
        tour.highlights = request.form.get('highlights', '').strip()
        tour.what_to_bring = request.form.get('what_to_bring', '').strip()
        tour.meeting_point = request.form.get('meeting_point', '').strip()
        tour.image_url = request.form.get('image_url', '').strip()
        tour.is_active = 'is_active' in request.form
        tour.is_featured = 'is_featured' in request.form

        db.session.commit()
        flash(f'Tour "{tour.name}" updated!', 'success')
        return redirect(url_for('admin_tours'))

    return render_template('admin/tour_form.html', tour=tour)


@app.route('/admin/tours/<int:tour_id>/delete', methods=['POST'])
@login_required
def admin_tour_delete(tour_id):
    """Delete a tour (soft delete - deactivate)."""
    tour = Tour.query.get_or_404(tour_id)
    tour.is_active = False
    db.session.commit()
    flash(f'Tour "{tour.name}" deactivated.', 'warning')
    return redirect(url_for('admin_tours'))


# --- Admin: Scooters ---

@app.route('/admin/scooters')
@login_required
def admin_scooters():
    """Fleet management - list all scooters."""
    scooters = Scooter.query.order_by(Scooter.scooter_id).all()
    return render_template('admin/scooters.html', scooters=scooters)


@app.route('/admin/scooters/new', methods=['GET', 'POST'])
@login_required
def admin_scooter_new():
    """Add a new scooter to fleet."""
    if request.method == 'POST':
        scooter = Scooter(
            name=request.form.get('name', '').strip(),
            scooter_id=request.form.get('scooter_id', '').strip(),
            model=request.form.get('model', 'Standard E-Scooter').strip(),
            status=request.form.get('status', 'available'),
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(scooter)
        db.session.commit()
        flash(f'Scooter {scooter.scooter_id} added to fleet!', 'success')
        return redirect(url_for('admin_scooters'))

    return render_template('admin/scooter_form.html', scooter=None)


@app.route('/admin/scooters/<int:scooter_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_scooter_edit(scooter_id):
    """Edit scooter details."""
    scooter = Scooter.query.get_or_404(scooter_id)

    if request.method == 'POST':
        scooter.name = request.form.get('name', '').strip()
        scooter.scooter_id = request.form.get('scooter_id', '').strip()
        scooter.model = request.form.get('model', '').strip()
        scooter.status = request.form.get('status', 'available')
        scooter.notes = request.form.get('notes', '').strip()

        db.session.commit()
        flash(f'Scooter {scooter.scooter_id} updated!', 'success')
        return redirect(url_for('admin_scooters'))

    return render_template('admin/scooter_form.html', scooter=scooter)


@app.route('/admin/scooters/<int:scooter_id>/delete', methods=['POST'])
@login_required
def admin_scooter_delete(scooter_id):
    """Remove a scooter from fleet."""
    scooter = Scooter.query.get_or_404(scooter_id)
    db.session.delete(scooter)
    db.session.commit()
    flash(f'Scooter {scooter.scooter_id} removed from fleet.', 'warning')
    return redirect(url_for('admin_scooters'))


# --- Admin: Guides ---

@app.route('/admin/guides')
@login_required
def admin_guides():
    """List all tour guides."""
    guides = Guide.query.order_by(Guide.name).all()
    return render_template('admin/guides.html', guides=guides)


@app.route('/admin/guides/new', methods=['GET', 'POST'])
@login_required
def admin_guide_new():
    """Add a new guide."""
    if request.method == 'POST':
        guide = Guide(
            name=request.form.get('name', '').strip(),
            email=request.form.get('email', '').strip(),
            phone=request.form.get('phone', '').strip(),
            bio=request.form.get('bio', '').strip(),
            is_active='is_active' in request.form,
            max_group_size=request.form.get('max_group_size', type=int) or 6
        )
        db.session.add(guide)
        db.session.commit()
        flash(f'Guide "{guide.name}" added!', 'success')
        return redirect(url_for('admin_guides'))

    return render_template('admin/guide_form.html', guide=None)


@app.route('/admin/guides/<int:guide_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_guide_edit(guide_id):
    """Edit guide details."""
    guide = Guide.query.get_or_404(guide_id)

    if request.method == 'POST':
        guide.name = request.form.get('name', '').strip()
        guide.email = request.form.get('email', '').strip()
        guide.phone = request.form.get('phone', '').strip()
        guide.bio = request.form.get('bio', '').strip()
        guide.is_active = 'is_active' in request.form
        guide.max_group_size = request.form.get('max_group_size', type=int) or 6

        db.session.commit()
        flash(f'Guide "{guide.name}" updated!', 'success')
        return redirect(url_for('admin_guides'))

    return render_template('admin/guide_form.html', guide=guide)


@app.route('/admin/guides/<int:guide_id>/delete', methods=['POST'])
@login_required
def admin_guide_delete(guide_id):
    """Deactivate a guide."""
    guide = Guide.query.get_or_404(guide_id)
    guide.is_active = False
    db.session.commit()
    flash(f'Guide "{guide.name}" deactivated.', 'warning')
    return redirect(url_for('admin_guides'))


# --- Admin: Time Slots ---

@app.route('/admin/slots', methods=['GET', 'POST'])
@login_required
def admin_slots():
    """Manage time slots for tours."""
    tours = Tour.query.filter_by(is_active=True).order_by(Tour.name).all()
    guides = Guide.query.filter_by(is_active=True).order_by(Guide.name).all()

    # Filter
    tour_filter = request.args.get('tour_id', type=int)
    date_filter = request.args.get('date')
    page = request.args.get('page', 1, type=int)

    query = TimeSlot.query.filter(TimeSlot.slot_date >= date.today())

    if tour_filter:
        query = query.filter_by(tour_id=tour_filter)
    if date_filter:
        try:
            filter_date = date.fromisoformat(date_filter)
            query = query.filter_by(slot_date=filter_date)
        except ValueError:
            pass

    slots = query.order_by(
        TimeSlot.slot_date, TimeSlot.start_time
    ).paginate(page=page, per_page=30, error_out=False)

    if request.method == 'POST':
        # Create new slot(s)
        tour_id = request.form.get('tour_id', type=int)
        guide_id = request.form.get('guide_id', type=int) or None
        slot_date_str = request.form.get('slot_date', '')
        start_time_str = request.form.get('start_time', '')
        end_time_str = request.form.get('end_time', '')
        max_riders = request.form.get('max_riders', type=int) or 6

        try:
            slot_date_val = date.fromisoformat(slot_date_str)
            start_parts = start_time_str.split(':')
            end_parts = end_time_str.split(':')
            start_time_val = time(int(start_parts[0]), int(start_parts[1]))
            end_time_val = time(int(end_parts[0]), int(end_parts[1]))

            slot = TimeSlot(
                tour_id=tour_id,
                guide_id=guide_id,
                slot_date=slot_date_val,
                start_time=start_time_val,
                end_time=end_time_val,
                max_riders=max_riders,
                status='open'
            )
            db.session.add(slot)
            db.session.commit()
            flash('Time slot created!', 'success')
        except (ValueError, IndexError):
            flash('Invalid date or time format.', 'danger')

        return redirect(url_for('admin_slots'))

    return render_template('admin/slots.html',
                           slots=slots,
                           tours=tours,
                           guides=guides,
                           tour_filter=tour_filter,
                           date_filter=date_filter)


@app.route('/admin/slots/<int:slot_id>/cancel', methods=['POST'])
@login_required
def admin_slot_cancel(slot_id):
    """Cancel a time slot."""
    slot = TimeSlot.query.get_or_404(slot_id)
    slot.status = 'cancelled'
    db.session.commit()
    flash('Time slot cancelled.', 'warning')
    return redirect(url_for('admin_slots'))


@app.route('/admin/slots/<int:slot_id>/open', methods=['POST'])
@login_required
def admin_slot_open(slot_id):
    """Reopen a cancelled time slot."""
    slot = TimeSlot.query.get_or_404(slot_id)
    slot.status = 'open'
    db.session.commit()
    flash('Time slot reopened.', 'success')
    return redirect(url_for('admin_slots'))


@app.route('/admin/slots/generate', methods=['POST'])
@login_required
def admin_slots_generate():
    """Bulk generate time slots for upcoming days."""
    tour_id = request.form.get('tour_id', type=int)
    days_ahead = request.form.get('days_ahead', type=int) or 14
    guide_id = request.form.get('guide_id', type=int) or None

    tour = Tour.query.get_or_404(tour_id)

    time_options = {
        60: [time(9, 0), time(11, 0), time(14, 0), time(16, 0)],
        90: [time(9, 0), time(11, 0), time(14, 0)],
        120: [time(16, 0), time(17, 0)],
    }
    times = time_options.get(tour.duration_minutes, [time(10, 0)])

    today = date.today()
    count = 0

    for day_offset in range(1, days_ahead + 1):
        slot_date = today + timedelta(days=day_offset)

        for start_t in times:
            # Check if slot already exists
            existing = TimeSlot.query.filter_by(
                tour_id=tour.id,
                slot_date=slot_date,
                start_time=start_t
            ).first()

            if existing:
                continue

            end_minutes = start_t.hour * 60 + start_t.minute + tour.duration_minutes
            end_t = time(end_minutes // 60, end_minutes % 60)

            slot = TimeSlot(
                tour_id=tour.id,
                guide_id=guide_id,
                slot_date=slot_date,
                start_time=start_t,
                end_time=end_t,
                max_riders=tour.max_riders,
                status='open'
            )
            db.session.add(slot)
            count += 1

    db.session.commit()
    flash(f'{count} time slots generated for {tour.name}!', 'success')
    return redirect(url_for('admin_slots'))


# --- Admin: Messages ---

@app.route('/admin/messages')
@login_required
def admin_messages():
    """View contact form messages."""
    page = request.args.get('page', 1, type=int)
    messages = ContactMessage.query.order_by(
        ContactMessage.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/messages.html', messages=messages)


@app.route('/admin/messages/<int:message_id>/read', methods=['POST'])
@login_required
def admin_message_read(message_id):
    """Mark a message as read."""
    msg = ContactMessage.query.get_or_404(message_id)
    msg.is_read = True
    db.session.commit()
    flash('Message marked as read.', 'success')
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/<int:message_id>/delete', methods=['POST'])
@login_required
def admin_message_delete(message_id):
    """Delete a contact message."""
    msg = ContactMessage.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.commit()
    flash('Message deleted.', 'warning')
    return redirect(url_for('admin_messages'))


# --- Admin: Reports ---

@app.route('/admin/reports')
@login_required
def admin_reports():
    """Revenue and booking reports."""
    today = date.today()

    # Date range from query params
    start_str = request.args.get('start_date', (today - timedelta(days=30)).isoformat())
    end_str = request.args.get('end_date', today.isoformat())

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        start_date = today - timedelta(days=30)
        end_date = today

    # Revenue
    revenue_query = db.session.query(
        db.func.coalesce(db.func.sum(Booking.total_cents), 0)
    ).filter(
        Booking.status == 'confirmed',
        Booking.payment_status == 'paid',
        Booking.created_at >= datetime.combine(start_date, time.min),
        Booking.created_at <= datetime.combine(end_date, time.max)
    )
    total_revenue = revenue_query.scalar()

    # Booking counts
    total_bookings = Booking.query.filter(
        Booking.created_at >= datetime.combine(start_date, time.min),
        Booking.created_at <= datetime.combine(end_date, time.max)
    ).count()

    confirmed_bookings = Booking.query.filter(
        Booking.status == 'confirmed',
        Booking.created_at >= datetime.combine(start_date, time.min),
        Booking.created_at <= datetime.combine(end_date, time.max)
    ).count()

    cancelled_bookings = Booking.query.filter(
        Booking.status == 'cancelled',
        Booking.created_at >= datetime.combine(start_date, time.min),
        Booking.created_at <= datetime.combine(end_date, time.max)
    ).count()

    # Total riders
    total_riders = db.session.query(
        db.func.coalesce(db.func.sum(Booking.num_riders), 0)
    ).filter(
        Booking.status == 'confirmed',
        Booking.created_at >= datetime.combine(start_date, time.min),
        Booking.created_at <= datetime.combine(end_date, time.max)
    ).scalar()

    # Revenue by tour
    revenue_by_tour = db.session.query(
        Tour.name,
        db.func.count(Booking.id),
        db.func.coalesce(db.func.sum(Booking.total_cents), 0)
    ).join(TimeSlot, Booking.time_slot_id == TimeSlot.id
    ).join(Tour, TimeSlot.tour_id == Tour.id
    ).filter(
        Booking.status == 'confirmed',
        Booking.payment_status == 'paid',
        Booking.created_at >= datetime.combine(start_date, time.min),
        Booking.created_at <= datetime.combine(end_date, time.max)
    ).group_by(Tour.name).all()

    return render_template('admin/reports.html',
                           total_revenue=total_revenue,
                           total_bookings=total_bookings,
                           confirmed_bookings=confirmed_bookings,
                           cancelled_bookings=cancelled_bookings,
                           total_riders=total_riders,
                           revenue_by_tour=revenue_by_tour,
                           start_date=start_date,
                           end_date=end_date)


# --- Admin: Settings ---

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Site settings management."""
    if request.method == 'POST':
        # Update settings
        settings_keys = ['business_name', 'business_tagline', 'business_email',
                         'business_phone', 'business_address', 'timezone']

        for key in settings_keys:
            value = request.form.get(key, '').strip()
            setting = SiteSettings.query.filter_by(key=key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = SiteSettings(key=key, value=value)
                db.session.add(setting)

        db.session.commit()
        flash('Settings updated!', 'success')
        return redirect(url_for('admin_settings'))

    # Load current settings
    settings = {}
    for s in SiteSettings.query.all():
        settings[s.key] = s.value

    return render_template('admin/settings.html', settings=settings)


# --- Admin: Waivers ---

@app.route('/admin/waivers')
@login_required
def admin_waivers():
    """Manage waiver templates."""
    waivers = WaiverTemplate.query.order_by(WaiverTemplate.created_at.desc()).all()
    return render_template('admin/waivers.html', waivers=waivers)


@app.route('/admin/waivers/new', methods=['GET', 'POST'])
@login_required
def admin_waiver_new():
    """Create a new waiver template."""
    if request.method == 'POST':
        # Deactivate existing waivers
        WaiverTemplate.query.update({WaiverTemplate.is_active: False})

        waiver_t = WaiverTemplate(
            title=request.form.get('title', '').strip(),
            content=request.form.get('content', '').strip(),
            version=request.form.get('version', '1.0').strip(),
            is_active=True
        )
        db.session.add(waiver_t)
        db.session.commit()
        flash('Waiver template created and set as active!', 'success')
        return redirect(url_for('admin_waivers'))

    return render_template('admin/waiver_form.html', waiver=None)


@app.route('/admin/waivers/<int:waiver_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_waiver_edit(waiver_id):
    """Edit a waiver template."""
    waiver_t = WaiverTemplate.query.get_or_404(waiver_id)

    if request.method == 'POST':
        waiver_t.title = request.form.get('title', '').strip()
        waiver_t.content = request.form.get('content', '').strip()
        waiver_t.version = request.form.get('version', '1.0').strip()
        waiver_t.is_active = 'is_active' in request.form

        if waiver_t.is_active:
            # Deactivate others
            WaiverTemplate.query.filter(
                WaiverTemplate.id != waiver_t.id
            ).update({WaiverTemplate.is_active: False})

        db.session.commit()
        flash('Waiver template updated!', 'success')
        return redirect(url_for('admin_waivers'))

    return render_template('admin/waiver_form.html', waiver=waiver_t)


# =========================================================================
#  HEALTH CHECK
# =========================================================================

@app.route('/health')
def health():
    """Health check endpoint for Railway."""
    return 'OK', 200


# =========================================================================
#  RUN
# =========================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
