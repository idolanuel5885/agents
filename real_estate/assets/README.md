# Atar-Laron branding assets

Place the office's branding PNGs here:

- `header_logo.png` — top-of-page logo strip with the Atar-Laron mark and a horizontal rule.
- `footer_strip.png` — bottom-of-page contact strip with a horizontal rule above it.

The report generator (`real_estate/docx_utils.py`) embeds whichever of these
files exists at document creation time. If a file is missing, the header/footer
paragraph is still emitted but rendered without an image — the document is
still valid and the layout is preserved.

Files are loaded by absolute path; do not import them — they live next to the
Python source so the deployed package picks them up automatically.
