from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, Index
import os
import json

# -------------------------------------------------------
# App setup
# -------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://sunilbasudeo.com"]}})

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

# -------------------------------------------------------
# Routes
# -------------------------------------------------------

@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from Flask + SQLite (Question DB)")

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

# -------------------------------------------------------
# Initialize DB
# -------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)
