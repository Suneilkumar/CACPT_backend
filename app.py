from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, Index
from datetime import datetime
import os
import json
from datetime import datetime, timezone
import pytz  # pip install pytz
import requests
import time
from dotenv import load_dotenv
from openai import OpenAI
import re

load_dotenv()  # reads .env and loads variables into the environment


# -------------------------------------------------------
# App setup
# -------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://sunilbasudeo.com", "https://www.sunilbasudeo.com", "http://localhost:3000"]}})

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'questions.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
openai_apikey = os.getenv("OPENAI_APIKEY")
openai_client = OpenAI(api_key=openai_apikey)

def get_clerk_user(user_id):
    """Fetch a user's profile info from Clerk REST API."""
    url = f"https://api.clerk.dev/v1/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️ Clerk fetch failed for {user_id}: {response.status_code}")
        return None

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

class TeachingNote(db.Model):
    __tablename__ = "teaching_notes"
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(150), nullable=False)
    topic = db.Column(db.String(200))
    title = db.Column(db.String(250))
    reading_time = db.Column(db.String(50))
    notes = db.Column(db.Text)
    summary = db.Column(db.Text)
    questions = db.Column(db.JSON)  # stores full TF quiz data (answer + explanation)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "topic": self.topic,
            "title": self.title,
            "reading_time": self.reading_time,
            "notes": self.notes,
            "summary": self.summary,
            "questions": self.questions or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
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
    Returns top users ranked by accuracy (% correct answers),
    optionally filtered by subject.
    Works with SQLite, handles null meta values safely.
    """
    from collections import defaultdict
    import json, time

    try:
        subject_q = request.args.get("subject", type=str)
        subject_q_lower = subject_q.lower() if subject_q else None

        # Always fetch all results first
        results = QuizResult.query.all()

        # Filter in Python since SQLite can't query JSON fields
        if subject_q_lower:
            filtered = []
            for r in results:
                meta = r.meta
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                elif meta is None:
                    meta = {}
                if isinstance(meta, dict) and meta.get("subject", "").lower() == subject_q_lower:
                    filtered.append(r)
            results = filtered

        # Aggregate stats
        stats = defaultdict(lambda: {"attempts": 0, "correct": 0})
        emails = {}

        for r in results:
            uid = r.user_id
            stats[uid]["attempts"] += 1
            if r.is_correct:
                stats[uid]["correct"] += 1
            emails[uid] = r.email or "unknown@example.com"

        leaderboard = []
        for uid, s in stats.items():
            total = s["attempts"]
            correct = s["correct"]
            accuracy = (correct / total * 100) if total > 0 else 0
            if total < 3 or accuracy < 40:
                continue
            leaderboard.append({
                "userId": uid,
                "email": emails.get(uid, "unknown@example.com"),
                "totalAttempts": total,
                "avgAccuracy": round(accuracy, 1)
            })

        leaderboard.sort(key=lambda x: x["avgAccuracy"], reverse=True)
        top_users = leaderboard[:50]

        # Enrich with Clerk (non-fatal)
        enriched = []
        for entry in top_users:
            try:
                clerk_user = get_clerk_user(entry["userId"])
                if clerk_user:
                    entry["fullName"] = (
                        f"{clerk_user.get('first_name', '')} {clerk_user.get('last_name', '')}".strip()
                        or entry["email"]
                    )
                    entry["imageUrl"] = f"{clerk_user.get('image_url')}?t={int(time.time())}"
                else:
                    entry["fullName"] = entry["email"]
                    entry["imageUrl"] = f"https://api.dicebear.com/7.x/identicon/svg?seed={entry['email']}"
            except Exception as e:
                print(f"⚠️ Clerk fetch failed for {entry['userId']}: {e}")
                entry["fullName"] = entry["email"]
                entry["imageUrl"] = f"https://api.dicebear.com/7.x/identicon/svg?seed={entry['email']}"
            enriched.append(entry)

        meta_info = (
            f"Top users for subject '{subject_q}'"
            if subject_q else "Top users overall"
        )

        return jsonify({
            "meta": meta_info,
            "subject": subject_q,
            "leaderboard": enriched,
            "count": len(enriched)
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

@app.route("/api/generate_notes", methods=["POST"])
def generate_notes():
    data = request.get_json()
    subject = data.get("subject", "Negotiable Instruments Act")
    topic = data.get("topic", "Promissory Note")

    print(f"📩 Request received → Subject: {subject}, Topic: {topic}")

    # 🧠 ADD THIS CACHING CHECK RIGHT HERE
    existing = TeachingNote.query.filter_by(subject=subject, topic=topic).first()
    if existing:
        print("⚡ Cached note found — skipping OpenAI call")
        return jsonify(existing.serialize())

    prompt = f"""
    Generate explanatory student notes for CA Foundation – {subject}.
    Topic: {topic}.

    Include the following sections:
    ### Title:
    ### Reading Time: (estimate in minutes)
    ### Notes:
    ### True or False Questions:
    Create exactly 6 True/False questions with:
    - The statement
    - Correct answer (True or False)
    - A one-line explanation
    ### Summary:
    """

    print("⏳ Sending prompt to OpenAI API...")

    # ✅ New API call syntax
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.choices[0].message.content

    print("\n✅ Raw response from API:\n")
    print(content)
    print("\n---------------------------------\n")

    def extract(header):
        match = re.search(rf"### {header}:(.*?)(?=###|\Z)", content, re.S)
        return match.group(1).strip() if match else ""

    title = extract("Title")
    reading_time = extract("Reading Time")
    notes = extract("Notes")
    summary = extract("Summary")

    # Extract True/False questions
    # Extract True/False questions
    tf_section = extract("True or False Questions")
    if not tf_section:
        print("⚠️ No TF section found in response")
        questions = []
    else:
        questions = []
        current_q = {}
        lines = [ln.strip() for ln in tf_section.splitlines() if ln.strip()]
        for line in lines:
            try:
                if re.match(r"^\d+\.", line):
                    if current_q:
                        questions.append(current_q)
                    current_q = {"statement": re.sub(r"^\d+\.\s*", "", line).strip()}
                elif re.match(r"^-?\s*(True|False)\b", line, re.I):
                    current_q["answer"] = "true" in line.lower()
                elif line.startswith("-"):
                    current_q["explanation"] = re.sub(r"^-\s*", "", line).strip()
                else:
                    # unrecognised line: append to current explanation
                    if "explanation" in current_q:
                        current_q["explanation"] += " " + line
            except Exception as e:
                print(f"⚠️ Skipped line (parse issue): {line} -> {e}")

        if current_q:
            questions.append(current_q)

    print(f"🧠 Parsed {len(questions)} True/False questions")
    
    # ✅ Save to DB
    try:
        note = TeachingNote(
            subject=subject,
            topic=topic,
            title=title,
            reading_time=reading_time,
            notes=notes,
            summary=summary,
            questions=questions,
        )
        db.session.add(note)
        db.session.commit()
        print(f"💾 Saved TeachingNote ID: {note.id}")
    except Exception as e:
        db.session.rollback()
        print(f"❌ DB Error: {e}")

    for i, q in enumerate(questions, 1):
        print(f"{i}. {q['statement']} → {q['answer']} ({q['explanation']})")

    print("\n✅ Data parsing complete. Returning JSON response.\n")

    return jsonify({
        "id": note.id if 'note' in locals() else None,
        "subject": subject,
        "topic": topic,
        "title": title,
        "reading_time": reading_time,
        "notes": notes,
        "questions": questions,
        "summary": summary
    })

@app.route("/api/get_notes", methods=["GET"])
def get_notes():
    subject = request.args.get("subject")
    topic = request.args.get("topic")

    if not subject or not topic:
        return jsonify({"error": "subject and topic are required"}), 400

    note = TeachingNote.query.filter_by(subject=subject, topic=topic).first()

    if not note:
        return jsonify({"message": "No notes found for this topic"}), 404

    return jsonify(note.serialize())

@app.route("/api/all_notes", methods=["GET"])
def get_all_notes():
    notes = TeachingNote.query.order_by(TeachingNote.created_at.desc()).all()
    return jsonify([n.serialize() for n in notes])

# -------------------------------------------------------
# Initialize DB
# -------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)


