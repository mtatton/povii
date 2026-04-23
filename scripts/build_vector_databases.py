#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import json
import re
import sqlite3
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from vector_features import (
    CAMERA_VECTOR_DIM,
    MATERIAL_VECTOR_DIM,
    SOURCE_VECTOR_DIM,
    VISUAL_VECTOR_DIM,
    camera_blocks,
    crop_bbox,
    extract_source_vector,
    extract_visual_vector,
    find_object_candidates,
    image_files,
    material_blocks,
    pov_files,
    relative_path,
    source_tokens,
    vector_to_blob,
)


VECTOR_MODEL = "povii-visual-descriptor-v1"
SOURCE_VECTOR_MODEL = "povii-pov-source-descriptor-v1"
MATERIAL_VECTOR_MODEL = "povii-pov-material-descriptor-v1"
CAMERA_VECTOR_MODEL = "povii-pov-camera-descriptor-v1"
SCENE_DB_NAME = "scene_vectors.sqlite"
OBJECT_DB_NAME = "object_vectors.sqlite"
POV_DB_NAME = "pov_vectors.sqlite"
MATERIAL_DB_NAME = "material_vectors.sqlite"
CAMERA_DB_NAME = "camera_vectors.sqlite"
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


@dataclass(frozen=True)
class PovStats:
    line_count: int
    byte_count: int
    token_count: int
    unique_token_count: int
    comment_line_count: int
    include_count: int
    declare_count: int
    macro_count: int
    primitive_count: int
    material_count: int
    light_count: int
    camera_count: int


@dataclass(frozen=True)
class MaterialStats:
    line_count: int
    token_count: int
    unique_token_count: int
    color_count: int
    has_texture: bool
    has_pigment: bool
    has_normal: bool
    has_finish: bool
    has_interior: bool
    has_pattern: bool
    has_reflection: bool
    has_emission: bool
    has_transparency: bool


