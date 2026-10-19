"""Simulator berbasis agen untuk evaluasi kebijakan penghematan listrik gedung kampus.

Model ini menerjemahkan ide webinar HPC Ignite, yaitu "simulasi penghematan listrik
gedung dengan memodelkan perilaku manusia" menjadi kode yang bisa dijalankan.

Sistem yang dimodelkan
----------------------
Gedung berisi beberapa ruang (kelas, lab, perpustakaan). Setiap ruang adalah
sebuah *agen* dengan state internal berupa suhu udara, status AC, dan
kepadatan occupants pada jam tersebut. Occupants (manusia) deciding dua hal:

1. apakah mereka merasa perlu AC (suhu di atas setpoint + deadband), dan
2. ketika kebijakan melarang AC menyala, apakah mereka menyalakannya manual
   (pelanggaran kebijakan) atau menahan diri (ketidaknyamanan).

Setiap ruang punya termal sederhana orde-1 (model RC), sehingga Policy AC
memang memengaruhi suhu dan bukan sekadar "daya on/off".

Kebijakan yang diuji
--------------------
* ``ac_start_hour``   - jam paling awal AC boleh menyala di gedung.
* ``min_setpoint_c``  - batas suhu minimum setpoint (AC tidak boleh mendinginkan
  di bawah nilai ini, misal 24 C berarti hemat energi).
* ``lab_close_hour``  - jam penutupan setelahnya AC lab harus dimatikan
  (ruang kritis seperti Lab Biologi dikecualikan).

Keluaran tiap simulasi: energi (kWh), puncak beban (kW), angka ketidaknyamanan
(orang-jam), pelanggaran kebijakan, dan paparan ruang kritis (jam).
"""

from __future__ import annotations

import csv
import math
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7
N_STEPS = HOURS_PER_DAY * DAYS_PER_WEEK

TYPE_CODE = {"kelas": 0, "lab": 1, "perpustakaan": 2}
TYPE_NAME = {0: "kelas", 1: "lab", 2: "perpustakaan"}


@dataclass(frozen=True)
class ModelParams:
    """Asumsi fisik dan perilaku yang dipakai simulator."""

    dt_hours: float = 0.25
    substeps: int = 4
    cop: float = 3.0
    fan_kw_per_unit: float = 0.25
    internal_gain_w_per_person: float = 100.0
    equipment_kw_per_person: float = 0.05
    lighting_kw_per_m2: float = 0.008
    standby_kw_fraction: float = 0.25
    comfort_max_c: float = 30.0
    comfort_min_c_base: float = 16.0
    comfort_min_c_span: float = 4.5
    override_base_prob: float = 0.30
    ua_kw_per_k_per_m2: float = 0.010
    c_kwh_per_k_per_m2: float = 0.060
    hold_hours: float = 1.0
    pre_cool_hours: float = 1.0
    pre_cool_probability: float = 0.70
    initial_indoor_c: float = 28.0
    late_lab_occupancy_fraction: float = 0.03
    outdoor_noise_c: float = 0.8
    tariff_idr_per_kwh: float = 1500.0


@dataclass(frozen=True)
class Room:
    """Agen tingkat ruang: inventaris fisik dan sifat ruang.

    ``setpoint_mode`` menentukan siapa yang menentukan suhu AC ruang ini:

    * ``policy`` - mengikuti setpoint kebijakan gedung (kelas, perpustakaan).
    * ``cap``    - ruang punya syarat suhu sendiri yang tidak boleh dilanggar
      (lab biologi untuk sample, lab kimia untuk fume hood), jadi suhu efektif
      adalah yang lebih dingin antara kebijakan dan batas ruang.
    """

    room_id: str
    name: str
    room_type: str
    floor: int
    area_m2: float
    capacity: int
    ac_kw: float
    ac_units: int
    base_kw: float
    setpoint_c: float
    setpoint_mode: str
    critical: bool


@dataclass(frozen=True)
class ScheduleWindow:
    """Jendela pemakaian ruang pada satu hari."""

    day: int
    start_hour: int
    end_hour: int
    occupancy_fraction: float


@dataclass(frozen=True)
class Policy:
    """Satu set parameter kebijakan yang diuji."""

    policy_id: str
    ac_start_hour: int
    min_setpoint_c: float
    lab_close_hour: int
    is_baseline: bool = False
    label: str = ""

    @property
    def seed_tag(self) -> int:
        return zlib.crc32(self.policy_id.encode("utf-8"))


