#updated
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

# Admin email for leave notifications
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
    R = 6371.0
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
                        <p style="color: #86868b; margin-top: 8px;">JAIN University Intern Attendance System</p>
                    </div>
                    
                    <div style="background: #e8f4fd; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                            <div style="background: #0071e3; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.2em;">
                                {username[0].upper()}
                            </div>
                            <div>
                                <div style="font-weight: bold; font-size: 1.1em; color: #1d1d1f;">{username}</div>
                                <div style="font-size: 0.9em; color: #86868b;">Logged in successfully</div>
                            </div>
                        </div>
                        <div style="background: white; border-radius: 6px; padding: 15px; margin-top: 10px;">
                            <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Login Time (IST)</div>
                            <div style="font-size: 1.2em; font-weight: bold; color: #0071e3;">{login_time_str}</div>
                        </div>
                    </div>
                    
                    <div style="border-top: 1px solid #e0e0e0; padding-top: 20px; text-align: center;">
                        <div style="font-style: italic; color: #6e6e73; margin-bottom: 20px;">"{quote}"</div>
                        <div style="font-size: 0.8em; color: #86868b;">This is an automated email. Please do not reply.</div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        mail.send(msg)
        print(f"Login email sent to {user_email}")
        return True
    except Exception as e:
        print(f"Failed to send login email: {e}")
        return False

def send_logout_email(user_email, username, login_time_str, logout_time_str, hours):
    """Send email notification on logout"""
    try:
        quote = random.choice(MOTIVATIONAL_QUOTES)
        msg = Message(
            subject=f"📊 Work Summary - {username}",
            recipients=[user_email]
        )
        
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f7; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #34c759; margin: 0;">📊 Work Summary</h1>
                        <p style="color: #86868b; margin-top: 8px;">JAIN University Intern Attendance System</p>
                    </div>
                    
                    <div style="background: #e8f4fd; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                            <div style="background: #34c759; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.2em;">
                                {username[0].upper()}
                            </div>
                            <div>
                                <div style="font-weight: bold; font-size: 1.1em; color: #1d1d1f;">{username}</div>
                                <div style="font-size: 0.9em; color: #86868b;">Daily attendance summary</div>
                            </div>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 10px;">
                            <div style="background: white; border-radius: 6px; padding: 12px;">
                                <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Login Time</div>
                                <div style="font-weight: bold; color: #1d1d1f;">{login_time_str}</div>
                            </div>
                            <div style="background: white; border-radius: 6px; padding: 12px;">
                                <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Logout Time</div>
                                <div style="font-weight: bold; color: #1d1d1f;">{logout_time_str}</div>
                            </div>
                        </div>
                        
                        <div style="background: #d1f4e0; border-radius: 6px; padding: 15px; text-align: center; margin-top: 10px;">
                            <div style="font-size: 0.8em; color: #0a7d3e; margin-bottom: 4px;">Total Hours Worked</div>
                            <div style="font-size: 2em; font-weight: bold; color: #0a7d3e;">{hours:.1f} hours</div>
                        </div>
                    </div>
                    
                    <div style="border-top: 1px solid #e0e0e0; padding-top: 20px; text-align: center;">
                        <div style="font-style: italic; color: #6e6e73; margin-bottom: 20px;">"{quote}"</div>
                        <div style="font-size: 0.8em; color: #86868b;">This is an automated email. Please do not reply.</div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        mail.send(msg)
        print(f"Logout email sent to {user_email}")
        return True
    except Exception as e:
        print(f"Failed to send logout email: {e}")
        return False

