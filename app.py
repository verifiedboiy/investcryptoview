from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
import random
import smtplib
from email.mime.text import MIMEText
import os
from functools import wraps
from pathlib import Path
import json
import csv
from datetime import datetime


SENDER_EMAIL = "cs4146669@gmail.com"
APP_PASSWORD = "idodwjvnxopzrasr"

# ---------- simple JSON storage helpers ----------
USERS_FILE = "data/users.json"       # ensure data/ exists
DEPOSITS_FILE = "data/deposits.json"
LOGS_FILE = "data/admin_logs.json"
USERS_FILE = os.path.join("data", "users.json")

os.makedirs("data", exist_ok=True)
for f in (USERS_FILE, DEPOSITS_FILE, LOGS_FILE):
    if not os.path.exists(f):
        with open(f, "w") as _f:
            # for users we will treat as dict later, but [] is fine initial
            json.dump({}, _f)

def send_email(to_email, subject, html_body):
    import smtplib
    from email.mime.text import MIMEText

    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_login = "cs4146669@gmail.com"
    smtp_password = "idodwjvnxopzrasr"  # your Google App Password

    sender_email = smtp_login

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_login, smtp_password)
            server.sendmail(sender_email, to_email, msg.as_string())

        print(f"✅ Email sent to {to_email}")
        return True

    except Exception as e:
        print("❌ Email error:", e)
        return False

def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except Exception:
            # fallback
            return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

# ---------- USER HELPERS (support dict or list) ----------

def _ensure_users_list(users_data):
    """Return a list of user dicts, whether users_data is dict or list."""
    if isinstance(users_data, dict):
        return list(users_data.values())
    return users_data or []

def _ensure_users_dict(users_data):
    """Return a dict keyed by user_id. If it's already dict, return as-is."""
    if isinstance(users_data, dict):
        return users_data
    # if it's a list, convert to dict using 'id' or email as key
    out = {}
    for u in users_data or []:
        uid = str(u.get("id")) or u.get("email")
        if uid:
            out[uid] = u
    return out

def find_user_by_id(user_id):
    users_data = load_json(USERS_FILE)
    # support dict format {user_id: {...}} and list format
    if isinstance(users_data, dict):
        if user_id in users_data:
            return users_data[user_id]
        for u in users_data.values():
            if str(u.get("id")) == str(user_id):
                return u
        return None
    else:
        for u in users_data:
            if str(u.get("id")) == str(user_id):
                return u
        return None

def save_user_data(email, new_balance, new_profit):
    """Update user balance/profit by email in USERS_FILE (dict-style)."""
    try:
        with open(USERS_FILE) as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if isinstance(users, dict):
        # dict shape {user_id: {...}}
        for uid, u in users.items():
            if u.get("email") == email:
                u["balance"] = float(new_balance)
                u["profit"] = float(new_profit)
                break
    else:
        # list fallback
        for u in users:
            if u.get("email") == email:
                u["balance"] = float(new_balance)
                u["profit"] = float(new_profit)
                break

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def update_user(user):
    """Update single user object back to USERS_FILE, supporting dict or list."""
    users_data = load_json(USERS_FILE)

    if isinstance(users_data, dict):
        uid = str(user.get("id"))
        if uid in users_data:
            users_data[uid] = user
        else:
            # fallback: match by email
            for k, v in users_data.items():
                if v.get("email") == user.get("email"):
                    users_data[k] = user
                    break
        save_json(USERS_FILE, users_data)
        return True
    else:
        # list format
        changed = False
        for i, u in enumerate(users_data):
            if str(u.get("id")) == str(user.get("id")):
                users_data[i] = user
                changed = True
                break
        if changed:
            save_json(USERS_FILE, users_data)
        return changed

def log_admin(action, details=""):
    logs = load_json(LOGS_FILE)
    # logs is dict or list; normalize to list
    if isinstance(logs, dict):
        logs_list = logs.get("logs", [])
    else:
        logs_list = logs
    logs_list.append({"time": datetime.utcnow().isoformat(), "action": action, "details": details})
    # save back as list (or wrap in dict if it used to be dict)
    if isinstance(logs, dict):
        logs["logs"] = logs_list
        save_json(LOGS_FILE, logs)
    else:
        save_json(LOGS_FILE, logs_list)