@dataclass(frozen=True)
class CameraStats:
    line_count: int
    token_count: int
    unique_token_count: int
    number_count: int
    vector_literal_count: int
    has_location: bool
    has_look_at: bool
    has_angle: bool
    has_right: bool
    has_up: bool
    has_direction: bool
    has_rotate: bool
    has_translate: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build scene, object, POV source, material, and camera vector databases from rendered scene files.",
    )
    parser.add_argument(
        "--scenes-dir",
        type=Path,
        default=Path("scenes"),
        help="Folder containing rendered scene images.",
    )
    parser.add_argument(
        "--pov-dir",
        type=Path,
        help="Folder containing POV-Ray scene source files. Defaults to --scenes-dir.",
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
    pov_dir = (args.pov_dir or args.scenes_dir).resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = image_files(scenes_dir)
    if not files:
        raise SystemExit(f"No scene images found in {scenes_dir}")
    source_files = pov_files(pov_dir)

    scene_db_path = output_dir / SCENE_DB_NAME
    object_db_path = output_dir / OBJECT_DB_NAME
    pov_db_path = output_dir / POV_DB_NAME
    material_db_path = output_dir / MATERIAL_DB_NAME
    camera_db_path = output_dir / CAMERA_DB_NAME
    for db_path in (scene_db_path, object_db_path, pov_db_path, material_db_path, camera_db_path):
        if db_path.exists():
            db_path.unlink()

    start = time.monotonic()
    with (
        sqlite3.connect(scene_db_path) as scene_conn,
        sqlite3.connect(object_db_path) as object_conn,
        sqlite3.connect(pov_db_path) as pov_conn,
        sqlite3.connect(material_db_path) as material_conn,
        sqlite3.connect(camera_db_path) as camera_conn,
    ):
        configure_connection(scene_conn)
        configure_connection(object_conn)
        configure_connection(pov_conn)
        configure_connection(material_conn)
        configure_connection(camera_conn)
        create_scene_schema(scene_conn)
        create_object_schema(object_conn)
        create_pov_schema(pov_conn)
        create_material_schema(material_conn)
        create_camera_schema(camera_conn)

        scene_count = 0
        object_count = 0
        pov_count = 0
        material_count = 0
        camera_count = 0

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

        for index, pov_path in enumerate(source_files, start=1):
            process_pov(pov_conn=pov_conn, pov_path=pov_path, base_dir=Path.cwd())
            material_count += process_materials(
                material_conn=material_conn,
                pov_path=pov_path,
                base_dir=Path.cwd(),
            )
            camera_count += process_cameras(
                camera_conn=camera_conn,
                pov_path=pov_path,
                base_dir=Path.cwd(),
            )
            pov_count += 1

            if args.progress_every and index % args.progress_every == 0:
                elapsed = time.monotonic() - start
                print(
                    f"processed {index}/{len(source_files)} POV sources, "
                    f"{material_count} materials, {camera_count} cameras in {elapsed:.1f}s",
                    flush=True,
                )

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
        write_metadata(
            pov_conn,
            {
                "kind": "pov_vectors",
                "created_at": created_at,
                "source_dir": relative_path(pov_dir, Path.cwd()),
                "source_pov_count": pov_count,
                "vector_model": SOURCE_VECTOR_MODEL,
                "vector_dim": SOURCE_VECTOR_DIM,
            },
        )
        write_metadata(
            material_conn,
            {
                "kind": "material_vectors",
                "created_at": created_at,
                "source_dir": relative_path(pov_dir, Path.cwd()),
                "source_pov_count": pov_count,
                "material_count": material_count,
                "vector_model": MATERIAL_VECTOR_MODEL,
                "vector_dim": MATERIAL_VECTOR_DIM,
            },
        )
        write_metadata(
            camera_conn,
            {
                "kind": "camera_vectors",
                "created_at": created_at,
                "source_dir": relative_path(pov_dir, Path.cwd()),
                "source_pov_count": pov_count,
                "camera_count": camera_count,
                "vector_model": CAMERA_VECTOR_MODEL,
                "vector_dim": CAMERA_VECTOR_DIM,
            },
        )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": relative_path(scenes_dir, Path.cwd()),
        "pov_source_dir": relative_path(pov_dir, Path.cwd()),
        "vector_model": VECTOR_MODEL,
        "vector_dim": VISUAL_VECTOR_DIM,
        "visual_vector_model": VECTOR_MODEL,
        "visual_vector_dim": VISUAL_VECTOR_DIM,
        "source_vector_model": SOURCE_VECTOR_MODEL,
        "source_vector_dim": SOURCE_VECTOR_DIM,
        "material_vector_model": MATERIAL_VECTOR_MODEL,
        "material_vector_dim": MATERIAL_VECTOR_DIM,
        "camera_vector_model": CAMERA_VECTOR_MODEL,
        "camera_vector_dim": CAMERA_VECTOR_DIM,
        "databases": {
            "scenes": {
                "path": relative_path(scene_db_path, Path.cwd()),
                "rows": scene_count,
                "table": "scenes",
                "vector_column": "vector",
                "vector_model": VECTOR_MODEL,
                "vector_dim": VISUAL_VECTOR_DIM,
            },
            "objects": {
                "path": relative_path(object_db_path, Path.cwd()),
                "rows": object_count,
                "table": "objects",
                "vector_column": "vector",
                "vector_model": VECTOR_MODEL,
                "vector_dim": VISUAL_VECTOR_DIM,
            },
            "povs": {
                "path": relative_path(pov_db_path, Path.cwd()),
                "rows": pov_count,
                "table": "povs",
                "vector_column": "vector",
                "vector_model": SOURCE_VECTOR_MODEL,
                "vector_dim": SOURCE_VECTOR_DIM,
            },
            "materials": {
                "path": relative_path(material_db_path, Path.cwd()),
                "rows": material_count,
                "table": "materials",
                "vector_column": "vector",
                "vector_model": MATERIAL_VECTOR_MODEL,
                "vector_dim": MATERIAL_VECTOR_DIM,
            },
            "cameras": {
                "path": relative_path(camera_db_path, Path.cwd()),
                "rows": camera_count,
                "table": "cameras",
                "vector_column": "vector",
                "vector_model": CAMERA_VECTOR_MODEL,
                "vector_dim": CAMERA_VECTOR_DIM,
            },
        },
    }
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    elapsed = time.monotonic() - start
    print(f"wrote {scene_count} scene vectors to {relative_path(scene_db_path, Path.cwd())}")
    print(f"wrote {object_count} object vectors to {relative_path(object_db_path, Path.cwd())}")
    print(f"wrote {pov_count} POV source vectors to {relative_path(pov_db_path, Path.cwd())}")
    print(f"wrote {material_count} material vectors to {relative_path(material_db_path, Path.cwd())}")
    print(f"wrote {camera_count} camera vectors to {relative_path(camera_db_path, Path.cwd())}")
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