def send_leave_application_email_to_admin(username, user_email, leave_date, leave_type, comments):
    """Send email to admin about new leave application"""
    try:
        msg = Message(
            subject=f"📋 New Leave Application - {username}",
            recipients=[ADMIN_EMAIL]
        )
        
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f7; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #ff9500; margin: 0;">📋 New Leave Application</h1>
                        <p style="color: #86868b; margin-top: 8px;">JAIN University Intern Attendance System</p>
                    </div>
                    
                    <div style="background: #fff3cd; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                            <div style="background: #ff9500; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.2em;">
                                {username[0].upper()}
                            </div>
                            <div>
                                <div style="font-weight: bold; font-size: 1.1em; color: #1d1d1f;">{username}</div>
                                <div style="font-size: 0.9em; color: #86868b;">{user_email}</div>
                            </div>
                        </div>
                        
                        <div style="background: white; border-radius: 6px; padding: 15px; margin-bottom: 10px;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                                <div>
                                    <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Leave Date</div>
                                    <div style="font-weight: bold; color: #1d1d1f;">{leave_date}</div>
                                </div>
                                <div>
                                    <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Leave Type</div>
                                    <div style="font-weight: bold; color: #ff9500;">{leave_type}</div>
                                </div>
                            </div>
                        </div>
                        
                        {comments if comments else ''}
                    </div>
                    
                    <div style="background: #e8f4fd; border-radius: 6px; padding: 15px; text-align: center;">
                        <p style="margin: 0; color: #0071e3; font-weight: 600;">Action Required: Please review this leave application in the Admin Dashboard</p>
                    </div>
                    
                    <div style="border-top: 1px solid #e0e0e0; padding-top: 20px; text-align: center;">
                        <div style="font-size: 0.8em; color: #86868b;">
                            <p style="margin: 0;">JAIN University - Admin Panel</p>
                            <p style="margin: 5px 0 0 0;">This is an automated notification. Please do not reply.</p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        if comments:
            msg.html = msg.html.replace("{comments if comments else ''}", f"""
                <div style="background: white; border-radius: 6px; padding: 15px; margin-top: 10px;">
                    <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Reason/Comments</div>
                    <div style="font-weight: normal; color: #1d1d1f;">{comments}</div>
                </div>
            """)
        
        mail.send(msg)
        print(f"Leave application email sent to admin")
        return True
    except Exception as e:
        print(f"Failed to send leave application email: {e}")
        return False

def send_leave_status_email_to_user(user_email, username, leave_date, leave_type, status, admin_comments):
    """Send email to user about leave status update"""
    try:
        status_color = "#34c759" if status == "approved" else "#ff3b30"
        status_icon = "✅" if status == "approved" else "❌"
        status_title = "Leave Approved" if status == "approved" else "Leave Denied"
        
        msg = Message(
            subject=f"{status_icon} Leave {status.capitalize()} - {username}",
            recipients=[user_email]
        )
        
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f7; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: {status_color}; margin: 0;">{status_icon} {status_title}</h1>
                        <p style="color: #86868b; margin-top: 8px;">JAIN University Intern Attendance System</p>
                    </div>
                    
                    <div style="background: {'#d1f4e0' if status == 'approved' else '#ffe5e5'}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                            <div style="background: {status_color}; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.2em;">
                                {username[0].upper()}
                            </div>
                            <div>
                                <div style="font-weight: bold; font-size: 1.1em; color: #1d1d1f;">{username}</div>
                                <div style="font-size: 0.9em; color: #86868b;">Leave status has been updated</div>
                            </div>
                        </div>
                        
                        <div style="background: white; border-radius: 6px; padding: 15px; margin-bottom: 10px;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                                <div>
                                    <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Leave Date</div>
                                    <div style="font-weight: bold; color: #1d1d1f;">{leave_date}</div>
                                </div>
                                <div>
                                    <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Leave Type</div>
                                    <div style="font-weight: bold; color: #ff9500;">{leave_type}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div style="background: white; border-radius: 6px; padding: 15px; margin-top: 10px;">
                            <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Status</div>
                            <div style="font-weight: bold; color: {status_color}; font-size: 1.2em;">
                                {status_icon} {status.upper()}
                            </div>
                        </div>
                        
                        {admin_comments if admin_comments else ''}
                    </div>
                    
                    <div style="border-top: 1px solid #e0e0e0; padding-top: 20px; text-align: center;">
                        <div style="font-size: 0.8em; color: #86868b;">
                            <p style="margin: 0;">JAIN University - Intern Attendance System</p>
                            <p style="margin: 5px 0 0 0;">This is an automated email. Please do not reply.</p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        if admin_comments:
            msg.html = msg.html.replace("{admin_comments if admin_comments else ''}", f"""
                <div style="background: #f5f5f7; border-radius: 6px; padding: 15px; margin-top: 10px;">
                    <div style="font-size: 0.8em; color: #86868b; margin-bottom: 4px;">Admin Comments</div>
                    <div style="font-weight: normal; color: #1d1d1f;">{admin_comments}</div>
                </div>
            """)
        
        mail.send(msg)
        print(f"Leave status email sent to {user_email}")
        return True
    except Exception as e:
        print(f"Failed to send leave status email: {e}")
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

# Leave Management API - FIXED VERSION
# Replace the /api/leave/apply route in your Flask app with this fixed version

