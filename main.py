# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime

app = FastAPI(title="Circadia Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SleepData(BaseModel):
    total_screen_time_ms: int
    evening_screen_time_ms: int          # Layar malam (20.00–23.59)
    app_switching_freq: int              # Frekuensi ganti app
    blue_light_duration_ms: int          # App "blue light"
    sleep_duration_hours: float           # Durasi tidur
    sleep_start_time: str                # "HH:MM"
    sleep_end_time: str                  # "HH:MM"
    journal_text: str

@app.get("/")
def read_root():
    return {"message": "✅ Circadia Backend Berjalan!"}

@app.post("/predict_sleep_health")
def predict_sleep_health( SleepData):
    try:
        # === 1. HITUNG INSOMNIA RISK SCORE (IRS) ===
        screen_hours = data.evening_screen_time_ms / 3_600_000
        screen_factor = min(screen_hours / 3.0, 1.0)  # Normalisasi [0,1]

        # Parse waktu tidur & bangun
        start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
        end = datetime.datetime.strptime(data.sleep_end_time, "%H:%M").time()

        # Faktor tidur larut (>23.00)
        timing_factor = 1.0 if start > datetime.time(23, 0) else 0.0

        # IRS: kombinasi layar malam + tidur larut
        insomnia_risk = min(0.95, screen_factor * 0.5 + timing_factor * 0.5)

        # === 2. HITUNG SLEEP DEPRIVATION INDEX (SDI) ===
        sleep_deprivation = 1 if data.sleep_duration_hours < 6.0 else 0

        # === 3. CIRCADIAN STABILITY (CSS) - Placeholder ===
        # Catatan: CSS butuh data historis 7 hari → simpan di DB nanti
        # Untuk sekarang, kembalikan null
        circadian_stability = None  # Akan diisi setelah integrasi PostgreSQL

        # === 4. REKOMENDASI BERJENJANG (Prioritas: Ritme → Insomnia → Sleep Deprivation) ===
        if circadian_stability is not None and circadian_stability < 0.6:
            # Prioritas 1: Ritme sirkadian tidak stabil
            recommendation = (
                "🌙 FOKUS UTAMA: Stabilkan ritme sirkadian Anda! "
                "Tidur dan bangun di jam yang sama setiap hari, bahkan di akhir pekan."
            )
        elif insomnia_risk > 0.6:
            # Prioritas 2: Risiko insomnia tinggi
            if screen_hours > 2:
                recommendation = (
                    "⚠️ FOKUS KEDUA: Paparan layar malam hari terlalu tinggi. "
                    "Matikan notifikasi & hindari media sosial setelah jam 21.00."
                )
            else:
                recommendation = (
                    "⚠️ FOKUS KEDUA: Anda tidur terlalu larut. "
                    "Coba mulai rutinitas tidur sebelum jam 23.00."
                )
        elif sleep_deprivation == 1:
            # Prioritas 3: Kurang tidur
            recommendation = (
                "😴 FOKUS KETIGA: Durasi tidur Anda kurang dari 6 jam. "
                "Hindari scroll ponsel larut malam — targetkan minimal 7 jam tidur."
            )
        else:
            # Semua baik
            recommendation = (
                "✅ Ritme sirkadian & pola tidur Anda optimal! "
                "Pertahankan konsistensi ini untuk kesehatan jangka panjang."
            )

        return {
            "circadian_stability": circadian_stability,  # null untuk sekarang
            "insomnia_risk": round(insomnia_risk, 2),
            "sleep_deprivation": sleep_deprivation,
            "recommendation": recommendation
        }

    except Exception as e:
        # Fallback aman
        return {
            "circadian_stability": None,
            "insomnia_risk": 0.5,
            "sleep_deprivation": 0,
            "recommendation": "⚠️ Terjadi kesalahan. Gunakan rekomendasi umum: hindari layar setelah jam 21.00."
        }