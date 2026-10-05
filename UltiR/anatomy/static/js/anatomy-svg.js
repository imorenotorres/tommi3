/* Anatomy Explorer — SVG preparation shared by the viewer page.
 *
 * Diagrams tag shapes with data-s (structure id) and data-side (R/L/M/auto,
 * patient's side). "auto" shapes are resolved here from their position
 * relative to the figure midline (the centre of the viewBox). Shapes that
 * straddle the midline are split into two clipped copies, one per side.
 */
(function (global) {
  'use strict';
  const SVGNS = 'http://www.w3.org/2000/svg';

  function rootX(svg, clientX) {
    const p = new DOMPoint(clientX, 0).matrixTransform(svg.getScreenCTM().inverse());
    return p.x;
  }

  // Viewer-left is the patient's right in anterior views, left in posterior.
  function sideFor(svg, x, mid) {
    const viewerLeft = x < mid;
    return (viewerLeft !== (svg.dataset.view === 'posterior')) ? 'R' : 'L';
  }

  function prepare(svg) {
    const vb = svg.viewBox.baseVal;
    const mid = vb.x + vb.width / 2;
    let defs = svg.querySelector('defs');
    if (!defs) { defs = document.createElementNS(SVGNS, 'defs'); svg.prepend(defs); }
    let n = 0;
    svg.querySelectorAll('[data-side="auto"]').forEach(el => {
      const r = el.getBoundingClientRect();
      if (!r.width) { el.dataset.side = 'M'; return; }
      const x0 = rootX(svg, r.left), x1 = rootX(svg, r.right);
      const span = x1 - x0;
      // Straddles the midline by more than 10% on each side: split it.
      if (x0 < mid - span * 0.1 && x1 > mid + span * 0.1) {
        const f = (mid - x0) / span;               // split point, 0..1 of bbox
        const flipped = el.getScreenCTM().a < 0;    // mirrored element
        const halves = [[0, f], [f, 1]].map(([a, b]) => flipped ? [1 - b, 1 - a] : [a, b]);
        const copy = el.cloneNode(true);
        [el, copy].forEach((node, i) => {
          const id = `ax-split-${n++}`;
          const cp = document.createElementNS(SVGNS, 'clipPath');
          cp.setAttribute('id', id);
          cp.setAttribute('clipPathUnits', 'objectBoundingBox');
          const rect = document.createElementNS(SVGNS, 'rect');
          rect.setAttribute('x', halves[i][0]); rect.setAttribute('y', -0.01);
          rect.setAttribute('width', halves[i][1] - halves[i][0]); rect.setAttribute('height', 1.02);
          cp.appendChild(rect); defs.appendChild(cp);
          node.setAttribute('clip-path', `url(#${id})`);
        });
        el.after(copy);
        el.dataset.side = sideFor(svg, (x0 + mid) / 2, mid);
        copy.dataset.side = sideFor(svg, (mid + x1) / 2, mid);
      } else {
        el.dataset.side = sideFor(svg, (x0 + x1) / 2, mid);
      }
    });
  }

  global.AnatomySVG = { prepare };
})(window);