@app.route("/api/leave/apply", methods=["POST"])
@login_required
def apply_leave():
    """Fixed leave application endpoint"""
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can apply for leave"}), 403
    
    try:
        # Check if request is JSON
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        leave_date = data.get("date")
        leave_type = data.get("type")
        comments = data.get("comments", "")
        
        # Validate required fields
        if not leave_date or not leave_type:
            return jsonify({"error": "Date and type are required"}), 400
        
        # Validate date format
        try:
            parsed_date = datetime.strptime(leave_date, "%Y-%m-%d")
            # Check if date is in the past (except today)
            if parsed_date.date() < date.today():
                return jsonify({"error": "Cannot apply for leave in the past"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # Check for existing leave application
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
                # Allow reapplication if previously denied
                mongo.db.leave_applications.delete_one({"_id": existing["_id"]})
        
        # Check if it's a holiday
        if leave_date in UNIVERSITY_HOLIDAYS_2026:
            holiday = UNIVERSITY_HOLIDAYS_2026[leave_date]
            return jsonify({"error": f"This is already a holiday: {holiday['name']}"}), 400
        
        # Check if it's a weekend (Saturday/Sunday)
        date_obj = datetime.strptime(leave_date, "%Y-%m-%d")
        if date_obj.weekday() in [5, 6]:  # 5=Saturday, 6=Sunday
            return jsonify({"error": "Cannot apply for leave on weekends"}), 400
        
        # Create leave application
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
        
        # Send email to admin (non-blocking)
        try:
            if current_user.email:
                send_leave_application_email_to_admin(
                    current_user.username,
                    current_user.email,
                    leave_date,
                    leave_type,
                    comments
                )
        except Exception as email_error:
            print(f"Failed to send email notification: {email_error}")
            # Don't fail the request if email fails
        
        return jsonify({
            "ok": True, 
            "message": "Leave application submitted successfully. Admin will review your request.",
            "leave_id": str(result.inserted_id)
        }), 200
        
    except Exception as e:
        print(f"Error in apply_leave: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# Also add this helper route to check leave status
@app.route("/api/leave/check/<leave_date>", methods=["GET"])
@login_required
def check_leave(leave_date):
    """Check if leave already exists for a date"""
    try:
        existing = mongo.db.leave_applications.find_one({
            "user_id": ObjectId(current_user.id),
            "date": leave_date
        })
        
        if existing:
            return jsonify({
                "exists": True,
                "status": existing.get("status"),
                "type": existing.get("type"),
                "comments": existing.get("comments", "")
            })
        
        # Check if it's a holiday
        if leave_date in UNIVERSITY_HOLIDAYS_2026:
            holiday = UNIVERSITY_HOLIDAYS_2026[leave_date]
            return jsonify({
                "is_holiday": True,
                "holiday_name": holiday["name"],
                "holiday_type": holiday["type"]
            })
        
        return jsonify({"exists": False})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/api/leaves", methods=["GET"])
@login_required
def get_all_leaves():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access leave data"}), 403
    
    try:
        cutoff = (date.today() - timedelta(days=90)).isoformat()
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
        
        user_email = leave_app.get("user_email")
        if user_email:
            send_leave_status_email_to_user(
                user_email,
                leave_app.get("username"),
                leave_app.get("date"),
                leave_app.get("type"),
                status,
                admin_comments
            )
        
        return jsonify({"ok": True, "message": f"Leave {status} successfully. User will be notified via email."})
        
    except Exception as e:
        print(f"Error updating leave status: {e}")
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

@app.route("/api/admin/calendar-data")
@login_required
def get_admin_calendar_data():
    if not current_user.is_authenticated or current_user.role != "admin":
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
        leaves = list(mongo.db.leave_applications.find({**query, "status": "approved"}))
        
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
                "comments": leave.get("comments", ""),
                "status": leave.get("status")
            }
        
        return jsonify({
            "calendar_data": calendar_data,
            "start_date": start_date,
            "end_date": end_date
        })
        
    except Exception as e:
        print(f"Error in admin calendar API: {e}")
        return jsonify({"error": str(e)}), 500

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

@app.route("/admin/notifications", methods=["GET","POST"])
@login_required
def admin_notifications():
    if not current_user.is_authenticated or current_user.role != "admin":
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
    recent_serialized = [serialize_attendance(r) for r in recent]
    
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
                         recent=recent_serialized,
                         leaves=leaves_data)

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
    if not current_user.is_authenticated or current_user.role != "admin":
        return redirect(url_for("user_dashboard"))
    
    username = request.form.get("username").strip()
    password = request.form.get("password")
    role = request.form.get("role", "intern")
    email = request.form.get("email", "")
    
    if mongo.db.users.find_one({"username": username}):
        flash("User exists", "danger")
        return redirect(url_for("admin_dashboard"))
    
    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    mongo.db.users.insert_one({
        "username": username, 
        "password": hashed, 
        "role": role, 
        "email": email, 
        "created_at": datetime.utcnow()
    })
    
    flash("User created", "success")
    return redirect(url_for("admin_dashboard"))

# Delete user
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

# Health endpoint
@app.route("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)