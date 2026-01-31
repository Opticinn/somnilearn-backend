# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
import os
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.exc import SQLAlchemyError

app = FastAPI(title="SomniLearn Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

# 🔥 DEFINISI CLASS HARUS DI ATAS FUNGSI
class SleepData(BaseModel):
    total_screen_time_ms: int
    evening_screen_time_ms: int
    app_switching_freq: int
    blue_light_duration_ms: int
    sleep_duration_hours: float
    sleep_start_time: str
    sleep_end_time: str
    journal_text: str

def get_engine() -> Engine:
    """Buat engine hanya saat dibutuhkan"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        # Fallback ke SQLite jika tidak ada DATABASE_URL
        return create_engine("sqlite:///./temp.db")
    return create_engine(DATABASE_URL)

@app.on_event("startup")
def init_db():
    """Buat tabel jika belum ada - dengan error handling kuat"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Untuk SQLite, gunakan sintaks yang kompatibel
            if "sqlite" in str(engine.url):
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sleep_records (
                        id INTEGER PRIMARY KEY,
                        user_id TEXT DEFAULT 'default_user',
                        date DATE,
                        sleep_start TIME,
                        sleep_end TIME,
                        duration_hours REAL,
                        screen_evening_ms INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            else:
                # Untuk PostgreSQL
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sleep_records (
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
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database initialization failed: {e}")

def calculate_circadian_stability(user_id: str = "default_user") -> float:
    """Hitung Circadian Stability Score dari 7 hari terakhir"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            if "sqlite" in str(engine.url):
                result = conn.execute(text("""
                    SELECT 
                        CAST(strftime('%H', sleep_start) AS INTEGER) * 60 + 
                        CAST(strftime('%M', sleep_start) AS INTEGER) as start_minutes,
                        CAST(strftime('%H', sleep_end) AS INTEGER) * 60 + 
                        CAST(strftime('%M', sleep_end) AS INTEGER) as end_minutes
                    FROM sleep_records 
                    WHERE user_id = :user_id 
                    AND date >= date('now', '-7 days')
                    ORDER BY date DESC
                    LIMIT 7
                """), {"user_id": user_id})
            else:
                result = conn.execute(text("""
                    SELECT 
                        EXTRACT(EPOCH FROM sleep_start)/60 as start_minutes,
                        EXTRACT(EPOCH FROM sleep_end)/60 as end_minutes
                    FROM sleep_records 
                    WHERE user_id = :user_id 
                    AND date >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY date DESC
                    LIMIT 7
                """), {"user_id": user_id})

            records = result.fetchall()

            if len(records) < 3:
                return None

            start_minutes = [r[0] for r in records]
            end_minutes = [r[1] for r in records]

            import statistics
            sd_start = statistics.stdev(start_minutes) if len(start_minutes) > 1 else 0
            sd_end = statistics.stdev(end_minutes) if len(end_minutes) > 1 else 0

            max_dev = 120.0
            stability = 1.0 - min((sd_start + sd_end) / (2 * max_dev), 1.0)
            return round(max(0.0, stability), 2)

    except Exception as e:
        print(f"Error menghitung CSS: {e}")
        return None

@app.post("/predict_sleep_health")
async def predict_sleep_health(data: SleepData):
    try:
        # Simpan data ke database
        try:
            engine = get_engine()
            with engine.connect() as conn:
                if "sqlite" in str(engine.url):
                    conn.execute(text("""
                        INSERT INTO sleep_records 
                        (date, sleep_start, sleep_end, duration_hours, screen_evening_ms)
                        VALUES (
                            date('now'),
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
                else:
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
        except SQLAlchemyError as e:
            print(f"Error simpan ke DB: {e}")

        # Hitung metrik
        screen_hours = data.evening_screen_time_ms / 3_600_000
        screen_factor = min(screen_hours / 3.0, 1.0)

        start = datetime.datetime.strptime(data.sleep_start_time, "%H:%M").time()
        timing_factor = 1.0 if start > datetime.time(23, 0) else 0.0
        insomnia_risk = min(0.95, screen_factor * 0.5 + timing_factor * 0.5)
        sleep_deprivation = 1 if data.sleep_duration_hours < 6.0 else 0

        circadian_stability = calculate_circadian_stability()

        # Rekomendasi berjenjang
        if circadian_stability is not None and circadian_stability < 0.6:
            recommendation = (
                "🌙 FOKUS UTAMA: Stabilkan ritme sirkadian Anda! "
                "Tidur dan bangun di jam yang sama setiap hari, bahkan di akhir pekan."
            )
        elif insomnia_risk > 0.6:
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
            recommendation = (
                "😴 FOKUS KETIGA: Durasi tidur Anda kurang dari 6 jam. "
                "Hindari scroll ponsel larut malam — targetkan minimal 7 jam tidur."
            )
        else:
            recommendation = (
                "✅ Ritme sirkadian & pola tidur Anda optimal! "
                "Pertahankan konsistensi ini untuk kesehatan jangka panjang."
            )

        return {
            "circadian_stability": circadian_stability,
            "insomnia_risk": round(insomnia_risk, 2),
            "sleep_deprivation": sleep_deprivation,
            "recommendation": recommendation
        }

    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            "circadian_stability": None,
            "insomnia_risk": 0.5,
            "sleep_deprivation": 0,
            "recommendation": "⚠️ Terjadi kesalahan. Hindari layar setelah jam 21.00."
        }