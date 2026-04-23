from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image


EPSILON = 1e-8
VISUAL_VECTOR_DIM = 327

try:
    LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS = Image.LANCZOS


@dataclass(frozen=True)
class ObjectCandidate:
    bbox: tuple[int, int, int, int]
    score: float
    method: str


def image_files(scene_dir: Path) -> list[Path]:
    return sorted(
        path for path in scene_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )


def vector_to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def vector_from_blob(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= EPSILON:
        return vector
    return vector / norm


def relative_path(path: Path, base: Path | None = None) -> str:
    base = base or Path.cwd()
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def crop_bbox(image: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    x, y, width, height = bbox
    return image.crop((x, y, x + width, y + height))


def extract_visual_vector(image: Image.Image, max_side: int = 256) -> np.ndarray:
    """Build a deterministic visual descriptor for scene and object retrieval."""
    rgb = image.convert("RGB")
    rgb.thumbnail((max_side, max_side), LANCZOS)
    arr = np.asarray(rgb, dtype=np.float32) / 255.0
    if arr.ndim != 3 or arr.shape[0] < 2 or arr.shape[1] < 2:
        return np.zeros(VISUAL_VECTOR_DIM, dtype=np.float32)

    height, width, _ = arr.shape
    gray = _luminance(arr)
    hsv = _rgb_to_hsv(arr)
    gradient, orientation = _gradient(gray)

    features: list[np.ndarray] = []

    for channel in range(3):
        features.append(_histogram(arr[..., channel], bins=16, value_range=(0.0, 1.0)))

    features.append(_histogram(hsv[..., 0], bins=18, value_range=(0.0, 1.0), weights=hsv[..., 1] * hsv[..., 2]))
    features.append(_histogram(hsv[..., 1], bins=8, value_range=(0.0, 1.0)))
    features.append(_histogram(hsv[..., 2], bins=8, value_range=(0.0, 1.0)))
    features.append(_histogram(orientation, bins=16, value_range=(0.0, 1.0), weights=gradient))

    y_edges = np.linspace(0, height, 5, dtype=int)
    x_edges = np.linspace(0, width, 5, dtype=int)
    cell_means: list[float] = []
    cell_stds: list[float] = []
    cell_luma: list[float] = []
    cell_edges: list[float] = []

    for y0, y1 in zip(y_edges[:-1], y_edges[1:]):
        for x0, x1 in zip(x_edges[:-1], x_edges[1:]):
            cell = arr[y0:y1, x0:x1]
            luma_cell = gray[y0:y1, x0:x1]
            edge_cell = gradient[y0:y1, x0:x1]
            if cell.size == 0:
                cell_means.extend([0.0, 0.0, 0.0])
                cell_stds.extend([0.0, 0.0, 0.0])
                cell_luma.extend([0.0, 0.0])
                cell_edges.append(0.0)
                continue
            cell_means.extend(cell.reshape(-1, 3).mean(axis=0).tolist())
            cell_stds.extend(cell.reshape(-1, 3).std(axis=0).tolist())
            cell_luma.append(float(luma_cell.mean()))
            cell_luma.append(float(luma_cell.std()))
            cell_edges.append(float(edge_cell.mean()))

    features.append(np.asarray(cell_means, dtype=np.float32))
    features.append(np.asarray(cell_stds, dtype=np.float32))
    features.append(np.asarray(cell_luma, dtype=np.float32))
    features.append(np.asarray(cell_edges, dtype=np.float32))

    small_gray = Image.fromarray(np.uint8(np.clip(gray * 255.0, 0, 255)), mode="L").resize((8, 8), LANCZOS)
    features.append(np.asarray(small_gray, dtype=np.float32).reshape(-1) / 255.0)

    flat = arr.reshape(-1, 3)
    flat_hsv = hsv.reshape(-1, 3)
    p5, p50, p95 = np.percentile(gray.reshape(-1), [5, 50, 95])
    edge_p90 = float(np.percentile(gradient.reshape(-1), 90))
    global_stats = np.asarray(
        [
            *flat.mean(axis=0).tolist(),
            *flat.std(axis=0).tolist(),
            *flat_hsv.mean(axis=0).tolist(),
            *flat_hsv.std(axis=0).tolist(),
            float(gray.mean()),
            float(gray.std()),
            float(p5),
            float(p50),
            float(p95),
            float((gray < 0.12).mean()),
            float((gray > 0.88).mean()),
            float(gradient.mean()),
            edge_p90,
        ],
        dtype=np.float32,
    )
    features.append(global_stats)

    vector = np.concatenate(features).astype(np.float32)
    return l2_normalize(vector)


def find_object_candidates(
    image: Image.Image,
    max_candidates: int = 8,
    max_side: int = 360,
    min_area_ratio: float = 0.006,
) -> list[ObjectCandidate]:
    thumb = image.convert("RGB")
    source_width, source_height = thumb.size
    scale = min(max_side / max(source_width, source_height), 1.0)
    thumb_size = (max(1, int(round(source_width * scale))), max(1, int(round(source_height * scale))))
    if thumb.size != thumb_size:
        thumb = thumb.resize(thumb_size, LANCZOS)

    arr = np.asarray(thumb, dtype=np.float32) / 255.0
    if arr.shape[0] < 16 or arr.shape[1] < 16:
        return []

    saliency = _saliency_map(arr)
    mask = _foreground_mask(saliency, arr)

    candidates = _component_candidates(mask, saliency, min_area_ratio)
    candidates.extend(_window_candidates(saliency, arr, min_area_ratio))

    selected = _non_max_suppression(candidates, max_candidates=max_candidates, iou_threshold=0.52)
    return [_scale_candidate(candidate, source_width, source_height, thumb.size) for candidate in selected]


def _scale_candidate(
    candidate: ObjectCandidate,
    source_width: int,
    source_height: int,
    thumb_size: tuple[int, int],
) -> ObjectCandidate:
    thumb_width, thumb_height = thumb_size
    x, y, width, height = candidate.bbox
    scale_x = source_width / max(thumb_width, 1)
    scale_y = source_height / max(thumb_height, 1)
    source_x = int(round(x * scale_x))
    source_y = int(round(y * scale_y))
    source_w = int(round(width * scale_x))
    source_h = int(round(height * scale_y))
    source_x = max(0, min(source_x, source_width - 1))
    source_y = max(0, min(source_y, source_height - 1))
    source_w = max(1, min(source_w, source_width - source_x))
    source_h = max(1, min(source_h, source_height - source_y))
    return ObjectCandidate((source_x, source_y, source_w, source_h), candidate.score, candidate.method)


def _rgb_to_hsv(arr: np.ndarray) -> np.ndarray:
    r = arr[..., 0]
    g = arr[..., 1]
    b = arr[..., 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    diff = maxc - minc

    hue = np.zeros_like(maxc)
    mask = diff > EPSILON
    r_max = mask & (maxc == r)
    g_max = mask & (maxc == g)
    b_max = mask & (maxc == b)
    hue[r_max] = ((g[r_max] - b[r_max]) / diff[r_max]) % 6.0
    hue[g_max] = ((b[g_max] - r[g_max]) / diff[g_max]) + 2.0
    hue[b_max] = ((r[b_max] - g[b_max]) / diff[b_max]) + 4.0
    hue = hue / 6.0

    saturation = np.zeros_like(maxc)
    saturation[maxc > EPSILON] = diff[maxc > EPSILON] / maxc[maxc > EPSILON]
    return np.stack([hue, saturation, maxc], axis=-1)


def _luminance(arr: np.ndarray) -> np.ndarray:
    return arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722


def _gradient(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gy, gx = np.gradient(gray)
    magnitude = np.hypot(gx, gy).astype(np.float32)
    orientation = ((np.arctan2(gy, gx) + np.pi) / (2.0 * np.pi)).astype(np.float32)
    return magnitude, orientation


def _histogram(
    values: np.ndarray,
    bins: int,
    value_range: tuple[float, float],
    weights: np.ndarray | None = None,
) -> np.ndarray:
    hist, _ = np.histogram(values.reshape(-1), bins=bins, range=value_range, weights=None if weights is None else weights.reshape(-1))
    hist = hist.astype(np.float32)
    total = float(hist.sum())
    if total > EPSILON:
        hist /= total
    return hist


def _saliency_map(arr: np.ndarray) -> np.ndarray:
    height, width, _ = arr.shape
    gray = _luminance(arr)
    gradient, _ = _gradient(gray)
    gradient = _normalize01(gradient, percentile=95)

    border_width = max(2, min(height, width) // 18)
    border = np.concatenate(
        [
            arr[:border_width, :, :].reshape(-1, 3),
            arr[-border_width:, :, :].reshape(-1, 3),
            arr[:, :border_width, :].reshape(-1, 3),
            arr[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    centers = _dominant_border_colors(border, count=6)
    distances = np.sqrt(((arr[..., None, :] - centers[None, None, :, :]) ** 2).sum(axis=-1)).min(axis=-1)
    color_distance = np.clip(distances / 0.72, 0.0, 1.0)

    hsv = _rgb_to_hsv(arr)
    saturation = hsv[..., 1]
    border_luma = float(np.median(_luminance(border.reshape(-1, 1, 3)).reshape(-1)))
    luma_distance = np.clip(np.abs(gray - border_luma) / 0.65, 0.0, 1.0)

    saliency = 0.44 * color_distance + 0.34 * gradient + 0.14 * saturation + 0.08 * luma_distance
    return _box_blur(saliency.astype(np.float32), passes=2)


def _dominant_border_colors(border: np.ndarray, count: int) -> np.ndarray:
    quantized = np.clip((border * 7.999).astype(np.int32), 0, 7)
    codes = quantized[:, 0] * 64 + quantized[:, 1] * 8 + quantized[:, 2]
    unique, counts = np.unique(codes, return_counts=True)
    if unique.size == 0:
        return np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32)
    order = np.argsort(counts)[::-1][:count]
    selected = unique[order]
    red = selected // 64
    green = (selected % 64) // 8
    blue = selected % 8
    return (np.stack([red, green, blue], axis=1).astype(np.float32) + 0.5) / 8.0


def _foreground_mask(saliency: np.ndarray, arr: np.ndarray) -> np.ndarray:
    gray = _luminance(arr)
    threshold = max(0.18, float(np.quantile(saliency, 0.72)))
    mask = saliency >= threshold
    mask &= (gray > 0.025) | (saliency > threshold + 0.12)
    mask = _dilate(mask, passes=2)
    mask = _erode(mask, passes=1)
    return mask


def _component_candidates(mask: np.ndarray, saliency: np.ndarray, min_area_ratio: float) -> list[ObjectCandidate]:
    height, width = mask.shape
    min_pixels = max(24, int(round(height * width * min_area_ratio)))
    max_bbox_ratio = 0.72
    visited = np.zeros_like(mask, dtype=bool)
    candidates: list[ObjectCandidate] = []
    ys, xs = np.nonzero(mask)

    for start_y, start_x in zip(ys.tolist(), xs.tolist()):
        if visited[start_y, start_x] or not mask[start_y, start_x]:
            continue

        stack = [(start_y, start_x)]
        visited[start_y, start_x] = True
        area = 0
        min_y = max_y = start_y
        min_x = max_x = start_x
        score_sum = 0.0

        while stack:
            y, x = stack.pop()
            area += 1
            score_sum += float(saliency[y, x])
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            min_x = min(min_x, x)
            max_x = max(max_x, x)

            for neighbor_y in (y - 1, y, y + 1):
                for neighbor_x in (x - 1, x, x + 1):
                    if neighbor_y == y and neighbor_x == x:
                        continue
                    if neighbor_y < 0 or neighbor_x < 0 or neighbor_y >= height or neighbor_x >= width:
                        continue
                    if visited[neighbor_y, neighbor_x] or not mask[neighbor_y, neighbor_x]:
                        continue
                    visited[neighbor_y, neighbor_x] = True
                    stack.append((neighbor_y, neighbor_x))

        if area < min_pixels:
            continue

        bbox_width = max_x - min_x + 1
        bbox_height = max_y - min_y + 1
        bbox_area = bbox_width * bbox_height
        bbox_ratio = bbox_area / float(width * height)
        if bbox_ratio < min_area_ratio or bbox_ratio > max_bbox_ratio:
            continue
        if bbox_width < 14 or bbox_height < 14:
            continue

        aspect = bbox_width / max(bbox_height, 1)
        if aspect > 6.0 or aspect < 1.0 / 6.0:
            continue

        fill = area / max(bbox_area, 1)
        margin = max(4, int(round(max(bbox_width, bbox_height) * 0.08)))
        x0 = max(0, min_x - margin)
        y0 = max(0, min_y - margin)
        x1 = min(width, max_x + margin + 1)
        y1 = min(height, max_y + margin + 1)
        mean_score = score_sum / max(area, 1)
        score = mean_score * (0.72 + 0.28 * fill) * np.sqrt(min(bbox_ratio, 0.45))
        candidates.append(ObjectCandidate((x0, y0, x1 - x0, y1 - y0), float(score), "connected_component"))

    return candidates


def _window_candidates(saliency: np.ndarray, arr: np.ndarray, min_area_ratio: float) -> list[ObjectCandidate]:
    height, width = saliency.shape
    gray = _luminance(arr)
    gradient, _ = _gradient(gray)
    candidates: list[ObjectCandidate] = []
    area = height * width

    window_areas = [0.04, 0.075, 0.13, 0.22, 0.34]
    aspect_ratios = [1.0, 1.33, 0.75, 1.78, 0.56]

    for area_ratio in window_areas:
        if area_ratio < min_area_ratio:
            continue
        for aspect_ratio in aspect_ratios:
            window_area = area * area_ratio
            window_width = int(round(np.sqrt(window_area * aspect_ratio)))
            window_height = int(round(window_area / max(window_width, 1)))
            if window_width < 20 or window_height < 20 or window_width > width or window_height > height:
                continue
            xs = _grid_positions(width - window_width, slots=5)
            ys = _grid_positions(height - window_height, slots=5)
            for x in xs:
                for y in ys:
                    crop_sal = saliency[y:y + window_height, x:x + window_width]
                    crop_gray = gray[y:y + window_height, x:x + window_width]
                    crop_edge = gradient[y:y + window_height, x:x + window_width]
                    if crop_sal.size == 0:
                        continue
                    texture = float(crop_gray.std()) + float(crop_edge.mean())
                    if texture < 0.025:
                        continue
                    score = float(crop_sal.mean()) * (0.62 + min(texture, 0.38)) * np.sqrt(area_ratio)
                    candidates.append(ObjectCandidate((x, y, window_width, window_height), score, "saliency_window"))

    return candidates


def _grid_positions(limit: int, slots: int) -> list[int]:
    if limit <= 0:
        return [0]
    return sorted(set(int(round(value)) for value in np.linspace(0, limit, slots)))


def _non_max_suppression(
    candidates: Iterable[ObjectCandidate],
    max_candidates: int,
    iou_threshold: float,
) -> list[ObjectCandidate]:
    selected: list[ObjectCandidate] = []
    ordered = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    for candidate in ordered:
        if all(_iou(candidate.bbox, existing.bbox) < iou_threshold for existing in selected):
            selected.append(candidate)
        if len(selected) >= max_candidates:
            break
    return selected


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2 = ax + aw
    ay2 = ay + ah
    bx2 = bx + bw
    by2 = by + bh
    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    union = aw * ah + bw * bh - intersection
    return intersection / max(union, 1)


def _normalize01(values: np.ndarray, percentile: float) -> np.ndarray:
    scale = float(np.percentile(values.reshape(-1), percentile))
    if scale <= EPSILON:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip(values / scale, 0.0, 1.0).astype(np.float32)


def _box_blur(values: np.ndarray, passes: int) -> np.ndarray:
    blurred = values.astype(np.float32)
    for _ in range(passes):
        padded = np.pad(blurred, 1, mode="edge")
        blurred = (
            padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
            + padded[1:-1, :-2] + padded[1:-1, 1:-1] + padded[1:-1, 2:]
            + padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
        ) / 9.0
    return blurred


def _dilate(mask: np.ndarray, passes: int) -> np.ndarray:
    result = mask.astype(bool)
    for _ in range(passes):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        result = (
            padded[:-2, :-2] | padded[:-2, 1:-1] | padded[:-2, 2:]
            | padded[1:-1, :-2] | padded[1:-1, 1:-1] | padded[1:-1, 2:]
            | padded[2:, :-2] | padded[2:, 1:-1] | padded[2:, 2:]
        )
    return result


def _erode(mask: np.ndarray, passes: int) -> np.ndarray:
    result = mask.astype(bool)
    for _ in range(passes):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        result = (
            padded[:-2, :-2] & padded[:-2, 1:-1] & padded[:-2, 2:]
            & padded[1:-1, :-2] & padded[1:-1, 1:-1] & padded[1:-1, 2:]
            & padded[2:, :-2] & padded[2:, 1:-1] & padded[2:, 2:]
        )
    return result
