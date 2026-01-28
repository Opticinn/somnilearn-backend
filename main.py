from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="InsomDetek API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SleepData(BaseModel):
    total_screen_time_ms: int
    evening_screen_time_ms: int
    app_switching_freq: int
    blue_light_duration_ms: int
    sleep_quality: int
    stress_level: int
    journal_text: str

@app.get("/")
def read_root():
    return {"message": "✅ SomniLearn Backend Berjalan!"}

# 🔥 INI YANG BENAR - Tambahkan ": SleepData" setelah parameter
@app.post("/predict_insomnia")
def predict_insomnia(data: SleepData):  # ← PERHATIKAN TANDA TITIK DUA SETELAH "data"
    screen_hours = data.evening_screen_time_ms / 3_600_000
    risk = min(0.95, (screen_hours * 0.4 + (data.stress_level / 10) * 0.6))

    if screen_hours > 2:
        rec = "Kurangi layar setelah jam 21.00"
    elif data.stress_level > 7:
        rec = "Coba teknik napas 4-7-8 sebelum tidur"
    else:
        rec = "Pertahankan rutinitas tidur konsisten"

    return {
        "insomnia_risk": round(risk, 2),
        "recommendation": rec
    }