# ---------- admin auth ----------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "admin123")  # set real password in env

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*a, **kw)
    return wrapper

def build_broadcast_email_html(username, subject, message):
    """Nice HTML layout for admin broadcast emails (no code box, no security tip)."""
    return f"""
    <div style="font-family: Arial, sans-serif; background:#0f172a; padding:30px; color:#e5e7eb;">
      <div style="max-width:600px; margin:auto; background:#020617; border-radius:16px; overflow:hidden;">

        <!-- Header -->
        <div style="background:#020617; border-bottom:1px solid #1f2933; padding:20px 24px;">
          <h1 style="margin:0; font-size:20px; color:#f9fafb;">
            <span style="color:#f9fafb;">Invest</span><span style="color:#3b82f6;">CryptoView</span>
          </h1>
          <p style="margin:4px 0 0; font-size:13px; color:#9ca3af;">
            Secure Account Notification
          </p>
        </div>

        <!-- Body -->
        <div style="padding:24px 24px 10px;">
          <h2 style="margin:0 0 12px; font-size:18px; color:#f9fafb;">{subject}</h2>

          <p style="margin:0 0 16px; font-size:14px; color:#e5e7eb;">
            Dear {username},
          </p>

          <p style="margin:0 0 24px; font-size:14px; color:#e5e7eb; white-space:pre-line;">
            {message}
          </p>

          <p style="margin:0 0 4px; font-size:14px; color:#e5e7eb;">
            Best regards,
          </p>
          <p style="margin:0; font-size:14px; font-weight:bold;">
            InvestCryptoView Team
          </p>
        </div>

        <!-- Footer -->
        <div style="padding:16px 24px 20px; border-top:1px solid #1f2933;">
          <p style="margin:0; font-size:11px; color:#6b7280;">
            © 2025 InvestCryptoView — All rights reserved.<br>
            This email was sent automatically. Please do not reply.
          </p>
        </div>

      </div>
    </div>
    """

def build_brand_email_html(title, code, purpose_note, button_text=None, button_url=None):
    """
    Returns a fully inlined, email-client-safe HTML string.
    - title:     e.g. "Verify Your Email" or "Reset Your Password"
    - code:      6-digit code as a string
    - purpose_note: short line like "Use this code to complete your sign up."
    - button_text/button_url: optional CTA (you can leave None)
    """
    # Colors (your palette)
    blue = "#1e86ff"
    green = "#17c964"
    black = "#0c0e12"
    gray_text = "#303540"
    light_border = "#e7ecf5"

    # Basic, table-based layout for max compatibility
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{title} • InvestCryptoView</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body style="margin:0;background:#f5f7fb;padding:24px;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif; color:{gray_text};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid {light_border};border-radius:12px;overflow:hidden;">
    <tr>
      <td style="background:{black};padding:22px 24px;text-align:center;">
        <div style="font-size:22px;color:#e9eefc;font-weight:800;letter-spacing:.3px;">Invest<span style="color:{blue}">Crypto</span>View</div>
        <div style="margin-top:6px;font-size:12px;color:#aab4c6;">Secure Account Notification</div>
      </td>
    </tr>

    <tr>
      <td style="padding:26px 24px 10px 24px;">
        <h1 style="margin:0 0 6px 0;font-size:22px;color:#0f1320;font-weight:800;">{title}</h1>
        <p style="margin:6px 0 12px 0;line-height:1.55;">{purpose_note}</p>
        <div style="margin:18px 0 8px 0;font-size:13px;color:#4a5160;">Your one-time code</div>

        <div style="display:inline-block;padding:14px 18px;border:1px dashed {blue};border-radius:10px;background:#f0f6ff;color:#0a1a33;font-weight:800;letter-spacing:3px;font-size:20px;">
          {code}
        </div>

        {"".join([
          f'<div style="margin:22px 0 6px 0;">',
          f'<a href="{button_url}" style="display:inline-block;background:{blue};color:#fff;text-decoration:none;padding:12px 16px;border-radius:10px;font-weight:700;">{button_text}</a>',
          f'</div>'
        ]) if button_text and button_url else ""}

        <div style="margin-top:18px;padding:12px 14px;border:1px solid {light_border};border-radius:10px;background:#fbfdfb;">
          <div style="font-size:13px;color:#0f5e2b;font-weight:700;">Security tip</div>
          <div style="font-size:13px;line-height:1.55;margin-top:4px;">
            Never share this code with anyone. <b>InvestCryptoView</b> will <b>never</b> ask for your code or password in chat, phone calls, or DMs.
          </div>
        </div>

        <p style="margin:18px 0 0 0;font-size:12px;color:#6a7385;">
          If you didn’t request this, you can ignore this message. Your code expires shortly.
        </p>
      </td>
    </tr>

    <tr>
      <td style="padding:18px 24px 24px 24px;color:#6e7787;font-size:12px;border-top:1px solid {light_border};">
        © 2025 InvestCryptoView — All rights reserved<br/>
        This email was sent automatically. Please don’t reply.
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html

