from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import CORS_ORIGINS, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME
from .database import Base, engine, SessionLocal
from .models import User
from .security import hash_password
from .routers import auth, users, interview, questions, dataset, meta, analytics


def seed_admin():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == ADMIN_EMAIL.lower()).first():
            db.add(User(name=ADMIN_NAME, email=ADMIN_EMAIL.lower(), hashed_password=hash_password(ADMIN_PASSWORD), role="admin"))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed_admin()
    yield
    from .services.nlp import store
    store.flush()


app = FastAPI(title="AI HR Interview Chatbot API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (auth, users, interview, questions, dataset, meta, analytics):
    app.include_router(r.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "docs": "/docs"}