@dataclass
class Building:
    """Gedung lengkap: ruang, jadwal, cuaca, dan matriks kehadiran."""

    rooms: list[Room]
    windows: dict[str, list[ScheduleWindow]]
    t_out: list[float]
    params: ModelParams
    occ_base: list[list[float]] = field(default_factory=list)
    late_mask: list[list[bool]] = field(default_factory=list)
    precool_mask: list[list[bool]] = field(default_factory=list)

    @property
    def n_rooms(self) -> int:
        return len(self.rooms)

    @property
    def n_steps(self) -> int:
        return len(self.t_out)


@dataclass
class SimResult:
    """Hasil satu simulasi (satu kebijakan, satu pengulangan acak)."""

    policy_id: str
    rep: int
    energy_kwh: float
    energy_ac_kwh: float
    energy_base_kwh: float
    peak_kw: float
    discomfort_person_hours: float
    blocked_cooling_person_hours: float
    policy_violations: int
    critical_exposure_hours: float
    cost_idr: float
    profile_kw: list[float] | None = None


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_building(data_dir: Path = DATA_DIR, params: ModelParams | None = None) -> Building:
    """Baca data CSV, bangun matriks kehadiran dasar per jam."""
    data_dir = Path(data_dir)
    params = params or ModelParams()

    rooms: list[Room] = []
    for row in _read_csv(data_dir / "rooms.csv"):
        rooms.append(Room(
            room_id=row["room_id"],
            name=row["name"],
            room_type=row["type"],
            floor=int(row["floor"]),
            area_m2=float(row["area_m2"]),
            capacity=int(row["capacity"]),
            ac_kw=float(row["ac_kw"]),
            ac_units=int(row["ac_units"]),
            base_kw=float(row["base_kw"]),
            setpoint_c=float(row["setpoint_c"]),
            setpoint_mode=row.get("setpoint_mode", "policy"),
            critical=bool(int(row["critical"])),
        ))

    windows: dict[str, list[ScheduleWindow]] = {room.room_id: [] for room in rooms}
    for row in _read_csv(data_dir / "schedules.csv"):
        windows[row["room_id"]].append(ScheduleWindow(
            day=int(row["day"]),
            start_hour=int(row["start_hour"]),
            end_hour=int(row["end_hour"]),
            occupancy_fraction=float(row["occupancy_fraction"]),
        ))

    weather_rows = _read_csv(data_dir / "weather.csv")
    weather_lookup = {
        (int(row["day"]), int(row["hour"])): float(row["t_out_c"])
        for row in weather_rows
    }
    t_out: list[float] = [
        weather_lookup[(day, hour)]
        for day in range(DAYS_PER_WEEK)
        for hour in range(HOURS_PER_DAY)
    ]

    occ_base, late_mask, precool_mask = _build_occupancy_matrices(rooms, windows, params)
    return Building(rooms=rooms, windows=windows, t_out=t_out, params=params,
                    occ_base=occ_base, late_mask=late_mask,
                    precool_mask=precool_mask)


def _build_occupancy_matrices(
    rooms: list[Room],
    windows: dict[str, list[ScheduleWindow]],
    params: ModelParams,
) -> tuple[list[list[float]], list[list[bool]], list[list[bool]]]:
    """Kehadiran dasar (fraksi kapasitas) per jam, penanda lembur lab, dan pra-pendinginan.

    Jendela jadwal diberi ekor 1 jam dengan fraksi 25% untuk memodelkan orang
    yang menuntaskan pekerjaan setelah jadwal berakhir. Pra-pendinginan adalah
    1 jam sebelum jadwal dimulai: petugas menyalakan AC lebih awal supaya
    ruangan tidak panas saat penghuni masuk.
    """
    n_rooms = len(rooms)
    occ_base = [[0.0] * n_rooms for _ in range(N_STEPS)]
    late_mask = [[False] * n_rooms for _ in range(N_STEPS)]
    precool_mask = [[False] * n_rooms for _ in range(N_STEPS)]

    for r_idx, room in enumerate(rooms):
        for window in windows[room.room_id]:
            for day in range(DAYS_PER_WEEK):
                if window.day != day:
                    continue
                for hour in range(window.start_hour, window.end_hour + 1):
                    step = day * HOURS_PER_DAY + hour
                    fraction = window.occupancy_fraction
                    if hour == window.end_hour:
                        fraction *= 0.25
                    if fraction > occ_base[step][r_idx]:
                        occ_base[step][r_idx] = fraction
                pre_cool_start = max(0, window.start_hour - int(params.pre_cool_hours))
                for hour in range(pre_cool_start, window.start_hour):
                    precool_mask[day * HOURS_PER_DAY + hour][r_idx] = True
        if room.room_type == "lab":
            for day in range(DAYS_PER_WEEK):
                for hour in range(17, 23):
                    step = day * HOURS_PER_DAY + hour
                    if occ_base[step][r_idx] == 0.0:
                        late_mask[step][r_idx] = True
    return occ_base, late_mask, precool_mask


