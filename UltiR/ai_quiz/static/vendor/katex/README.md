# KaTeX 0.19.0

Formula rendering for the AI Quiz tool, shipped with the module so that no
page asks any other host for it.

- Source: the npm package `katex`, version 0.19.0, files `dist/katex.min.js`,
  `dist/katex.min.css` and `dist/fonts/*.woff2`, unchanged.
- Licence: MIT, see `LICENSE` in this folder.
- The stylesheet also names `.woff` and `.ttf` versions of each font as
  fallbacks. They are not shipped: every browser that can run the tool's
  pages reads `.woff2`, and takes the first format it supports.
- To update: replace the files with those of a newer release, then update
  the list of assets in `lti_provider.py` if the set of fonts changed, and
  the checksums in `tests/test_katex.py`.
