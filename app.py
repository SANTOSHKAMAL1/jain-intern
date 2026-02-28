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
import requests

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

# Google Maps API Key
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

# Admin email
ADMIN_EMAIL = 'admin@jainuniversity.ac.in'

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

# Working hours configuration
DEFAULT_WORK_HOURS = 8
MIN_WORK_HOURS = 2

# SHIFT_TIMINGS
SHIFT_TIMINGS = {
    "shift1": {"name": "Shift 1", "start": None, "end": None, "hours": 0},
    "shift2": {"name": "Shift 2", "start": None, "end": None, "hours": 0},
    "normal": {"name": "Normal Login", "start": None, "end": None, "hours": 0}
}

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

# University Holidays 2026
UNIVERSITY_HOLIDAYS_2026 = {
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
    "2026-08-21": {"name": "Varamahalakshmi Vrata", "type": "restricted"},
    "2026-01-16": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-03-20": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-04-04": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-05-02": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-06-27": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-08-22": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-10-19": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
    "2026-11-09": {"name": "Special Holiday (Govt. Follow-up)", "type": "special"},
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


# User model
class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc["_id"])
        self.username = user_doc["username"]
        self.role = user_doc.get("role", "intern")
        self.email = user_doc.get("email")
        self.work_hours = user_doc.get("work_hours", DEFAULT_WORK_HOURS)

@login_manager.user_loader
def load_user(user_id):
    doc = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if doc:
        return User(doc)
    return None

# Utility functions
def get_ist_now():
    return datetime.now(IST)

def utc_to_ist(utc_dt):
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
    if dt is None:
        return None
    ist_dt = utc_to_ist(dt)
    if ist_dt is None:
        return None
    return ist_dt.strftime(format_str)