def load_policies(data_dir: Path = DATA_DIR) -> list[Policy]:
    """Baca grid kebijakan dari ``data/policies.csv``."""
    policies: list[Policy] = []
    for row in _read_csv(Path(data_dir) / "policies.csv"):
        policies.append(Policy(
            policy_id=row["policy_id"],
            ac_start_hour=int(row["ac_start_hour"]),
            min_setpoint_c=float(row["min_setpoint_c"]),
            lab_close_hour=int(row["lab_close_hour"]),
            is_baseline=bool(int(row["is_baseline"])),
            label=row.get("label", ""),
        ))
    return policies


def simulate(
    policy: Policy,
    bld: Building,
    seed: int,
    rep: int,
    collect_profile: bool = False,
    trace: list | None = None,
) -> SimResult:
    """Jalankan satu simulasi mingguan untuk satu kebijakan.

    Keputusan kebijakan dan perilaku penghuni dihitung **per jam** (menunggu
    jadwal, AC boleh menyala atau tidak, penghuni menyalakan AC manual), lalu
    termal tiap ruang diintegrasikan **per 15 menit** agar termostat tidak
    "melewati" setpoint. Satu minggu = 168 jam = 672 langkah integrasi.

    ``trace`` bila diisi menerima catatan diagnosis tiap kejadian
    ketidaknyamanan (hari, jam, ruang, suhu, jenis) untuk investigasi.
    """
    params = bld.params
    n_hours = bld.n_steps
    n_rooms = bld.n_rooms
    substeps = params.substeps
    dt = params.dt_hours
    dt_hour = dt * substeps

    rng = np.random.default_rng(np.random.SeedSequence([int(seed), policy.seed_tag, int(rep)]))
    u_occ = rng.random((n_hours, n_rooms)).tolist()
    u_over = rng.random((n_hours, n_rooms)).tolist()
    u_late = rng.random((n_hours, n_rooms)).tolist()
    u_precool = rng.random((n_hours, n_rooms)).tolist()
    u_out = rng.random(n_hours).tolist()
    u_comfort = rng.random(n_rooms).tolist()

    area = [room.area_m2 for room in bld.rooms]
    capacity = [float(room.capacity) for room in bld.rooms]
    ac_kw = [room.ac_kw for room in bld.rooms]
    ac_units = [float(room.ac_units) for room in bld.rooms]
    base_kw = [room.base_kw for room in bld.rooms]
    critical = [room.critical for room in bld.rooms]
    is_lab = [room.room_type == "lab" for room in bld.rooms]
    ua = [params.ua_kw_per_k_per_m2 * a for a in area]
    ceff = [params.c_kwh_per_k_per_m2 * a for a in area]
    comfort_min = [params.comfort_min_c_base + params.comfort_min_c_span * u for u in u_comfort]
    standby = [b * params.standby_kw_fraction for b in base_kw]

    occ_base = bld.occ_base
    late_mask = bld.late_mask
    precool_mask = bld.precool_mask
    t_out_list = bld.t_out

    setpoint = [
        policy.min_setpoint_c if room.setpoint_mode == "policy"
        else min(policy.min_setpoint_c, room.setpoint_c)
        for room in bld.rooms
    ]
    indoor = [params.initial_indoor_c] * n_rooms
    hold = [0.0] * n_rooms

    people_arr = [0.0] * n_rooms
    allowed_arr = [False] * n_rooms
    run_arr = [False] * n_rooms
    precool_arr = [False] * n_rooms

    energy_ac = 0.0
    energy_base = 0.0
    peak_kw = 0.0
    discomfort = 0.0
    blocked_cooling = 0.0
    violations = 0
    critical_exposure = 0.0
    profile: list[float] = []

    for t in range(n_hours):
        hour = t % HOURS_PER_DAY
        t_out = t_out_list[t] + (u_out[t] - 0.5) * 2.0 * params.outdoor_noise_c
        base_row = occ_base[t]
        late_row = late_mask[t]
        precool_row = precool_mask[t]
        occ_noise_row = u_occ[t]
        over_row = u_over[t]
        late_noise_row = u_late[t]
        precool_noise_row = u_precool[t]

        for r in range(n_rooms):
            frac = base_row[r]
            if late_row[r]:
                frac = params.late_lab_occupancy_fraction * late_noise_row[r]
            elif frac > 0.0:
                frac = frac * (0.8 + 0.4 * occ_noise_row[r])
            people = frac * capacity[r]
            people_arr[r] = people

            allowed = hour >= policy.ac_start_hour
            if is_lab[r] and not critical[r] and hour >= policy.lab_close_hour:
                allowed = False
            allowed_arr[r] = allowed

            if people > 0.0:
                if allowed:
                    run_arr[r] = True
                    hold[r] = params.hold_hours
                else:
                    tendency = params.override_base_prob * (0.4 + 0.6 * (people / capacity[r]))
                    if over_row[r] < tendency:
                        run_arr[r] = True
                        hold[r] = params.hold_hours
                        violations += 1
                    else:
                        run_arr[r] = False
                        blocked_cooling += people * dt_hour
                precool_arr[r] = False
            else:
                precool_arr[r] = (
                    precool_row[r]
                    and precool_noise_row[r] < params.pre_cool_probability
                    and allowed
                )
                run_arr[r] = False

        for _ in range(substeps):
            building_kw = 0.0
            for r in range(n_rooms):
                people = people_arr[r]
                occupied = people > 0.0
                temp = indoor[r]
                sp = setpoint[r]

                if occupied:
                    machine_on = run_arr[r]
                elif precool_arr[r]:
                    machine_on = True
                elif hold[r] > 0.0 and allowed_arr[r]:
                    hold[r] -= dt
                    machine_on = True
                else:
                    machine_on = False

                q_internal = people * (params.internal_gain_w_per_person / 1000.0
                                       + params.equipment_kw_per_person)
                if machine_on:
                    q_max = ac_kw[r] * params.cop
                    q_load = ua[r] * (temp - sp) + q_internal
                    q_target = q_load + ceff[r] * (temp - sp) / dt
                    if q_target < 0.0:
                        q_target = 0.0
                    q_ac = q_target if q_target < q_max else q_max
                    if q_ac < 0.0:
                        q_ac = 0.0
                    part_load = (q_ac / q_max) if q_max > 0.0 else 0.0
                    p_ac = (q_ac / params.cop
                            + params.fan_kw_per_unit * ac_units[r] * (0.35 + 0.65 * part_load))
                    new_temp = temp + dt * (ua[r] * (t_out - temp) + q_internal - q_ac) / ceff[r]
                    if q_ac >= q_target and new_temp < sp:
                        new_temp = sp
                else:
                    q_ac = 0.0
                    p_ac = 0.0
                    new_temp = temp + dt * (ua[r] * (t_out - temp) + q_internal) / ceff[r]

                p_base = standby[r]
                if occupied:
                    p_base += base_kw[r] + people * params.equipment_kw_per_person \
                        + params.lighting_kw_per_m2 * area[r]
                else:
                    p_base += base_kw[r] * params.standby_kw_fraction

                indoor[r] = new_temp

                if occupied:
                    if new_temp > params.comfort_max_c:
                        discomfort += people * dt
                        if trace is not None:
                            trace.append((t // HOURS_PER_DAY, hour, bld.rooms[r].room_id,
                                          round(new_temp, 2), "panas", round(people, 1)))
                    elif new_temp < comfort_min[r]:
                        discomfort += people * dt
                        if trace is not None:
                            trace.append((t // HOURS_PER_DAY, hour, bld.rooms[r].room_id,
                                          round(new_temp, 2), "dingin", round(people, 1)))
                    if critical[r] and not allowed_arr[r]:
                        critical_exposure += dt

                power_kw = p_ac + p_base
                building_kw += power_kw
                energy_ac += p_ac * dt
                energy_base += p_base * dt

            if building_kw > peak_kw:
                peak_kw = building_kw
            if collect_profile:
                profile.append(building_kw)

    total_kwh = energy_ac + energy_base
    return SimResult(
        policy_id=policy.policy_id,
        rep=rep,
        energy_kwh=total_kwh,
        energy_ac_kwh=energy_ac,
        energy_base_kwh=energy_base,
        peak_kw=peak_kw,
        discomfort_person_hours=discomfort,
        blocked_cooling_person_hours=blocked_cooling,
        policy_violations=violations,
        critical_exposure_hours=critical_exposure,
        cost_idr=total_kwh * params.tariff_idr_per_kwh,
        profile_kw=profile or None,
    )


