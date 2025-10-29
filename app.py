# app.py
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from bson.objectid import ObjectId
from datetime import datetime, timedelta, date
import pytz
import io
import pandas as pd
import math
import os

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

if not app.config.get("MONGO_URI"):
    raise RuntimeError("MONGO_URI not set in .env (see README)")

mongo = PyMongo(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# JAIN Head Office coordinates
OFFICE_LAT = 12.9248224
OFFICE_LNG = 77.5702351
ALLOWED_RADIUS_KM = 10

# IST Timezone
IST = pytz.timezone('Asia/Kolkata')

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
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def ensure_admin():
    if not current_user.is_authenticated or current_user.role != "admin":
        flash("Admin access required", "danger")
        return False
    return True

def serialize_attendance(rec):
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

# Routes: auth
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

    # Get current IST date
    ist_now = get_ist_now()
    today = ist_now.date().isoformat()
    
    rec = mongo.db.attendance.find_one({"user_id": ObjectId(current_user.id), "date": today, "logout_time": {"$exists": False}})
    if rec:
        return jsonify({"error":"Already logged in and not logged out yet."}), 400

    # Store as UTC but we'll convert to IST when displaying
    now_utc = datetime.utcnow()
    mongo.db.attendance.insert_one({
        "user_id": ObjectId(current_user.id),
        "username": current_user.username,
        "date": today,
        "login_time": now_utc,
        "login_location": {"lat": lat, "lng": lng},
        "created_at": now_utc
    })
    return jsonify({"ok": True, "login_time": format_ist_time(now_utc)})

@app.route("/attendance/logout", methods=["POST"])
@login_required
def attendance_logout():
    if current_user.role != "intern":
        return jsonify({"error":"Only interns can record attendance"}), 403

    lat, lng = _get_lat_lng_from_request()
    
    # Get current IST date
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
    return jsonify({"ok": True, "logout_time": format_ist_time(logout_time), "hours": updates["hours"]})

# API endpoint for dashboard data
@app.route("/api/dashboard-data")
@login_required
def get_dashboard_data():
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access this dashboard"}), 403
    
    try:
        # Get current IST date
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

@app.route("/api/leave/<leave_date>", methods=["GET", "DELETE"])
@login_required
def manage_leave(leave_date):
    if current_user.role != "intern":
        return jsonify({"error": "Only interns can access leave data"}), 403
    
    try:
        if request.method == "GET":
            leave = mongo.db.leaves.find_one({
                "user_id": ObjectId(current_user.id),
                "date": leave_date
            })
            
            if leave:
                return jsonify({
                    "date": leave.get("date"),
                    "type": leave.get("type"),
                    "comments": leave.get("comments", "")
                })
            else:
                return jsonify({"error": "No leave found for this date"}), 404
        
        elif request.method == "DELETE":
            result = mongo.db.leaves.delete_one({
                "user_id": ObjectId(current_user.id),
                "date": leave_date
            })
            
            if result.deleted_count > 0:
                return jsonify({"ok": True, "message": "Leave deleted successfully"})
            else:
                return jsonify({"error": "No leave found to delete"}), 404
            
    except Exception as e:
        print(f"Error managing leave: {e}")
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

# Dashboards & history
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
    
    users = list(mongo.db.users.find())
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

# Health
@app.route("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)