def get_address_from_coords(lat, lng):
    """Get full address from coordinates"""
    if lat is None or lng is None:
        return "Address not available"
    
    if not GOOGLE_MAPS_API_KEY:
        return f"Location: {lat:.6f}, {lng:.6f}"
    
    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == 'OK' and len(data['results']) > 0:
            return data['results'][0].get('formatted_address', f"Lat: {lat:.6f}, Lng: {lng:.6f}")
        
        return f"Lat: {lat:.6f}, Lng: {lng:.6f}"
    except Exception as e:
        print(f"Error getting address: {e}")
        return f"Lat: {lat:.6f}, Lng: {lng:.6f}"

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def calculate_shift_hours(target_hours):
    return target_hours / 2

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
        work_hours = float(request.form.get("work_hours", DEFAULT_WORK_HOURS))
        
        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists", "danger")
            return redirect(url_for("register"))
        
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        mongo.db.users.insert_one({
            "username": username,
            "password": hashed,
            "role": role,
            "email": email,
            "work_hours": work_hours,
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
        return jsonify({"error": "Only interns can record attendance"}), 403

    data = request.get_json() if request.is_json else {}
    lat, lng = _get_lat_lng_from_request()
    
    if lat is None or lng is None:
        return jsonify({"error": "Location required"}), 400

    dist = haversine_km(lat, lng, OFFICE_LAT, OFFICE_LNG)
    if dist > ALLOWED_RADIUS_KM:
        address = get_address_from_coords(lat, lng)
        return jsonify({
            "error": "Not within office radius", 
            "distance_km": round(dist, 4),
            "current_location": {"lat": lat, "lng": lng, "address": address},
            "office_location": {"lat": OFFICE_LAT, "lng": OFFICE_LNG, "address": "JAIN University Head Office"}
        }), 403

    ist_now = get_ist_now()
    today = ist_now.date().isoformat()
    
    login_type = data.get("login_type", "normal")
    shift_type = data.get("shift_type", "normal")
    shift_name = data.get("shift_name", "Normal Login")
    
    user = mongo.db.users.find_one({"_id": ObjectId(current_user.id)})
    work_hours_target = user.get("work_hours", DEFAULT_WORK_HOURS)
    shift_hours = calculate_shift_hours(work_hours_target)
    
    if login_type == "shift":
        existing_shift = mongo.db.attendance.find_one({
            "user_id": ObjectId(current_user.id),
            "date": today,
            "shift_type": shift_type,
            "logout_time": {"$exists": False}
        })
        
        if existing_shift:
            return jsonify({"error": f"You already have an active {shift_name} session"}), 400
        
        session_count = mongo.db.attendance.count_documents({
            "user_id": ObjectId(current_user.id),
            "date": today
        })
        
        session_number = session_count + 1
    else:
        existing = mongo.db.attendance.find_one({
            "user_id": ObjectId(current_user.id),
            "date": today,
            "logout_time": {"$exists": False}
        })
        
        if existing:
            return jsonify({"error": "You're already logged in. Please logout first."}), 400
        
        session_number = 1
    
    now_utc = datetime.utcnow()
    address = get_address_from_coords(lat, lng)
    
    attendance_record = {
        "user_id": ObjectId(current_user.id),
        "username": current_user.username,
        "date": today,
        "login_time": now_utc,
        "login_location": {"lat": lat, "lng": lng, "address": address},
        "login_address": address,
        "created_at": now_utc,
        "login_type": login_type,
        "shift_type": shift_type,
        "shift_name": shift_name,
        "session_number": session_number,
        "work_hours_target": work_hours_target,
        "shift_target_hours": shift_hours
    }
    
    result = mongo.db.attendance.insert_one(attendance_record)
    
    login_time_str = format_ist_time(now_utc, "%Y-%m-%d %I:%M:%S %p")
    
    return jsonify({
        "ok": True, 
        "login_time": format_ist_time(now_utc),
        "login_type": login_type,
        "shift_name": shift_name,
        "session_number": session_number,
        "address": address,
        "shift_target_hours": shift_hours
    })

@app.route("/attendance/logout", methods=["POST"])
@login_required
def attendance_logout():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can record attendance"}), 403

    data = request.get_json() if request.is_json else {}
    lat, lng = _get_lat_lng_from_request()
    force_logout = data.get("force_logout", False)
    
    ist_now = get_ist_now()
    today = ist_now.date().isoformat()
    
    shift_type = data.get("shift_type")
    
    query = {
        "user_id": ObjectId(current_user.id),
        "date": today,
        "logout_time": {"$exists": False}
    }
    
    if shift_type:
        query["shift_type"] = shift_type
    
    rec = mongo.db.attendance.find_one(query)
    
    if not rec:
        rec = mongo.db.attendance.find_one({
            "user_id": ObjectId(current_user.id),
            "date": today,
            "logout_time": {"$exists": False}
        })
        
        if not rec:
            return jsonify({"error": "No active login session found"}), 400

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

    shift_target_hours = rec.get("shift_target_hours", MIN_WORK_HOURS)
    
    if not force_logout and duration is not None and duration < MIN_WORK_HOURS:
        return jsonify({
            "warning": True,
            "message": f"You've only worked {duration:.1f} hours. Minimum recommended is {MIN_WORK_HOURS} hours. Are you sure?",
            "hours_worked": round(duration, 1),
            "min_hours": MIN_WORK_HOURS
        }), 200

    updates = {
        "logout_time": logout_time, 
        "hours": round(duration, 4) if duration is not None else None
    }
    
    if lat is not None and lng is not None:
        address = get_address_from_coords(lat, lng)
        updates["logout_location"] = {"lat": lat, "lng": lng, "address": address}
        updates["logout_address"] = address

    mongo.db.attendance.update_one({"_id": rec["_id"]}, {"$set": updates})
    
    # Calculate total hours for the day
    total_daily_hours = 0
    shift1_hours = 0
    shift2_hours = 0
    
    all_sessions = list(mongo.db.attendance.find({
        "user_id": ObjectId(current_user.id),
        "date": today
    }))
    
    for session in all_sessions:
        hours = session.get("hours", 0) or 0
        total_daily_hours += hours
        
        if session.get("shift_type") == "shift1":
            shift1_hours += hours
        elif session.get("shift_type") == "shift2":
            shift2_hours += hours
    
    target_hours = rec.get("work_hours_target", DEFAULT_WORK_HOURS)
    target_achieved = total_daily_hours >= target_hours
    
    shift_target = target_hours / 2
    shift1_completed = shift1_hours >= shift_target
    shift2_completed = shift2_hours >= shift_target
    
    return jsonify({
        "ok": True, 
        "logout_time": format_ist_time(logout_time), 
        "hours": updates["hours"],
        "total_daily_hours": round(total_daily_hours, 1),
        "target_hours": target_hours,
        "target_achieved": target_achieved,
        "shift1_hours": round(shift1_hours, 1),
        "shift2_hours": round(shift2_hours, 1),
        "shift1_completed": shift1_completed,
        "shift2_completed": shift2_completed,
        "shift_target": round(shift_target, 1),
        "session_type": rec.get("shift_name", "Normal Login"),
        "session_number": rec.get("session_number", 1),
        "shift_target_hours": round(shift_target_hours, 1),
        "can_login_shift1": not shift1_completed,
        "can_login_shift2": not shift2_completed,
        "message": f"Shift 1: {shift1_hours:.1f}/{shift_target:.1f} hrs, Shift 2: {shift2_hours:.1f}/{shift_target:.1f} hrs"
    })

@app.route("/api/dashboard-data")
@login_required
def get_dashboard_data():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access this dashboard"}), 403
    
    try:
        ist_now = get_ist_now()
        today = ist_now.date().isoformat()
        
        today_sessions = list(mongo.db.attendance.find({
            "user_id": ObjectId(current_user.id), 
            "date": today
        }).sort("login_time", 1))
        
        today_data = []
        total_hours_today = 0
        shift1_hours = 0
        shift2_hours = 0
        active_session = None
        
        for session in today_sessions:
            login_time = session.get("login_time")
            logout_time = session.get("logout_time")
            session_hours = session.get("hours", 0) or 0
            total_hours_today += session_hours
            
            if session.get("shift_type") == "shift1":
                shift1_hours += session_hours
            elif session.get("shift_type") == "shift2":
                shift2_hours += session_hours
            
            login_loc = session.get("login_location", {})
            
            session_info = {
                "session_number": session.get("session_number", 1),
                "login_type": session.get("login_type", "normal"),
                "shift_type": session.get("shift_type", "normal"),
                "shift_name": session.get("shift_name", "Normal Login"),
                "login_time": format_ist_time(login_time),
                "logout_time": format_ist_time(logout_time) if logout_time else None,
                "hours": round(session_hours, 1),
                "is_active": logout_time is None,
                "login_address": login_loc.get("address", "Address not available")
            }
            
            if logout_time is None:
                active_session = session_info
            
            today_data.append(session_info)
        
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.id)})
        work_hours_target = user.get("work_hours", DEFAULT_WORK_HOURS)
        shift_target = work_hours_target / 2
        
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        all_records = list(mongo.db.attendance.find({
            "user_id": ObjectId(current_user.id),
            "date": {"$gte": cutoff}
        }).sort("date", -1))
        
        total_hours = sum([r.get("hours", 0) or 0 for r in all_records])
        
        all_formatted = []
        for rec in all_records:
            login_time = rec.get("login_time")
            logout_time = rec.get("logout_time")
            
            login_loc = rec.get("login_location", {})
            logout_loc = rec.get("logout_location", {})
            
            all_formatted.append({
                "date": rec.get("date", "N/A"),
                "login_time": format_ist_time(login_time) if login_time else "N/A",
                "logout_time": format_ist_time(logout_time) if logout_time else "N/A",
                "hours": str(round(rec.get("hours", 0) or 0, 1)) if rec.get("hours") else "N/A",
                "shift_type": rec.get("shift_type", "normal"),
                "shift_name": rec.get("shift_name", "Normal Login"),
                "session_number": rec.get("session_number", 1),
                "login_address": login_loc.get("address", "N/A"),
                "logout_address": logout_loc.get("address", "N/A"),
                "login_lat": login_loc.get("lat"),
                "login_lng": login_loc.get("lng"),
                "logout_lat": logout_loc.get("lat"),
                "logout_lng": logout_loc.get("lng")
            })
        
        # Get leave data
        leaves = list(mongo.db.leave_applications.find({
            "user_id": ObjectId(current_user.id),
            "status": "approved"
        }))
        
        leave_dates = [l["date"] for l in leaves]
        
        return jsonify({
            "username": current_user.username,
            "today_sessions": today_data,
            "active_session": active_session,
            "total_hours_today": round(total_hours_today, 1),
            "shift1_hours": round(shift1_hours, 1),
            "shift2_hours": round(shift2_hours, 1),
            "work_hours_target": work_hours_target,
            "shift_target": round(shift_target, 1),
            "shift1_completed": shift1_hours >= shift_target,
            "shift2_completed": shift2_hours >= shift_target,
            "can_login_shift1": not (shift1_hours >= shift_target),
            "can_login_shift2": not (shift2_hours >= shift_target),
            "total_hours_yeartodate": f"{total_hours:.1f}",
            "office_address": "JAIN University Head Office, Bengaluru",
            "office_lat": OFFICE_LAT,
            "office_lng": OFFICE_LNG,
            "allowed_radius_km": ALLOWED_RADIUS_KM,
            "allowed_radius_m": ALLOWED_RADIUS_KM * 1000,
            "history": all_formatted,
            "leaves": leave_dates,
            "shifts": SHIFT_TIMINGS,
            "min_hours_warning": MIN_WORK_HOURS
        })
        
    except Exception as e:
        print(f"Error in dashboard data API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/statistics", methods=["POST"])