# 🔥 Absolute path fix
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

print("📁 Template folder path:", TEMPLATE_DIR)  # This will print in your terminal

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = "dev-secret-change-me"

# Persistent auth users file (email → password/verified/code)
AUTH_USERS_FILE = os.path.join("data", "auth_users.json")
os.makedirs("data", exist_ok=True)

# Load auth-users from file so they survive restart
try:
    with open(AUTH_USERS_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)          # users is still a dict keyed by email
except Exception:
    users = {}
    with open(AUTH_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

@app.route("/")
def home():
    return render_template("base.html")

@app.route('/market')
def market():
    return render_template('market.html')

@app.route("/deposit")
def deposit():
    username = session.get("username", "Investor")
    return render_template("deposit.html", username=username)

@app.route('/payment_confirmation')
def payment_confirmation():
    asset = request.args.get('asset', '')
    network = request.args.get('network', '')
    amount = request.args.get('amount', '')

    # Generate random order number, e.g. ICV-4728319
    order_no = f"ICV-{random.randint(1000000, 9999999)}"

    return render_template('payment_confirmation.html',
                           asset=asset,
                           network=network,
                           amount=amount,
                           order_no=order_no)
    return render_template("payment_confirmation.html", order_no=order_no)

@app.route("/withdraw")
def withdraw():
    username = session.get("username", "Investor")
    email    = session.get("email")

    # Load users.json
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except:
        users = {}

    user = None
    user_id = ""

    if email:
        for uid, data in users.items():
            if data.get("email") == email:
                user = data
                user_id = uid
                break

    # fallback if not found
    if not user:
        user = {"balance": 0.0, "profit": 0.0}

    return render_template(
        "withdraw.html",
        username=username,
        user=user,
        user_id=user_id
    )

@app.route("/kyc")
def kyc():
    username = session.get("username", "Investor")
    return render_template("kyc.html", username=username)

@app.route("/kyc_upload")
def kyc_upload():
    username = session.get("username", "Investor")
    return render_template("kyc_upload.html", username=username)

@app.route("/about")
def about():
    username = session.get("username", "Investor")
    return render_template("about.html", username=username)

@app.route("/trades")
def trades():
    username = session.get("username", "Investor")
    email    = session.get("email")

    try:
        with open(USERS_FILE) as f:
            users = json.load(f)
    except:
        users = {}

    user = None
    user_id = ""

    for uid, data in users.items():
        if data.get("email") == email:
            user = data
            user_id = uid
            # removed break so newest user is picked

    if not user:
        user = {"balance": 0.0, "profit": 0.0}

    return render_template("trades.html",
                           username=username,
                           user=user,
                           user_id=user_id)

@app.route("/api/update_balance", methods=["POST"])
def api_update_balance():
    data = request.get_json(force=True) or {}

    user_id = data.get("user_id")
    balance = float(data.get("balance", 0) or 0)
    profit  = float(data.get("profit", 0) or 0)

    app.logger.debug("/api/update_balance: %s %s %s", user_id, balance, profit)

    # 1) Load JSON safely
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except Exception:
        users = {}

    if not isinstance(users, dict):
        users = {}

    # 2) Find user by id first
    if user_id and user_id in users:
        u = users[user_id]
    else:
        # fallback: match by email in session
        email = session.get("email")
        u = None
        for uid, info in users.items():
            if info.get("email") == email:
                user_id = uid
                u = info
                break

        if u is None:
            # nothing to update, but don't crash
            return jsonify({"ok": True, "skipped": True})

    # 3) Update fields
    u["balance"] = balance
    u["profit"] = profit

    # 4) SAVE: overwrite file completely (no extra })
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

    return jsonify({"ok": True})

@app.route("/contact")
def contact():
    username = session.get("username", "Investor")
    return render_template("contact.html", username=username)

@app.route("/logout")
def logout():
    session.clear()
    flash("You’ve been logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/privacy")
def privacy():
    username = session.get("username", "Investor")
    return render_template("privacy.html", username=username)

@app.route("/withdraw_lock")
def withdraw_lock():
    username = session.get("username", "Investor")
    email = session.get("email")

    # Load users.json so we can find the logged-in user's ID
    import json, os
    USERS_FILE = "data/users.json"

    user_id = None
    user = None

    if email and os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            data = json.load(f)

        # Find the user entry that matches the session email
        for uid, u in data.items():
            if u.get("email") == email:
                user_id = uid
                user = u
                break

    return render_template(
        "withdraw_lock.html",
        username=username,
        email=email,
        user_id=user_id,
        user=user
    )

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if request.method == "POST":
        new_username = request.form.get("username")
        new_password = request.form.get("password")
        session["username"] = new_username
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))
    username = session.get("username", "Investor")
    return render_template("edit_profile.html", username=username)

