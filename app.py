from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from bson.objectid import ObjectId
from datetime import datetime, timedelta, date
import pytz
import io
import pandas as pd
import math
import os
import random
import json

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

if not app.config.get("MONGO_URI"):
    raise RuntimeError("MONGO_URI not set in .env (see README)")

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'info.loginpanel@gmail.com'
app.config['MAIL_PASSWORD'] = 'wedbfepklgtwtugf'
app.config['MAIL_DEFAULT_SENDER'] = 'info.loginpanel@gmail.com'

mongo = PyMongo(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
mail = Mail(app)

# JAIN Head Office coordinates
OFFICE_LAT = 12.9248224
OFFICE_LNG = 77.5702351
ALLOWED_RADIUS_KM = 50

# IST Timezone
IST = pytz.timezone('Asia/Kolkata')

# Motivational Quotes
MOTIVATIONAL_QUOTES = [
    "Success is the sum of small efforts repeated day in and day out.",
    "The only way to do great work is to love what you do.",
    "Believe you can and you're halfway there.",
    "Your limitation—it's only your imagination.",
    "Great things never come from comfort zones.",
    "Dream it. Wish it. Do it.",
    "Success doesn't just find you. You have to go out and get it.",
    "The harder you work for something, the greater you'll feel when you achieve it.",
    "Don't stop when you're tired. Stop when you're done.",
    "Wake up with determination. Go to bed with satisfaction."
]

# University Holidays 2026 – JAIN (Deemed-to-be University)

UNIVERSITY_HOLIDAYS_2026 = {

    # General Government / University Holidays
    "2026-01-15": {"name": "Uttarayana Punyakala / Makara Sankranti", "type": "general"},
    "2026-01-26": {"name": "Republic Day", "type": "general"},
    "2026-03-19": {"name": "Chandramana Ugadi", "type": "general"},
    "2026-03-21": {"name": "Khutub-E-Ramzan", "type": "general"},
    "2026-03-31": {"name": "Mahaveera Jayanthi", "type": "general"},
    "2026-04-03": {"name": "Good Friday", "type": "general"},
    "2026-04-14": {"name": "Dr. B. R. Ambedkar Jayanthi", "type": "general"},
    "2026-04-20": {"name": "Basava Jayanthi / Akshaya Tritiya", "type": "general"},
    "2026-05-01": {"name": "Labour Day / May Day", "type": "general"},
    "2026-05-28": {"name": "Bakrid (Eid al-Adha)", "type": "general"},
    "2026-06-26": {"name": "Ashura (10th Day of Muharram)", "type": "general"},
    "2026-08-15": {"name": "Independence Day", "type": "general"},
    "2026-08-26": {"name": "Eid-e-Milad", "type": "general"},
    "2026-09-14": {"name": "Swarnagowri Vrata / Varasiddhi Vinayaka Vrata", "type": "general"},
    "2026-10-02": {"name": "Gandhi Jayanthi", "type": "general"},
    "2026-10-10": {"name": "Mahalaya Amavasye", "type": "general"},
    "2026-10-20": {"name": "Maha Navami / Ayudha Pooja", "type": "general"},
    "2026-10-21": {"name": "Vijayadashami", "type": "general"},
    "2026-11-10": {"name": "Balipadyami / Deepavali", "type": "general"},
    "2026-11-27": {"name": "Kanakadasa Jayanthi", "type": "general"},
    "2026-12-25": {"name": "Christmas", "type": "general"},

    # Restricted Holiday
    "2026-08-21": {"name": "Varamahalakshmi Vrata", "type": "restricted"},

    # Special Holidays (University following Government Holiday)
    "2026-01-16": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-03-20": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-04-04": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-05-02": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-06-27": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-08-22": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-10-19": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-11-09": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},

    # University-Declared Saturday Holidays
    "2026-01-24": {"name": "4th Saturday Holiday", "type": "saturday"},
    "2026-02-21": {"name": "3rd Saturday Holiday", "type": "saturday"},
    "2026-04-04": {"name": "1st Saturday Holiday", "type": "saturday"},
    "2026-05-02": {"name": "1st Saturday Holiday", "type": "saturday"},
    "2026-06-27": {"name": "4th Saturday Holiday", "type": "saturday"},
    "2026-07-18": {"name": "3rd Saturday Holiday", "type": "saturday"},
    "2026-08-22": {"name": "4th Saturday Holiday", "type": "saturday"},
    "2026-09-19": {"name": "3rd Saturday Holiday", "type": "saturday"},
    "2026-12-19": {"name": "3rd Saturday Holiday", "type": "saturday"},
}


# User model for Flask-Login
class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc["_id"])
        self.username = user_doc["username"]
        self.role = user_doc.get("role", "intern")
        self.email = user_doc.get("email")

