"""
Seed script - populates the database with sample data for Mulberry E-Scooter Tours.
Run: python seed_data.py
"""
from app import app, db
from models import Admin, Scooter, Guide, Tour, TimeSlot, WaiverTemplate
from datetime import date, time, timedelta


def seed():
          with app.app_context():
                        db.create_all()

              # Admin User
                        if not Admin.query.filter_by(username='admin').first():
                                          admin = Admin(
                                                                username='admin',
                                                                email='admin@mulberryscootertours.com',
                                                                full_name='Carter (Owner)',
                                                                role='admin'
                                          )
                                          admin.set_password('MSTadmin2026!')
                                          db.session.add(admin)
                                          print('Admin user created')

                        # Guides
                        guides_data = [
                            {'name': 'Alex Rivera', 'email': 'alex@mulberryscootertours.com', 'phone': '(706) 555-0101', 'bio': 'Born and raised in Mulberry.'},
                            {'name': 'Jordan Lee', 'email': 'jordan@mulberryscootertours.com', 'phone': '(706) 555-0102', 'bio': 'Outdoor enthusiast and certified safety instructor.'},
                        ]
                        for g in guides_data:
                                          if not Guide.query.filter_by(email=g['email']).first():
                                                                db.session.add(Guide(**g, is_active=True, max_group_size=6))
                                                        print('Guides seeded')

                        # Scooters (10-unit fleet)
                        for i in range(1, 11):
                                          sid = f'MST-{i:03d}'
                                          if not Scooter.query.filter_by(scooter_id=sid).first():
                                                                db.session.add(Scooter(
                                                                                          name=f'Scooter {i}',
                                                                                          scooter_id=sid,
                                                                                          model='Standard E-Scooter',
                                                                                          status='available'
                                                                ))
                                                        print('10 scooters added to fleet')

                        # Tours
                        tours_data = [
                            {
                                'name': 'Downtown Discovery',
                                'slug': 'downtown-discovery',
                                'description': 'Cruise through the heart of Mulberry on this beginner-friendly tour.',
                                'short_description': 'A relaxed cruise through historic downtown Mulberry.',
                                'duration_minutes': 60,
                                'price_cents': 3500,
                                'max_riders': 6,
                                'difficulty': 'easy',
                                'distance_miles': 4.0,
                                'highlights': 'Historic Main Street, Mulberry Town Square, Local art murals',
                                'what_to_bring': 'Comfortable closed-toe shoes, sunscreen, water bottle.',
                                'meeting_point': 'Mulberry Town Square, Main Street, Mulberry, GA 30260',
                                'is_active': True,
                                'is_featured': True,
                            },
                            {
                                'name': 'Scenic Countryside Cruise',
                                'slug': 'scenic-countryside-cruise',
                                'description': 'Escape the town center and explore the beautiful countryside.',
                                'short_description': 'Rolling fields, quiet backroads, and stunning rural Georgia views.',
                                'duration_minutes': 90,
                                'price_cents': 4900,
                                'max_riders': 6,
                                'difficulty': 'moderate',
                                'distance_miles': 7.5,
                                'highlights': 'Countryside backroads, Rolling farmland views, Wildlife spotting',
                                'what_to_bring': 'Comfortable shoes, layers for weather, water bottle, camera.',
                                'meeting_point': 'Mulberry Town Square, Main Street, Mulberry, GA 30260',
                                'is_active': True,
                                'is_featured': True,
                            },
                            {
                                'name': 'Sunset and Sights Tour',
                                'slug': 'sunset-and-sights-tour',
                                'description': 'Our most popular tour! Time your ride to catch the golden hour.',
                                'short_description': 'Catch golden hour on our most scenic route.',
                                'duration_minutes': 120,
                                'price_cents': 5900,
                                'max_riders': 6,
                                'difficulty': 'moderate',
                                'distance_miles': 10.0,
                                'highlights': 'Golden hour photography, Best of downtown and countryside, Scenic overlook',
                                'what_to_bring': 'Camera/phone, layers, closed-toe shoes, water.',
                                'meeting_point': 'Mulberry Town Square, Main Street, Mulberry, GA 30260',
                                'is_active': True,
                                'is_featured': True,
                            },
                        ]
                        for t in tours_data:
                                          if not Tour.query.filter_by(slug=t['slug']).first():
                                                                db.session.add(Tour(**t))
                                                        print('3 tours created')

                        db.session.commit()

              # Time Slots (next 14 days)
                        tours = Tour.query.filter_by(is_active=True).all()
        guides = Guide.query.filter_by(is_active=True).all()
        today = date.today()
        slot_count = 0

        time_options = {
                          60: [time(9, 0), time(11, 0), time(14, 0), time(16, 0)],
                          90: [time(9, 0), time(11, 0), time(14, 0)],
                          120: [time(16, 0), time(17, 0)],
        }

        for tour in tours:
                          times = time_options.get(tour.duration_minutes, [time(10, 0)])
                          for day_offset in range(1, 15):
                                                slot_date = today + timedelta(days=day_offset)
                                                existing = TimeSlot.query.filter_by(tour_id=tour.id, slot_date=slot_date).first()
                                                if existing:
                                                                          continue
                                                                      for i, start_t in enumerate(times):
                                                                                                end_minutes = start_t.hour * 60 + start_t.minute + tour.duration_minutes
                                                                                                end_t = time(end_minutes // 60, end_minutes % 60)
                                                                                                guide = guides[i % len(guides)] if guides else None
                                                                                                slot = TimeSlot(
                                                                                                    tour_id=tour.id,
                                                                                                    guide_id=guide.id if guide else None,
                                                                                                    slot_date=slot_date,
                                                                                                    start_time=start_t,
                                                                                                    end_time=end_t,
                                                                                                    max_riders=tour.max_riders
                                                                                                )
                                                                                                db.session.add(slot)
                                                                                                slot_count += 1

                                        db.session.commit()
        print(f'{slot_count} time slots generated')

        # Waiver Template
        if not WaiverTemplate.query.filter_by(is_active=True).first():
                          db.session.add(WaiverTemplate(
                              title='Standard Liability Waiver',
                              content='Built-in waiver template',
                              version='1.0',
                              is_active=True
        ))
            db.session.commit()
            print('Waiver template created')

        print('Database seeded successfully!')
        print('Admin login: admin / MSTadmin2026!')


if __name__ == '__main__':
          seed()
