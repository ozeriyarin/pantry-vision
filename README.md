# Pantry Vision

Hebrew Telegram bot that turns fridge, freezer and pantry photos into an inventory. A zero-shot YOLO-World
detector runs on CPU (ONNX), and Claude Haiku checks only uncertain crops under a monthly cap. Runs on Google
Cloud Run. Built spec-first with GitHub spec-kit: see `specs/001-pantry-photo-inventory/`.

Work in progress. Full README with architecture, cost and eval tables comes with the first release.