def create_pov_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE povs (
            pov_id INTEGER PRIMARY KEY,
            pov_key TEXT NOT NULL UNIQUE,
            source_path TEXT NOT NULL UNIQUE,
            vector_model TEXT NOT NULL,
            vector_dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            line_count INTEGER NOT NULL,
            byte_count INTEGER NOT NULL,
            token_count INTEGER NOT NULL,
            unique_token_count INTEGER NOT NULL,
            comment_line_count INTEGER NOT NULL,
            include_count INTEGER NOT NULL,
            declare_count INTEGER NOT NULL,
            macro_count INTEGER NOT NULL,
            primitive_count INTEGER NOT NULL,
            material_count INTEGER NOT NULL,
            light_count INTEGER NOT NULL,
            camera_count INTEGER NOT NULL,
            source_size_bytes INTEGER NOT NULL,
            source_mtime REAL NOT NULL
        );

        CREATE INDEX idx_povs_pov_key ON povs(pov_key);
        CREATE INDEX idx_povs_source_path ON povs(source_path);
        CREATE INDEX idx_povs_token_count ON povs(token_count);
        """
    )


def create_material_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE materials (
            material_id INTEGER PRIMARY KEY,
            material_key TEXT NOT NULL UNIQUE,
            pov_key TEXT NOT NULL,
            source_path TEXT NOT NULL,
            material_name TEXT,
            block_type TEXT NOT NULL,
            detection_method TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            line_count INTEGER NOT NULL,
            token_count INTEGER NOT NULL,
            unique_token_count INTEGER NOT NULL,
            color_count INTEGER NOT NULL,
            has_texture INTEGER NOT NULL,
            has_pigment INTEGER NOT NULL,
            has_normal INTEGER NOT NULL,
            has_finish INTEGER NOT NULL,
            has_interior INTEGER NOT NULL,
            has_pattern INTEGER NOT NULL,
            has_reflection INTEGER NOT NULL,
            has_emission INTEGER NOT NULL,
            has_transparency INTEGER NOT NULL,
            vector_model TEXT NOT NULL,
            vector_dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            snippet TEXT NOT NULL,
            source_size_bytes INTEGER NOT NULL,
            source_mtime REAL NOT NULL
        );

        CREATE INDEX idx_materials_pov_key ON materials(pov_key);
        CREATE INDEX idx_materials_source_path ON materials(source_path);
        CREATE INDEX idx_materials_material_name ON materials(material_name);
        CREATE INDEX idx_materials_block_type ON materials(block_type);
        """
    )


