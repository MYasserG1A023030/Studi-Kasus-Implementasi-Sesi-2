"""Analisis hasil sweep: ringkasan kebijakan, rekomendasi, dan grafik.

Membaca ``results/sweep_results.csv`` (hasil simulasi per pengulangan) lalu
menghasilkan:

* ``results/policy_summary.csv``  - ringkasan per kebijakan (energi, ketidaknyamanan,
  pelanggaran, hemat vs status quo, kelayakan).
* ``results/recommended_policy.json`` - kebijakan yang direkomendasikan beserta
  alasannya.
* ``results/figures/*.png`` - grafik profil beban, frontier energi vs
  ketidaknyamanan, peta panas kebijakan, speedup, dan efisiensi.

Jalankan::

    python src/analysis.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import model  # noqa: E402

FIG_DIR = model.RESULTS_DIR / "figures"
PALETTE = {
    "serial": "#2b2d42",
    "parallel": "#ef233c",
    "amdahl": "#3a86ff",
    "ceiling": "#ffb703",
    "grid": "#e5e5e5",
    "accent": "#06d6a0",
    "muted": "#8d99ae",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analisis hasil sweep kebijakan.")
    parser.add_argument("--results", type=Path,
                        default=model.RESULTS_DIR / "sweep_results.csv")
    parser.add_argument("--data-dir", type=Path, default=model.DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=model.RESULTS_DIR)
    parser.add_argument("--max-discomfort", type=float, default=60.0,
                        help="batas tolerated orang-jam tidak nyaman per minggu")
    return parser.parse_args()


def build_summary(raw: pd.DataFrame, max_discomfort: float,
                  occupied_person_hours: float) -> pd.DataFrame:
    """Agregasi per pengulangan menjadi ringkasan per kebijakan.

    Syarat layak (feasible) memakai dua batasan nyata:

    * ``mean_critical_exposure_hours == 0`` - ruang kritis (Lab Biologi) tidak
      boleh kehilangan pendinginan saat dipakai. Ini batasan keras.
    * ``mean_discomfort_person_hours <= max_discomfort`` - ketidaknyamanan
      ter tolerated/minggu. Ini batasan lunak.

    ``mean_policy_violations`` (peristiwa AC dinyalakan manual oleh penghuni)
    bukan penentu kelayakan, melainkan ukuran resistansi terhadap kebijakan:
    kebijakan yang terlalu ketat membuat penghuni menabrak aturan.
    """
    grouped = raw.groupby("policy_id", sort=False)
    summary = grouped.agg(
        ac_start_hour=("ac_start_hour", "first"),
        min_setpoint_c=("min_setpoint_c", "first"),
        lab_close_hour=("lab_close_hour", "first"),
        is_baseline=("is_baseline", "first"),
        n_reps=("energy_kwh", "size"),
        mean_energy_kwh=("energy_kwh", "mean"),
        std_energy_kwh=("energy_kwh", "std"),
        p95_energy_kwh=("energy_kwh", lambda s: s.quantile(0.95)),
        mean_peak_kw=("peak_kw", "mean"),
        mean_discomfort_person_hours=("discomfort_person_hours", "mean"),
        mean_blocked_cooling_person_hours=("blocked_cooling_person_hours", "mean"),
        mean_policy_violations=("policy_violations", "mean"),
        mean_critical_exposure_hours=("critical_exposure_hours", "mean"),
        mean_cost_idr=("cost_idr", "mean"),
    ).reset_index()

    baseline = summary.loc[summary["is_baseline"] == 1, "mean_energy_kwh"]
    base_value = float(baseline.iloc[0]) if len(baseline) else float("nan")
    summary["saving_vs_baseline_pct"] = (base_value - summary["mean_energy_kwh"]) / base_value * 100.0
    summary["discomfort_rate_pct"] = (
        summary["mean_discomfort_person_hours"] / occupied_person_hours * 100.0
        if occupied_person_hours else 0.0
    )
    summary["feasible"] = (
        (summary["mean_critical_exposure_hours"] <= 0.0)
        & (summary["mean_discomfort_person_hours"] <= max_discomfort)
    ).astype(int)
    summary = summary.sort_values(["feasible", "mean_energy_kwh"],
                                  ascending=[False, True]).reset_index(drop=True)
    return summary


def select_recommendation(summary: pd.DataFrame, max_discomfort: float) -> dict:
    """Pilih kebijakan paling hemat yang tetap memenuhi seluruh batasan.

    Dua kandidat dilaporkan:

    * ``best`` - energi terkecil di antara kebijakan yang memenuhi batasan.
    * ``recommended`` - kebijakan yang paling *dapat ditegakkan*: dari kandidat
      yang energinya dalam 1% dari yang terbaik, ambil yang paling sedikit
      peristiwa AC dinyalakan manual (resistansi penghuni).
    """
    feasible = summary[summary["feasible"] == 1]
    if feasible.empty:
        best = summary.sort_values("mean_energy_kwh").iloc[0]
        reason = ("Tidak ada kebijakan yang memenuhi batasan keras; "
                  "dipilih yang paling hemat untuk pemeriksaan manual.")
        recommended = best
    else:
        best = feasible.iloc[0]
        near_best = feasible[
            feasible["mean_energy_kwh"] <= best["mean_energy_kwh"] * 1.01
        ].sort_values("mean_policy_violations")
        recommended = near_best.iloc[0] if not near_best.empty else best
        reason = (f"Hemat {recommended['saving_vs_baseline_pct']:.1f}% dibanding status quo, "
                  f"tanpa paparan ruang kritis, dan ketidaknyamanan "
                  f"{recommended['mean_discomfort_person_hours']:.1f} orang-jam/minggu "
                  f"(batas {max_discomfort:.0f}).")

    baseline_rows = summary[summary["is_baseline"] == 1]
    baseline_energy = float(baseline_rows["mean_energy_kwh"].iloc[0]) if len(baseline_rows) else None
    baseline_saving = None
    if len(baseline_rows):
        b = baseline_rows.iloc[0]
        baseline_saving = {
            "mean_energy_kwh": round(float(b["mean_energy_kwh"]), 2),
            "mean_discomfort_person_hours": round(float(b["mean_discomfort_person_hours"]), 2),
            "mean_policy_violations": float(b["mean_policy_violations"]),
            "mean_critical_exposure_hours": float(b["mean_critical_exposure_hours"]),
        }

    def _pack(row) -> dict:
        return {
            "policy_id": row["policy_id"],
            "ac_start_hour": int(row["ac_start_hour"]),
            "min_setpoint_c": float(row["min_setpoint_c"]),
            "lab_close_hour": int(row["lab_close_hour"]),
            "mean_energy_kwh": round(float(row["mean_energy_kwh"]), 2),
            "saving_vs_baseline_pct": round(float(row["saving_vs_baseline_pct"]), 2),
            "mean_peak_kw": round(float(row["mean_peak_kw"]), 2),
            "mean_discomfort_person_hours": round(float(row["mean_discomfort_person_hours"]), 2),
            "discomfort_rate_pct": round(float(row["discomfort_rate_pct"]), 3),
            "mean_policy_violations": float(row["mean_policy_violations"]),
            "mean_critical_exposure_hours": float(row["mean_critical_exposure_hours"]),
            "mean_cost_idr": round(float(row["mean_cost_idr"]), 2),
        }

    return {
        **_pack(recommended),
        "baseline_mean_energy_kwh": round(baseline_energy, 2) if baseline_energy else None,
        "n_feasible_policies": int(summary["feasible"].sum()),
        "n_policies_evaluated": int(len(summary)),
        "max_discomfort_person_hours": max_discomfort,
        "baseline": baseline_saving,
        "lowest_energy_feasible": _pack(best),
        "reason": reason,
    }


def plot_heatmap(summary: pd.DataFrame, out_path: Path) -> None:
    """Peta panas energi rata-rata: jam mulai AC x jam tutup lab (setpoint terbaik)."""
    best_setpoint = summary.sort_values("mean_energy_kwh")["min_setpoint_c"].iloc[0]
    subset = summary[summary["min_setpoint_c"] == best_setpoint]
    pivot = subset.pivot_table(index="lab_close_hour", columns="ac_start_hour",
                               values="mean_energy_kwh", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.imshow(pivot.values, cmap="YlGnBu_r", aspect="auto", origin="lower")
    ax.set_xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [str(i) for i in pivot.index])
    ax.set_xlabel("Jam mulai AC (jam)")
    ax.set_ylabel("Jam tutup lab (jam)")
    ax.set_title(f"Rata-rata energi (kWh/minggu) pada setpoint {best_setpoint:.0f} C")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.0f}", ha="center", va="center",
                    fontsize=9, color="white" if pivot.values[i, j] > pivot.values.mean() else "black")
    fig.colorbar(image, ax=ax, label="kWh/minggu")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_frontier(summary: pd.DataFrame, out_path: Path) -> None:
    """Frontier tradeoff: energi vs ketidaknyamanan, tandai kelayakan.

    Panel kiri: seluruh kebijakan. Panel kanan: zoom pada daerah layak,
    karena kebijakan yang melanggar batasan membuat skala mendatar penuh.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    feasible = summary[summary["feasible"] == 1]
    infeasible = summary[summary["feasible"] == 0]
    baseline = summary[summary["is_baseline"] == 1]
    best = summary.sort_values(["feasible", "mean_energy_kwh"], ascending=[False, True]).iloc[0]

    for ax, xmax in zip(axes, (None, 120.0)):
        ax.scatter(infeasible["mean_discomfort_person_hours"], infeasible["mean_energy_kwh"],
                   s=28, color=PALETTE["muted"], alpha=0.55, label="Melanggar batasan")
        ax.scatter(feasible["mean_discomfort_person_hours"], feasible["mean_energy_kwh"],
                   s=34, color=PALETTE["accent"], alpha=0.85, label="Memenuhi batasan")
        if not baseline.empty:
            b = baseline.iloc[0]
            ax.scatter([b["mean_discomfort_person_hours"]], [b["mean_energy_kwh"]],
                       s=170, marker="*", color=PALETTE["serial"], label="Status quo")
        ax.scatter([best["mean_discomfort_person_hours"]], [best["mean_energy_kwh"]],
                   s=190, marker="*", color=PALETTE["parallel"], label="Rekomendasi")
        ax.set_xlabel("Ketidaknyamanan (orang-jam/minggu)")
        ax.set_ylabel("Energi (kWh/minggu)")
        ax.grid(alpha=0.25)
        if xmax is not None:
            ax.set_xlim(-5, xmax)
            ax.set_title("Zoom daerah layak (batas 60 orang-jam)")
        else:
            ax.set_title("Seluruh kebijakan")

    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_scaling(out_dir: Path) -> None:
    """Grafik speedup, efisiensi, dan kurva Amdahl dari hasil benchmark."""
    speedup_path = out_dir / "speedup.csv"
    if not speedup_path.exists():
        return
    speedup = pd.read_csv(speedup_path)
    ceiling_path = out_dir / "hardware_ceiling.csv"
    ceiling = pd.read_csv(ceiling_path) if ceiling_path.exists() else None

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax = axes[0]
    ax.plot(speedup["workers"], speedup["speedup"], "o-", color=PALETTE["parallel"],
            label="Speedup terukur")
    ax.plot(speedup["workers"], speedup["steady_state_speedup"], "s--",
            color=PALETTE["accent"], label="Speedup tanpa biaya start up pool")
    ideal = speedup["workers"].max()
    ax.plot([1, ideal], [1, ideal], ":", color=PALETTE["muted"], label="Speedup ideal (linear)")
    ax.plot(speedup["workers"], speedup["amdahl_predicted_speedup"], "--",
            color=PALETTE["amdahl"], label=f"Amdahl (f = {speedup['amdahl_f'].iloc[0]:.3f})")
    if ceiling is not None:
        ax.plot(ceiling["workers"], ceiling["speedup"], "^:", color=PALETTE["ceiling"],
                label="Plafon mesin (CPU murni)")
    ax.set_xlabel("Jumlah pekerja")
    ax.set_ylabel("Speedup")
    ax.set_title("Speedup paralel")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    ax.plot(speedup["workers"], speedup["efficiency"] * 100, "o-", color=PALETTE["parallel"],
            label="Efisiensi (speedup/N)")
    if ceiling is not None:
        ax.plot(ceiling["workers"], ceiling["efficiency"] * 100, "^:",
                color=PALETTE["ceiling"], label="Efisiensi plafon mesin")
    ax.set_xlabel("Jumlah pekerja")
    ax.set_ylabel("Efisiensi (%)")
    ax.set_title("Efisiensi paralel")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(out_dir / "figures" / "speedup.png", dpi=150)
    plt.close(fig)


