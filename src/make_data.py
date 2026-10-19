"""Pembuat data sintetis untuk simulasi kebijakan penghematan listrik gedung kampus.

Data yang dihasilkan (CSV, seluruhnya di folder ``data/``):

* ``rooms.csv``     - inventaris ruang: tipe, luas, kapasitas, daya AC, sifat kritis.
* ``schedules.csv`` - jadwal pemakaian tiap ruang per hari (Senin=0 ... Minggu=6).
* ``weather.csv``   - suhu udara luar per jam untuk satu minggu simulasi.
* ``policies.csv``  - grid kebijakan yang diuji (100 kombinasi) + kebijakan status quo.

Seluruh asumsi bersifat sintetis dan sengaja ditulis eksplisit supaya bisa
dibandingkan dengan data jadwal kampus yang sebenarnya. Cara menggantinya
dijelaskan di ``README.md``.

Jalankan::

    python src/make_data.py
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
DAY_INDEX = {name: i for i, name in enumerate(DAYS)}

ROOMS: list[dict] = [
    # id, nama, tipe, lantai, luas_m2, kapasitas, ac_kw, ac_unit, base_kw, setpoint_c, mode, kritis
    ("K01", "Kelas A1", "kelas", 1, 72, 40, 5.5, 2, 0.30, 24.0, "policy", 0),
    ("K02", "Kelas A2", "kelas", 1, 68, 40, 5.5, 2, 0.30, 24.0, "policy", 0),
    ("K03", "Kelas B1", "kelas", 2, 78, 48, 7.0, 3, 0.32, 24.0, "policy", 0),
    ("K04", "Kelas B2", "kelas", 2, 64, 36, 5.0, 2, 0.28, 24.0, "policy", 0),
    ("K05", "Kelas C1", "kelas", 3, 60, 36, 5.0, 2, 0.28, 24.0, "policy", 0),
    ("L01", "Lab Komputasi", "lab", 2, 90, 30, 8.0, 3, 0.60, 24.0, "policy", 0),
    ("L02", "Lab Elektronika", "lab", 3, 80, 24, 7.0, 3, 0.55, 24.0, "policy", 0),
    ("L03", "Lab Biologi", "lab", 3, 85, 26, 8.0, 3, 0.65, 22.0, "cap", 1),
    ("L04", "Lab Kimia", "lab", 1, 75, 22, 6.0, 2, 0.55, 23.0, "cap", 0),
    ("P01", "Perpustakaan Pusat", "perpustakaan", 1, 150, 80, 12.0, 4, 0.45, 24.0, "policy", 0),
    ("P02", "Perpustakaan Lansing", "perpustakaan", 2, 120, 60, 10.0, 3, 0.40, 24.0, "policy", 0),
    ("D01", "Ruang Dosen", "kelas", 1, 90, 18, 5.0, 2, 0.35, 24.0, "policy", 0),
    ("D02", "Ruang Diskusi", "kelas", 3, 60, 20, 4.0, 2, 0.25, 24.0, "policy", 0),
]

ROOM_TYPE_ID = {"kelas": 0, "lab": 1, "perpustakaan": 2}


def _class_blocks() -> list[tuple[int, int, int, float]]:
    """Blok kuliah: (hari, mulai, selesai, fraksi kehadiran).

    Hari sekolah Senin-Kamis, Jumat setengah hari, Sabtu kelas registrasi.
    """
    blocks: list[tuple[int, int, int, float]] = []
    for day in range(4):
        for start, end in ((8, 10), (10, 12), (13, 16)):
            blocks.append((day, start, end, 0.85))
    blocks.append((4, 8, 11, 0.80))
    blocks.append((5, 9, 12, 0.55))
    return blocks


def build_schedules() -> list[dict]:
    """Jadwal pemakaian ruang, digabung per tipe ruang."""
    rows: list[dict] = []

    for room in ROOMS:
        rid = room[0]
        rtype = room[2]
        sid = 0
        if rtype == "kelas" and rid.startswith("K"):
            for day, start, end, frac in _class_blocks():
                rows.append(_row(rid, sid, day, start, end, frac, "Kuliah"))
                sid += 1
        elif rid == "D01":
            for day in range(5):
                rows.append(_row(rid, sid, day, 8, 17, 0.55, "Dosen"))
                sid += 1
        elif rid == "D02":
            for day in range(5):
                rows.append(_row(rid, sid, day, 9, 17, 0.45, "Diskusi"))
                sid += 1
        elif rid == "L01":
            for day in range(5):
                for start, end, frac in ((7, 12, 0.55), (13, 17, 0.60), (19, 21, 0.30)):
                    rows.append(_row(rid, sid, day, start, end, frac, "Lab Komputasi"))
                    sid += 1
            rows.append(_row(rid, sid, 5, 9, 15, 0.40, "Lab Komputasi Sabtu"))
            sid += 1
        elif rid == "L02":
            for day in range(5):
                for start, end, frac in ((8, 12, 0.60), (13, 17, 0.55)):
                    rows.append(_row(rid, sid, day, start, end, frac, "Lab Elektronika"))
                    sid += 1
        elif rid == "L03":
            for day in range(5):
                for start, end, frac in ((7, 12, 0.65), (13, 19, 0.60)):
                    rows.append(_row(rid, sid, day, start, end, frac, "Lab Biologi"))
                    sid += 1
        elif rid == "L04":
            for day in range(4):
                for start, end, frac in ((8, 12, 0.60), (13, 16, 0.50)):
                    rows.append(_row(rid, sid, day, start, end, frac, "Lab Kimia"))
                    sid += 1
            rows.append(_row(rid, 4, 4, 8, 11, 0.50, "Lab Kimia Jumat"))
            sid += 1
        elif rid == "P01":
            for day in range(5):
                rows.append(_row(rid, sid, day, 8, 21, 0.35, "Perpustakaan"))
                sid += 1
            rows.append(_row(rid, sid, 5, 9, 16, 0.30, "Perpustakaan Sabtu"))
            sid += 1
        elif rid == "P02":
            for day in range(5):
                rows.append(_row(rid, sid, day, 8, 18, 0.28, "Perpustakaan"))
                sid += 1
            rows.append(_row(rid, sid, 5, 9, 14, 0.25, "Perpustakaan Sabtu"))
            sid += 1
    return rows


def _row(rid, sid, day, start, end, frac, label):
    return {
        "schedule_id": f"{rid}-S{sid:02d}",
        "room_id": rid,
        "day": day,
        "day_name": DAYS[day],
        "start_hour": start,
        "end_hour": end,
        "occupancy_fraction": frac,
        "label": label,
    }


def build_weather() -> list[dict]:
    """Suhu udara luar per jam, model sinus harian + pengaman_range per hari."""
    profiles = {
        0: (24.0, 33.0), 1: (24.2, 33.2), 2: (24.0, 32.8), 3: (23.8, 33.0),
        4: (24.5, 32.5), 5: (24.0, 32.0), 6: (23.5, 31.5),
    }
    rows: list[dict] = []
    for day in range(7):
        t_min, t_max = profiles[day]
        mid = 0.5 * (t_min + t_max)
        amp = 0.5 * (t_max - t_min)
        for hour in range(24):
            t_out = mid - amp * math.cos(2.0 * math.pi * (hour - 15.0) / 24.0)
            rows.append({
                "day": day,
                "day_name": DAYS[day],
                "hour": hour,
                "t_out_c": round(t_out, 3),
            })
    return rows


def build_policies() -> list[dict]:
    """Grid kebijakan: 5 jam mulai x 5 setpoint x 4 jam tutup lab = 100 kombinasi."""
    ac_starts = [6, 7, 8, 9, 10]
    setpoints = [22.0, 23.0, 24.0, 25.0, 26.0]
    lab_closes = [18, 19, 20, 21]
    rows: list[dict] = []
    idx = 1
    for ac_start in ac_starts:
        for setpoint in setpoints:
            for lab_close in lab_closes:
                rows.append({
                    "policy_id": f"P{idx:03d}",
                    "ac_start_hour": ac_start,
                    "min_setpoint_c": setpoint,
                    "lab_close_hour": lab_close,
                    "is_baseline": 0,
                    "label": f"AC>={ac_start}, setpoint>={setpoint:.0f}C, lab<={lab_close}",
                })
                idx += 1
    rows.append({
        "policy_id": "BASE",
        "ac_start_hour": 0,
        "min_setpoint_c": 22.0,
        "lab_close_hour": 24,
        "is_baseline": 1,
        "label": "Status quo (AC bebas, setpoint 22C, lab terbuka 24 jam)",
    })
    return rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[make_data] {path.relative_to(path.parent.parent)}  ({len(rows)} baris)")


def main() -> None:
    _write_csv(
        DATA_DIR / "rooms.csv",
        [dict(zip(
            ["room_id", "name", "type", "floor", "area_m2", "capacity", "ac_kw",
             "ac_units", "base_kw", "setpoint_c", "setpoint_mode", "critical"],
            room,
        )) for room in ROOMS],
        ["room_id", "name", "type", "floor", "area_m2", "capacity", "ac_kw",
         "ac_units", "base_kw", "setpoint_c", "setpoint_mode", "critical"],
    )
    _write_csv(
        DATA_DIR / "schedules.csv",
        build_schedules(),
        ["schedule_id", "room_id", "day", "day_name", "start_hour", "end_hour",
         "occupancy_fraction", "label"],
    )
    _write_csv(
        DATA_DIR / "weather.csv",
        build_weather(),
        ["day", "day_name", "hour", "t_out_c"],
    )
    _write_csv(
        DATA_DIR / "policies.csv",
        build_policies(),
        ["policy_id", "ac_start_hour", "min_setpoint_c", "lab_close_hour",
         "is_baseline", "label"],
    )


if __name__ == "__main__":
    main()
