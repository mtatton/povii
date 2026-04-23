POVII
===== 

POVII are scripts for turning rendered POV-Ray scenes into searchable visual indexes.

The repository currently has two parts:

1. POV-Ray scene source files in `scenes/`
2. Python tools in `scripts/` that build and query SQLite vector databases from rendered images

In practice, the project is meant to let you:
- index full scene renders
- index likely object crops inside each rendered scene
- search for visually similar scenes
- search for visually similar object patches

The vectorization pipeline is deterministic. It does not rely on a remote API or a downloaded ML embedding model. Instead, it builds feature vectors from image color, luminance, edge orientation, coarse spatial layout, and thumbnail structure.


REPOSITORY LAYOUT
-----------------

`scenes/`
    POV-Ray scene files such as `00001_ren.pov`, `00002_ren.pov`, and so on.

`scripts/build_vector_databases.py`
    Builds two SQLite databases from a folder of rendered images.

`scripts/query_vector_databases.py`
    Searches the generated databases using a query image, with optional cropping for object-level lookup.

`scripts/vector_features.py`
    Shared image feature extraction and object-candidate detection utilities.

`scripts/README_vector_databases.md`
    Short notes describing the scene/object database workflow.

`vector_databases/`
    Output location for generated databases and the build manifest.


WHAT GETS BUILT
---------------

Running the builder creates:

- `vector_databases/scene_vectors.sqlite`
  One vector row per rendered scene image.

- `vector_databases/object_vectors.sqlite`
  Multiple object-candidate rows per scene, including source path and bounding-box metadata.

- `vector_databases/manifest.json`
  A summary of the build, including database paths, vector dimension, and row counts.


IMPORTANT NOTE ABOUT INPUTS
---------------------------

The builder does not read `.pov` files directly.

It scans the input folder for rendered image files with these extensions:
- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

That means you should render the POV-Ray scene files first, then point the builder at the folder containing the rendered images.

The checked-in repo snapshot includes POV-Ray scene source files in `scenes/`, but the database builder expects image outputs.


REQUIREMENTS
------------

To use the Python tools you need:

- Python 3
- `numpy`
- `Pillow`
- SQLite support in Python's standard library (`sqlite3`)

If you want to generate images from the `.pov` scene files, you will also need POV-Ray.


INSTALL
-------

Create a virtual environment if you want one, then install the Python dependencies:

    pip install numpy pillow


QUICK START
-----------

1. Render your POV-Ray scenes to images.

2. Put the rendered files somewhere under `scenes/` or another image folder.

3. Build the databases:

    python3 scripts/build_vector_databases.py --scenes-dir scenes --output-dir vector_databases

4. Query for similar full scenes:

    python3 scripts/query_vector_databases.py --database scenes --query-image scenes/00001_ren.png --top-k 5

5. Query for similar objects by cropping a region from the query image:

    python3 scripts/query_vector_databases.py --database objects --query-image scenes/00001_ren.png --crop 250 200 500 500 --top-k 5


HOW THE BUILDER WORKS
---------------------

For each rendered scene image, the builder:

- computes one scene-level visual vector
- finds salient object candidates inside the image
- crops each candidate region
- computes one visual vector per accepted object crop
- writes scene rows to `scene_vectors.sqlite`
- writes object rows to `object_vectors.sqlite`
- writes a manifest file describing the outputs

The object database stores both pixel bounding boxes and normalized bounding boxes, which makes it easier to reuse approximate placement information later.

By default, very large object candidates are skipped so the object database does not fill up with crops that are effectively whole-scene images.


USEFUL BUILDER OPTIONS
----------------------

`build_vector_databases.py` supports several command-line options, including:

- `--scenes-dir`
    Folder containing rendered scene images.

- `--output-dir`
    Folder where the databases and manifest will be written.

- `--max-objects-per-scene`
    Maximum number of object candidates saved per source image.

- `--object-min-area-ratio`
    Minimum object size relative to the full image.

- `--object-max-area-ratio`
    Maximum object size relative to the full image.

- `--progress-every`
    Print progress every N processed scenes.

- `--workers`
    Number of worker processes to use during extraction.


QUERY OUTPUT
------------

Scene queries print ranked matches like this:

    01  score=0.9234  scene=00001_ren  path=scenes/00001_ren.png

Object queries print ranked matches with extra placement information:

    01  score=0.9012  object=00001_ren:object:01  scene=00001_ren  area=0.083  bbox=250,200,500,500  path=scenes/00001_ren.png

Higher scores mean higher similarity.

Because the vectors are L2-normalized, cosine similarity can be computed as a dot product.


CURRENT STATUS OF THIS REPOSITORY SNAPSHOT
------------------------------------------

At the time of writing this README, the repository tree includes:

- POV-Ray scene source files in `scenes/`
- Python scripts for building and querying vector databases
- a `vector_databases/manifest.json` file

The checked-in manifest currently reports zero rows for both the scene and object databases, so you should treat the database files as outputs to generate from rendered images rather than as populated datasets ready to query.


SUGGESTED WORKFLOW
------------------

A practical workflow is:

1. author or edit `.pov` scene files
2. render them to images
3. build the scene and object databases
4. query the databases with a full image or a cropped patch
5. reuse the returned scene match or object placement metadata in downstream scene-construction or retrieval tasks


LIMITATIONS
-----------

- The builder only indexes image files, not raw POV-Ray source files.
- Similarity is feature-based, not semantic. It is best suited for visual lookup rather than text-style understanding.
- The object detector is heuristic and saliency-based, so candidate quality depends on composition, contrast, and clutter.


LICENSE / PROJECT NOTES
-----------------------

No license file or project description was visible in the current repository snapshot. Add those if you want the repository to be easier for other people to reuse.