@app.route("/profile")
def profile():
    username = session.get("username", "Investor")
    return render_template("profile_dropdown.html", username=username)

@app.route("/api/deposit_notify", methods=["POST"])
def deposit_notify():
    data = request.get_json() or {}

    # values coming from JS or from the URL query (fallback)
    raw_amount = data.get("amount") or request.args.get("amount", "0")
    asset      = data.get("asset")  or request.args.get("asset",  "Unknown")
    network    = data.get("network") or request.args.get("network", "Unknown")
    tx_ref     = data.get("tx_ref") or request.args.get("tx_ref", "")

    try:
        amount = float(raw_amount)
    except:
        amount = 0.0

    method = f"{asset} / {network}"

    # get user info from session
    email    = session.get("email", "Unknown")
    username = session.get("username", "Unknown")

    # 🔍 look up user_id in data/users.json by email
    user_id = "Unknown"
    try:
        with open(USERS_FILE, "r") as f:
            users_data = json.load(f)

        if isinstance(users_data, dict):
            for uid, u in users_data.items():
                if u.get("email") == email:
                    user_id = uid
                    break
    except Exception as e:
        print("deposit_notify: could not load USERS_FILE:", e)

    # build email HTML (same as before, just with User ID added)
    html = f"""
<h2>New Deposit Marked as Paid</h2>

<p><strong>User:</strong> {username} ({email})</p>
<p><strong>User ID:</strong> {user_id}</p>

<p><strong>Amount:</strong> ${amount:,.2f}</p>
<p><strong>Method:</strong> {method}</p>

<p><strong>Reference / Note:</strong> {tx_ref or 'Not provided'}</p>

<hr>

<p>This user clicked "I have made my payment" on the InvestCryptoView deposit page.</p>
"""

    # send to your review inbox
    send_email("invest.cryptoview@mail.com",
               "New deposit pending review",
               html)

    return jsonify({"ok": True})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form["fullname"]
        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        country = request.form["country"]
        password = request.form["password"]

        # 🔥 LOAD AUTH USERS (the temporary users = verification users)
        global users  

        # ✅ CHECK IF EMAIL ALREADY EXISTS (email is the key)
        for existing_email in users.keys():
            if existing_email == email:
                return render_template(
                    "signup.html",
                    error_email="Email already exists"
                )

        # -----------------------------------------------
        # ✅ CHECK IF USERNAME ALREADY EXISTS
        # -----------------------------------------------
        for u in users.values():
            if u.get("username") == username:
                return render_template("signup.html",
                                       error_username="Username is not available")

        # If no duplicate found → continue signup normally
        # -----------------------------------------------

        code = str(random.randint(100000, 999999))
        users[email] = {
            "name": full_name,
            "username": username,
            "password": password,
            "verified": False,
            "code": code
        }

        html = build_brand_email_html(
            title="Verify Your Email",
            code=code,
            purpose_note="Use this code to complete your sign up on InvestCryptoView."
        )
        send_email(email, "Your InvestCryptoView Verification Code", html)

        session["email"] = email

        # ---------- SAVE INTO ADMIN users.json ----------
        import uuid
        import json as _json
        from datetime import datetime as _dt

        _USERS_FILE = "data/users.json"
        os.makedirs("data", exist_ok=True)

        # Load admin users database
        try:
            with open(_USERS_FILE, "r") as f:
                users_data = _json.load(f)
        except:
            users_data = {}

        user_id = str(uuid.uuid4())[:8]

        users_data[user_id] = {
            "id": user_id,
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone": phone,
            "country": country,
            "balance": 0.0,
            "profit": 0.0,
            "location": request.remote_addr,
            "kyc_status": "Pending",
            "registered_at": _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Save database
        with open(_USERS_FILE, "w") as f:
            _json.dump(users_data, f, indent=4)

        return redirect(url_for("verify"))

    print("✅ Flask reached signup page")
    return render_template("signup.html")

@app.route("/admin/user/<user_id>/update", methods=["POST"])
@admin_required
def admin_update_user(user_id):
    # Load existing users
    try:
        with open("data/users.json") as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    # Find the target user (support dict or list)
    user_ref_key = None
    user = None

    if isinstance(users, dict):
        if user_id in users:
            user = users[user_id]
            user_ref_key = user_id
        else:
            for uid, data in users.items():
                if data.get("id") == user_id:
                    user = data
                    user_ref_key = uid
                    break
    else:
        for idx, data in enumerate(users):
            if str(data.get("id")) == str(user_id):
                user = data
                user_ref_key = idx
                break

    if not user:
        return f"<h2>User ID {user_id} not found</h2>", 404

    # ✅ Update fields safely
    user["balance"] = float(request.form.get("balance", user.get("balance", 0)))
    user["profit"] = float(request.form.get("profit", user.get("profit", 0)))
    user["kyc_status"] = request.form.get("kyc_status", user.get("kyc_status", "Pending"))

    # Save back to file
    if isinstance(users, dict):
        users[user_ref_key] = user
    else:
        users[user_ref_key] = user

    with open("data/users.json", "w") as f:
        json.dump(users, f, indent=4)

    flash("User updated successfully!", "success")
    return redirect(url_for("admin_view_user", user_id=user_id))

@app.route("/admin/user/<user_id>/delete", methods=["POST"])
def admin_delete_user(user_id):
    # load users.json
    try:
        with open(USERS_FILE) as f:
            users = json.load(f)
    except:
        users = {}

    # remove user if exists
    if user_id in users:
        users.pop(user_id)

        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)

    # back to users list
    return redirect(url_for("admin_users"))

