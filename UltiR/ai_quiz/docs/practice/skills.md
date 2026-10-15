# Practice skills of the two demo handouts

Which skills of the course material a **programmed tutor** can teach: a program that a model helped to write
once and an instructor reviewed, which generates exercises, computes the answer, recognises predictable
mistakes and gives feedback from fixed texts, with no model call while students practise. Read from the two
synthetic handouts of the demo course (2026-10-15):

- `sample.pdf`, "Feature Matching in Computer Vision", 18 pages (pages as the text reading numbers them);
- `contratos-sintetico.pdf`, "Introducción al Derecho de contratos", 3 pages.

Three criteria decide whether a skill fits a programmed tutor:

- **C** answer computable: a program gets the exact answer from the exercise's data;
- **M** mistakes predictable: the usual wrong answers follow from rules that can be written down, so each one
  computes a different wrong value that can be recognised;
- **V** variants generable: new data can be drawn at random, at more than one level.

A skill that fails one of them stays with the instructor (open reasoning, cases told in words).

## sample.pdf

| # | Skill | Page | Formula or procedure | Typical mistakes | C | M | V | Programmed tutor? |
|---|---|---|---|---|---|---|---|---|
| 1 | Harris corner measure | 2 | R = det M − κ (tr M)², κ 0.04–0.06; corner if R ≫ 0, edge if R < 0, flat if R ≈ 0 | κ·tr M not squared; det and trace swapped; sign read the wrong way | ✓ | ✓ | ✓ | Yes |
| 2 | Extra blur to reach a target blur | 2 | σ_add = √(σ_b² − σ_a²) (1.6 → 2.016 needs ≈ 1.23) | σ_b − σ_a (0.416); √(σ_b² + σ_a²); σ_b² − σ_a² without the root | ✓ | ✓ | ✓ | Yes |
| 3 | Blur of a pyramid level | 2 | σ_{o,s} = σ₀ · 2^(o + s/S) | 2^(s/S) without the octave; σ₀·(o + s/S); o and s swapped | ✓ | ✓ | ✓ | Yes |
| 4 | Images per octave | 2–3 | S + 3 Gaussian images, S + 2 differences, extrema in S levels | S or S + 1 images; differences = images | ✓ | ✓ | ~ | Yes, small (few variants) |
| 5 | Edge test threshold | 5 | keep if (tr H)²/det H < (r+1)²/r; r = 10 gives 12.1 | (r+1)/r; r²/r = r; (r+1)² without dividing | ✓ | ✓ | ✓ | Yes |
| 6 | Orientation histogram bin and refinement | 6 | bin = ⌊36 θ / 2π⌋; offset = (h_{j−1} − h_{j+1}) / (2 (h_{j−1} − 2h_j + h_{j+1})) bins (100, 60, 80 → 1/6 bin ≈ 1.7°) | bins of 36° instead of 10°; sign of the offset; bins not taken modulo 36 | ✓ | ✓ | ✓ | Yes |
| 7 | Descriptor size in memory | 8 | SIFT 128 × 4 bytes = 512 B; binary: bits / 8 (256 bits = 32 B); SIFT as bytes 128 B | bits taken as bytes; 128 × 8; forgetting the 4 bytes per float | ✓ | ✓ | ✓ | Yes |
| 8 | Euclidean, Manhattan, squared distance | 9 | d₂ = √Σ(aᵢ − bᵢ)²; d₁ = Σ|aᵢ − bᵢ|; for unit vectors ‖a − b‖² = 2 − 2a·b | no square root; squares in d₁; 2 − a·b | ✓ | ✓ | ✓ | Yes |
| 9 | Hellinger kernel and χ² distance | 9 | K = Σ√(aᵢbᵢ); χ² = ½ Σ (aᵢ − bᵢ)²/(aᵢ + bᵢ) | ½ forgotten; division by aᵢ only; √(Σ aᵢbᵢ) | ✓ | ✓ | ✓ | Yes |
| 10 | Hamming distance of bit strings | 10 | count of 1s in a XOR b (10110100, 10011101 → 3) | counting equal bits; AND instead of XOR | ✓ | ✓ | ✓ | Yes |
| 11 | Ratio test | 11 | ρ = d₁/d₂, accept if ρ < τ (0.21/0.35 = 0.60 accepted) | d₂/d₁; accepting if ρ > τ | ✓ | ✓ | ✓ | Yes |
| 12 | **Precision, recall, F1 from counts** | 17 (Table 2, p. 12) | P = TP/(TP+FP), R = TP/(TP+FN), F1 = 2PR/(P+R) | **P and R swapped**; returned matches as R's denominator; F1 as the arithmetic mean; percent for fraction | ✓ | ✓ | ✓ | **Yes: built first** |
| 13 | **RANSAC number of iterations** | 15–16 | N = ⌈log(1 − p) / log(1 − wˢ)⌉, w = n_in/n; s = 2 line, 4 homography, 7 or 8 fundamental | **w instead of wˢ**; **rounding down or to nearest**; another model's sample size; outlier fraction as w; log p for log(1 − p) | ✓ | ✓ | ✓ | **Yes: built first** |
| 14 | Average precision from operating points | 17 | AP ≈ Σ (R_k − R_{k−1}) P_k, R₀ = 0 | R_k instead of the step; P_{k−1} | ✓ | ✓ | ✓ | Yes |
| 15 | Repeatability | 17 | \|C\| / min(n₁, n₂) | max instead of min; n₁ + n₂ | ✓ | ✓ | ✓ | Yes |
| 16 | Degrees of freedom and minimal samples | 13 | homography 8 DOF, 4 correspondences; fundamental 7 DOF, 7 or 8; essential 5 | 9 for the homography; 2 equations per correspondence for F | ✓ | ✓ | ✗ | No: a handful of fixed facts, better in a quiz |
| 17 | Why the ratio test works; aperture problem; covariance vs invariance; choosing a descriptor or a distance | 1–11 | explanation | many and in words | ✗ | ✗ | ✗ | **No: open reasoning, stays with the instructor** |

## contratos-sintetico.pdf

| # | Skill | Page | Procedure | Typical mistakes | C | M | V | Programmed tutor? |
|---|---|---|---|---|---|---|---|---|
| 18 | The three essential elements of a contract | 1 | consentimiento, objeto, causa | confusing objeto and causa | ~ | ✓ | ✗ | No: one fixed list; a quiz question |
| 19 | Which defect of consent a case shows | 2 | error (only on the substance or the main conditions), violencia, intimidación, dolo | dolo taken for the buyer's error; intimidación for violencia; a secondary error taken as enough | ~ | ✓ | ✗ | **No: the cases are told in words, cannot be generated from parameters**; stays with the instructor or with quiz questions the instructor reviewed |
| 20 | Form of a contract | 3 | libertad de forma; form required by law vs form for proof | thinking a verbal contract does not bind | ✗ | ~ | ✗ | **No: open reasoning** |

## What this means

- Every computable skill is in `sample.pdf`; the law handout has none. Fifteen skills (1–15) fit a
  programmed tutor; 16 is too small, and 17–20 stay with the instructor.
- The first two tutors are 13 (RANSAC iterations, where a draft once said 5 iterations where the table says
  17) and 12 (precision, recall and F1, where the simulated class swapped the two measures).
- A programmed tutor shows the page of its handout found from a sentence of the document, never one written
  in by hand; if the handout is not in the course, the tutor is not offered.
