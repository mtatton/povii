#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
from PIL import Image

from vector_features import crop_bbox, extract_visual_vector, vector_from_blob


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query the generated scene or object vector database with an image.",
    )
    parser.add_argument(
        "--database",
        choices=("scenes", "objects"),
        default="scenes",
        help="Which vector database to query.",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=Path("vector_databases"),
        help="Folder containing scene_vectors.sqlite and object_vectors.sqlite.",
    )
    parser.add_argument(
        "--query-image",
        type=Path,
        required=True,
        help="Image to embed and search for.",
    )
    parser.add_argument(
        "--crop",
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        type=int,
        nargs=4,
        help="Optional crop box inside the query image before embedding.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of nearest rows to print.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = args.db_dir / ("scene_vectors.sqlite" if args.database == "scenes" else "object_vectors.sqlite")
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")

    with Image.open(args.query_image) as raw_image:
        image = raw_image.convert("RGB")
    if args.crop:
        image = crop_bbox(image, tuple(args.crop))

    query_vector = extract_visual_vector(image)
    rows = load_rows(db_path, args.database)
    if not rows:
        raise SystemExit(f"No rows found in {db_path}")

    matrix = np.stack([row["vector"] for row in rows])
    scores = matrix @ query_vector
    order = np.argsort(scores)[::-1][: args.top_k]

    for rank, row_index in enumerate(order, start=1):
        row = rows[int(row_index)]
        score = float(scores[int(row_index)])
        if args.database == "scenes":
            print(f"{rank:02d}  score={score:.4f}  scene={row['scene_key']}  path={row['source_path']}")
        else:
            bbox = ",".join(str(value) for value in row["bbox"])
            print(
                f"{rank:02d}  score={score:.4f}  object={row['object_key']}  "
                f"scene={row['scene_key']}  area={row['area_ratio']:.3f}  "
                f"bbox={bbox}  path={row['source_path']}"
            )

    return 0


def load_rows(db_path: Path, database: str) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if database == "scenes":
            sql = """
                SELECT scene_key, source_path, vector_dim, vector
                FROM scenes
                ORDER BY scene_id
            """
        else:
            sql = """
                SELECT object_key, scene_key, source_path, area_ratio,
                       bbox_x, bbox_y, bbox_width, bbox_height,
                       vector_dim, vector
                FROM objects
                ORDER BY object_id
            """

        rows: list[dict[str, object]] = []
        for db_row in conn.execute(sql):
            row = dict(db_row)
            row["vector"] = vector_from_blob(row["vector"], int(row["vector_dim"]))
            if database == "objects":
                row["bbox"] = (
                    row.pop("bbox_x"),
                    row.pop("bbox_y"),
                    row.pop("bbox_width"),
                    row.pop("bbox_height"),
                )
            rows.append(row)
        return rows


if __name__ == "__main__":
    raise SystemExit(main())