@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("email")
    if not email:
        return redirect(url_for("signup"))

    if request.method == "POST":
        entered_code = request.form["code"]
        if entered_code == users[email]["code"]:
            users[email]["verified"] = True
            flash("✅ Email verified successfully!")
            return redirect(url_for("login"))
        else:
            flash("❌ Invalid code. Please try again.")

    return render_template("verify.html", email=email)

@app.route("/resend")
def resend():
    email = session.get("email")
    if not email:
        return "No email found", 400

    new_code = str(random.randint(100000, 999999))
    users[email]["code"] = new_code
    html = build_brand_email_html(
        title="Your New Verification Code",
        code=new_code,
        purpose_note="Here’s a fresh code to continue verifying your email."
    )
    send_email(email, "New Verification Code — InvestCryptoView", html)

    send_email(email, "Your New Verification Code", f"<h2>Your new code is {new_code}</h2>")

    # Just return a simple OK response so JS fetch() doesn't reload
    return "OK"

# ======================
# LOGIN + PASSWORD RESET
# ======================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users.get(email)

        # Email not found
        if not user:
            return render_template("login.html", error="Email not found", user=None)

        # Password incorrect
        if user.get("password") != password:
            return render_template("login.html", error="Incorrect password", user=None)

        # Not verified yet
        if not user.get("verified"):
            session["email"] = email
            return redirect(url_for("verify"))

        # Successful login:
        session["email"] = email
        session["username"] = user.get("username", "Investor")

        # Redirect to dashboard instead of rendering
        return redirect(url_for("main"))

    # GET request → ALWAYS pass user=None to avoid UndefinedError
    return render_template("login.html", user=None)

