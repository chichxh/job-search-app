#!/usr/bin/env python3
"""Developer utility for offline matching calibration.

Examples:
  python scripts/matching_calibration.py --pairs-json ./pairs.json
  python scripts/matching_calibration.py --pairs-json ./pairs.json --variant tuned=./tuned_weights.json --top-k 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.models import Profile, Vacancy
from app.db.session import SessionLocal
from app.services.matching.matching_service import MatchingService, build_scoring_config


def _load_pairs(pairs_json: Path | None, sample_size: int) -> list[dict[str, Any]]:
    if pairs_json:
        payload = json.loads(pairs_json.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            msg = "pairs json must be a list of objects"
            raise ValueError(msg)
        return payload

    with SessionLocal() as db:
        profile_ids = db.execute(select(Profile.id).order_by(Profile.id.asc()).limit(sample_size)).scalars().all()
        vacancy_ids = db.execute(select(Vacancy.id).order_by(Vacancy.id.asc()).limit(sample_size)).scalars().all()

    pairs: list[dict[str, Any]] = []
    for profile_id, vacancy_id in zip(profile_ids, vacancy_ids, strict=False):
        pairs.append({"profile_id": profile_id, "vacancy_id": vacancy_id})
    return pairs


def _load_variants(variant_args: list[str]) -> list[tuple[str, dict[str, Any] | None]]:
    variants: list[tuple[str, dict[str, Any] | None]] = [("default", None)]
    for raw in variant_args:
        if "=" not in raw:
            raise ValueError(f"Invalid --variant '{raw}', expected <label>=<path>")
        label, path = raw.split("=", 1)
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        variants.append((label.strip(), config))
    return variants


def _precision_at_k(rows: list[dict[str, Any]], k: int) -> float | None:
    labeled = [row for row in rows if row.get("label") is not None]
    if not labeled:
        return None
    top = sorted(labeled, key=lambda x: x["final_score"], reverse=True)[:k]
    if not top:
        return 0.0
    positives = sum(1 for row in top if int(row["label"]) == 1)
    return positives / len(top)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline matching calibration helper")
    parser.add_argument("--pairs-json", type=Path, help="JSON list of {profile_id, vacancy_id, label?}")
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Additional config variant in format <label>=<path-to-json>",
    )
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    pairs = _load_pairs(args.pairs_json, sample_size=args.sample_size)
    if not pairs:
        print("No pairs found. Provide --pairs-json or add profile/vacancy data.")
        return

    variants = _load_variants(args.variant)

    with SessionLocal() as db:
        for variant_name, overrides in variants:
            print(f"\n=== Variant: {variant_name} ===")
            service = MatchingService(db, scoring_config=build_scoring_config(overrides))
            rows: list[dict[str, Any]] = []

            for pair in pairs:
                profile_id = int(pair["profile_id"])
                vacancy_id = int(pair["vacancy_id"])
                label = pair.get("label")
                score = service.compute_for_pair(profile_id=profile_id, vacancy_id=vacancy_id)
                explanation = score.explanation or {}
                final = explanation.get("final", {})

                row = {
                    "profile_id": profile_id,
                    "vacancy_id": vacancy_id,
                    "label": label,
                    "final_score": float(score.final_score),
                    "verdict": score.verdict,
                    "components": final.get("components", {}),
                    "penalties": final.get("penalties", []),
                    "warnings": explanation.get("eligibility", {}).get("warnings", []),
                    "reasons_failed": explanation.get("eligibility", {}).get("reasons_failed", []),
                }
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False))

            precision = _precision_at_k(rows, k=args.top_k)
            reject_in_top = sum(
                1
                for row in sorted(rows, key=lambda x: x["final_score"], reverse=True)[: args.top_k]
                if row["verdict"] == "reject"
            )

            print("--- summary ---")
            if precision is None:
                print(f"precision@{args.top_k}: n/a (labels not provided)")
            else:
                print(f"precision@{args.top_k}: {precision:.3f}")
            print(f"reject_in_top_{args.top_k}: {reject_in_top}")


if __name__ == "__main__":
    main()
