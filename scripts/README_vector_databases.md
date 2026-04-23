# 3D Scene Vector Databases

The database builder turns rendered images and POV-Ray source files from `scenes/` into five portable SQLite vector databases:

- `vector_databases/scene_vectors.sqlite` stores one visual vector per full scene render.
- `vector_databases/object_vectors.sqlite` stores salient object candidates cropped from each scene, with source scene path and bounding-box placement metadata.
- `vector_databases/pov_vectors.sqlite` stores one source-code vector per `.pov` file, with line, token, primitive, material, light, camera, and directive metadata.
- `vector_databases/material_vectors.sqlite` stores named and inline POV-Ray material/texture blocks, including source line spans and material feature flags.
- `vector_databases/camera_vectors.sqlite` stores named and inline POV-Ray camera blocks, including source line spans and parsed camera fields such as `location`, `look_at`, `angle`, `right`, `up`, and `direction`.

Build all databases:

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

Query similar POV-Ray source files:

```bash
python3 scripts/query_vector_databases.py --database povs --query-pov scenes/00001_ren.pov --top-k 5
```

Query similar material blocks:

```bash
python3 scripts/query_vector_databases.py --database materials --query-pov scenes/00907_cinder_fold_ambulatory.pov --query-material-name AmberGlassTex --top-k 5
```

Query similar camera blocks:

```bash
python3 scripts/query_vector_databases.py --database cameras --query-pov scenes/00908_material_proofing_alcove.pov --top-k 5
```

The visual vectors are deterministic descriptors built from color, luminance, edge orientation, coarse spatial layout, and thumbnail structure. The POV source, material, and camera vectors are deterministic descriptors built from hashed source tokens, POV-Ray keyword frequencies, and structural code statistics. All vectors are L2-normalized, so cosine similarity is just a dot product. Object rows include normalized bounding boxes and area ratios so a scene-construction step can retrieve a compatible object patch and reuse its approximate source placement. Material rows include the source snippet, source line range, block type, declaration name when available, and flags for pigment, normal, finish, interior, pattern, reflection, emission, and transparency. Camera rows include the source snippet, source line range, declaration name when available, detection method, and parsed common camera fields. By default, object candidates larger than 45% of the source render are skipped so the object database does not fill up with whole-scene crops.