def occupied_person_hours(bld: Building) -> float:
    """Total jam-orang pemakaian mingguan ( Deterministik, tanpa derau acak).

    Dipakai sebagai penyebut untuk mengubah "orang-jam tidak nyaman" menjadi
    persentase, supaya metriknya bisa dibandingkan antar gedung.
    """
    total = 0.0
    for step in range(bld.n_steps):
        row = bld.occ_base[step]
        for r_idx, fraction in enumerate(row):
            if fraction:
                total += fraction * bld.rooms[r_idx].capacity
    return total


def simulate_chunk(
    policy: Policy,
    bld: Building,
    seed: int,
    rep_start: int,
    rep_end: int,
) -> list[SimResult]:
    """Jalankan ``rep_start..rep_end-1`` untuk satu kebijakan (unit kerja paralel)."""
    return [simulate(policy, bld, seed, rep) for rep in range(rep_start, rep_end)]


def sweep_serial(
    policies: list[Policy],
    bld: Building,
    seed: int,
    reps: int,
) -> list[SimResult]:
    """Sweep kebijakan secara serial (baseline untuk pembanding kecepatan)."""
    results: list[SimResult] = []
    for policy in policies:
        for rep in range(reps):
            results.append(simulate(policy, bld, seed, rep))
    return results


