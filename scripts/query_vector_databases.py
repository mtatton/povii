#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
from PIL import Image

from vector_features import camera_blocks, crop_bbox, extract_source_vector, extract_visual_vector, material_blocks, vector_from_blob


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query the generated scene, object, POV source, material, or camera vector database.",
    )
    parser.add_argument(
        "--database",
        choices=("scenes", "objects", "povs", "materials", "cameras"),
        default="scenes",
        help="Which vector database to query.",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=Path("vector_databases"),
        help="Folder containing the SQLite vector databases.",
    )
    parser.add_argument(
        "--query-image",
        type=Path,
        help="Image to embed and search for. Required for scene and object queries.",
    )
    parser.add_argument(
        "--query-pov",
        type=Path,
        help="POV-Ray source file to embed and search for. Required for POV source queries unless --query-text is used.",
    )
    parser.add_argument(
        "--query-text",
        help="Raw source or material snippet to embed and search for.",
    )
    parser.add_argument(
        "--query-lines",
        metavar=("START", "END"),
        type=int,
        nargs=2,
        help="Line range from --query-pov to embed for source or material queries.",
    )
    parser.add_argument(
        "--query-material-name",
        help="Named material/texture block from --query-pov to embed for material queries.",
    )
    parser.add_argument(
        "--query-camera-name",
        help="Named camera block from --query-pov to embed for camera queries.",
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
    db_path = database_path(args.db_dir, args.database)
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")

    if args.database in {"povs", "materials", "cameras"}:
        if args.crop:
            raise SystemExit("--crop is only supported for image queries")
        query_vector = extract_source_vector(load_source_query_text(args))
    else:
        if not args.query_image:
            raise SystemExit("--query-image is required when --database scenes or objects")
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
        elif args.database == "objects":
            bbox = ",".join(str(value) for value in row["bbox"])
            print(
                f"{rank:02d}  score={score:.4f}  object={row['object_key']}  "
                f"scene={row['scene_key']}  area={row['area_ratio']:.3f}  "
                f"bbox={bbox}  path={row['source_path']}"
            )
        elif args.database == "povs":
            print(
                f"{rank:02d}  score={score:.4f}  pov={row['pov_key']}  "
                f"lines={row['line_count']}  tokens={row['token_count']}  path={row['source_path']}"
            )
        elif args.database == "materials":
            name = f"  name={row['material_name']}" if row["material_name"] else ""
            print(
                f"{rank:02d}  score={score:.4f}  material={row['material_key']}  "
                f"pov={row['pov_key']}{name}  type={row['block_type']}  "
                f"method={row['detection_method']}  lines={row['start_line']}-{row['end_line']}  "
                f"tokens={row['token_count']}  path={row['source_path']}"
            )
        else:
            name = f"  name={row['camera_name']}" if row["camera_name"] else ""
            angle = f"  angle={row['angle_text']}" if row["angle_text"] else ""
            print(
                f"{rank:02d}  score={score:.4f}  camera={row['camera_key']}  "
                f"pov={row['pov_key']}{name}  method={row['detection_method']}  "
                f"lines={row['start_line']}-{row['end_line']}  tokens={row['token_count']}{angle}  "
                f"path={row['source_path']}"
            )

    return 0


def load_source_query_text(args: argparse.Namespace) -> str:
    if args.query_text:
        return args.query_text
    if not args.query_pov:
        raise SystemExit(f"--query-pov or --query-text is required when --database {args.database}")

    source_text = args.query_pov.read_text(encoding="utf-8", errors="replace")
    if args.query_lines:
        start_line, end_line = args.query_lines
        lines = source_text.splitlines(keepends=True)
        if start_line < 1 or end_line < start_line or end_line > len(lines):
            raise SystemExit(f"--query-lines must fit inside 1-{len(lines)}")
        return "".join(lines[start_line - 1:end_line])

    if args.query_material_name:
        if args.database != "materials":
            raise SystemExit("--query-material-name is only supported for material queries")
        for block in material_blocks(source_text):
            if block.name == args.query_material_name:
                return block.text
        raise SystemExit(f"Material block does not exist in {args.query_pov}: {args.query_material_name}")

    if args.query_camera_name:
        if args.database != "cameras":
            raise SystemExit("--query-camera-name is only supported for camera queries")
        for block in camera_blocks(source_text):
            if block.name == args.query_camera_name:
                return block.text
        raise SystemExit(f"Camera block does not exist in {args.query_pov}: {args.query_camera_name}")

    if args.database == "materials":
        blocks = material_blocks(source_text)
        if not blocks:
            raise SystemExit(f"No material blocks found in {args.query_pov}; use --query-text or --query-lines")
        return blocks[0].text

    if args.database == "cameras":
        blocks = camera_blocks(source_text)
        if not blocks:
            raise SystemExit(f"No camera blocks found in {args.query_pov}; use --query-text or --query-lines")
        return blocks[0].text

    return source_text


def database_path(db_dir: Path, database: str) -> Path:
    if database == "scenes":
        return db_dir / "scene_vectors.sqlite"
    if database == "objects":
        return db_dir / "object_vectors.sqlite"
    if database == "povs":
        return db_dir / "pov_vectors.sqlite"
    if database == "materials":
        return db_dir / "material_vectors.sqlite"
    return db_dir / "camera_vectors.sqlite"


def load_rows(db_path: Path, database: str) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if database == "scenes":
            sql = """
                SELECT scene_key, source_path, vector_dim, vector
                FROM scenes
                ORDER BY scene_id
            """
        elif database == "objects":
            sql = """
                SELECT object_key, scene_key, source_path, area_ratio,
                       bbox_x, bbox_y, bbox_width, bbox_height,
                       vector_dim, vector
                FROM objects
                ORDER BY object_id
            """
        elif database == "povs":
            sql = """
                SELECT pov_key, source_path, line_count, token_count,
                       vector_dim, vector
                FROM povs
                ORDER BY pov_id
            """
        elif database == "materials":
            sql = """
                SELECT material_key, pov_key, source_path, material_name,
                       block_type, detection_method, start_line, end_line,
                       token_count, vector_dim, vector
                FROM materials
                ORDER BY material_id
            """
        else:
            sql = """
                SELECT camera_key, pov_key, source_path, camera_name,
                       detection_method, start_line, end_line, token_count,
                       angle_text, vector_dim, vector
                FROM cameras
                ORDER BY camera_id
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
