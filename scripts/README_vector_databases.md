# 3D Scene Vector Databases

The database builder turns rendered images from `scenes/` into two portable SQLite vector databases:

- `vector_databases/scene_vectors.sqlite` stores one visual vector per full scene render.
- `vector_databases/object_vectors.sqlite` stores salient object candidates cropped from each scene, with source scene path and bounding-box placement metadata.

Build both databases:

```bash
python3 scripts/build_vector_databases.py --scenes-dir scenes --output-dir vector_databases
```

Query similar full scenes:

```bash
python3 scripts/query_vector_databases.py --database scenes --query-image scenes/00001_ren.png --top-k 5
```

Query similar object candidates:

```bash
python3 scripts/query_vector_databases.py --database objects --query-image scenes/00001_ren.png --crop 250 200 500 500 --top-k 5
```

The vectors are deterministic visual descriptors built from color, luminance, edge orientation, coarse spatial layout, and thumbnail structure. They are L2-normalized, so cosine similarity is just a dot product. Object rows include normalized bounding boxes and area ratios so a scene-construction step can retrieve a compatible object patch and reuse its approximate source placement. By default, object candidates larger than 45% of the source render are skipped so the object database does not fill up with whole-scene crops.