@app.route("/main")
def main():
    username = session.get("username", "Investor")
    email    = session.get("email")

    # 🔹 load from the SAME users.json file the admin & trades use
    try:
        with open(USERS_FILE) as f:
            users_data = json.load(f)
    except:
        users_data = {}

    user = None
    user_id = None   # ✅ add this

    for uid, data in users_data.items():
        if data.get("email") == email:
            user = data
            user_id = uid   # ✅ capture the id
            # (no break, so the latest record for this email wins)

    if not user:
        user = {"balance": 0.0, "profit": 0.0}

    return render_template(
        "main.html",
        username=username,
        user=user,
        user_id=user_id   # ✅ now defined
    )

@app.route("/dashboard")
def dashboard():
    path = os.path.join(TEMPLATE_DIR, "dashboard.html")
    if not os.path.exists(path):
        return f"❌ File not found at {path}", 500
    return render_template("main.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"]

        if email not in users:
            flash("No account found with that email.")
            return render_template("forgot.html")

        code = str(random.randint(100000, 999999))
        users[email]["reset_code"] = code

        html = build_brand_email_html(
            title="Password Reset Code",
            code=code,
            purpose_note="Use this code to verify your password reset request on InvestCryptoView."
        )
        send_email(email, "Your Password Reset Code – InvestCryptoView", html)

        session["email"] = email
        return redirect(url_for("reset_verify"))

    return render_template("forgot.html")

# ---------- admin login ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Bad admin password", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

# ---------- admin dashboard (overview) ----------
@app.route("/admin")
@admin_required
def admin_dashboard():
    users_data = load_json(USERS_FILE)
    user_list = _ensure_users_list(users_data)
    deposits = load_json(DEPOSITS_FILE)
    total_users = len(user_list)
    total_deposits = sum([d.get("amount", 0) for d in deposits if d.get("status") == "approved"])
    total_profit = sum([u.get("profit", 0) for u in user_list])
    pending_deposits = [d for d in deposits if d.get("status") == "pending"]
    pending_kyc = [u for u in user_list if str(u.get("kyc_status", "")).lower() in ("pending", "submitted")]
    return render_template("admin_dashboard.html",
                           total_users=total_users,
                           total_deposits=total_deposits,
                           total_profit=total_profit,
                           pending_deposits=len(pending_deposits),
                           pending_kyc=len(pending_kyc))

# ---------- users list with search ----------
@app.route("/admin/users")
@admin_required
def admin_users():
    q = request.args.get("q", "").lower()

    try:
        with open("data/users.json") as f:
            raw = json.load(f)
    except Exception as e:
        print("❌ Error loading users.json:", e)
        raw = {}

    if not isinstance(raw, dict):
        print("❌ users.json root is not a dict. Got:", type(raw))
        return render_template("admin_users.html", users=[], q=q)

    users = []
    for user_id, data in raw.items():
        print(f"🔍 Checking user_id={user_id}, type={type(data)}")
        if isinstance(data, dict):
            uid = str(data.get("id", user_id))
            uname = data.get("full_name", "Unknown")
            if not q or q in uid.lower() or q in uname.lower():
                users.append({"id": uid, "name": uname})
        else:
            print(f"⚠ Skipping {user_id} because it's {data} ({type(data)})")

    return render_template("admin_users.html", users=users, q=q)