@login_required
def get_statistics():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access statistics"}), 403
    
    try:
        data = request.get_json()
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        
        if not start_date or not end_date:
            return jsonify({"error": "Start and end dates required"}), 400
        
        # Get all sessions in date range
        sessions = list(mongo.db.attendance.find({
            "user_id": ObjectId(current_user.id),
            "date": {"$gte": start_date, "$lte": end_date}
        }).sort("date", 1))
        
        # Calculate statistics
        total_days = len(set(s.get("date") for s in sessions))
        total_hours = sum(s.get("hours", 0) or 0 for s in sessions)
        avg_hours_per_day = total_hours / total_days if total_days > 0 else 0
        
        # Shift breakdown
        shift1_sessions = [s for s in sessions if s.get("shift_type") == "shift1"]
        shift2_sessions = [s for s in sessions if s.get("shift_type") == "shift2"]
        normal_sessions = [s for s in sessions if s.get("login_type") == "normal"]
        
        shift1_hours = sum(s.get("hours", 0) or 0 for s in shift1_sessions)
        shift2_hours = sum(s.get("hours", 0) or 0 for s in shift2_sessions)
        normal_hours = sum(s.get("hours", 0) or 0 for s in normal_sessions)
        
        # Early logouts (less than target)
        early_logouts = []
        for session in sessions:
            if session.get("hours") and session.get("work_hours_target"):
                target = session.get("work_hours_target")
                if session.get("hours") < target:
                    early_logouts.append({
                        "date": session.get("date"),
                        "hours": session.get("hours"),
                        "target": target,
                        "shortfall": target - session.get("hours")
                    })
        
        # Leaves in date range
        leaves = list(mongo.db.leave_applications.find({
            "user_id": ObjectId(current_user.id),
            "date": {"$gte": start_date, "$lte": end_date},
            "status": "approved"
        }))
        
        return jsonify({
            "ok": True,
            "period": {"start": start_date, "end": end_date},
            "total_days": total_days,
            "total_hours": round(total_hours, 1),
            "avg_hours_per_day": round(avg_hours_per_day, 1),
            "shift1_hours": round(shift1_hours, 1),
            "shift2_hours": round(shift2_hours, 1),
            "normal_hours": round(normal_hours, 1),
            "shift1_sessions": len(shift1_sessions),
            "shift2_sessions": len(shift2_sessions),
            "normal_sessions": len(normal_sessions),
            "early_logouts": len(early_logouts),
            "early_logout_details": early_logouts,
            "leaves_taken": len(leaves),
            "leave_details": [{"date": l["date"], "type": l["type"]} for l in leaves]
        })
        
    except Exception as e:
        print(f"Error in statistics API: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/leave/apply", methods=["POST"])
