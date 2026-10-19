"""Uji kebenaran simulator dan jalur paralel.

Dapat dijalankan tanpa pytest::

    python tests/test_model.py

Atau dengan pytest bila terpasang::

    pytest tests/test_model.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import model  # noqa: E402
import sweep_parallel as sp  # noqa: E402

SEED = 42


def _building():
    return model.load_building(ROOT / "data")


def _policy(**kwargs) -> model.Policy:
    defaults = dict(policy_id="T", ac_start_hour=7, min_setpoint_c=24.0,
                    lab_close_hour=20, is_baseline=False, label="uji")
    defaults.update(kwargs)
    return model.Policy(**defaults)


def test_building_loads() -> None:
    bld = _building()
    assert bld.n_rooms == 13, bld.n_rooms
    assert bld.n_steps == 168, bld.n_steps
    assert len(bld.occ_base) == 168
    assert len(bld.occ_base[0]) == 13
    assert any(room.critical for room in bld.rooms), "harus ada ruang kritis"
    assert bld.t_out[12] > 24.0


def test_determinism() -> None:
    bld = _building()
    policy = _policy()
    first = model.simulate(policy, bld, SEED, 0)
    second = model.simulate(policy, bld, SEED, 0)
    assert first.energy_kwh == second.energy_kwh
    assert first.discomfort_person_hours == second.discomfort_person_hours
    other = model.simulate(policy, bld, SEED, 1)
    assert other.energy_kwh != first.energy_kwh, "pengulangan berbeda harus beda hasil"


def test_energy_accounting() -> None:
    bld = _building()
    result = model.simulate(_policy(), bld, SEED, 0)
    total = result.energy_ac_kwh + result.energy_base_kwh
    assert abs(total - result.energy_kwh) < 1e-9
    assert result.peak_kw > 0
    assert result.energy_ac_kwh > 0, "AC harus ada yang menyala"


def test_serial_matches_parallel() -> None:
    bld = _building()
    policies = [_policy(policy_id=f"P{i}") for i in range(4)]
    serial = model.sweep_serial(policies, bld, SEED, 3)
    parallel, _ = sp.run_parallel(policies, bld, SEED, 3, workers=3,
                                  data_dir=ROOT / "data")
    assert len(serial) == len(parallel) == 12
    for a, b in zip(serial, parallel):
        assert a.policy_id == b.policy_id
        assert a.rep == b.rep
        assert abs(a.energy_kwh - b.energy_kwh) < 1e-9
        assert a.policy_violations == b.policy_violations


def test_critical_room_constraint() -> None:
    bld = _building()
    awal = model.simulate(_policy(ac_start_hour=6), bld, SEED, 0)
    akhir = model.simulate(_policy(ac_start_hour=10), bld, SEED, 0)
    assert awal.critical_exposure_hours == 0.0, "AC menyala jam 6 harus menutupi lab kritis"
    assert akhir.critical_exposure_hours > 0.0, "lab kritis harus terekspos bila AC telat"


def test_setpoint_saves_energy() -> None:
    bld = _building()
    dingin = model.simulate(_policy(min_setpoint_c=22.0), bld, SEED, 0)
    hangat = model.simulate(_policy(min_setpoint_c=26.0), bld, SEED, 0)
    assert hangat.energy_kwh < dingin.energy_kwh, "setpoint lebih tinggi harus hemat energi"


def test_lab_close_saves_energy() -> None:
    bld = _building()
    buka = model.simulate(_policy(lab_close_hour=23), bld, SEED, 0)
    tutup = model.simulate(_policy(lab_close_hour=17), bld, SEED, 0)
    assert tutup.energy_kwh < buka.energy_kwh, "lab lebih cepat ditutup harus hemat energi"


def test_policy_effect_direction() -> None:
    bld = _building()
    pagi = model.simulate(_policy(ac_start_hour=6), bld, SEED, 0)
    siang = model.simulate(_policy(ac_start_hour=10), bld, SEED, 0)
    assert siang.energy_kwh < pagi.energy_kwh, "AC lebih lambat menyala harus hemat energi"
    assert siang.critical_exposure_hours > pagi.critical_exposure_hours


def test_amdahl() -> None:
    assert abs(model.amdahl_speedup(1, 0.9) - 1.0) < 1e-9
    assert abs(model.amdahl_speedup(10, 1.0) - 10.0) < 1e-9
    assert model.amdahl_speedup(8, 0.9) < 8.0
    workers = [2, 4, 8, 16]
    speedups = [model.amdahl_speedup(n, 0.9) for n in workers]
    assert abs(model.fit_amdahl(speedups, workers) - 0.9) < 0.02


def test_write_and_read_results(tmp_dir: Path | None = None) -> None:
    import tempfile

    bld = _building()
    policy = _policy(policy_id="PX")
    results = [model.simulate(policy, bld, SEED, rep) for rep in range(2)]
    target_dir = Path(tmp_dir) if tmp_dir else Path(tempfile.mkdtemp())
    path = target_dir / "sweep_results.csv"
    model.write_results_csv(path, results, {policy.policy_id: policy})
    rows = model.load_results_csv(path)
    assert len(rows) == 2
    assert abs(float(rows[0]["energy_kwh"]) - results[0].energy_kwh) < 1e-4


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    gagal = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            gagal += 1
            print(f"GAGAL  {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            gagal += 1
            print(f"ERROR  {test.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"LULUS  {test.__name__}")
    print(f"\n{len(tests) - gagal}/{len(tests)} uji lulus")
    return 1 if gagal else 0


if __name__ == "__main__":
    raise SystemExit(main())
