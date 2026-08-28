# evals/ — golden-set evaluation harness

Added in **Stage 10**. Runs the pipeline over the generated golden set plus a
handful of real public documents, then reports field-level precision / recall /
F1 and a classification confusion matrix. RAG answers are scored with Ragas plus
retrieval hit@k. A CI job fails the build when F1 regresses past the committed
baseline on any change to prompts or schemas.
