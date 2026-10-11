/* Formulas. A text may carry LaTeX between $ and $ (inside a line) or between $$ and $$ (set apart).
   The formulas are drawn by KaTeX, which is served by the tool itself. KaTeX builds elements;
   nothing here assigns HTML, and its "trust" setting stays off, so a formula cannot carry a link,
   an image address or a script. A formula that KaTeX cannot draw is shown as its source text. */
(function () {
  'use strict';

  var A = window.AiQuiz;

  // $$…$$ first. A single $ opens a formula only if no space follows it, and closes one only if no
  // space comes before it and no digit after it, so that "$5 and $6" stays ordinary text.
  var FORMULA = /\$\$([\s\S]+?)\$\$|\$((?:[^\s$\\]|\\.)(?:(?:[^$\\]|\\.)*?(?:[^\s$\\]|\\.))?)\$(?!\d)/g;

  /* "a $x^2$ b" -> [{text: 'a '}, {tex: 'x^2', display: false, source: '$x^2$'}, {text: ' b'}] */
  function parts(text) {
    var found = [], last = 0, match;
    text = String(text === null || text === undefined ? '' : text);
    FORMULA.lastIndex = 0;
    while ((match = FORMULA.exec(text)) !== null) {
      if (match.index > last) { found.push({ text: text.slice(last, match.index) }); }
      var display = match[1] !== undefined;
      found.push({ tex: (display ? match[1] : match[2]).trim(), display: display, source: match[0] });
      last = FORMULA.lastIndex;
    }
    if (last < text.length) { found.push({ text: text.slice(last) }); }
    return found;
  }

  function hasFormula(text) {
    return parts(text).some(function (part) { return part.tex !== undefined; });
  }

  /* Run `draw` so that no element gets a style attribute.

     KaTeX sets nearly all its styles through an element's style object, which a content security
     policy without inline styles allows. In a few places (large delimiters and other drawn
     shapes, boxes with a border, bold symbols in the MathML it writes for screen readers) it
     writes a style attribute instead, which such a policy blocks and reports. While `draw` runs,
     which is one synchronous call, setting the attribute "style" is turned into the same change
     through the style object. The shipped KaTeX files stay as released. */
  function withoutStyleAttributes(draw) {
    var setAttribute = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function (name, value) {
      if (name !== 'style') { return setAttribute.call(this, name, value); }
      if (this.style) { this.style.cssText = value; }
    };
    try { draw(); } finally { Element.prototype.setAttribute = setAttribute; }
  }

  /* Put `text` into `node`, formulas drawn. Returns how many formulas could not be drawn. */
  function fill(node, text) {
    var failed = 0;
    A.clear(node);
    parts(text).forEach(function (part) {
      if (part.tex === undefined) {
        node.appendChild(document.createTextNode(part.text));
        return;
      }
      var box = document.createElement('span');
      box.className = part.display ? 'formula set-apart' : 'formula';
      try {
        if (!window.katex) { throw new Error('KaTeX is not loaded'); }
        withoutStyleAttributes(function () {
          window.katex.render(part.tex, box, {
            displayMode: part.display, throwOnError: true, trust: false, strict: 'ignore',
            maxSize: 10, maxExpand: 100
          });
        });
      } catch (error) {
        failed += 1;
        box = A.el('code', { class: 'formula-source', text: part.source });
      }
      node.appendChild(box);
    });
    return failed;
  }

  /* An element showing `text`: with formulas when `latex` is true, as plain text otherwise. */
  function shown(tag, props, text, latex) {
    var node = A.el(tag, props);
    if (latex) { fill(node, text); } else { node.textContent = text; }
    return node;
  }

  A.math = { parts: parts, hasFormula: hasFormula, fill: fill, shown: shown };
})();