def write_results_csv(path: Path, results: list[SimResult], policies: dict[str, Policy]) -> None:
    """Tulis hasil simulasi per pengulangan ke CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "policy_id", "ac_start_hour", "min_setpoint_c", "lab_close_hour", "is_baseline",
        "rep", "energy_kwh", "energy_ac_kwh", "energy_base_kwh", "peak_kw",
        "discomfort_person_hours", "blocked_cooling_person_hours",
        "policy_violations", "critical_exposure_hours", "cost_idr",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for res in results:
            pol = policies[res.policy_id]
            writer.writerow({
                "policy_id": res.policy_id,
                "ac_start_hour": pol.ac_start_hour,
                "min_setpoint_c": pol.min_setpoint_c,
                "lab_close_hour": pol.lab_close_hour,
                "is_baseline": int(pol.is_baseline),
                "rep": res.rep,
                "energy_kwh": round(res.energy_kwh, 4),
                "energy_ac_kwh": round(res.energy_ac_kwh, 4),
                "energy_base_kwh": round(res.energy_base_kwh, 4),
                "peak_kw": round(res.peak_kw, 4),
                "discomfort_person_hours": round(res.discomfort_person_hours, 3),
                "blocked_cooling_person_hours": round(res.blocked_cooling_person_hours, 3),
                "policy_violations": res.policy_violations,
                "critical_exposure_hours": round(res.critical_exposure_hours, 3),
                "cost_idr": round(res.cost_idr, 2),
            })


def load_results_csv(path: Path) -> list[dict]:
    return _read_csv(Path(path))


def amdahl_speedup(workers: float, parallel_fraction: float) -> float:
    """Speedup teoretis menurut Hukum Amdahl."""
    if workers <= 0:
        return 1.0
    if parallel_fraction >= 1.0:
        return workers
    if parallel_fraction <= 0.0:
        return 1.0
    return 1.0 / ((1.0 - parallel_fraction) + parallel_fraction / workers)


def fit_amdahl(speedups: list[float], worker_counts: list[int]) -> float:
    """Estimasi fraksi paralel ``f`` dengan regresi non-linear (grid + golden section).

    Kuadrat kesalahan minimum: |S(N) - 1/((1-f) + f/N)|.
    """
    if not speedups:
        return 1.0
    best_f = 1.0
    best_err = float("inf")
    for i in range(1, 1001):
        f = i / 1000.0
        err = 0.0
        for workers, measured in zip(worker_counts, speedups):
            predicted = amdahl_speedup(workers, f)
            err += (measured - predicted) ** 2
        if err < best_err:
            best_err = err
            best_f = f
    return best_f


