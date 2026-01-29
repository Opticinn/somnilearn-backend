# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI(title="SomniLearn Backend")

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
    sleep_duration_hours: float
    sleep_start_time: str
    sleep_end_time: str
    functional_impact: int
    journal_text: str

@app.get("/")
def read_root():
    return {"message": "✅ SomniLearn Backend Berjalan!"}

@app.post("/predict_insomnia")
def predict_insomnia(data: SleepData):
    # Logika prediksi berdasarkan data baru
    screen_hours = data.evening_screen_time_ms / 3_600_000
    sleep_quality_factor = max(0, (8 - data.sleep_duration_hours) / 8)  # Kurang dari 8 jam = risiko
    impact_factor = data.functional_impact / 10

    # Kombinasi faktor
    risk = min(0.95,
               (screen_hours * 0.3 +
                sleep_quality_factor * 0.4 +
                impact_factor * 0.3)
               )

    # Rekomendasi berdasarkan pola
    if screen_hours > 2:
        rec = "Kurangi penggunaan layar setelah jam 21.00"
    elif data.sleep_duration_hours < 6:
        rec = "Coba tidur minimal 6-7 jam per malam"
    elif data.functional_impact > 7:
        rec = "Pertimbangkan teknik relaksasi sebelum tidur"
    else:
        rec = "Pertahankan rutinitas tidur konsisten"

    return {
        "insomnia_risk": round(risk, 2),
        "recommendation": rec
    }

# Logging untuk debugging (opsional)
if os.getenv("RAILWAY_ENVIRONMENT"):
    import sys
    print("🚀 SomniLearn Backend siap di Railway!", file=sys.stderr)