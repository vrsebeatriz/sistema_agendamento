from fastapi import FastAPI
from app.database import create_db_and_tables
from app.models import user, service, appointment
from app.routers import users
from app.routers import auth
from app.routers import services
from app.routers import appointments
from app.routers import business_hours, time_blocks
from app.routers import dashboard

app = FastAPI()
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(services.router)
app.include_router(appointments.router)
app.include_router(business_hours.router)
app.include_router(time_blocks.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message": "API sistema_agendamento funcionando 🚀"}