@login_required
def apply_leave():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can apply for leave"}), 403
    
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415
        
        data = request.get_json()
        leave_date = data.get("date")
        leave_type = data.get("type")
        comments = data.get("comments", "")
        
        if not leave_date or not leave_type:
            return jsonify({"error": "Date and type are required"}), 400
        
        try:
            parsed_date = datetime.strptime(leave_date, "%Y-%m-%d")
            if parsed_date.date() < date.today():
                return jsonify({"error": "Cannot apply for leave in the past"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
        
        existing = mongo.db.leave_applications.find_one({
            "user_id": ObjectId(current_user.id),
            "date": leave_date
        })
        
        if existing:
            status = existing.get("status", "unknown")
            if status == "pending":
                return jsonify({"error": "You already have a pending leave application for this date"}), 400
            elif status == "approved":
                return jsonify({"error": "You already have an approved leave for this date"}), 400
            elif status == "denied":
                mongo.db.leave_applications.delete_one({"_id": existing["_id"]})
        
        if leave_date in UNIVERSITY_HOLIDAYS_2026:
            holiday = UNIVERSITY_HOLIDAYS_2026[leave_date]
            return jsonify({"error": f"This is already a holiday: {holiday['name']}"}), 400
        
        date_obj = datetime.strptime(leave_date, "%Y-%m-%d")
        if date_obj.weekday() in [5, 6]:
            return jsonify({"error": "Cannot apply for leave on weekends"}), 400
        
        leave_doc = {
            "user_id": ObjectId(current_user.id),
            "username": current_user.username,
            "user_email": current_user.email or "",
            "date": leave_date,
            "type": leave_type,
            "comments": comments,
            "status": "pending",
            "applied_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_notified": False
        }
        
        result = mongo.db.leave_applications.insert_one(leave_doc)
        
        return jsonify({
            "ok": True, 
            "message": "Leave application submitted successfully",
            "leave_id": str(result.inserted_id)
        }), 200
        
    except Exception as e:
        print(f"Error in apply_leave: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/api/leaves", methods=["GET"])
@login_required
def get_all_leaves():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access leave data"}), 403
    
    try:
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        leaves = list(mongo.db.leave_applications.find({
            "user_id": ObjectId(current_user.id),
            "date": {"$gte": cutoff}
        }))
        
        result = {}
        for leave in leaves:
            result[leave["date"]] = {
                "type": leave.get("type"),
                "comments": leave.get("comments", ""),
                "status": leave.get("status", "pending"),
                "admin_comments": leave.get("admin_comments", "")
            }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error fetching leaves: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/notifications")
@login_required
def get_notifications():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access notifications"}), 403
    
    try:
        notifications = list(mongo.db.leave_applications.find({
            "user_id": ObjectId(current_user.id),
            "status": {"$in": ["approved", "denied"]},
            "user_notified": {"$ne": True}
        }).sort("updated_at", -1))
        
        result = []
        for notif in notifications:
            result.append({
                "id": str(notif["_id"]),
                "type": "leave_status",
                "date": notif.get("date"),
                "leave_type": notif.get("type"),
                "status": notif.get("status"),
                "admin_comments": notif.get("admin_comments", ""),
                "updated_at": notif.get("updated_at").isoformat() if notif.get("updated_at") else None
            })
        
        return jsonify({"notifications": result})
        
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/notifications/<notif_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notif_id):
    try:
        mongo.db.leave_applications.update_one(
            {"_id": ObjectId(notif_id), "user_id": ObjectId(current_user.id)},
            {"$set": {"user_notified": True}}
        )
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/leave-applications")
@login_required
def get_leave_applications():
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        status_filter = request.args.get("status", "all")
        
        query = {}
        if status_filter != "all":
            query["status"] = status_filter
        
        applications = list(mongo.db.leave_applications.find(query).sort("applied_at", -1))
        
        result = []
        for app in applications:
            result.append({
                "id": str(app["_id"]),
                "username": app.get("username"),
                "user_email": app.get("user_email"),
                "date": app.get("date"),
                "type": app.get("type"),
                "comments": app.get("comments", ""),
                "status": app.get("status", "pending"),
                "admin_comments": app.get("admin_comments", ""),
                "applied_at": app.get("applied_at").isoformat() if app.get("applied_at") else None,
                "updated_at": app.get("updated_at").isoformat() if app.get("updated_at") else None
            })
        
        return jsonify({"applications": result})
        
    except Exception as e:
        print(f"Error fetching leave applications: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/leave/<leave_id>/update", methods=["POST"])
@login_required
def update_leave_status(leave_id):
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415
        
        data = request.get_json()
        status = data.get("status")
        admin_comments = data.get("admin_comments", "")
        
        if status not in ["approved", "denied"]:
            return jsonify({"error": "Invalid status"}), 400
        
        leave_app = mongo.db.leave_applications.find_one({"_id": ObjectId(leave_id)})
        if not leave_app:
            return jsonify({"error": "Leave application not found"}), 404
        
        mongo.db.leave_applications.update_one(
            {"_id": ObjectId(leave_id)},
            {
                "$set": {
                    "status": status,
                    "admin_comments": admin_comments,
                    "updated_at": datetime.utcnow(),
                    "updated_by": current_user.username,
                    "user_notified": False
                }
            }
        )
        
        return jsonify({"ok": True, "message": f"Leave {status} successfully."})
        
    except Exception as e:
        print(f"Error updating leave status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/early-logouts")
@login_required
def get_early_logouts():
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        today = date.today().isoformat()
        
        sessions = list(mongo.db.attendance.find({
            "date": today,
            "logout_time": {"$exists": True}
        }))
        
        early_logouts = []
        for session in sessions:
            target_hours = session.get("work_hours_target", DEFAULT_WORK_HOURS)
            hours_worked = session.get("hours", 0) or 0
            
            if hours_worked < target_hours:
                login_time = session.get("login_time")
                logout_time = session.get("logout_time")
                login_loc = session.get("login_location", {})
                logout_loc = session.get("logout_location", {})
                
                early_logouts.append({
                    "username": session.get("username"),
                    "date": session.get("date"),
                    "login_time": format_ist_time(login_time),
                    "logout_time": format_ist_time(logout_time),
                    "hours_worked": round(hours_worked, 1),
                    "target_hours": target_hours,
                    "shortfall": round(target_hours - hours_worked, 1),
                    "shift_type": session.get("shift_type", "normal"),
                    "shift_name": session.get("shift_name", "Normal Login"),
                    "session_number": session.get("session_number", 1),
                    "login_address": login_loc.get("address", "Address not available"),
                    "logout_address": logout_loc.get("address", "Address not available")
                })
        
        return jsonify({
            "early_logouts": early_logouts,
            "count": len(early_logouts),
            "date": today
        })
        
    except Exception as e:
        print(f"Error fetching early logouts: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/shift-usage")
@login_required
def get_shift_usage():
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        start_date = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
        end_date = request.args.get("end_date", date.today().isoformat())
        
        sessions = list(mongo.db.attendance.find({
            "date": {"$gte": start_date, "$lte": end_date},
            "login_type": "shift"
        }))
        
        shift_stats = {}
        user_shift_stats = {}
        
        for session in sessions:
            shift_type = session.get("shift_type", "unknown")
            shift_name = session.get("shift_name", "Unknown Shift")
            username = session.get("username")
            
            if shift_type not in shift_stats:
                shift_stats[shift_type] = {
                    "name": shift_name,
                    "count": 0,
                    "total_hours": 0,
                    "users": set()
                }
            
            shift_stats[shift_type]["count"] += 1
            shift_stats[shift_type]["total_hours"] += session.get("hours", 0) or 0
            shift_stats[shift_type]["users"].add(username)
            
            if username not in user_shift_stats:
                user_shift_stats[username] = {}
            
            if shift_type not in user_shift_stats[username]:
                user_shift_stats[username][shift_type] = {
                    "name": shift_name,
                    "count": 0,
                    "total_hours": 0
                }
            
            user_shift_stats[username][shift_type]["count"] += 1
            user_shift_stats[username][shift_type]["total_hours"] += session.get("hours", 0) or 0
        
        for shift in shift_stats.values():
            shift["unique_users"] = len(shift["users"])
            del shift["users"]
        
        return jsonify({
            "shift_stats": shift_stats,
            "user_shift_stats": user_shift_stats,
            "period": {"start": start_date, "end": end_date},
            "total_shift_sessions": len(sessions)
        })
        
    except Exception as e:
        print(f"Error fetching shift usage: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/user-locations/<date>")
@login_required
def get_user_locations(date):
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        sessions = list(mongo.db.attendance.find({"date": date}))
        
        locations = []
        for session in sessions:
            login_loc = session.get("login_location", {})
            logout_loc = session.get("logout_location", {})
            
            locations.append({
                "username": session.get("username"),
                "date": session.get("date"),
                "shift_type": session.get("shift_type", "normal"),
                "shift_name": session.get("shift_name", "Normal Login"),
                "session_number": session.get("session_number", 1),
                "login_time": format_ist_time(session.get("login_time")),
                "logout_time": format_ist_time(session.get("logout_time")) if session.get("logout_time") else None,
                "login_lat": login_loc.get("lat"),
                "login_lng": login_loc.get("lng"),
                "login_address": login_loc.get("address", "Address not available"),
                "logout_lat": logout_loc.get("lat"),
                "logout_lng": logout_loc.get("lng"),
                "logout_address": logout_loc.get("address", "Address not available") if logout_loc else None,
                "hours": session.get("hours", 0) or 0
            })
        
        return jsonify({
            "locations": locations,
            "date": date,
            "count": len(locations)
        })
        
    except Exception as e:
        print(f"Error fetching user locations: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/holidays")
def get_holidays():
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
    try:
        today = date.today()
        current_year = today.year
        current_month = today.month
        
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

@app.route("/api/admin/user-stats/<user_id>")
@login_required
def get_user_stats(user_id):
    if not current_user.is_authenticated or current_user.role != "admin":
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
        
        leaves_count = mongo.db.leave_applications.count_documents({
            "user_id": ObjectId(user_id),
            "date": {"$gte": first_day.isoformat(), "$lte": last_day.isoformat()},
            "status": "approved"
        })
        
        total_working_days = mongo.db.attendance.count_documents({
            "user_id": ObjectId(user_id)
        })
        
        shift_sessions = list(mongo.db.attendance.find({
            "user_id": ObjectId(user_id),
            "login_type": "shift"
        }))
        
        shift_breakdown = {}
        for session in shift_sessions:
            shift_type = session.get("shift_type", "unknown")
            if shift_type not in shift_breakdown:
                shift_breakdown[shift_type] = {
                    "count": 0,
                    "total_hours": 0,
                    "name": session.get("shift_name", "Unknown")
                }
            shift_breakdown[shift_type]["count"] += 1
            shift_breakdown[shift_type]["total_hours"] += session.get("hours", 0) or 0
        
        return jsonify({
            "username": user["username"],
            "email": user.get("email", "N/A"),
            "attendance_this_month": attendance_count,
            "leaves_this_month": leaves_count,
            "total_working_days": total_working_days,
            "work_hours_target": user.get("work_hours", DEFAULT_WORK_HOURS),
            "shift_usage": shift_breakdown,
            "total_shift_sessions": len(shift_sessions)
        })
        
    except Exception as e:
        print(f"Error fetching user stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/update-user-work-hours", methods=["POST"])
@login_required
def update_user_work_hours():
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        work_hours = float(data.get("work_hours", DEFAULT_WORK_HOURS))
        
        if work_hours < 1 or work_hours > 12:
            return jsonify({"error": "Work hours must be between 1 and 12"}), 400
        
        result = mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"work_hours": work_hours}}
        )
        
        if result.modified_count > 0:
            return jsonify({"ok": True, "message": f"Work hours updated to {work_hours} hours"})
        else:
            return jsonify({"error": "User not found or no changes made"}), 404
            
    except Exception as e:
        print(f"Error updating work hours: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/user/dashboard")