@login_manager.user_loader
def load_user(user_id):
    doc = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if doc:
        return User(doc)
    return None

# Utility functions
def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)

def utc_to_ist(utc_dt):
    """Convert UTC datetime to IST"""
    if utc_dt is None:
        return None
    if isinstance(utc_dt, str):
        try:
            utc_dt = datetime.fromisoformat(utc_dt.replace('Z', '+00:00'))
        except:
            return None
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    return utc_dt.astimezone(IST)

def format_ist_time(dt, format_str="%I:%M %p"):
    """Format IST datetime to string"""
    if dt is None:
        return None
    ist_dt = utc_to_ist(dt)
    if ist_dt is None:
        return None
    return ist_dt.strftime(format_str)

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in kilometers"""
    R = 6371.0  # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def ensure_admin():
    """Check if current user is admin"""
    if not current_user.is_authenticated or current_user.role != "admin":
        flash("Admin access required", "danger")
        return False
    return True

def serialize_attendance(rec):
    """Convert attendance record to serializable format"""
    if not rec:
        return None
    out = {
        "id": str(rec.get("_id")),
        "user_id": str(rec.get("user_id")) if rec.get("user_id") else None,
        "username": rec.get("username"),
        "date": rec.get("date")
    }
    lt = rec.get("login_time")
    out["login_time"] = format_ist_time(lt, "%Y-%m-%d %I:%M:%S %p") if lt else None
    lot = rec.get("logout_time")
    out["logout_time"] = format_ist_time(lot, "%Y-%m-%d %I:%M:%S %p") if lot else None
    out["hours"] = rec.get("hours")
    out["login_location"] = rec.get("login_location")
    out["logout_location"] = rec.get("logout_location")
    return out

def send_login_email(user_email, username, login_time_str):
    """Send email notification on login"""
    try:
        quote = random.choice(MOTIVATIONAL_QUOTES)
        msg = Message(
            subject=f"✅ Login Successful - {username}",
            recipients=[user_email]
        )
        
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f7; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #0071e3; margin: 0;">🎉 Login Successful!</h1>
                    </div>
                    
                    <div style="background: #f0f8ff; border-left: 4px solid #0071e3; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <p style="margin: 0; color: #333; font-size: 16px;">
                            <strong>Hello {username},</strong>
                        </p>
                        <p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">
                            You have successfully logged in to the attendance system.
                        </p>
                    </div>
                    
                    <div style="background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="color: #333; margin-top: 0;">📋 Login Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 10px 0; color: #666;">
                                    <strong>Username:</strong>
                                </td>
                                <td style="padding: 10px 0; color: #333; text-align: right;">
                                    {username}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #666; border-top: 1px solid #f0f0f0;">
                                    <strong>Login Time (IST):</strong>
                                </td>
                                <td style="padding: 10px 0; color: #0071e3; text-align: right; border-top: 1px solid #f0f0f0;">
                                    <strong>{login_time_str}</strong>
                                </td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <p style="color: white; font-size: 16px; font-style: italic; margin: 0; text-align: center;">
                            "{quote}"
                        </p>
                    </div>
                    
                    <div style="text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                        <p style="margin: 0;">JAIN University - Intern Attendance System</p>
                        <p style="margin: 5px 0 0 0;">This is an automated email. Please do not reply.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        mail.send(msg)
        print(f"Login email sent successfully to {user_email}")
        return True
    except Exception as e:
        print(f"Failed to send login email: {e}")
        return False

def send_logout_email(user_email, username, login_time_str, logout_time_str, hours_worked):
    """Send email notification on logout with working duration"""
    try:
        quote = random.choice(MOTIVATIONAL_QUOTES)
        msg = Message(
            subject=f"👋 Logout Successful - {username}",
            recipients=[user_email]
        )
        
        # Calculate hours and minutes
        hours = int(hours_worked)
        minutes = int((hours_worked - hours) * 60)
        
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f7; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #34c759; margin: 0;">✅ Great Work Today!</h1>
                    </div>
                    
                    <div style="background: #f0fff4; border-left: 4px solid #34c759; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <p style="margin: 0; color: #333; font-size: 16px;">
                            <strong>Hello {username},</strong>
                        </p>
                        <p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">
                            You have successfully logged out. Here's your work summary for today.
                        </p>
                    </div>
                    
                    <div style="background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="color: #333; margin-top: 0;">📊 Today's Work Summary</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 10px 0; color: #666;">
                                    <strong>Username:</strong>
                                </td>
                                <td style="padding: 10px 0; color: #333; text-align: right;">
                                    {username}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #666; border-top: 1px solid #f0f0f0;">
                                    <strong>Login Time (IST):</strong>
                                </td>
                                <td style="padding: 10px 0; color: #0071e3; text-align: right; border-top: 1px solid #f0f0f0;">
                                    {login_time_str}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #666; border-top: 1px solid #f0f0f0;">
                                    <strong>Logout Time (IST):</strong>
                                </td>
                                <td style="padding: 10px 0; color: #34c759; text-align: right; border-top: 1px solid #f0f0f0;">
                                    {logout_time_str}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #666; border-top: 1px solid #f0f0f0;">
                                    <strong>Working Duration:</strong>
                                </td>
                                <td style="padding: 10px 0; text-align: right; border-top: 1px solid #f0f0f0;">
                                    <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 16px;">
                                        {hours}h {minutes}m
                                    </span>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #666; border-top: 1px solid #f0f0f0;">
                                    <strong>Total Hours:</strong>
                                </td>
                                <td style="padding: 10px 0; color: #333; text-align: right; border-top: 1px solid #f0f0f0; font-size: 18px;">
                                    <strong>{hours_worked:.2f} hours</strong>
                                </td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <p style="color: white; font-size: 16px; font-style: italic; margin: 0; text-align: center;">
                            "{quote}"
                        </p>
                    </div>
                    
                    <div style="background: #fff9e6; border: 1px solid #ffd700; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
                        <p style="margin: 0; color: #333; font-size: 14px;">
                            <strong>🌟 Keep up the excellent work!</strong>
                        </p>
                    </div>
                    
                    <div style="text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                        <p style="margin: 0;">JAIN University - Intern Attendance System</p>
                        <p style="margin: 5px 0 0 0;">This is an automated email. Please do not reply.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        mail.send(msg)
        print(f"Logout email sent successfully to {user_email}")
        return True
    except Exception as e:
        print(f"Failed to send logout email: {e}")
        return False

# Routes: Authentication
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("user_dashboard") if current_user.role == "intern" else url_for("admin_dashboard"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form.get("role", "intern")
        email = request.form.get("email", "")
        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists", "danger")
            return redirect(url_for("register"))
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        mongo.db.users.insert_one({
            "username": username,
            "password": hashed,
            "role": role,
            "email": email,
            "created_at": datetime.utcnow()
        })
        flash("Registered! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = mongo.db.users.find_one({"username": username})
        if not user:
            flash("No such user", "danger")
            return redirect(url_for("login"))
        if bcrypt.check_password_hash(user["password"], password):
            user_obj = User(user)
            login_user(user_obj)
            flash("Logged in", "success")
            return redirect(url_for("user_dashboard") if user_obj.role == "intern" else url_for("admin_dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("login"))

# Attendance endpoints
def _get_lat_lng_from_request():
    lat = lng = None
    if request.is_json:
        j = request.get_json(silent=True) or {}
        lat = j.get("lat")
        lng = j.get("lng")
    if lat is None:
        lat = request.form.get("lat") or request.args.get("lat")
    if lng is None:
        lng = request.form.get("lng") or request.args.get("lng")
    try:
        if lat is not None:
            lat = float(lat)
        if lng is not None:
            lng = float(lng)
    except (ValueError, TypeError):
        lat = lng = None
    return lat, lng

@app.route("/attendance/login", methods=["POST"])
@login_required
def attendance_login():
    if current_user.role != "intern":
        return jsonify({"error":"Only interns can record attendance"}), 403

    lat, lng = _get_lat_lng_from_request()
    if lat is None or lng is None:
        return jsonify({"error":"Location required (allow browser geolocation)."}), 400

    dist = haversine_km(lat, lng, OFFICE_LAT, OFFICE_LNG)
    if dist > ALLOWED_RADIUS_KM:
        return jsonify({"error":"Not within office radius", "distance_km": round(dist,4)}), 403

    ist_now = get_ist_now()
    today = ist_now.date().isoformat()
    
    rec = mongo.db.attendance.find_one({"user_id": ObjectId(current_user.id), "date": today, "logout_time": {"$exists": False}})
    if rec:
        return jsonify({"error":"Already logged in and not logged out yet."}), 400

    now_utc = datetime.utcnow()
    mongo.db.attendance.insert_one({
        "user_id": ObjectId(current_user.id),
        "username": current_user.username,
        "date": today,
        "login_time": now_utc,
        "login_location": {"lat": lat, "lng": lng},
        "created_at": now_utc
    })
    
    # Send login email
    login_time_str = format_ist_time(now_utc, "%Y-%m-%d %I:%M:%S %p")
    if current_user.email:
        send_login_email(current_user.email, current_user.username, login_time_str)
    
    return jsonify({"ok": True, "login_time": format_ist_time(now_utc)})

@app.route("/attendance/logout", methods=["POST"])
@login_required
def attendance_logout():
    if current_user.role != "intern":
        return jsonify({"error":"Only interns can record attendance"}), 403

    lat, lng = _get_lat_lng_from_request()
    
    ist_now = get_ist_now()
    today = ist_now.date().isoformat()
    
    rec = mongo.db.attendance.find_one({"user_id": ObjectId(current_user.id), "date": today, "logout_time": {"$exists": False}})
    if not rec:
        return jsonify({"error":"No active login found for today"}), 400

    logout_time = datetime.utcnow()
    login_time = rec.get("login_time")
    
    if isinstance(login_time, datetime):
        duration = (logout_time - login_time).total_seconds() / 3600.0
    else:
        try:
            parsed = datetime.fromisoformat(login_time) if isinstance(login_time, str) else None
            duration = (logout_time - parsed).total_seconds() / 3600.0 if parsed else None
        except Exception:
            duration = None

    updates = {"logout_time": logout_time, "hours": round(duration, 4) if duration is not None else None}
    if lat is not None and lng is not None:
        updates["logout_location"] = {"lat": lat, "lng": lng}

    mongo.db.attendance.update_one({"_id": rec["_id"]}, {"$set": updates})
    
    # Send logout email with work summary
    if current_user.email and duration is not None:
        login_time_str = format_ist_time(login_time, "%Y-%m-%d %I:%M:%S %p")
        logout_time_str = format_ist_time(logout_time, "%Y-%m-%d %I:%M:%S %p")
        send_logout_email(current_user.email, current_user.username, login_time_str, logout_time_str, duration)
    
    return jsonify({"ok": True, "logout_time": format_ist_time(logout_time), "hours": updates["hours"]})

# API endpoint for dashboard data
@app.route("/api/dashboard-data")
@login_required
def get_dashboard_data():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access this dashboard"}), 403
    
    try:
        ist_now = get_ist_now()
        today = ist_now.date().isoformat()
        
        today_record = mongo.db.attendance.find_one({
            "user_id": ObjectId(current_user.id), 
            "date": today
        })
        
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        all_records = list(mongo.db.attendance.find({
            "user_id": ObjectId(current_user.id),
            "date": {"$gte": cutoff}
        }).sort("date", -1))
        
        total_hours = sum([r.get("hours", 0) or 0 for r in all_records])
        
        today_data = None
        if today_record:
            login_time = today_record.get("login_time")
            logout_time = today_record.get("logout_time")
            
            today_data = {
                "login_time": format_ist_time(login_time),
                "logout_time": format_ist_time(logout_time),
                "hours": str(round(today_record.get("hours", 0) or 0, 1))
            }
        
        all_formatted = []
        for rec in all_records:
            login_time = rec.get("login_time")
            logout_time = rec.get("logout_time")
            
            all_formatted.append({
                "date": rec.get("date", "N/A"),
                "login_time": format_ist_time(login_time) if login_time else "N/A",
                "logout_time": format_ist_time(logout_time) if logout_time else "N/A",
                "hours": str(round(rec.get("hours", 0) or 0, 1)) if rec.get("hours") else "N/A"
            })
        
        return jsonify({
            "username": current_user.username,
            "today_record": today_data,
            "total_hours": f"{total_hours:.1f}",
            "office_address": "JAIN University Head Office, Bengaluru",
            "office_lat": OFFICE_LAT,
            "office_lng": OFFICE_LNG,
            "allowed_radius_km": ALLOWED_RADIUS_KM,
            "allowed_radius_m": ALLOWED_RADIUS_KM * 1000,
            "history": all_formatted
        })
        
    except Exception as e:
        print(f"Error in dashboard data API: {e}")
        return jsonify({"error": str(e)}), 500

# Leave Management API
@app.route("/api/leave", methods=["POST"])
@login_required
def save_leave():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can save leave"}), 403
    
    try:
        data = request.get_json()
        leave_date = data.get("date")
        leave_type = data.get("type")
        comments = data.get("comments", "")
        
        if not leave_date or not leave_type:
            return jsonify({"error": "Date and type are required"}), 400
        
        mongo.db.leaves.update_one(
            {
                "user_id": ObjectId(current_user.id),
                "date": leave_date
            },
            {
                "$set": {
                    "user_id": ObjectId(current_user.id),
                    "username": current_user.username,
                    "date": leave_date,
                    "type": leave_type,
                    "comments": comments,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return jsonify({"ok": True, "message": "Leave saved successfully"})
        
    except Exception as e:
        print(f"Error saving leave: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/leaves", methods=["GET"])
@login_required
def get_all_leaves():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access leave data"}), 403
    
    try:
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        leaves = list(mongo.db.leaves.find({
            "user_id": ObjectId(current_user.id),
            "date": {"$gte": cutoff}
        }))
        
        result = {}
        for leave in leaves:
            result[leave["date"]] = {
                "type": leave.get("type"),
                "comments": leave.get("comments", "")
            }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error fetching leaves: {e}")
        return jsonify({"error": str(e)}), 500

# Holidays API
@app.route("/api/holidays")
def get_holidays():
    """Get holidays for a specific year and month"""
    try:
        year = request.args.get('year', type=int, default=2026)
        month = request.args.get('month', type=int, default=None)
        
        filtered_holidays = {}
        for date_str, info in UNIVERSITY_HOLIDAYS_2026.items():
            holiday_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if holiday_date.year != year:
                continue
                
            if month and holiday_date.month != month:
                continue
            
            # Format holiday info
            filtered_holidays[date_str] = {
                "name": info["name"],
                "type": info["type"],
                "day": holiday_date.strftime("%A"),
                "month": holiday_date.strftime("%B"),
                "date": date_str
            }
        
        return jsonify({
            "holidays": filtered_holidays,
            "total": len(filtered_holidays),
            "year": year,
            "month": month
        })
        
    except Exception as e:
        print(f"Error fetching holidays: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/holidays/current-month")
def get_current_month_holidays():
    """Get holidays for the current month"""
    try:
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        # If we're in 2025, show 2026 holidays for testing
        if current_year < 2026:
            current_year = 2026
        
        holidays_list = []
        for date_str, info in UNIVERSITY_HOLIDAYS_2026.items():
            holiday_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if holiday_date.year == current_year and holiday_date.month == current_month:
                holidays_list.append({
                    "date": date_str,
                    "name": info["name"],
                    "type": info["type"],
                    "day": holiday_date.strftime("%A"),
                    "month": holiday_date.strftime("%B")
                })
        
        # Sort by date
        holidays_list.sort(key=lambda x: x["date"])
        
        return jsonify({
            "holidays": holidays_list,
            "total_count": len(holidays_list),
            "month": datetime(current_year, current_month, 1).strftime("%B %Y"),
            "year": current_year
        })
        
    except Exception as e:
        print(f"Error fetching current month holidays: {e}")
        return jsonify({"error": str(e)}), 500

# User Statistics API
@app.route("/api/admin/user-stats/<user_id>")
@login_required
def get_user_stats(user_id):
    if not ensure_admin():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        today = date.today()
        first_day = date(today.year, today.month, 1)
        if today.month == 12:
            last_day = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)
        
        attendance_count = mongo.db.attendance.count_documents({
            "user_id": ObjectId(user_id),
            "date": {"$gte": first_day.isoformat(), "$lte": last_day.isoformat()}
        })
        
        leaves_count = mongo.db.leaves.count_documents({
            "user_id": ObjectId(user_id),
            "date": {"$gte": first_day.isoformat(), "$lte": last_day.isoformat()}
        })
        
        total_working_days = mongo.db.attendance.count_documents({
            "user_id": ObjectId(user_id)
        })
        
        return jsonify({
            "username": user["username"],
            "email": user.get("email", "N/A"),
            "attendance_this_month": attendance_count,
            "leaves_this_month": leaves_count,
            "total_working_days": total_working_days
        })
        
    except Exception as e:
        print(f"Error fetching user stats: {e}")
        return jsonify({"error": str(e)}), 500

# ADMIN CALENDAR API
@app.route("/api/admin/calendar-data")
@login_required
def get_admin_calendar_data():
    if not ensure_admin():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        user_ids = request.args.getlist('users')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date:
            start_date = (date.today() - timedelta(days=90)).isoformat()
        if not end_date:
            end_date = date.today().isoformat()
        
        query = {"date": {"$gte": start_date, "$lte": end_date}}
        
        if user_ids and 'all' not in user_ids:
            query["user_id"] = {"$in": [ObjectId(uid) for uid in user_ids if uid]}
        
        attendance = list(mongo.db.attendance.find(query))
        leaves = list(mongo.db.leaves.find(query))
        
        calendar_data = {}
        
        for rec in attendance:
            username = rec.get("username")
            date_str = rec.get("date")
            
            if username not in calendar_data:
                calendar_data[username] = {}
            
            login_time = rec.get("login_time")
            logout_time = rec.get("logout_time")
            
            calendar_data[username][date_str] = {
                "type": "present",
                "login_time": format_ist_time(login_time) if login_time else "N/A",
                "logout_time": format_ist_time(logout_time) if logout_time else "N/A",
                "hours": round(rec.get("hours", 0) or 0, 1)
            }
        
        for leave in leaves:
            username = leave.get("username")
            date_str = leave.get("date")
            
            if username not in calendar_data:
                calendar_data[username] = {}
            
            calendar_data[username][date_str] = {
                "type": "leave",
                "leave_type": leave.get("type"),
                "comments": leave.get("comments", "")
            }
        
        return jsonify({
            "calendar_data": calendar_data,
            "start_date": start_date,
            "end_date": end_date
        })
        
    except Exception as e:
        print(f"Error in admin calendar API: {e}")
        return jsonify({"error": str(e)}), 500

# Dashboards
@app.route("/user/dashboard")
@login_required
def user_dashboard():
    if current_user.role != "intern":
        return redirect(url_for("admin_dashboard"))
    return render_template("user_dashboard.html")

@app.route("/history")
@login_required
def attendance_history():
    if current_user.role != "intern":
        return redirect(url_for("admin_dashboard"))
    raw_history = list(mongo.db.attendance.find({"user_id": ObjectId(current_user.id)}).sort("date", -1))
    history = [serialize_attendance(r) for r in raw_history]
    return render_template("attendance_history.html", history=history)

# Notifications
@app.route("/admin/notifications", methods=["GET","POST"])
@login_required
def admin_notifications():
    if not ensure_admin():
        return redirect(url_for("user_dashboard"))
    if request.method == "POST":
        to_user = request.form.get("to_user")
        message = request.form.get("message")
        mongo.db.notifications.insert_one({
            "sender": current_user.username,
            "to_user": to_user,
            "message": message,
            "timestamp": datetime.utcnow(),
            "replies": []
        })
        flash("Notification sent", "success")
        return redirect(url_for("admin_notifications"))
    notifications = list(mongo.db.notifications.find().sort("timestamp", -1))
    users = list(mongo.db.users.find())
    return render_template("notifications.html", notifications=notifications, users=users)

@app.route("/notifications")
@login_required
def view_notifications():
    notifs = list(mongo.db.notifications.find({"$or":[{"to_user":"all"}, {"to_user": current_user.id}, {"to_user": current_user.username}] }).sort("timestamp", -1))
    return render_template("notifications.html", notifications=notifs, users=[])

@app.route("/notifications/<nid>/reply", methods=["POST"])
@login_required
def reply_notification(nid):
    text = request.form.get("reply_text")
    reply = {"user_id": current_user.id, "username": current_user.username, "text": text, "timestamp": datetime.utcnow()}
    mongo.db.notifications.update_one({"_id": ObjectId(nid)}, {"$push": {"replies": reply}})
    flash("Reply sent", "success")
    return redirect(url_for("view_notifications") if current_user.role=="intern" else url_for("admin_notifications"))

# Admin dashboard
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not ensure_admin():
        return redirect(url_for("user_dashboard"))
    
    users_raw = list(mongo.db.users.find())
    users = []
    for user in users_raw:
        user['_id'] = str(user['_id'])
        users.append(user)
    
    recent = list(mongo.db.attendance.find().sort("date", -1).limit(100))
    recent_serialized = [serialize_attendance(r) for r in recent]
    
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    leaves = list(mongo.db.leaves.find({"date": {"$gte": cutoff}}).sort("date", -1))
    
    leaves_data = []
    for leave in leaves:
        leaves_data.append({
            "username": leave.get("username"),
            "date": leave.get("date"),
            "type": leave.get("type"),
            "comments": leave.get("comments", ""),
            "updated_at": leave.get("updated_at")
        })
    
    return render_template("admin_dashboard.html", 
                         users=users, 
                         recent=recent_serialized,
                         leaves=leaves_data)

@app.route("/admin/export", methods=["GET"])
@login_required
def admin_export():
    if not ensure_admin():
        return redirect(url_for("admin_dashboard"))
    start = request.args.get("start")
    end = request.args.get("end")
    if not start:
        start = (date.today() - timedelta(days=30)).isoformat()
    if not end:
        end = date.today().isoformat()
    recs = list(mongo.db.attendance.find({"date": {"$gte": start, "$lte": end}}).sort([("date",1), ("username",1)]))
    rows = []
    for r in recs:
        lt = r.get("login_time")
        lot = r.get("logout_time")
        rows.append({
            "username": r.get("username"),
            "date": r.get("date"),
            "login_time": format_ist_time(lt, "%Y-%m-%d %I:%M:%S %p") if lt else "",
            "logout_time": format_ist_time(lot, "%Y-%m-%d %I:%M:%S %p") if lot else "",
            "hours": r.get("hours", 0) or 0
        })
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    mem = io.BytesIO()
    mem.write(buf.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"attendance_{start}_to_{end}.csv"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/csv")

# Admin: create user
@app.route("/admin/create_user", methods=["POST"])
@login_required
def admin_create_user():
    if not ensure_admin():
        return redirect(url_for("user_dashboard"))
    username = request.form.get("username").strip()
    password = request.form.get("password")
    role = request.form.get("role", "intern")
    email = request.form.get("email", "")
    if mongo.db.users.find_one({"username": username}):
        flash("User exists", "danger")
        return redirect(url_for("admin_dashboard"))
    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    mongo.db.users.insert_one({"username": username, "password": hashed, "role": role, "email": email, "created_at": datetime.utcnow()})
    flash("User created", "success")
    return redirect(url_for("admin_dashboard"))

# Delete user
@app.route("/admin/delete_user/<user_id>", methods=["POST"])
@login_required
def admin_delete_user(user_id):
    if not ensure_admin():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        if str(user_id) == str(current_user.id):
            return jsonify({"error": "Cannot delete your own account"}), 400
        
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        mongo.db.attendance.delete_many({"user_id": ObjectId(user_id)})
        mongo.db.leaves.delete_many({"user_id": ObjectId(user_id)})
        
        return jsonify({"ok": True, "message": f"User {user['username']} deleted successfully"})
        
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"error": str(e)}), 500

# Health endpoint
@app.route("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)