def create_camera_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE cameras (
            camera_id INTEGER PRIMARY KEY,
            camera_key TEXT NOT NULL UNIQUE,
            pov_key TEXT NOT NULL,
            source_path TEXT NOT NULL,
            camera_name TEXT,
            detection_method TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            line_count INTEGER NOT NULL,
            token_count INTEGER NOT NULL,
            unique_token_count INTEGER NOT NULL,
            number_count INTEGER NOT NULL,
            vector_literal_count INTEGER NOT NULL,
            has_location INTEGER NOT NULL,
            has_look_at INTEGER NOT NULL,
            has_angle INTEGER NOT NULL,
            has_right INTEGER NOT NULL,
            has_up INTEGER NOT NULL,
            has_direction INTEGER NOT NULL,
            has_rotate INTEGER NOT NULL,
            has_translate INTEGER NOT NULL,
            location_text TEXT,
            look_at_text TEXT,
            angle_text TEXT,
            right_text TEXT,
            up_text TEXT,
            direction_text TEXT,
            vector_model TEXT NOT NULL,
            vector_dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            snippet TEXT NOT NULL,
            source_size_bytes INTEGER NOT NULL,
            source_mtime REAL NOT NULL
        );

        CREATE INDEX idx_cameras_pov_key ON cameras(pov_key);
        CREATE INDEX idx_cameras_source_path ON cameras(source_path);
        CREATE INDEX idx_cameras_camera_name ON cameras(camera_name);
        CREATE INDEX idx_cameras_start_line ON cameras(start_line);
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