def plot_daily_profile(bld, policy, out_path: Path) -> None:
    """Profil beban 24 jam (rata-rata 7 hari) dari satu simulasi."""
    fig, ax = plt.subplots(figsize=(9, 5))
    substeps = bld.params.substeps
    for pol, color, label in ((policy["baseline"], PALETTE["serial"], "Status quo"),
                              (policy["recommended"], PALETTE["accent"], "Rekomendasi")):
        result = model.simulate(pol, bld, seed=20260101, rep=0, collect_profile=True)
        profile = np.array(result.profile_kw)
        hourly = profile.reshape(7, 24, substeps).mean(axis=2)
        daily = hourly.mean(axis=0)
        ax.plot(range(24), daily, marker="o", color=color, label=label)
    ax.set_xlabel("Jam")
    ax.set_ylabel("Daya gedung (kW)")
    ax.set_title("Profil beban harian gedung (rata-rata 7 hari simulasi)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.results)
    bld = model.load_building(args.data_dir)
    occupied = model.occupied_person_hours(bld)
    summary = build_summary(raw, args.max_discomfort, occupied)

    summary.to_csv(out_dir / "policy_summary.csv", index=False)

    policies = {p.policy_id: p for p in model.load_policies(args.data_dir)}
    recommendation = select_recommendation(summary, args.max_discomfort)
    (out_dir / "recommended_policy.json").write_text(
        json.dumps(recommendation, indent=2), encoding="utf-8")

    bld = model.load_building(args.data_dir)
    baseline_policy = next(p for p in policies.values() if p.is_baseline)
    recommended_policy = policies[recommendation["policy_id"]]
    plot_daily_profile(bld, {"baseline": baseline_policy, "recommended": recommended_policy},
                       fig_dir / "profil_beban_harian.png")
    plot_frontier(summary, fig_dir / "frontier_kebijakan.png")
    plot_heatmap(summary, fig_dir / "peta_panas_kebijakan.png")
    plot_scaling(out_dir)

    print(f"[analisis] {len(summary)} kebijakan diringkas -> {out_dir / 'policy_summary.csv'}")
    print(f"[analisis] rekomendasi: {recommendation['policy_id']} "
          f"(AC>={recommendation['ac_start_hour']}, setpoint>={recommendation['min_setpoint_c']}C, "
          f"lab<={recommendation['lab_close_hour']})")
    print(f"[analisis] {recommendation['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
