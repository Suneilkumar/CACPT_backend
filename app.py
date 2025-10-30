from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, Index
from datetime import datetime
import os
import json
from datetime import datetime, timezone
import pytz  # pip install pytz

# -------------------------------------------------------
# App setup
# -------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://sunilbasudeo.com", "https://www.sunilbasudeo.com", "http://localhost:3000"]}})

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'questions.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------------------------------------------
# Model
# -------------------------------------------------------
class Question(db.Model):
    __tablename__ = "question"
    __table_args__ = (Index("ix_question_chapter", "chapter"),)

    id = db.Column(db.Integer, primary_key=True)
    difficulty = db.Column(db.String(50))
    subject = db.Column(db.String(100))
    chapter = db.Column(db.String(150))
    hint = db.Column(db.Text)
    explanation = db.Column(db.Text)
    featured = db.Column(db.Text)     # JSON list (stringified)
    hot = db.Column(db.Boolean, default=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON list (stringified)
    answer = db.Column(db.Integer)
    topic = db.Column(db.String(150))
    normaltime = db.Column(db.String(50))
    giventime = db.Column(db.String(50))

    def serialize(self):
        return {
            "id": self.id,
            "difficulty": self.difficulty,
            "subject": self.subject,
            "chapter": self.chapter,
            "hint": self.hint,
            "explanation": self.explanation,
            "featured": json.loads(self.featured or "[]"),
            "hot": self.hot,
            "question_text": self.question_text,
            "options": json.loads(self.options or "[]"),
            "answer": self.answer,
            "topic": self.topic,
            "normaltime": self.normaltime,
            "giventime": self.giventime,
        }

class QuizResult(db.Model):
    __tablename__ = "quiz_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255))
    question_id = db.Column(db.String(64))
    question_text = db.Column(db.Text)
    submitted_answer_index = db.Column(db.Integer)
    submitted_answer_text = db.Column(db.Text)
    correct_answer_index = db.Column(db.Integer)
    correct_answer_text = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)
    user_action = db.Column(db.String(64))
    time_taken = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)
    meta = db.Column(db.JSON)

    def serialize(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "question_id": self.question_id,
            "question_text": self.question_text,
            "submitted_answer_index": self.submitted_answer_index,
            "submitted_answer_text": self.submitted_answer_text,
            "correct_answer_index": self.correct_answer_index,
            "correct_answer_text": self.correct_answer_text,
            "is_correct": self.is_correct,
            "user_action": self.user_action,
            "time_taken": self.time_taken,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "meta": self.meta,
        }

# -------------------------------------------------------
# Routes
# -------------------------------------------------------

@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from Flask + SQLite (Question DB)")
    

def to_local_time(utc_dt, tz_name="Asia/Kolkata"):
    """Convert UTC datetime to local timezone and return date, time strings."""
    if not utc_dt:
        return None, None
    local_tz = pytz.timezone(tz_name)
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(local_tz)
    date = local_dt.strftime("%Y-%m-%d")
    time = local_dt.strftime("%H:%M:%S")
    return date, time



# Add a new question
@app.route("/api/questions", methods=["POST"])
def add_question():
    data = request.get_json()
    q = Question(
        difficulty=data.get("difficulty"),
        subject=data.get("subject"),
        chapter=data.get("chapter"),
        hint=data.get("hint"),
        explanation=data.get("explanation"),
        featured=json.dumps(data.get("featured", [])),
        hot=data.get("hot", False),
        question_text=data.get("question_text"),
        options=json.dumps(data.get("options", [])),
        answer=data.get("answer"),
        topic=data.get("topic"),
        normaltime=data.get("normaltime"),
        giventime=data.get("giventime"),
    )
    db.session.add(q)
    db.session.commit()
    return jsonify(q.serialize()), 201

@app.route("/api/questions/bulk", methods=["POST"])
def bulk_add_questions():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify(error="Expected a JSON array of questions"), 400

    added, skipped = 0, 0
    for item in data:
        q = Question(
            difficulty=item.get("difficulty"),
            subject=item.get("subject"),
            chapter=item.get("chapter"),
            hint=item.get("hint"),
            explanation=item.get("explanation"),
            featured=json.dumps(item.get("featured", [])),
            hot=item.get("hot", False),
            question_text=item.get("question_text"),
            options=json.dumps(item.get("options", [])),
            answer=item.get("answer"),
            topic=item.get("topic"),
            normaltime=item.get("normaltime"),
            giventime=item.get("giventime"),
        )
        db.session.add(q)
        added += 1

    db.session.commit()
    return jsonify({"added": added, "skipped": skipped}), 201


