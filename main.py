# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
import os
from sqlalchemy import create_engine, text

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
    journal_text: str

class ScreenUsageData(BaseModel):
    total_screen_time_ms: int
    evening_screen_time_ms: int
    app_switching_freq: int
    blue_light_duration_ms: int

def get_db_url():
    return os.getenv("DATABASE_URL")

def get_engine():
    db_url = get_db_url()
    if not db_url:
        return None
    try:
        engine = create_engine(db_url)
        return engine
    except Exception as e:
        print(f"❌ Engine creation failed: {e}")
        return None

@app.on_event("startup")
def init_db():
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                # Buat tabel screen_usage_daily
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS screen_usage_daily (
                        id SERIAL PRIMARY KEY,
                        date DATE UNIQUE,
                        total_screen_time_ms INT,
                        evening_screen_time_ms INT,
                        app_switching_freq INT,
                        blue_light_duration_ms INT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))

                # Buat tabel sleep_records untuk jurnal mingguan
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sleep_records (
                        id SERIAL PRIMARY KEY,
                        period_start DATE,
                        period_end DATE,
                        sleep_start TIME,
                        sleep_end TIME,
                        duration_hours FLOAT,
                        journal_text TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("✅ Tables created/verified")
        except Exception as e:
            print(f"❌ DB init error: {e}")

@app.post("/save_daily_usage")
async def save_daily_usage(usage_data: ScreenUsageData):
    """Simpan data penggunaan HP harian (otomatis dari WorkManager)"""
    engine = get_engine()
    if not engine:
        return {"status": "error", "message": "Database not configured"}

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO screen_usage_daily 
                (date, total_screen_time_ms, evening_screen_time_ms, app_switching_freq, blue_light_duration_ms)
                VALUES (
                    CURRENT_DATE,
                    :total_screen,
                    :evening_screen,
                    :app_switching,
                    :blue_light
                )
                ON CONFLICT (date) 
                DO UPDATE SET
                    total_screen_time_ms = EXCLUDED.total_screen_time_ms,
                    evening_screen_time_ms = EXCLUDED.evening_screen_time_ms,
                    app_switching_freq = EXCLUDED.app_switching_freq,
                    blue_light_duration_ms = EXCLUDED.blue_light_duration_ms,
                    created_at = NOW()
            """), {
                "total_screen": usage_data.total_screen_time_ms,
                "evening_screen": usage_data.evening_screen_time_ms,
                "app_switching": usage_data.app_switching_freq,
                "blue_light": usage_data.blue_light_duration_ms
            })
            conn.commit()
        return {"status": "success", "message": "Daily usage saved"}
    except Exception as e:
        print(f"❌ Daily usage save error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/submit_weekly_journal")
async def submit_weekly_journal(journal_ SleepData):
"""Simpan jurnal tidur mingguan (manual dari user)"""
engine = get_engine()
if not engine:
    return {"status": "error", "message": "Database not configured"}

try:
    # Hitung periode mingguan (7 hari terakhir)
    today = datetime.date.today()
    period_start = today - datetime.timedelta(days=6)
    period_end = today

    with engine.connect() as conn:
        conn.execute(text("""
                INSERT INTO sleep_records 
                (period_start, period_end, sleep_start, sleep_end, duration_hours, journal_text)
                VALUES (
                    :period_start,
                    :period_end,
                    :sleep_start,
                    :sleep_end,
                    :duration,
                    :journal_text
                )
            """), {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "sleep_start": journal_data.sleep_start_time,
            "sleep_end": journal_data.sleep_end_time,
            "duration": journal_data.sleep_duration_hours,
            "journal_text": journal_data.journal_text
        })
        conn.commit()

    # Hitung metrik berdasarkan data mingguan + data penggunaan terbaru
    screen_hours = journal_data.evening_screen_time_ms / 3_600_000
    screen_factor = min(screen_hours / 3.0, 1.0)

    start = datetime.datetime.strptime(journal_data.sleep_start_time, "%H:%M").time()
    timing_factor = 1.0 if start > datetime.time(23, 0) else 0.0
    insomnia_risk = min(0.95, screen_factor * 0.5 + timing_factor * 0.5)
    sleep_deprivation = 1 if journal_data.sleep_duration_hours < 6.0 else 0

    # Rekomendasi berbasis data mingguan
    if insomnia_risk > 0.6:
        if screen_hours > 2:
            recommendation = "⚠️ FOKUS KEDUA: Paparan layar malam hari terlalu tinggi. Matikan notifikasi & hindari media sosial setelah jam 21.00."
        else:
            recommendation = "⚠️ FOKUS KEDUA: Anda tidur terlalu larut. Coba mulai rutinitas tidur sebelum jam 23.00."
    elif sleep_deprivation == 1:
        recommendation = "😴 FOKUS KETIGA: Durasi tidur Anda kurang dari 6 jam. Hindari scroll ponsel larut malam — targetkan minimal 7 jam tidur."
    else:
        recommendation = "✅ Pola tidur mingguan Anda optimal! Pertahankan konsistensi ini untuk kesehatan jangka panjang."

    return {
        "circadian_stability": None,
        "insomnia_risk": round(insomnia_risk, 2),
        "sleep_deprivation": sleep_deprivation,
        "recommendation": recommendation,
        "status": "success"
    }

except Exception as e:
    print(f"❌ Weekly journal save error: {e}")
    return {"status": "error", "message": str(e)}

# Endpoint lama untuk kompatibilitas
@app.post("/predict_sleep_health")
async def predict_sleep_health( SleepData):
    """Kompatibilitas dengan versi Android saat ini"""
    return await submit_weekly_journal(data)