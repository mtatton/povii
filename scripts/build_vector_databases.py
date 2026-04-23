#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import json
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from vector_features import (
    VISUAL_VECTOR_DIM,
    crop_bbox,
    extract_visual_vector,
    find_object_candidates,
    image_files,
    relative_path,
    vector_to_blob,
)


VECTOR_MODEL = "povii-visual-descriptor-v1"
SCENE_DB_NAME = "scene_vectors.sqlite"
OBJECT_DB_NAME = "object_vectors.sqlite"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class ImageStats:
    palette: list[str]
    mean_rgb: tuple[float, float, float]
    brightness: float
    contrast: float


@dataclass(frozen=True)
class SceneBuildResult:
    scene_row: tuple[object, ...]
    object_rows: list[tuple[object, ...]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build scene and object vector databases from rendered scene images.",
    )
    parser.add_argument(
        "--scenes-dir",
        type=Path,
        default=Path("scenes"),
        help="Folder containing rendered scene images.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("vector_databases"),
        help="Folder where the SQLite vector databases will be written.",
    )
    parser.add_argument(
        "--max-objects-per-scene",
        type=int,
        default=8,
        help="Maximum salient object candidates to store for each scene.",
    )
    parser.add_argument(
        "--object-min-area-ratio",
        type=float,
        default=0.006,
        help="Minimum object candidate area as a ratio of the source scene image.",
    )
    parser.add_argument(
        "--object-max-area-ratio",
        type=float,
        default=0.45,
        help="Maximum object candidate area as a ratio of the source scene image.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress after this many processed scenes. Use 0 to disable.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes to use while extracting scene and object vectors.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenes_dir = args.scenes_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = image_files(scenes_dir)
    if not files:
        raise SystemExit(f"No scene images found in {scenes_dir}")

    scene_db_path = output_dir / SCENE_DB_NAME
    object_db_path = output_dir / OBJECT_DB_NAME
    for db_path in (scene_db_path, object_db_path):
        if db_path.exists():
            db_path.unlink()

    start = time.monotonic()
    with sqlite3.connect(scene_db_path) as scene_conn, sqlite3.connect(object_db_path) as object_conn:
        configure_connection(scene_conn)
        configure_connection(object_conn)
        create_scene_schema(scene_conn)
        create_object_schema(object_conn)

        scene_count = 0
        object_count = 0

        build_args = [
            (
                image_path,
                Path.cwd(),
                args.max_objects_per_scene,
                args.object_min_area_ratio,
                args.object_max_area_ratio,
            )
            for image_path in files
        ]

        if args.workers > 1:
            max_workers = min(args.workers, os.cpu_count() or args.workers)
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(process_scene_data_from_args, build_args, chunksize=8)
                for index, result in enumerate(results, start=1):
                    scene_objects = insert_scene_result(scene_conn, object_conn, result)
                    scene_count += 1
                    object_count += scene_objects

                    if args.progress_every and index % args.progress_every == 0:
                        elapsed = time.monotonic() - start
                        print(f"processed {index}/{len(files)} scenes, {object_count} objects in {elapsed:.1f}s", flush=True)
        else:
            for index, image_path in enumerate(files, start=1):
                scene_objects = process_scene(
                    scene_conn=scene_conn,
                    object_conn=object_conn,
                    image_path=image_path,
                    base_dir=Path.cwd(),
                    max_objects=args.max_objects_per_scene,
                    min_area_ratio=args.object_min_area_ratio,
                    max_area_ratio=args.object_max_area_ratio,
                )
                scene_count += 1
                object_count += scene_objects

                if args.progress_every and index % args.progress_every == 0:
                    elapsed = time.monotonic() - start
                    print(f"processed {index}/{len(files)} scenes, {object_count} objects in {elapsed:.1f}s", flush=True)

        created_at = datetime.now(timezone.utc).isoformat()
        write_metadata(
            scene_conn,
            {
                "kind": "scene_vectors",
                "created_at": created_at,
                "source_dir": relative_path(scenes_dir, Path.cwd()),
                "source_image_count": scene_count,
                "vector_model": VECTOR_MODEL,
                "vector_dim": VISUAL_VECTOR_DIM,
            },
        )
        write_metadata(
            object_conn,
            {
                "kind": "object_vectors",
                "created_at": created_at,
                "source_dir": relative_path(scenes_dir, Path.cwd()),
                "source_image_count": scene_count,
                "object_count": object_count,
                "max_objects_per_scene": args.max_objects_per_scene,
                "object_min_area_ratio": args.object_min_area_ratio,
                "object_max_area_ratio": args.object_max_area_ratio,
                "vector_model": VECTOR_MODEL,
                "vector_dim": VISUAL_VECTOR_DIM,
            },
        )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": relative_path(scenes_dir, Path.cwd()),
        "vector_model": VECTOR_MODEL,
        "vector_dim": VISUAL_VECTOR_DIM,
        "databases": {
            "scenes": {
                "path": relative_path(scene_db_path, Path.cwd()),
                "rows": scene_count,
                "table": "scenes",
                "vector_column": "vector",
            },
            "objects": {
                "path": relative_path(object_db_path, Path.cwd()),
                "rows": object_count,
                "table": "objects",
                "vector_column": "vector",
            },
        },
    }
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    elapsed = time.monotonic() - start
    print(f"wrote {scene_count} scene vectors to {relative_path(scene_db_path, Path.cwd())}")
    print(f"wrote {object_count} object vectors to {relative_path(object_db_path, Path.cwd())}")
    print(f"wrote manifest to {relative_path(manifest_path, Path.cwd())}")
    print(f"finished in {elapsed:.1f}s")
    return 0


def configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")


def create_scene_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE scenes (
            scene_id INTEGER PRIMARY KEY,
            scene_key TEXT NOT NULL UNIQUE,
            source_path TEXT NOT NULL UNIQUE,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            vector_model TEXT NOT NULL,
            vector_dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            palette_json TEXT NOT NULL,
            mean_rgb_json TEXT NOT NULL,
            brightness REAL NOT NULL,
            contrast REAL NOT NULL,
            source_size_bytes INTEGER NOT NULL,
            source_mtime REAL NOT NULL
        );

        CREATE INDEX idx_scenes_scene_key ON scenes(scene_key);
        """
    )


def create_object_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE objects (
            object_id INTEGER PRIMARY KEY,
            object_key TEXT NOT NULL UNIQUE,
            scene_key TEXT NOT NULL,
            source_path TEXT NOT NULL,
            bbox_x INTEGER NOT NULL,
            bbox_y INTEGER NOT NULL,
            bbox_width INTEGER NOT NULL,
            bbox_height INTEGER NOT NULL,
            bbox_norm_x REAL NOT NULL,
            bbox_norm_y REAL NOT NULL,
            bbox_norm_width REAL NOT NULL,
            bbox_norm_height REAL NOT NULL,
            area_ratio REAL NOT NULL,
            saliency_score REAL NOT NULL,
            detection_method TEXT NOT NULL,
            vector_model TEXT NOT NULL,
            vector_dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            palette_json TEXT NOT NULL,
            mean_rgb_json TEXT NOT NULL,
            brightness REAL NOT NULL,
            contrast REAL NOT NULL,
            source_size_bytes INTEGER NOT NULL,
            source_mtime REAL NOT NULL
        );

        CREATE INDEX idx_objects_scene_key ON objects(scene_key);
        CREATE INDEX idx_objects_source_path ON objects(source_path);
        CREATE INDEX idx_objects_area_ratio ON objects(area_ratio);
        """
    )