# ---------- edit user balance / profit (POST) ----------
@app.route("/admin/user/<user_id>/edit", methods=["POST"])
@admin_required
def admin_edit_user(user_id):
    user = find_user_by_id(user_id)
    if not user:
        return redirect(url_for("admin_users"))
    try:
        new_balance = float(request.form.get("balance", user.get("balance", 0)))
        new_profit = float(request.form.get("profit", user.get("profit", 0)))
    except:
        flash("Invalid numbers", "danger")
        return redirect(url_for("admin_view_user", user_id=user_id))
    user["balance"] = round(new_balance, 2)
    user["profit"] = round(new_profit, 2)
    update_user(user)
    log_admin("edit_user", f"{user_id} balance->{user['balance']} profit->{user['profit']}")
    flash("User updated", "success")
    return redirect(url_for("admin_view_user", user_id=user_id))

# ---------- deposits list ----------
@app.route("/admin/deposits")
@admin_required
def admin_deposits():
    deposits = load_json(DEPOSITS_FILE)
    return render_template("admin_deposits.html", deposits=deposits)

# ---------- approve / decline deposit ----------
@app.route("/admin/deposit/<int:dep_id>/approve", methods=["POST"])
@admin_required
def admin_deposit_approve(dep_id):
    deposits = load_json(DEPOSITS_FILE)
    for d in deposits:
        if int(d.get("id")) == int(dep_id):
            d["status"] = "approved"
            d["admin_action_time"] = datetime.utcnow().isoformat()
            # add to user's balance
            user = find_user_by_id(d.get("user_id"))
            if user:
                user["balance"] = round(user.get("balance", 0) + float(d.get("amount", 0)), 2)
                update_user(user)
            save_json(DEPOSITS_FILE, deposits)
            log_admin("deposit_approved", f"dep:{dep_id} by user:{d.get('user_id')}")
            flash("Deposit approved and balance updated", "success")
            return redirect(url_for("admin_deposits"))
    flash("Deposit not found", "warning")
    return redirect(url_for("admin_deposits"))

@app.route("/admin/deposit/<int:dep_id>/decline", methods=["POST"])
@admin_required
def admin_deposit_decline(dep_id):
    deposits = load_json(DEPOSITS_FILE)
    for d in deposits:
        if int(d.get("id")) == int(dep_id):
            d["status"] = "declined"
            d["admin_action_time"] = datetime.utcnow().isoformat()
            save_json(DEPOSITS_FILE, deposits)
            log_admin("deposit_declined", f"dep:{dep_id}")
            flash("Deposit declined", "info")
            return redirect(url_for("admin_deposits"))
    flash("Deposit not found", "warning")
    return redirect(url_for("admin_deposits"))

# ---------- KYC list and approve/decline ----------
@app.route("/admin/kyc")
@admin_required
def admin_kyc():
    users_data = load_json(USERS_FILE)
    user_list = _ensure_users_list(users_data)
    pending = [u for u in user_list if str(u.get("kyc_status", "")).lower() in ("pending", "submitted")]
    return render_template("admin_kyc.html", users=pending)

@app.route("/admin/kyc/<user_id>/approve", methods=["POST"])
@admin_required
def admin_kyc_approve(user_id):
    user = find_user_by_id(user_id)
    if not user:
        flash("User not found", "warning")
        return redirect(url_for("admin_kyc"))
    user["kyc_status"] = "verified"
    update_user(user)
    log_admin("kyc_approved", f"user:{user_id}")
    flash("KYC approved", "success")
    return redirect(url_for("admin_kyc"))

@app.route("/admin/kyc/<user_id>/decline", methods=["POST"])
@admin_required
def admin_kyc_decline(user_id):
    user = find_user_by_id(user_id)
    if not user:
        flash("User not found", "warning")
        return redirect(url_for("admin_kyc"))
    user["kyc_status"] = "rejected"
    update_user(user)
    log_admin("kyc_declined", f"user:{user_id}")
    flash("KYC declined", "info")
    return redirect(url_for("admin_kyc"))

