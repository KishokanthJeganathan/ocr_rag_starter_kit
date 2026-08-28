# generator/ — synthetic document generator

Added in **Stage 1**. Produces parameterized NDAs (and later invoices) as clean
digital PDFs or degraded "scanned" images, each with a ground-truth JSON sidecar
used by the Stage 10 eval harness. Supports `--violation` flags to emit documents
that deliberately fail specific validation rules.

This is a fixture factory for the pipeline, not the product.