# Get all questions
@app.route("/api/questions", methods=["GET"])
def get_questions():
    questions = Question.query.all()
    return jsonify([q.serialize() for q in questions])

# Get one question by ID
@app.route("/api/questions/<int:id>", methods=["GET"])
def get_question(id):
    q = Question.query.get_or_404(id)
    return jsonify(q.serialize())

# Search questions by chapter / subject / difficulty
@app.route("/api/questions/search", methods=["GET"])
def search_questions():
    chapter_q = request.args.get("chapter", type=str)
    subject_q = request.args.get("subject", type=str)
    difficulty_q = request.args.get("difficulty", type=str)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    query = Question.query

    # case-insensitive filtering
    if chapter_q:
        pattern = f"%{chapter_q}%"
        query = query.filter(func.lower(Question.chapter).like(func.lower(pattern)))

    if subject_q:
        pattern = f"%{subject_q}%"
        query = query.filter(func.lower(Question.subject).like(func.lower(pattern)))

    if difficulty_q:
        query = query.filter(Question.difficulty == difficulty_q)

    paginated = query.order_by(Question.id).paginate(page=page, per_page=per_page, error_out=False)
    items = [item.serialize() for item in paginated.items]

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "items": items
    })
    
@app.route("/api/quiz_results", methods=["POST"])
def save_quiz_results():
    data = request.get_json()
    user_id = data.get("user_id")
    email = data.get("email")
    results = data.get("results", [])

    if not user_id or not results:
        return jsonify({"error": "Missing user_id or results"}), 400

    saved = []
    for r in results:
        result = QuizResult(
            user_id=user_id,
            email=email,
            question_id=r.get("questionId"),
            question_text=r.get("questionText"),
            submitted_answer_index=r.get("submittedAnswerIndex"),
            submitted_answer_text=r.get("submittedAnswerText"),
            correct_answer_index=r.get("correctAnswerIndex"),
            correct_answer_text=r.get("correctAnswerText"),
            is_correct=r.get("isCorrect", False),
            user_action=r.get("userAction", "unanswered"),
            time_taken=r.get("timeTaken"),
            timestamp=datetime.utcnow(),
            meta=r.get("meta"),
        )
        db.session.add(result)
        saved.append(result)

    db.session.commit()
    return jsonify({"status": "success", "saved": len(saved)}), 201
    
from collections import defaultdict
from sqlalchemy import func

@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    """
    Returns top 10 users ranked by accuracy (% correct answers),
    optionally filtered by subject.
    Filters: min 3 attempts, min 40% accuracy.
    Example: /api/leaderboard?subject=Accounting
    """
    try:
        subject_q = request.args.get("subject", type=str)

        # Base query
        query = QuizResult.query

        # Filter by subject (inside JSON field)
        if subject_q:
            query = query.filter(
                func.lower(QuizResult.meta["subject"].astext) == subject_q.lower()
            )

        results = query.all()

        # Aggregate user stats
        stats = defaultdict(lambda: {"attempts": 0, "correct": 0})
        emails = {}

        for r in results:
            uid = r.user_id
            stats[uid]["attempts"] += 1
            if r.is_correct:
                stats[uid]["correct"] += 1
            emails[uid] = r.email or "unknown@example.com"

        # Build leaderboard list
        leaderboard = []
        for uid, s in stats.items():
            total = s["attempts"]
            correct = s["correct"]
            accuracy = (correct / total * 100) if total > 0 else 0

            # Apply filters: min 3 attempts and 40% accuracy
            if total < 3 or accuracy < 40:
                continue

            leaderboard.append({
                "userId": uid,
                "email": emails.get(uid, "unknown@example.com"),
                "totalAttempts": total,
                "avgAccuracy": round(accuracy, 1)
            })

        # Sort and limit
        leaderboard.sort(key=lambda x: x["avgAccuracy"], reverse=True)
        top_10 = leaderboard[:10]

        # Response
        meta_info = (
            f"Top 10 users for subject '{subject_q}'" if subject_q else "Top 10 users overall"
        )
        return jsonify({
            "meta": meta_info,
            "subject": subject_q,
            "leaderboard": top_10,
            "count": len(leaderboard)
        })

    except Exception as e:
        print("❌ Leaderboard generation error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/quiz_summary", methods=["GET"])