@login_required
def user_dashboard():
    if current_user.role != "intern":
        return redirect(url_for("admin_dashboard"))
    return render_template("user_dashboard.html")

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_authenticated or current_user.role != "admin":
        return redirect(url_for("user_dashboard"))
    
    users_raw = list(mongo.db.users.find())
    users = []
    for user in users_raw:
        user['_id'] = str(user['_id'])
        users.append(user)
    
    recent = list(mongo.db.attendance.find().sort("date", -1).limit(100))
    
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    leaves = list(mongo.db.leave_applications.find({"date": {"$gte": cutoff}}).sort("applied_at", -1))
    
    leaves_data = []
    for leave in leaves:
        leaves_data.append({
            "id": str(leave["_id"]),
            "username": leave.get("username"),
            "user_email": leave.get("user_email"),
            "date": leave.get("date"),
            "type": leave.get("type"),
            "comments": leave.get("comments", ""),
            "status": leave.get("status", "pending"),
            "admin_comments": leave.get("admin_comments", ""),
            "applied_at": leave.get("applied_at"),
            "updated_at": leave.get("updated_at")
        })
    
    return render_template("admin_dashboard.html", 
                         users=users, 
                         recent=recent,
                         leaves=leaves_data,
                         shifts=SHIFT_TIMINGS,
                         today_date=date.today().isoformat())