def process_pov(pov_conn: sqlite3.Connection, pov_path: Path, base_dir: Path) -> None:
    pov_conn.execute(
        """
        INSERT INTO povs (
            pov_key, source_path, vector_model, vector_dim, vector,
            line_count, byte_count, token_count, unique_token_count,
            comment_line_count, include_count, declare_count, macro_count,
            primitive_count, material_count, light_count, camera_count,
            source_size_bytes, source_mtime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        process_pov_data(pov_path=pov_path, base_dir=base_dir),
    )


def process_pov_data(pov_path: Path, base_dir: Path) -> tuple[object, ...]:
    source_text = pov_path.read_text(encoding="utf-8", errors="replace")
    source_stat = pov_path.stat()
    pov_key = scene_key_from_path(pov_path)
    source_path = relative_path(pov_path, base_dir)
    source_vector = extract_source_vector(source_text)
    stats = pov_stats(source_text)
    return (
        pov_key,
        source_path,
        SOURCE_VECTOR_MODEL,
        int(source_vector.size),
        vector_to_blob(source_vector),
        stats.line_count,
        stats.byte_count,
        stats.token_count,
        stats.unique_token_count,
        stats.comment_line_count,
        stats.include_count,
        stats.declare_count,
        stats.macro_count,
        stats.primitive_count,
        stats.material_count,
        stats.light_count,
        stats.camera_count,
        source_stat.st_size,
        source_stat.st_mtime,
    )


def process_materials(material_conn: sqlite3.Connection, pov_path: Path, base_dir: Path) -> int:
    rows = process_material_data(pov_path=pov_path, base_dir=base_dir)
    if rows:
        material_conn.executemany(
            """
            INSERT INTO materials (
                material_key, pov_key, source_path, material_name, block_type, detection_method,
                start_line, end_line, line_count, token_count, unique_token_count,
                color_count, has_texture, has_pigment, has_normal, has_finish, has_interior,
                has_pattern, has_reflection, has_emission, has_transparency,
                vector_model, vector_dim, vector, snippet,
                source_size_bytes, source_mtime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def process_material_data(pov_path: Path, base_dir: Path) -> list[tuple[object, ...]]:
    source_text = pov_path.read_text(encoding="utf-8", errors="replace")
    source_stat = pov_path.stat()
    pov_key = scene_key_from_path(pov_path)
    source_path = relative_path(pov_path, base_dir)

    rows: list[tuple[object, ...]] = []
    for index, block in enumerate(material_blocks(source_text), start=1):
        vector = extract_source_vector(block.text)
        stats = material_stats(block.text, block.start_line, block.end_line)
        rows.append(
            (
                f"{pov_key}:material:{index:03d}",
                pov_key,
                source_path,
                block.name,
                block.block_type,
                block.detection_method,
                block.start_line,
                block.end_line,
                stats.line_count,
                stats.token_count,
                stats.unique_token_count,
                stats.color_count,
                int(stats.has_texture),
                int(stats.has_pigment),
                int(stats.has_normal),
                int(stats.has_finish),
                int(stats.has_interior),
                int(stats.has_pattern),
                int(stats.has_reflection),
                int(stats.has_emission),
                int(stats.has_transparency),
                MATERIAL_VECTOR_MODEL,
                int(vector.size),
                vector_to_blob(vector),
                block.text.strip(),
                source_stat.st_size,
                source_stat.st_mtime,
            )
        )
    return rows


def process_cameras(camera_conn: sqlite3.Connection, pov_path: Path, base_dir: Path) -> int:
    rows = process_camera_data(pov_path=pov_path, base_dir=base_dir)
    if rows:
        camera_conn.executemany(
            """
            INSERT INTO cameras (
                camera_key, pov_key, source_path, camera_name, detection_method,
                start_line, end_line, line_count, token_count, unique_token_count,
                number_count, vector_literal_count,
                has_location, has_look_at, has_angle, has_right, has_up,
                has_direction, has_rotate, has_translate,
                location_text, look_at_text, angle_text, right_text, up_text, direction_text,
                vector_model, vector_dim, vector, snippet,
                source_size_bytes, source_mtime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def process_camera_data(pov_path: Path, base_dir: Path) -> list[tuple[object, ...]]:
    source_text = pov_path.read_text(encoding="utf-8", errors="replace")
    source_stat = pov_path.stat()
    pov_key = scene_key_from_path(pov_path)
    source_path = relative_path(pov_path, base_dir)

    rows: list[tuple[object, ...]] = []
    for index, block in enumerate(camera_blocks(source_text), start=1):
        vector = extract_source_vector(block.text)
        stats = camera_stats(block.text, block.start_line, block.end_line)
        rows.append(
            (
                f"{pov_key}:camera:{index:03d}",
                pov_key,
                source_path,
                block.name,
                block.detection_method,
                block.start_line,
                block.end_line,
                stats.line_count,
                stats.token_count,
                stats.unique_token_count,
                stats.number_count,
                stats.vector_literal_count,
                int(stats.has_location),
                int(stats.has_look_at),
                int(stats.has_angle),
                int(stats.has_right),
                int(stats.has_up),
                int(stats.has_direction),
                int(stats.has_rotate),
                int(stats.has_translate),
                camera_field_text(block.text, "location"),
                camera_field_text(block.text, "look_at"),
                camera_field_text(block.text, "angle"),
                camera_field_text(block.text, "right"),
                camera_field_text(block.text, "up"),
                camera_field_text(block.text, "direction"),
                CAMERA_VECTOR_MODEL,
                int(vector.size),
                vector_to_blob(vector),
                block.text.strip(),
                source_stat.st_size,
                source_stat.st_mtime,
            )
        )
    return rows


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


def pov_stats(source_text: str) -> PovStats:
    tokens = source_tokens(source_text)
    token_set = set(tokens)
    token_counts = Counter(tokens)
    lines = source_text.splitlines()
    stripped_lines = [line.strip().lower() for line in lines]

    primitive_tokens = {
        "sphere",
        "box",
        "cylinder",
        "cone",
        "torus",
        "plane",
        "triangle",
        "mesh",
        "mesh2",
        "prism",
        "lathe",
        "blob",
        "isosurface",
        "height_field",
        "text",
    }
    material_tokens = {
        "texture",
        "pigment",
        "normal",
        "finish",
        "interior",
        "material",
        "color",
        "colour",
        "rgb",
        "srgb",
        "rgbf",
        "rgbt",
        "ambient",
        "diffuse",
        "specular",
        "roughness",
        "reflection",
        "phong",
        "metallic",
        "emission",
    }
    light_tokens = {"light_source", "area_light", "spotlight"}

    return PovStats(
        line_count=len(lines),
        byte_count=len(source_text.encode("utf-8", errors="ignore")),
        token_count=len(tokens),
        unique_token_count=len(token_set),
        comment_line_count=sum(
            1
            for line in stripped_lines
            if line.startswith("//") or line.startswith("/*") or line.startswith("*")
        ),
        include_count=sum(1 for line in stripped_lines if line.startswith("#include")),
        declare_count=sum(1 for line in stripped_lines if line.startswith("#declare")),
        macro_count=sum(1 for line in stripped_lines if line.startswith("#macro")),
        primitive_count=sum(token_counts.get(token, 0) for token in primitive_tokens),
        material_count=sum(token_counts.get(token, 0) for token in material_tokens),
        light_count=sum(token_counts.get(token, 0) for token in light_tokens),
        camera_count=token_counts.get("camera", 0),
    )


def material_stats(source_text: str, start_line: int, end_line: int) -> MaterialStats:
    tokens = source_tokens(source_text)
    token_set = set(tokens)
    token_counts = Counter(tokens)

    pattern_tokens = {
        "checker",
        "gradient",
        "bozo",
        "marble",
        "wood",
        "granite",
        "crackle",
        "wrinkles",
        "bumps",
        "mandel",
        "agate",
        "onion",
        "spiral1",
        "spiral2",
        "image_map",
        "color_map",
        "colour_map",
        "pigment_map",
        "normal_map",
        "finish_map",
        "turbulence",
        "warp",
    }

    return MaterialStats(
        line_count=max(1, end_line - start_line + 1),
        token_count=len(tokens),
        unique_token_count=len(token_set),
        color_count=sum(token_counts.get(token, 0) for token in ("color", "colour", "rgb", "srgb", "rgbf", "rgbt")),
        has_texture=token_counts.get("texture", 0) > 0,
        has_pigment=token_counts.get("pigment", 0) > 0,
        has_normal=token_counts.get("normal", 0) > 0,
        has_finish=token_counts.get("finish", 0) > 0,
        has_interior=token_counts.get("interior", 0) > 0,
        has_pattern=any(token_counts.get(token, 0) > 0 for token in pattern_tokens),
        has_reflection=token_counts.get("reflection", 0) > 0,
        has_emission=token_counts.get("emission", 0) > 0 or token_counts.get("ambient", 0) > 0,
        has_transparency=any(token_counts.get(token, 0) > 0 for token in ("rgbf", "rgbt", "filter", "transmit")),
    )


def camera_stats(source_text: str, start_line: int, end_line: int) -> CameraStats:
    tokens = source_tokens(source_text)
    token_set = set(tokens)
    token_counts = Counter(tokens)

    return CameraStats(
        line_count=max(1, end_line - start_line + 1),
        token_count=len(tokens),
        unique_token_count=len(token_set),
        number_count=sum(1 for token in tokens if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", token)),
        vector_literal_count=source_text.count("<"),
        has_location=token_counts.get("location", 0) > 0,
        has_look_at=token_counts.get("look_at", 0) > 0,
        has_angle=token_counts.get("angle", 0) > 0,
        has_right=token_counts.get("right", 0) > 0,
        has_up=token_counts.get("up", 0) > 0,
        has_direction=token_counts.get("direction", 0) > 0,
        has_rotate=token_counts.get("rotate", 0) > 0,
        has_translate=token_counts.get("translate", 0) > 0,
    )


def camera_field_text(source_text: str, field_name: str) -> str | None:
    pattern = re.compile(rf"(?im)\b{re.escape(field_name)}\b\s+([^\n\r{{}}]+)")
    match = pattern.search(source_text)
    if not match:
        return None
    value = match.group(1).split("//", 1)[0].strip()
    return value or None


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
