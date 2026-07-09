import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, User, Transcript
from app.core.security import hash_password

engine = create_engine("sqlite:///./briefai.db")
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed():
    db = SessionLocal()
    # Create user
    user = db.query(User).filter(User.username == "testuser").first()
    if not user:
        user = User(username="testuser", email="test@example.com", hashed_password=hash_password("password"))
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create mock transcript
    t = db.query(Transcript).filter(Transcript.title == "Project Sync (Diarized)").first()
    if not t:
        t = Transcript(
            user_id=user.id,
            title="Project Sync (Diarized)",
            content="Hello everyone. Let's start the sync.\nYes, I am ready.\nGreat. Let's discuss the roadmap.\nI think we should prioritize the backend.",
            diarization_status="complete",
            diarized_segments=[
                {"start": 0.0, "end": 2.0, "text": "Hello everyone. Let's start the sync.", "speaker": "Speaker 1"},
                {"start": 2.5, "end": 4.0, "text": "Yes, I am ready.", "speaker": "Speaker 2"},
                {"start": 4.5, "end": 6.0, "text": "Great. Let's discuss the roadmap.", "speaker": "Speaker 1"},
                {"start": 6.5, "end": 9.0, "text": "I think we should prioritize the backend.", "speaker": "Speaker 2"}
            ]
        )
        db.add(t)
        db.commit()

seed()
print("Seeded.")
