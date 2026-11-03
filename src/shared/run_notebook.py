#!/usr/bin/env python3
"""
Execute a notebook in place and save it with its outputs, as 03_analyse.sh does for each
analysis notebook.

Each cell's printed output is merged into one stream. The kernel otherwise splits a cell's
prints into several output blocks depending on timing, so the same run could save a different
file. nbclient's coalesce_streams option does this, but nbconvert's command line cannot set it.

Usage:  .venv/bin/python src/shared/run_notebook.py notebooks/<name>.ipynb
"""
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

path = Path(sys.argv[1]).resolve()
nb = nbformat.read(path, as_version=4)
NotebookClient(nb, timeout=None, record_timing=False, coalesce_streams=True,
               resources={"metadata": {"path": str(path.parent)}}).execute()
nbformat.write(nb, path)