def process_scene(
    scene_conn: sqlite3.Connection,
    object_conn: sqlite3.Connection,
    image_path: Path,
    base_dir: Path,
    max_objects: int,
    min_area_ratio: float,
    max_area_ratio: float,
) -> int:
    with Image.open(image_path) as raw_image:
        image = raw_image.convert("RGB")

    width, height = image.size
    scene_key = scene_key_from_path(image_path)
    source_path = relative_path(image_path, base_dir)
    source_stat = image_path.stat()
    scene_stats = image_stats(image)
    scene_vector = extract_visual_vector(image)

    scene_conn.execute(
        """
        INSERT INTO scenes (
            scene_key, source_path, width, height, vector_model, vector_dim, vector,
            palette_json, mean_rgb_json, brightness, contrast, source_size_bytes, source_mtime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scene_key,
            source_path,
            width,
            height,
            VECTOR_MODEL,
            int(scene_vector.size),
            vector_to_blob(scene_vector),
            json.dumps(scene_stats.palette),
            json.dumps(list(scene_stats.mean_rgb)),
            scene_stats.brightness,
            scene_stats.contrast,
            source_stat.st_size,
            source_stat.st_mtime,
        ),
    )

    object_count = 0
    candidates = find_object_candidates(
        image,
        max_candidates=max_objects,
        min_area_ratio=min_area_ratio,
    )

    for candidate in candidates:
        x, y, bbox_width, bbox_height = candidate.bbox
        area_ratio = (bbox_width * bbox_height) / float(width * height)
        if area_ratio > max_area_ratio:
            continue

        crop = crop_bbox(image, candidate.bbox)
        object_stats = image_stats(crop)
        object_vector = extract_visual_vector(crop)
        object_key = f"{scene_key}:object:{object_count + 1:02d}"

        object_conn.execute(
            """
            INSERT INTO objects (
                object_key, scene_key, source_path,
                bbox_x, bbox_y, bbox_width, bbox_height,
                bbox_norm_x, bbox_norm_y, bbox_norm_width, bbox_norm_height,
                area_ratio, saliency_score, detection_method,
                vector_model, vector_dim, vector,
                palette_json, mean_rgb_json, brightness, contrast,
                source_size_bytes, source_mtime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                object_key,
                scene_key,
                source_path,
                x,
                y,
                bbox_width,
                bbox_height,
                x / width,
                y / height,
                bbox_width / width,
                bbox_height / height,
                area_ratio,
                candidate.score,
                candidate.method,
                VECTOR_MODEL,
                int(object_vector.size),
                vector_to_blob(object_vector),
                json.dumps(object_stats.palette),
                json.dumps(list(object_stats.mean_rgb)),
                object_stats.brightness,
                object_stats.contrast,
                source_stat.st_size,
                source_stat.st_mtime,
            ),
        )
        object_count += 1

    return object_count


def process_scene_data_from_args(args: tuple[Path, Path, int, float, float]) -> SceneBuildResult:
    image_path, base_dir, max_objects, min_area_ratio, max_area_ratio = args
    return process_scene_data(
        image_path=image_path,
        base_dir=base_dir,
        max_objects=max_objects,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
    )


