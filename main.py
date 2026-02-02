from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, date
import os
from sqlalchemy import create_engine, text, exc

def validate_sleep_source(provided_source: str, has_manual: bool) -> str:
    """Validasi dan return sleep_source yang sesuai constraint"""
    valid_sources = {'manual', 'auto_confirmed', 'auto_passive_confirmed', 'auto_detected'}

    if provided_source in valid_sources:
        return provided_source
    elif has_manual:
        return 'manual'
    else:
        return 'auto_detected'


app = FastAPI(title="Circadia Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SleepData(BaseModel):
    # Data penggunaan HP (auto-collected atau manual)
    total_screen_time_ms: int
    evening_screen_time_ms: int
    app_switching_freq: int
    blue_light_duration_ms: int

    # Data jurnal tidur (manual input - boleh null)
    sleep_duration_hours: float = None
    sleep_start_time: str = None  # "HH:MM"
    sleep_end_time: str = None    # "HH:MM"
    journal_text: str = ""

    # Tanggal spesifik (opsional, default: today)
    date: str = None  # "YYYY-MM-DD"

    # ✅ TAMBAHKAN INI!
    sleep_source: str = None  # "manual", "auto_detected", dll

def get_db_url():
    return os.getenv("DATABASE_URL")

def get_engine():
    db_url = get_db_url()
    if not db_url:
        return None
    return create_engine(db_url)

@app.on_event("startup")
def init_db():
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                # Buat tabel dengan kolom sleep_source
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS daily_sleep_data (
                        id SERIAL PRIMARY KEY,
                        date DATE UNIQUE,
                        total_screen_time_ms INT,
                        evening_screen_time_ms INT,
                        app_switching_freq INT,
                        blue_light_duration_ms INT,
                        sleep_start TIME NULL,
                        sleep_end TIME NULL,
                        duration_hours FLOAT NULL,
                        journal_text TEXT DEFAULT '',
                        has_manual_input BOOLEAN DEFAULT FALSE,
                        sleep_source VARCHAR(30) CHECK (
                            sleep_source IN ('manual', 'auto_confirmed', 'auto_passive_confirmed', 'auto_detected')
                        ),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("✅ Table daily_sleep_data ready with sleep_source column")
        except Exception as e:
            print(f"❌ DB init error: {str(e)}")

def parse_date(date_str: str = None):
    """Parse tanggal dari string atau return today"""
    if date_str:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    return datetime.date.today()

@app.post("/submit_daily_data")
async def submit_daily_data(data: SleepData):
    engine = get_engine()
    if not engine:
        return await _calculate_prediction(data)

    try:
        # Parse tanggal
        if data.date:
            target_date = datetime.strptime(data.date, "%Y-%m-%d").date()
        else:
            target_date = date.today()  # ← LEBIH BAIK pakai date.today()

        with engine.connect() as conn:
            # ✅ GUNAKAN UPSERT DENGAN ON CONFLICT
            query = text("""
                INSERT INTO daily_sleep_data (
                    date, total_screen_time_ms, evening_screen_time_ms,
                    app_switching_freq, blue_light_duration_ms,
                    sleep_start, sleep_end, duration_hours, journal_text,
                    has_manual_input, sleep_source
                ) VALUES (
                    :date, :total_screen_time_ms, :evening_screen_time_ms,
                    :app_switching_freq, :blue_light_duration_ms,
                    :sleep_start, :sleep_end, :duration_hours, :journal_text,
                    :has_manual_input, :sleep_source
                )
                ON CONFLICT (date) 
                DO UPDATE SET
                    total_screen_time_ms = EXCLUDED.total_screen_time_ms,
                    evening_screen_time_ms = EXCLUDED.evening_screen_time_ms,
                    app_switching_freq = EXCLUDED.app_switching_freq,
                    blue_light_duration_ms = EXCLUDED.blue_light_duration_ms,
                    sleep_start = EXCLUDED.sleep_start,
                    sleep_end = EXCLUDED.sleep_end,
                    duration_hours = EXCLUDED.duration_hours,
                    journal_text = EXCLUDED.journal_text,
                    has_manual_input = EXCLUDED.has_manual_input,
                    sleep_source = EXCLUDED.sleep_source,
                    updated_at = NOW()
            """)

            has_manual = any([
                data.sleep_duration_hours is not None,
                data.sleep_start_time is not None,
                data.sleep_end_time is not None
            ])

            # Validasi sleep_source
            valid_sources = {'manual', 'auto_confirmed', 'auto_passive_confirmed', 'auto_detected'}
            sleep_source = data.sleep_source if data.sleep_source in valid_sources else ('manual' if has_manual else 'auto_detected')

            conn.execute(query, {
                "date": target_date,
                "total_screen_time_ms": data.total_screen_time_ms,
                "evening_screen_time_ms": data.evening_screen_time_ms,
                "app_switching_freq": data.app_switching_freq,
                "blue_light_duration_ms": data.blue_light_duration_ms,
                "sleep_start": data.sleep_start_time,
                "sleep_end": data.sleep_end_time,
                "duration_hours": data.sleep_duration_hours,
                "journal_text": data.journal_text or "",
                "has_manual_input": has_manual,
                "sleep_source": sleep_source
            })
            conn.commit()

            print(f"✅ Data berhasil disimpan untuk tanggal {target_date}")

        return await _calculate_prediction(data)

    except Exception as e:
        print(f"💥 ERROR KRITIS SAAT MENYIMPAN DATA: {str(e)}")
        print(f"   Detail: {repr(e)}")  # ← INI AKAN TAMPILKAN ERROR SEBENARNYA
        return await _calculate_prediction(data)
async def _calculate_prediction(data: SleepData):
    """Hitung prediksi insomnia berdasarkan data input"""
    # Hitung metrik
    screen_hours = data.evening_screen_time_ms / 3_600_000
    screen_factor = min(screen_hours / 3.0, 1.0)

    timing_factor = 0.0
    if data.sleep_start_time:
        try:
            start = datetime.strptime(data.sleep_start_time, "%H:%M").time()
            timing_factor = 1.0 if start > datetime.time(23, 0) else 0.0
        except:
            timing_factor = 0.0

    insomnia_risk = min(0.95, screen_factor * 0.5 + timing_factor * 0.5)
    sleep_deprivation = 1 if data.sleep_duration_hours and data.sleep_duration_hours < 6.0 else 0

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
        "circadian_stability": None,  # Akan dihitung dari data historis
        "insomnia_risk": round(insomnia_risk, 2),
        "sleep_deprivation": sleep_deprivation,
        "recommendation": recommendation
    }

@app.get("/get_missing_dates")
async def get_missing_dates(days: int = 3):
    """
    Endpoint untuk mendapatkan tanggal yang belum ada datanya
    Digunakan untuk menentukan form mana yang harus ditampilkan
    """
    engine = get_engine()
    if not engine:
        # Jika tidak ada database, kembalikan 3 hari terakhir
        today = date.today()
        return {
            "missing_dates": [
                (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, days + 1)
            ]
        }

    try:
        with engine.connect() as conn:
            # Dapatkan tanggal yang sudah ada dalam N hari terakhir
            today = date.today()
            date_range = [today - datetime.timedelta(days=i) for i in range(days)]
            date_strings = [d.strftime("%Y-%m-%d") for d in date_range]

            existing_dates = conn.execute(text("""
                SELECT date FROM daily_sleep_data 
                WHERE date IN :dates
            """), {"dates": tuple(date_range)}).fetchall()

            existing_set = {str(row[0]) for row in existing_dates}
            missing_dates = [d for d in date_strings if d not in existing_set]

            return {"missing_dates": missing_dates}

    except Exception as e:
        print(f"❌ Error getting missing dates: {str(e)}")
        # Fallback
        today = datetime.date.today()
        return {
            "missing_dates": [
                (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, days + 1)
            ]
        }