def quiz_summary():
    """
    Returns aggregated quiz results per user, per day, with subjects and chapters.
    Query params:
      - user_id (optional)
      - start_date (optional)
      - end_date (optional)
    """
    user_filter = request.args.get("user_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = QuizResult.query
    if user_filter:
        query = query.filter(QuizResult.user_id == user_filter)

    results = query.order_by(QuizResult.timestamp).all()

    summary_map = defaultdict(lambda: {
        "user_id": None,
        "email": None,
        "date": None,
        "last_attempt_time": None,
        "total_attempts": 0,
        "total_correct": 0,
        "total_questions": 0,
        "total_time": 0.0,
        "subjects": {}
    })

    for r in results:
        date, time = to_local_time(r.timestamp)
        if not date:
            continue

        key = f"{r.user_id}_{date}"
        meta = r.meta
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        subj = (meta or {}).get("subject", "Unknown Subject")
        chap = (meta or {}).get("chapter", "Unknown Chapter")
    	
        time_taken = r.time_taken or 0.0

        day = summary_map[key]
        day["user_id"] = r.user_id
        day["email"] = r.email
        day["date"] = date
        current_time = str(time or "00:00:00")
        last_time = str(day.get("last_attempt_time") or "00:00:00")

        day["last_attempt_time"] = max(current_time, last_time)
        day["total_attempts"] += 1
        day["total_questions"] += 1
        day["total_time"] += time_taken
        if r.is_correct:
            day["total_correct"] += 1

        # Subject grouping
        subjects = day["subjects"]
        if subj not in subjects:
            subjects[subj] = {
                "subject": subj,
                "total_attempts": 0,
                "total_correct": 0,
                "total_time": 0.0,
                "chapters": {}
            }
        s = subjects[subj]
        s["total_attempts"] += 1
        s["total_time"] += time_taken
        if r.is_correct:
            s["total_correct"] += 1

        # Chapter grouping
        chapters = s["chapters"]
        if chap not in chapters:
            chapters[chap] = {
                "chapter": chap,
                "attempts": 0,
                "correct": 0,
                "total_time": 0.0,
                "last_attempt_time": time
            }
        ch = chapters[chap]
        ch["attempts"] += 1
        ch["total_time"] += time_taken
        if r.is_correct:
            ch["correct"] += 1
        if time > ch["last_attempt_time"]:
            ch["last_attempt_time"] = time

    # Compute accuracy and averages
    summaries = []
    for day in summary_map.values():
        day["accuracy"] = round(day["total_correct"] / day["total_questions"] * 100, 1)
        day["avg_time_sec"] = round(day["total_time"] / day["total_questions"], 2)

        for s in day["subjects"].values():
            s["accuracy"] = round(s["total_correct"] / s["total_attempts"] * 100, 1)
            s["avg_time_sec"] = round(s["total_time"] / s["total_attempts"], 2)

            for ch in s["chapters"].values():
                ch["accuracy"] = round(ch["correct"] / ch["attempts"] * 100, 1)
                ch["avg_time_sec"] = round(ch["total_time"] / ch["attempts"], 2)

            s["chapters"] = list(s["chapters"].values())

        day["subjects"] = list(day["subjects"].values())
        summaries.append(day)

    return jsonify(summaries)

@app.route("/api/quiz_results/<user_id>", methods=["GET"])
def get_quiz_results(user_id):
    results = QuizResult.query.filter_by(user_id=user_id).order_by(QuizResult.timestamp.desc()).all()
    return jsonify([r.serialize() for r in results])

@app.route("/api/quiz_results", methods=["GET"])
def get_all_quiz_results():
    """
    Returns all quiz results across all users, ordered by most recent first.
    Optional query params:
      - limit (int): number of records to return
      - subject (str): filter by subject
      - user (str): filter by user_id or email
    """
    limit = request.args.get("limit", type=int)
    subject_q = request.args.get("subject", type=str)
    user_q = request.args.get("user", type=str)

    query = QuizResult.query

    if subject_q:
        query = query.filter(func.lower(QuizResult.meta["subject"].astext) == subject_q.lower())

    if user_q:
        query = query.filter(
            (QuizResult.user_id.ilike(f"%{user_q}%")) |
            (QuizResult.email.ilike(f"%{user_q}%"))
        )

    query = query.order_by(QuizResult.timestamp.desc())

    if limit:
        results = query.limit(limit).all()
    else:
        results = query.all()

    return jsonify([r.serialize() for r in results])



# -------------------------------------------------------
# Initialize DB
# -------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)
