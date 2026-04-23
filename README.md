POVII
=====

POVII is several scripts for turning rendered POV-Ray scenes and POV-Ray
source files into searchable vector indexes.

The current repository contains:

1. POV-Ray scene source files in `scenes/`
2. Python tools in `scripts/` for building and querying SQLite vector databases
3. A `vector_databases/` folder that holds generated outputs and a manifest
4. A root `README.md`

The important point is that the current Python tooling is broader than the older
README in the repository root. The current builder can index five things:

- rendered scene images
- object-like crops found inside rendered scene images
- full POV-Ray source files
- material / texture-style blocks extracted from POV source
- camera blocks extracted from POV source

The project is designed for local, deterministic retrieval. It does not depend
on a remote API or a downloaded embedding service.


REPOSITORY LAYOUT
-----------------

`scenes/`
    POV-Ray source files such as `00001_ren.pov` through `00010_ren.pov`.
    This folder currently appears to contain `.pov` files, not rendered image
    files.

`scripts/build_vector_databases.py`
    Builds the SQLite databases and writes a manifest.

`scripts/query_vector_databases.py`
    Queries one of the generated databases using an image or POV/text input.

`scripts/vector_features.py`
    Shared feature extraction, POV block parsing, and object candidate logic.

`scripts/README_vector_databases.md`
    Supplemental notes in the repository.

`vector_databases/`
    Output folder for generated SQLite databases and `manifest.json`.

`README.md`
    Existing Markdown README in the repository root. At the time of this
    update, it still describes only the older scene/object workflow.


WHAT THE CURRENT BUILDER CREATES
--------------------------------

Running the current builder writes these files into `vector_databases/`:

- `scene_vectors.sqlite`
    One visual vector per rendered image.

- `object_vectors.sqlite`
    Multiple object-candidate vectors per rendered image, with source path and
    bounding-box metadata.

- `pov_vectors.sqlite`
    One source-code vector per `.pov` file.

- `material_vectors.sqlite`
    One vector per detected material / texture / pigment / finish / interior
    block found in POV source.

- `camera_vectors.sqlite`
    One vector per detected camera block found in POV source.

- `manifest.json`
    A summary of the generated outputs, vector metadata, and row counts.


IMPORTANT INPUT RULES
---------------------

The build step expects rendered image files for scene/object indexing.

Accepted image extensions are:

- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

The build step also reads `.pov` files for source/material/camera indexing.

By default:

- `--scenes-dir` points to the folder containing rendered scene images
- `--pov-dir` points to the folder containing `.pov` files
- if `--pov-dir` is not supplied, it defaults to the same folder as
  `--scenes-dir`

Because the checked-in `scenes/` folder currently contains `.pov` files, you
will usually need to do one of these before building:

1. render the scenes to images and place those images in `scenes/`, or
2. place rendered images in another folder and pass that folder with
   `--scenes-dir`, while pointing `--pov-dir` at `scenes/`


REQUIREMENTS
------------

To run the Python tools you need:

- Python 3
- `numpy`
- `Pillow`
- SQLite support in the standard library (`sqlite3`)

You will also need POV-Ray if you want to render the `.pov` files yourself.


INSTALL
-------

Install the Python dependencies:

    pip install numpy pillow


QUICK START
-----------

Example workflow when rendered images live in `renders/` and POV source stays in
`scenes/`:

1. Render the POV-Ray scenes to `.png`, `.jpg`, `.jpeg`, or `.webp` files.

2. Build all databases:

    python3 scripts/build_vector_databases.py \
        --scenes-dir renders \
        --pov-dir scenes \
        --output-dir vector_databases

3. Query visually similar full scenes:

    python3 scripts/query_vector_databases.py \
        --database scenes \
        --db-dir vector_databases \
        --query-image renders/00001_ren.png \
        --top-k 5

4. Query visually similar object regions:

    python3 scripts/query_vector_databases.py \
        --database objects \
        --db-dir vector_databases \
        --query-image renders/00001_ren.png \
        --crop 250 200 500 500 \
        --top-k 5

5. Query similar POV source files:

    python3 scripts/query_vector_databases.py \
        --database povs \
        --db-dir vector_databases \
        --query-pov scenes/00001_ren.pov \
        --top-k 5

6. Query similar material blocks from a POV file:

    python3 scripts/query_vector_databases.py \
        --database materials \
        --db-dir vector_databases \
        --query-pov scenes/00001_ren.pov \
        --top-k 5

7. Query a named material block, if the source uses named declarations:

    python3 scripts/query_vector_databases.py \
        --database materials \
        --db-dir vector_databases \
        --query-pov scenes/00001_ren.pov \
        --query-material-name MyMaterial \
        --top-k 5