# ------------------------------
# ADMIN BROADCAST EMAIL SYSTEM
# ------------------------------
@app.route("/admin/broadcast", methods=["GET", "POST"])
@admin_required
def admin_broadcast():
    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        message = (request.form.get("message") or "").strip()

        if not subject or not message:
            flash("Subject and message are required.", "danger")
            return redirect(url_for("admin_broadcast"))

        # Load all users
        try:
            with open(USERS_FILE) as f:   # USERS_FILE should be "data/users.json"
                users_data = json.load(f)
        except Exception:
            users_data = {}

        sent_to = 0

        # Send to every user
        for uid, u in users_data.items():
            username = u.get("username", "Investor")
            email = u.get("email")

            if not email:
                continue

            # Build nice HTML email (no OTP, no security tip)
            html = build_broadcast_email_html(username, subject, message)

            send_email(email, subject, html)
            sent_to += 1
            print(f"Broadcast email sent to {email}")

        flash(f"Broadcast email sent to {sent_to} users.", "success")
        return redirect(url_for("admin_dashboard"))

    # GET → show the broadcast form page
    return render_template("admin_broadcast.html")

@app.route("/admin/user/<user_id>")
@admin_required
def admin_view_user(user_id):
    # Load users from JSON
    try:
        with open(USERS_FILE) as f:
            users_data = json.load(f)
    except:
        users_data = {}

    # Find the user by id
    user = users_data.get(user_id)
    if not user:
        return f"User ID {user_id} not found", 404

    # Render the detail page you already use
    return render_template("admin_user_view.html", user=user, user_id=user_id)

# ---------- export users as CSV ----------
@app.route("/admin/export/users.csv")
@admin_required
def admin_export_users():
    users_data = load_json(USERS_FILE)
    user_list = _ensure_users_list(users_data)
    path = "data/users_export.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "email", "balance", "profit", "kyc_status", "last_ip"])
        for u in user_list:
            w.writerow([
                u.get("id"),
                u.get("full_name") or u.get("name"),
                u.get("email"),
                u.get("balance", 0),
                u.get("profit", 0),
                u.get("kyc_status", ""),
                u.get("last_ip", "") or u.get("location", "")
            ])
    return send_file(path, as_attachment=True)

@app.route("/reset_verify", methods=["GET", "POST"])
def reset_verify():
    email = session.get("email")
    if not email:
        return redirect(url_for("forgot"))

    if request.method == "POST":
        code = request.form["code"]
        if code == users[email].get("reset_code"):
            session["reset_verified"] = True
            return redirect(url_for("update_password"))
        else:
            return render_template("reset_verify.html", error="❌ Invalid code")

    return render_template("reset_verify.html")

@app.route("/reset_resend")
def reset_resend():
    email = session.get("email")
    if not email:
        return redirect(url_for("forgot"))

    new_code = str(random.randint(100000, 999999))
    users[email]["reset_code"] = new_code
    html = build_brand_email_html(
        title="New Password Reset Code",
        code=new_code,
        purpose_note="Here’s a new code to finish resetting your password."
    )
    send_email(email, "New Password Reset Code — InvestCryptoView", html)

    # ✅ Actually send the new reset code
    send_email(email, "New Password Reset Code", f"<h2>Your new reset code is {new_code}</h2>")

    return ("ok", 200)


@app.route("/update_password", methods=["GET", "POST"])
def update_password():
    email = session.get("email")
    if not email or not session.get("reset_verified"):
        return redirect(url_for("forgot"))

    if request.method == "POST":
        new_pass = request.form["new_password"]
        confirm = request.form["confirm_password"]

        if new_pass != confirm:
            return render_template("update_password.html", error="Passwords do not match")

        users[email]["password"] = new_pass
        session.pop("reset_verified", None)
        return render_template("login.html", message="✅ Password updated successfully!")

    return render_template("update_password.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)