@app.route("/admin/export", methods=["GET"])
@login_required
def admin_export():
    if not current_user.is_authenticated or current_user.role != "admin":
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
        login_loc = r.get("login_location", {})
        logout_loc = r.get("logout_location", {})
        
        rows.append({
            "username": r.get("username"),
            "date": r.get("date"),
            "login_type": r.get("login_type", "normal"),
            "shift_type": r.get("shift_type", "normal"),
            "shift_name": r.get("shift_name", "Normal Login"),
            "session_number": r.get("session_number", 1),
            "login_time": format_ist_time(lt, "%Y-%m-%d %I:%M:%S %p") if lt else "",
            "logout_time": format_ist_time(lot, "%Y-%m-%d %I:%M:%S %p") if lot else "",
            "hours": r.get("hours", 0) or 0,
            "login_lat": login_loc.get("lat"),
            "login_lng": login_loc.get("lng"),
            "login_address": login_loc.get("address", ""),
            "logout_lat": logout_loc.get("lat"),
            "logout_lng": logout_loc.get("lng"),
            "logout_address": logout_loc.get("address", "")
        })
    
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    mem = io.BytesIO()
    mem.write(buf.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"attendance_{start}_to_{end}.csv"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/csv")

@app.route("/admin/create_user", methods=["POST"])
@login_required
def admin_create_user():
    if not current_user.is_authenticated or current_user.role != "admin":
        return redirect(url_for("user_dashboard"))
    
    username = request.form.get("username").strip()
    password = request.form.get("password")
    role = request.form.get("role", "intern")
    email = request.form.get("email", "")
    work_hours = float(request.form.get("work_hours", DEFAULT_WORK_HOURS))
    
    if mongo.db.users.find_one({"username": username}):
        flash("User exists", "danger")
        return redirect(url_for("admin_dashboard"))
    
    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    mongo.db.users.insert_one({
        "username": username, 
        "password": hashed, 
        "role": role, 
        "email": email,
        "work_hours": work_hours,
        "created_at": datetime.utcnow()
    })
    
    flash("User created", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_user/<user_id>", methods=["POST"])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_authenticated or current_user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        if str(user_id) == str(current_user.id):
            return jsonify({"error": "Cannot delete your own account"}), 400
        
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        mongo.db.attendance.delete_many({"user_id": ObjectId(user_id)})
        mongo.db.leave_applications.delete_many({"user_id": ObjectId(user_id)})
        
        return jsonify({"ok": True, "message": f"User {user['username']} deleted successfully"})
        
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)