def process_scene_data(
    image_path: Path,
    base_dir: Path,
    max_objects: int,
    min_area_ratio: float,
    max_area_ratio: float,
) -> SceneBuildResult:
    with Image.open(image_path) as raw_image:
        image = raw_image.convert("RGB")

    width, height = image.size
    scene_key = scene_key_from_path(image_path)
    source_path = relative_path(image_path, base_dir)
    source_stat = image_path.stat()
    scene_stats = image_stats(image)
    scene_vector = extract_visual_vector(image)

    scene_row = (
        scene_key,
        source_path,
        width,
        height,
        VECTOR_MODEL,
        int(scene_vector.size),
        vector_to_blob(scene_vector),
        json.dumps(scene_stats.palette),
        json.dumps(list(scene_stats.mean_rgb)),
        scene_stats.brightness,
        scene_stats.contrast,
        source_stat.st_size,
        source_stat.st_mtime,
    )

    object_rows: list[tuple[object, ...]] = []
    candidates = find_object_candidates(
        image,
        max_candidates=max_objects,
        min_area_ratio=min_area_ratio,
    )

    object_count = 0
    for candidate in candidates:
        x, y, bbox_width, bbox_height = candidate.bbox
        area_ratio = (bbox_width * bbox_height) / float(width * height)
        if area_ratio > max_area_ratio:
            continue

        crop = crop_bbox(image, candidate.bbox)
        object_stats = image_stats(crop)
        object_vector = extract_visual_vector(crop)
        object_key = f"{scene_key}:object:{object_count + 1:02d}"
        object_rows.append(
            (
                object_key,
                scene_key,
                source_path,
                x,
                y,
                bbox_width,
                bbox_height,
                x / width,
                y / height,
                bbox_width / width,
                bbox_height / height,
                area_ratio,
                candidate.score,
                candidate.method,
                VECTOR_MODEL,
                int(object_vector.size),
                vector_to_blob(object_vector),
                json.dumps(object_stats.palette),
                json.dumps(list(object_stats.mean_rgb)),
                object_stats.brightness,
                object_stats.contrast,
                source_stat.st_size,
                source_stat.st_mtime,
            )
        )
        object_count += 1

    return SceneBuildResult(scene_row=scene_row, object_rows=object_rows)


def insert_scene_result(
    scene_conn: sqlite3.Connection,
    object_conn: sqlite3.Connection,
    result: SceneBuildResult,
) -> int:
    scene_conn.execute(
        """
        INSERT INTO scenes (
            scene_key, source_path, width, height, vector_model, vector_dim, vector,
            palette_json, mean_rgb_json, brightness, contrast, source_size_bytes, source_mtime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        result.scene_row,
    )

    if result.object_rows:
        object_conn.executemany(
            """
            INSERT INTO objects (
                object_key, scene_key, source_path,
                bbox_x, bbox_y, bbox_width, bbox_height,
                bbox_norm_x, bbox_norm_y, bbox_norm_width, bbox_norm_height,
                area_ratio, saliency_score, detection_method,
                vector_model, vector_dim, vector,
                palette_json, mean_rgb_json, brightness, contrast,
                source_size_bytes, source_mtime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            result.object_rows,
        )

    return len(result.object_rows)


def write_metadata(conn: sqlite3.Connection, values: dict[str, object]) -> None:
    conn.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        [(key, json.dumps(value)) for key, value in values.items()],
    )


def scene_key_from_path(path: Path) -> str:
    stem = path.stem
    if stem.endswith("_ren"):
        return stem[:-4]
    return stem


def image_stats(image: Image.Image) -> ImageStats:
    rgb = image.convert("RGB")
    preview = rgb.copy()
    preview.thumbnail((160, 160))
    arr = np.asarray(preview, dtype=np.float32) / 255.0
    if arr.size == 0:
        return ImageStats([], (0.0, 0.0, 0.0), 0.0, 0.0)

    flat = arr.reshape(-1, 3)
    mean = tuple(float(value) for value in flat.mean(axis=0))
    luma = flat[:, 0] * 0.2126 + flat[:, 1] * 0.7152 + flat[:, 2] * 0.0722
    return ImageStats(
        palette=dominant_palette(rgb),
        mean_rgb=mean,
        brightness=float(luma.mean()),
        contrast=float(luma.std()),
    )


def dominant_palette(image: Image.Image, color_count: int = 6) -> list[str]:
    preview = image.convert("RGB")
    preview.thumbnail((96, 96))
    quantized = preview.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    colors = quantized.getcolors(maxcolors=96 * 96) or []
    colors.sort(reverse=True)

    result: list[str] = []
    for _, color_index in colors[:color_count]:
        offset = color_index * 3
        if offset + 2 >= len(palette):
            continue
        red, green, blue = palette[offset:offset + 3]
        result.append(f"#{red:02x}{green:02x}{blue:02x}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
