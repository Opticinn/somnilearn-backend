# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime

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
    sleep_start_time: str  # "HH:MM"
    sleep_end_time: str    # "HH:MM"
    journal_text: str      # functional_impact TIDAK dikirim ke backend

@app.get("/")
def read_root():
    return {"message": "✅ SomniLearn Backend Berjalan!"}

@app.post("/predict_insomnia")
def predict_insomnia( SleepData):
    # 1. Faktor Layar Malam (20.00–23.59)
    screen_hours = data.evening_screen_time_ms / 3_600_000
    screen_factor = min(screen_hours / 3.0, 1.0)  # Normalisasi ke [0,1]

    # 2. Faktor Durasi Tidur (<7 jam = risiko)
    duration_factor = max(0.0, (7.0 - data.sleep_duration_hours) / 7.0) if data.sleep_duration_hours < 7 else 0.0

    # 3. 🔥 Faktor Timing Tidur (paling penting!)
    try:
        start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
        end = datetime.datetime.strptime(data.sleep_end_time, "%H:%M").time()

        # Ideal: tidur ≤ 21:30, bangun ≤ 08:00
        bedtime_late_minutes = max(0, (start.hour * 60 + start.minute) - (21 * 60 + 30))
        waketime_late_minutes = max(0, (end.hour * 60 + end.minute) - (8 * 60))

        # Gabungkan deviasi maksimal (dalam menit), lalu normalisasi ke [0,1]
        max_deviation = max(bedtime_late_minutes, waketime_late_minutes)
        timing_factor = min(max_deviation / 240.0, 1.0)  # 240 menit = 4 jam toleransi
    except Exception:
        timing_factor = 0.5  # fallback jika parsing gagal

    # 4. Kombinasi akhir (timing paling dominan)
    risk = min(0.95,
               screen_factor * 0.2 +
               duration_factor * 0.3 +
               timing_factor * 0.5   # ⚠️ Timing = 50% bobot!
               )

    # 5. Rekomendasi berbasis pola
    start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
    end = datetime.datetime.strptime(data.sleep_end_time, "%H:%M").time()

    if start > datetime.time(21, 30):
        rec = "⚠️ Tidur terlalu larut! Targetkan tidur sebelum jam 21.30"
    elif end > datetime.time(8, 0):
        rec = "⏰ Bangun terlalu siang! Coba bangun sebelum jam 08.00"
    elif data.sleep_duration_hours < 7:
        rec = "🛌 Durasi tidur kurang! Target minimal 7-8 jam"
    elif screen_hours > 2:
        rec = "📱 Kurangi layar setelah jam 21.00"
    else:
        rec = "✅ Pola tidur Anda optimal! Pertahankan!"

    return {
        "insomnia_risk": round(risk, 2),
        "recommendation": rec
    }