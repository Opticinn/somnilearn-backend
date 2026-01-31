# main.py (versi diperbaiki)
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

def get_db_url():
    return os.getenv("DATABASE_URL")

def get_engine():
    db_url = get_db_url()
    print(f"🔍 DATABASE_URL: {'SET' if db_url else 'NOT SET'}")
    if not db_url:
        return None
    try:
        engine = create_engine(db_url)
        print("✅ Engine created successfully")
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
                # Cek apakah koneksi berhasil
                result = conn.execute(text("SELECT version()"))
                print(f"✅ Database connected: {result.fetchone()[0]}")

                # Buat tabel di schema public
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS public.sleep_records (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT DEFAULT 'default_user',
                        date DATE,
                        sleep_start TIME,
                        sleep_end TIME,
                        duration_hours FLOAT,
                        screen_evening_ms INT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("✅ Table sleep_records created/verified")
        except Exception as e:
            print(f"❌ DB init error: {e}")

@app.post("/predict_sleep_health")
async def predict_sleep_health(data: SleepData):
    # Simpan ke database jika tersedia
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO sleep_records 
                    (date, sleep_start, sleep_end, duration_hours, screen_evening_ms)
                    VALUES (
                        CURRENT_DATE,
                        :sleep_start,
                        :sleep_end,
                        :duration,
                        :screen_evening
                    )
                """), {
                    "sleep_start": data.sleep_start_time,
                    "sleep_end": data.sleep_end_time,
                    "duration": data.sleep_duration_hours,
                    "screen_evening": data.evening_screen_time_ms
                })
                conn.commit()
        except Exception as e:
            print(f"DB insert error: {e}")

    # Hitung metrik
    screen_hours = data.evening_screen_time_ms / 3_600_000
    screen_factor = min(screen_hours / 3.0, 1.0)

    start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
    timing_factor = 1.0 if start > datetime.time(23, 0) else 0.0
    insomnia_risk = min(0.95, screen_factor * 0.5 + timing_factor * 0.5)
    sleep_deprivation = 1 if data.sleep_duration_hours < 6.0 else 0

    # Rekomendasi
    if insomnia_risk > 0.6:
        if screen_hours > 2:
            recommendation = "⚠️ FOKUS KEDUA: Paparan layar malam hari terlalu tinggi. Matikan notifikasi & hindari media sosial setelah jam 21.00."
        else:
            recommendation = "⚠️ FOKUS KEDUA: Anda tidur terlalu larut. Coba mulai rutinitas tidur sebelum jam 23.00."
    elif sleep_deprivation == 1:
        recommendation = "😴 FOKUS KETIGA: Durasi tidur Anda kurang dari 6 jam. Hindari scroll ponsel larut malam — targetkan minimal 7 jam tidur."
    else:
        recommendation = "✅ Ritme sirkadian & pola tidur Anda optimal! Pertahankan konsistensi ini untuk kesehatan jangka panjang."

    return {
        "circadian_stability": None,
        "insomnia_risk": round(insomnia_risk, 2),
        "sleep_deprivation": sleep_deprivation,
        "recommendation": recommendation
    }