# Mulberry E-Scooter Tours — Training Manual

## Welcome!

This manual covers everything you need to run your booking website day-to-day. Whether you're managing tours, handling bookings, or updating your fleet — it's all here.

---

## Table of Contents

1. [Logging Into Admin](#1-logging-into-admin)
2. [Dashboard Overview](#2-dashboard-overview)
3. [Managing Tours](#3-managing-tours)
4. [Managing Time Slots](#4-managing-time-slots)
5. [Managing Bookings](#5-managing-bookings)
6. [Processing Refunds](#6-processing-refunds)
7. [Fleet Management (Scooters)](#7-fleet-management)
8. [Managing Guides](#8-managing-guides)
9. [Contact Messages](#9-contact-messages)
10. [Reports & Exports](#10-reports--exports)
11. [Understanding the Customer Experience](#11-customer-experience)
12. [Embedding the Booking Widget](#12-booking-widget)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Logging Into Admin

1. Go to `yourdomain.com/admin`
2. Enter your username and password
3. Click **Sign In**

**Default credentials (change after first login):**
- Username: `admin`
- Password: `MSTadmin2026!`

> ⚠️ Change your password immediately after your first login for security.

---

## 2. Dashboard Overview

Your dashboard is your command center. At a glance, you'll see:

| Metric | What It Shows |
|--------|--------------|
| Today's Bookings | Number of confirmed bookings for today |
| Total Bookings | All-time confirmed booking count |
| Revenue Today | Total revenue from today's bookings |
| Revenue This Month | Month-to-date revenue |
| Active Scooters | Available scooters vs. total fleet |
| Upcoming Slots | Open time slots in the future |
| Pending Waivers | Confirmed bookings without signed waivers |
| Unread Messages | Contact form messages you haven't read |

Below the stats, you'll see:
- **Upcoming Tours** — Next 10 scheduled time slots with booking status
- **Recent Bookings** — Last 10 bookings with quick status view

---

## 3. Managing Tours

### Viewing Tours
Navigate to **Tours** in the sidebar. You'll see all tours with their price, duration, difficulty, and status.

### Creating a New Tour
1. Click **New Tour**
2. Fill in the details:
   - **Tour Name** — e.g., "Downtown Discovery"
   - **Short Description** — Shows on tour cards (max 250 chars)
   - **Full Description** — Detailed description for the tour page
   - **Duration** — In minutes (e.g., 60, 90, 120)
   - **Price per Person** — In dollars (e.g., 35.00)
   - **Max Riders** — Maximum group size (default: 6)
   - **Difficulty** — Easy, Moderate, or Challenging

---

## 4. Managing Time Slots

Time slots are the specific dates and times when tours are available for booking.

### Generating Slots in Bulk
This is the fastest way to set up your schedule:

1. Go to **Time Slots** in the sidebar
2. Under "Generate Time Slots":
   - Select the **Tour**
   - Optionally assign a **Guide**
   - Set the **Start Date** and **End Date**
   - Enter **Start Times** (comma-separated, 24-hour format)
     - Example: `09:00,11:00,14:00,16:00`
3. Click **Generate Slots**

The system automatically calculates end times based on tour duration and won't create duplicate slots.

### Typical Weekly Setup
Run this every week or two to keep your calendar full:
- Set date range for the next 2 weeks
- Use your standard time schedule
- Assign guides as needed

### Cancelling a Slot
Click **Cancel** on any slot. This will:
- Mark the slot as cancelled
- Automatically cancel all bookings for that slot
- Automatically refund all payments via Stripe
- Send cancellation emails to affected customers

> This action cannot be undone. All bookings for this slot will be cancelled and refunded.

---

## 5. Managing Bookings

### Viewing Bookings
Go to **Bookings** in the sidebar. Use the filter buttons to view:
- **All** - Every booking
- **Confirmed** - Paid and ready
- **Pending** - Payment in progress
- **Completed** - Tour finished
- **Cancelled** - Customer or admin cancelled
- **No-Show** - Customer didn't show up

### Booking Detail View
Click any booking reference to see full details:
- Customer info (name, email, phone)
- Tour and time slot info
- Payment status and Stripe details
- Waiver status
- Participant list (for group bookings)
- Special requests

### Updating Booking Status
On the booking detail page, use the **Update Status** form:
- **Confirmed** - Ready to go
- **Completed** - Tour finished (do this after each tour)
- **No-Show** - Customer didn't show up
- **Cancelled** - Cancel the booking

### After Each Tour Day
1. Go to Bookings
2. Filter by "Confirmed"
3. Mark completed tours as **Completed**
4. Mark no-shows as **No-Show**

---

## 6. Processing Refunds

### Full Refund
1. Open the booking detail page
2. In the "Process Refund" section, enter the full booking amount
3. Click **Process Refund**
4. The refund is processed through Stripe immediately
5. The customer receives a refund to their original payment

---

## 7. Fleet Management

### Viewing Your Fleet
Go to **Scooters** in the sidebar to see all scooters with their status.

### Adding a Scooter
1. Click **Add Scooter**
2. Enter:
   - **Scooter ID** - e.g., MST-011
   - **Display Name** - e.g., Scooter 11
   - **Model** - Scooter model name
   - **Status** - Available, Maintenance, or Retired
   - **Notes** - Any relevant notes
3. Click **Add Scooter**

### Status Meanings
| Status | Meaning |
|--------|---------|
| Available | Ready for tours |
| Maintenance | Being repaired/serviced - not available |
| Retired | Permanently out of service |

### Maintenance Workflow
1. Edit the scooter - Set status to **Maintenance**
2. Add notes about the issue
3. When fixed - Set status back to **Available**

Tip: Keep at least 1-2 spare scooters marked as Available beyond your max group size for backup.

---

## 8. Managing Guides

### Adding a Guide
1. Go to **Guides** then **Add Guide**
2. Enter name, email, phone, bio, and max group size
3. Check **Active** to make them assignable
4. Click **Add Guide**

### Assigning Guides to Slots
When generating time slots, select a guide from the dropdown. Guides can also be assigned by generating different batches of slots.

### Deactivating a Guide
Edit the guide and uncheck "Active." They won't be available for new slot assignments but existing assignments remain.

---

## 9. Contact Messages

### Viewing Messages
Go to **Messages** in the sidebar. New messages are highlighted in yellow.

### Managing Messages
- Click **Mark Read** to clear the notification
- The unread count shows on the dashboard
- Reply to customers via your regular email

---

## 10. Reports & Exports

### CSV Export
Go to **Reports** then **Download CSV** to get a spreadsheet of all bookings with:
- Booking reference, customer info, tour, date, time
- Riders, total, payment status, booking status
- Waiver status, creation date

---

## 11. Customer Experience

Here's what your customers see:

### Booking Flow
1. **Browse Tours** - View all tours with prices, duration, difficulty
2. **Select a Tour** - Read full description, highlights, what to bring
3. **Check Availability** - Pick a date, see available time slots
4. **Fill Out Booking Form** - Name, email, phone, number of riders
5. **Pay Securely** - Credit card, Apple Pay, or Google Pay via Stripe
6. **Confirmation** - Success page + confirmation email
7. **Sign Waiver** - Digital waiver with e-signature
8. **Add to Calendar** - Download .ics file for their calendar app

### Customer Self-Service
Customers can manage their own bookings at yourdomain.com/booking/lookup:
- View booking details
- Sign waiver
- Add to calendar
- Cancel booking (24+ hours before tour = full refund)

### Confirmation Email
Automatically sent after payment with:
- Booking reference number
- Tour details and meeting point
- What to bring
- Waiver reminder (if not yet signed)

---

## 12. Booking Widget

You can embed a booking widget on any external website:

Add the following HTML to any page:
- A div with id mst-booking-widget
- Set window.MST_BASE_URL to your domain
- Include the script from yourdomain.com/widget/embed.js

The widget shows a tour selector, date picker, and rider count, then opens your tour page for the full booking flow.

---

## 13. Troubleshooting

### Payment failed errors
- Customer should try a different card
- Check Stripe Dashboard for declined payment details
- Common reasons: insufficient funds, expired card, bank block

### Customer says they didn't receive confirmation email
1. Check the booking in admin - is it status Confirmed?
2. Ask them to check spam/junk folder
3. Verify the email address is correct
4. Check your SMTP settings in the .env file

### Waiver shows Pending but customer says they signed
- The waiver link is specific to each booking
- Have the customer go to yourdomain.com/booking/lookup, enter their reference and email, then click Sign Waiver

### Slot shows full but scooters are available
- Time slots have their own rider limit (usually 6)
- This is separate from physical scooter count
- You can generate additional slots at the same time if you have enough scooters and a second guide

### Can't generate time slots
- Make sure you have at least one Active tour
- Check that start date is in the future
- Verify time format is correct (24-hour: 09:00, not 9:00 AM)

### Need to change a booking's date/time
Currently, you'll need to:
1. Cancel the original booking (process refund)
2. Ask the customer to rebook for the new date/time
3. Or: create a new booking manually via the customer flow

---

## Daily Checklist

- Check dashboard for today's bookings
- Verify all today's riders have signed waivers
- Check scooter availability matches bookings
- Review any new contact messages
- After tours: mark bookings as Completed or No-Show

## Weekly Checklist

- Generate time slots for the coming 2 weeks
- Export booking CSV for records
- Review Stripe dashboard for any payment issues
- Check scooter maintenance needs
- Update tour descriptions if needed

---

*Last updated: April 2026*
*Mulberry E-Scooter Tours - Mulberry, GA*

Open in Excel or Google Sheets for analysis.

### Stripe Dashboard
Click **Open Stripe Dashboard** to access detailed financial reports:
- Payment history and trends
- Refund tracking
- Dispute management
- Tax reports
- Payout schedules method (5-10 business days)

### Partial Refund
Same process, but enter a smaller amount. You can issue multiple partial refunds up to the original total.

### Refund Tracking
- **Paid** - No refunds issued
- **Partial Refund** - Some amount refunded
- **Refunded** - Full amount refunded

All refund history is visible in the Stripe Dashboard for detailed records.
   - **Distance** — In miles
   - **Meeting Point** — Where customers should meet
   - **Highlights** — One per line (shows as a checklist)
   - **What to Bring** — Instructions for customers
3. Check **Active** to make it visible on the website
4. Check **Featured** to highlight it on the homepage
5. Click **Create Tour**

### Editing a Tour
Click **Edit** next to any tour to update its details. Changes take effect immediately.

### Deactivating a Tour
Uncheck "Active" when editing a tour. It will be hidden from the public website but existing bookings won't be affected.
