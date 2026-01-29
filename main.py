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
    journal_text: str

@app.get("/")
def read_root():
    return {"message": "✅ SomniLearn Backend Berjalan!"}

@app.post("/predict_insomnia")
def predict_insomnia(data: SleepData):
    try:
        # 1. Faktor Layar Malam (20.00–23.59)
        screen_hours = data.evening_screen_time_ms / 3_600_000
        screen_factor = min(screen_hours / 3.0, 1.0)

        # 2. Faktor Durasi Tidur (<7 jam = risiko)
        duration_factor = max(0.0, (7.0 - data.sleep_duration_hours) / 7.0) if data.sleep_duration_hours < 7 else 0.0

        # 3. Faktor Timing Tidur (paling penting!)
        try:
            start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
            end = datetime.datetime.strptime(data.sleep_end_time, "%H:%M").time()

            bedtime_late_minutes = max(0, (start.hour * 60 + start.minute) - (21 * 60 + 30))
            waketime_late_minutes = max(0, (end.hour * 60 + end.minute) - (8 * 60))
            max_deviation = max(bedtime_late_minutes, waketime_late_minutes)
            timing_factor = min(max_deviation / 240.0, 1.0)
        except Exception:
            timing_factor = 0.5

        # 4. Kombinasi akhir
        risk = min(0.95,
                   screen_factor * 0.2 +
                   duration_factor * 0.3 +
                   timing_factor * 0.5)

        # 5. 🔥 REKOMENDASI (PERBAIKAN UTAMA)
        start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
        end = datetime.datetime.strptime(data.sleep_end_time, "%H:%M").time()

        if start.hour > 21 or (start.hour == 21 and start.minute > 30):
            rec = f"Risiko insomnia Anda tinggi ({round(risk * 100)}%) karena tidur terlalu larut. Disarankan tidur sebelum jam 21.30 untuk kualitas tidur optimal."
        elif end.hour > 8:
            rec = f"Risiko insomnia Anda ({round(risk * 100)}%) dipengaruhi oleh bangun terlalu siang. Coba bangun sebelum jam 08.00 untuk menjaga ritme sirkadian."
        elif data.sleep_duration_hours < 7:
            rec = f"Durasi tidur Anda hanya {data.sleep_duration_hours} jam. Risiko insomnia: {round(risk * 100)}%. Targetkan minimal 7-8 jam per malam."
        elif screen_hours > 2:
            rec = f"Penggunaan layar malam hari melebihi 2 jam → risiko insomnia {round(risk * 100)}%. Kurangi layar setelah jam 21.00."
        else:
            rec = f"Pola tidur Anda optimal! Risiko insomnia rendah ({round(risk * 100)}%). Pertahankan konsistensi ini."

        return {
            "insomnia_risk": round(risk, 2),
            "recommendation": rec
        }

    except Exception as e:
        return {
            "insomnia_risk": 0.5,
            "recommendation": "⚠️ Terjadi kesalahan dalam pemrosesan data. Silakan coba lagi."
        }