8. Query camera blocks:

    python3 scripts/query_vector_databases.py \
        --database cameras \
        --db-dir vector_databases \
        --query-pov scenes/00001_ren.pov \
        --top-k 5


BUILDER OPTIONS YOU WILL ACTUALLY USE
-------------------------------------

The main builder options are:

- `--scenes-dir`
    Folder containing rendered scene images.

- `--pov-dir`
    Folder containing POV-Ray source files. If omitted, it defaults to the
    same folder as `--scenes-dir`.

- `--output-dir`
    Destination for the SQLite databases and manifest.

- `--max-objects-per-scene`
    Maximum number of object candidates stored per image. Default: 8.

- `--object-min-area-ratio`
    Minimum object size relative to the full image. Default: 0.006.

- `--object-max-area-ratio`
    Maximum object size relative to the full image. Default: 0.45.

- `--progress-every`
    Print progress every N processed scenes. Use 0 to disable progress logs.
    Default: 25.

- `--workers`
    Number of worker processes used for scene/object extraction. Default: 1.


QUERY MODES
-----------

`query_vector_databases.py` supports five database targets:

- `scenes`
- `objects`
- `povs`
- `materials`
- `cameras`

Input rules:

- `scenes` and `objects` require `--query-image`
- `objects` optionally supports `--crop X Y WIDTH HEIGHT`
- `povs`, `materials`, and `cameras` accept `--query-pov` or `--query-text`
- `materials` can also use `--query-lines START END` or
  `--query-material-name NAME`
- `cameras` can also use `--query-camera-name NAME`
- `--top-k` controls how many matches are printed; default is 10


WHAT THE INDEXES REPRESENT
--------------------------

Scene and object indexes are image-based.

- The visual descriptor is deterministic and currently 327 dimensions wide.
- Similarity is computed with L2-normalized vectors, so cosine similarity is a
  dot product.
- Object matches include bounding-box and area-ratio metadata.

POV, material, and camera indexes are source-based.

- Full `.pov` files are embedded as source vectors.
- Material-like blocks are extracted from source and indexed separately.
- Camera blocks are extracted from source and indexed separately.
- These source indexes support retrieval by full file, by raw text snippet, by
  line range, or by named material / camera block when available.


EXAMPLE QUERY OUTPUT
--------------------

Scene query output looks like:

    01 score=0.9234 scene=00001_ren path=renders/00001_ren.png

Object query output looks like:

    01 score=0.9012 object=00001_ren:object:001 scene=00001_ren area=0.083 bbox=250,200,500,500 path=renders/00001_ren.png

POV query output looks like:

    01 score=0.8821 pov=00001_ren lines=145 tokens=812 path=scenes/00001_ren.pov

Material query output looks like:

    01 score=0.8740 material=00001_ren:material:001 pov=00001_ren name=MyMaterial type=texture method=declared lines=12-34 tokens=97 path=scenes/00001_ren.pov

Camera query output looks like:

    01 score=0.8610 camera=00001_ren:camera:001 pov=00001_ren name=MainCamera method=declared lines=3-10 tokens=41 angle=35 path=scenes/00001_ren.pov

Higher scores mean closer matches.


CURRENT REPOSITORY SNAPSHOT
---------------------------

As of this README update, the repository tree visibly includes:

- a root `README.md`
- `scenes/`
- `scripts/`
- `vector_databases/`

The `scenes/` folder shown in the repository currently lists numbered `.pov`
files such as `00001_ren.pov` through `00010_ren.pov`.

The checked-in `vector_databases/manifest.json` appears to be older than the
current builder code:

- it lists only `scenes` and `objects`
- both row counts are `0`

So treat the checked-in database files and manifest as placeholders or old
artifacts. To match the current Python scripts, rerun the builder locally.


SUGGESTED WORKFLOW
------------------

A practical workflow is:

1. author or edit `.pov` scene files
2. render those scenes to image files
3. build all vector databases
4. query images for scene-level or object-level visual matches
5. query `.pov` files for similar source, material, or camera structures
6. use the returned scene, object, material, or camera metadata in downstream
   scene construction or retrieval tasks


LIMITATIONS
-----------

- The scene/object pipeline does not index raw `.pov` files directly; it needs
  rendered images.
- The current `image_files()` and `pov_files()` helpers scan only the immediate
  directory, not nested subdirectories.
- Retrieval is feature-based, not semantic or language-model based.
- Object detection is heuristic and saliency-based, so results depend on scene
  contrast, composition, and clutter.
- The checked-in manifest does not currently reflect the full capabilities of
  the latest builder script.


LICENSE / PROJECT NOTES
-----------------------

No separate license file is visible in the current repository snapshot.
Add a license if you want other people to reuse the project with clear terms.
