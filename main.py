from flask import Flask, render_template, request, jsonify, make_response
from features.text_analyzer import text_analyzer_bp
from features.video_analyzer import video_analyzer_bp
from features.debate_with_ai import debate_bp
import sqlite3
import bcrypt
import jwt
import datetime
from functools import wraps
import logging

app = Flask(__name__)
SECRET_KEY = "your-secret-key"  # Replace with a secure key in production

# === Logging Setup ===
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === Database Setup ===
def init_db():
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = c.fetchone()
        
        if table_exists:
            c.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in c.fetchall()]
            expected_columns = ['id', 'email', 'username', 'password', 'avatar', 'created_at',
                              'email_notifications', 'debate_reminders', 'achievement_alerts',
                              'debate_difficulty', 'language_preference']
            if not all(col in columns for col in expected_columns):
                logger.warning("Users table schema is outdated. Adding missing columns.")
                for col in expected_columns:
                    if col not in columns:
                        if col == 'created_at':
                            c.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT '2025-05-10 00:00:00'")
                        elif col in ['email_notifications', 'debate_reminders', 'achievement_alerts']:
                            c.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
                        elif col == 'debate_difficulty':
                            c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT 'Beginner'")
                        elif col == 'language_preference':
                            c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT 'English'")
                conn.commit()
        else:
            c.execute("""CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                avatar TEXT DEFAULT 'default',
                created_at TEXT DEFAULT '2025-05-10 00:00:00',
                email_notifications INTEGER DEFAULT 0,
                debate_reminders INTEGER DEFAULT 0,
                achievement_alerts INTEGER DEFAULT 0,
                debate_difficulty TEXT DEFAULT 'Beginner',
                language_preference TEXT DEFAULT 'English'
            )""")
            conn.commit()
            logger.info("Users table created successfully")
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debate_stats'")
        if not c.fetchone():
            c.execute("""CREATE TABLE debate_stats (
                user_id INTEGER PRIMARY KEY,
                total_debates INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_points INTEGER DEFAULT 0,
                strengths TEXT,
                weaknesses TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            conn.commit()
            logger.info("Debate stats table created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
    finally:
        conn.close()

init_db()

# === Error Handlers ===
@app.errorhandler(404)
def not_found(error):
    logger.error(f"404 error: {str(error)}")
    return jsonify({"error": "Page not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

# === JWT Token Required Decorator ===
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            logger.warning("Profile access denied: Token is missing")
            return jsonify({"error": "Token is missing"}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            conn = sqlite3.connect("users.db")
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email = ?", (data["email"],))
            user = c.fetchone()
            conn.close()
            if not user:
                logger.warning("Profile access denied: User not found")
                return jsonify({"error": "User not found"}), 401
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            logger.warning("Profile access denied: Token has expired")
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            logger.warning("Profile access denied: Invalid token")
            return jsonify({"error": "Invalid token"}), 401
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500
    return decorated

# === Register Blueprints ===
app.register_blueprint(text_analyzer_bp)
app.register_blueprint(video_analyzer_bp)
app.register_blueprint(debate_bp, url_prefix='/debate')

# === Routes ===
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/create_new_room")
def create_new_room():
    return render_template("create_new_room.html")

@app.route("/login_signup")
def login_signup():
    return render_template("login_signup.html")

@app.route("/profile")
@token_required
def profile():
    try:
        token = request.cookies.get("token")
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = data["email"]
        
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        
        # Get user info
        c.execute("SELECT username, avatar, created_at FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        
        if not user:
            logger.warning(f"No user found with email: {email}")
            return jsonify({"error": "User not found"}), 401
            
        # Get debate stats
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        user_id = c.fetchone()[0]
        c.execute("SELECT * FROM debate_stats WHERE user_id = ?", (user_id,))
        stats = c.fetchone()
        
        user_data = {
            "username": user[0],
            "avatar": user[1],
            "created_at": user[2],
            "stats": {
                "total_debates": stats[1] if stats else 0,
                "wins": stats[2] if stats else 0,
                "losses": stats[3] if stats else 0,
                "total_points": stats[4] if stats else 0,
                "strengths": stats[5] if stats else "Complete debates to identify strengths",
                "weaknesses": stats[6] if stats else "Complete debates to identify areas to improve"
            }
        }
        
        logger.info("Profile route accessed successfully")
        return render_template("profile.html", user=user_data)
    except Exception as e:
        logger.error(f"Error rendering profile page: {str(e)}")
        return jsonify({"error": "Failed to render profile page"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        logger.debug(f"Signup request data: {data}")
        email = data.get("email")
        username = data.get("username")
        password = data.get("password")
        confirm_password = data.get("confirm_password")

        if not all([email, username, password, confirm_password]):
            logger.warning("Missing fields in signup request")
            return jsonify({"error": "All fields are required"}), 400
        if password != confirm_password:
            logger.warning("Password mismatch in signup request")
            return jsonify({"error": "Passwords do not match"}), 400

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        created_at = datetime.datetime.utcnow().isoformat()  # Store signup time in ISO format
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)",
                  (email, username, hashed, created_at))
        conn.commit()
        token = jwt.encode({
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, SECRET_KEY, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        response = make_response(jsonify({"message": "Signup successful"}))
        response.set_cookie("token", token, httponly=True)
        logger.info(f"User {email} signed up successfully")
        return response
    except sqlite3.IntegrityError as e:
        logger.error(f"Database integrity error: {str(e)}")
        return jsonify({"error": "Email or username already exists"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in signup: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/api/login", methods=["POST"])
def login():
    try:
        logger.debug("Received login request")
        data = request.get_json(force=True)
        logger.debug(f"Login request data: {data}")
        email = data.get("email")
        password = data.get("password")
        
        if not email or not password:
            logger.warning("Missing email or password in login request")
            return jsonify({"error": "Email and password are required"}), 400

        logger.debug("Connecting to database")
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        logger.debug(f"Querying user with email: {email}")
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        logger.debug(f"User query result: {user}")
        
        if not user:
            logger.warning(f"No user found with email: {email}")
            conn.close()
            return jsonify({"error": "Invalid credentials"}), 401

        logger.debug("Checking password")
        stored_password = user[3]
        if not isinstance(stored_password, (str, bytes)):
            logger.error(f"Invalid password format in database for user {email}: {stored_password}")
            conn.close()
            return jsonify({"error": "Internal server error"}), 500

        if isinstance(stored_password, str):
            stored_password = stored_password.encode("utf-8")
        if not bcrypt.checkpw(password.encode("utf-8"), stored_password):
            logger.warning(f"Password mismatch for user {email}")
            conn.close()
            return jsonify({"error": "Invalid credentials"}), 401

        logger.debug("Generating JWT token")
        token = jwt.encode({
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, SECRET_KEY, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        logger.debug("Setting response with token")
        response = make_response(jsonify({"message": "Login successful"}))
        response.set_cookie("token", token, httponly=True)
        logger.info(f"User {email} logged in successfully")
        conn.close()
        return response
    except ValueError as ve:
        logger.error(f"Error parsing JSON in login request: {str(ve)}")
        return jsonify({"error": "Invalid request data"}), 400
    except sqlite3.Error as se:
        logger.error(f"Database error in login: {str(se)}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in login: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/api/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"message": "Logged out"}))
    response.delete_cookie("token")
    logger.info("User logged out")
    return response

@app.route("/api/check_auth", methods=["GET"])
def check_auth():
    try:
        token = request.cookies.get("token")
        if not token:
            return jsonify({"authenticated": False})
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT email, username, avatar, created_at FROM users WHERE email = ?", (data["email"],))
        user = c.fetchone()
        conn.close()
        if user:
            return jsonify({
                "authenticated": True,
                "email": user[0],
                "username": user[1],
                "avatar": user[2],
                "created_at": user[3]
            })
        return jsonify({"authenticated": False})
    except Exception as e:
        logger.error(f"Error in check_auth: {str(e)}")
        return jsonify({"authenticated": False})

@app.route("/api/update_avatar", methods=["POST"])
@token_required
def update_avatar():
    try:
        data = request.get_json()
        avatar = data.get("avatar")
        if not avatar:
            logger.warning("Missing avatar in update request")
            return jsonify({"error": "Avatar is required"}), 400

        token = request.cookies.get("token")
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = decoded["email"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("UPDATE users SET avatar = ? WHERE email = ?", (avatar, email))
        conn.commit()
        logger.info(f"User {email} updated avatar to {avatar}")
        return jsonify({"message": "Avatar updated successfully"})
    except Exception as e:
        logger.error(f"Error updating avatar: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/api/update_preferences", methods=["POST"])
@token_required
def update_preferences():
    try:
        data = request.get_json()
        email_notifications = 1 if data.get("emailNotifications") else 0
        debate_reminders = 1 if data.get("debateReminders") else 0
        achievement_alerts = 1 if data.get("achievementAlerts") else 0
        debate_difficulty = data.get("debateDifficulty", "Beginner")
        language_preference = data.get("languagePreference", "English")

        token = request.cookies.get("token")
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = decoded["email"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("""UPDATE users SET email_notifications = ?, debate_reminders = ?, 
                     achievement_alerts = ?, debate_difficulty = ?, language_preference = ?
                     WHERE email = ?""",
                  (email_notifications, debate_reminders, achievement_alerts,
                   debate_difficulty, language_preference, email))
        conn.commit()
        logger.info(f"User {email} updated preferences")
        return jsonify({"message": "Preferences updated successfully"})
    except Exception as e:
        logger.error(f"Error updating preferences: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/friend_vs_friend")
def friend_vs_friend():
    return render_template("friend_vs_friend.html")

@app.route("/api/get_debate_stats", methods=["GET"])
@token_required
def get_debate_stats():
    try:
        token = request.cookies.get("token")
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = decoded["email"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        # First get the user ID
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_id = user[0]
        # Get the stats
        c.execute("SELECT * FROM debate_stats WHERE user_id = ?", (user_id,))
        stats = c.fetchone()
        if stats:
            stats_data = {
                "total_debates": stats[1],
                "wins": stats[2],
                "losses": stats[3],
                "total_points": stats[4],
                "strengths": stats[5],
                "weaknesses": stats[6]
            }
        else:
            # Return defaults if no stats exist yet
            stats_data = {
                "total_debates": 0,
                "wins": 0,
                "losses": 0,
                "total_points": 0,
                "strengths": "",
                "weaknesses": ""
            }
        return jsonify(stats_data)
    except Exception as e:
        logger.error(f"Error getting debate stats: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/api/update_debate_stats", methods=["POST"])
@token_required
def update_debate_stats():
    try:
        data = request.get_json()
        token = request.cookies.get("token")
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = decoded["email"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        # First get the user ID
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_id = user[0]
        # Check if stats already exist
        c.execute("SELECT strengths, weaknesses FROM debate_stats WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        exists = row is not None
        prev_strengths = row[0] if exists else ""
        prev_weaknesses = row[1] if exists else ""
        new_strengths = data.get("strengths", "")
        new_weaknesses = data.get("weaknesses", "")
        strengths_to_set = new_strengths if new_strengths else prev_strengths
        weaknesses_to_set = new_weaknesses if new_weaknesses else prev_weaknesses
        if exists:
            # Update existing stats
            c.execute("""UPDATE debate_stats SET 
                        total_debates = total_debates + ?,
                        wins = wins + ?,
                        losses = losses + ?,
                        total_points = total_points + ?,
                        strengths = ?,
                        weaknesses = ?
                        WHERE user_id = ?""",
                     (data.get("total_debates", 0),
                     data.get("wins", 0),
                     data.get("losses", 0),
                     data.get("total_points", 0),
                     strengths_to_set,
                     weaknesses_to_set,
                     user_id))
        else:
            # Insert new stats
            c.execute("""INSERT INTO debate_stats 
                        (user_id, total_debates, wins, losses, total_points, strengths, weaknesses)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (user_id,
                     data.get("total_debates", 0),
                     data.get("wins", 0),
                     data.get("losses", 0),
                     data.get("total_points", 0),
                     strengths_to_set,
                     weaknesses_to_set))
        conn.commit()
        return jsonify({"message": "Debate stats updated successfully"})
    except Exception as e:
        logger.error(f"Error updating debate stats: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html")

@app.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        # Join users and debate_stats, order by total_points desc
        c.execute("""
            SELECT u.username, u.avatar, ds.total_debates, ds.wins, ds.losses, ds.total_points
            FROM users u
            LEFT JOIN debate_stats ds ON u.id = ds.user_id
            ORDER BY ds.total_points DESC NULLS LAST, ds.wins DESC NULLS LAST
        """)
        rows = c.fetchall()
        leaderboard = []
        for row in rows:
            leaderboard.append({
                "username": row[0],
                "avatar": row[1] or 'default',
                "total_debates": row[2] or 0,
                "wins": row[3] or 0,
                "losses": row[4] or 0,
                "total_points": row[5] or 0
            })
        return jsonify(leaderboard)
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    app.run(debug=True)