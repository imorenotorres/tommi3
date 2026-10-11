"""Part of a real result of docling_worker.py, recorded on 2026-10-10.

Docling 2.137.0 with OCR off read the synthetic 18-page handout on feature matching
(the sample of the reader test). These are 62 of its 223 items, unchanged: pages 2 to 5
(a paragraph over a page break, figures 1 and 2 with the page-header logo beside them,
formulas 8 to 13), pages 7 and 8 (figure 5, whose caption Docling took from a label inside
the figure; a table that collapsed into one row), and page 15 (a block of pseudocode read
as one formula, and formula 41, which came out broken).

Kept as a Python literal because the repository ignores *.json. The images are not
recorded: `images()` makes plain ones of the recorded sizes.
"""

from .images import png

RAW = {'version': 1,
 'docling': '2.137.0',
 'status': 'success',
 'n_pages': 18,
 'seconds': 48.1,
 'items': [{'prov': [{'page': 2, 'charspan': [0, 373]}, {'page': 3, 'charspan': [374, 604]}],
            'kind': 'text',
            'label': 'text',
            'text': 'A common choice is three intervals per octave and a base blur of 1.6 pixels. Each octave then '
                    'contains six Gaussian images, because three extra levels are needed to detect extrema at all '
                    'three intervals. When an octave is complete, the Gaussian image whose blur is twice the base '
                    'blur is downsampled by keeping every second pixel in each direction, and it becomes the first '
                    'image of the next octave. Downsampling loses no relevant information, because the image has '
                    'already been smoothed strongly enough, and each octave then costs only a quarter of the one '
                    'before it. The structure is shown in Figure 1.',
            'orig': 'A common choice is three intervals per octave and a base blur of 1.6 pixels. Each octave then '
                    'contains six Gaussian images, because three extra levels are needed to detect extrema at all '
                    'three intervals. When an octave is complete, the Gaussian image whose blur is twice the base '
                    'blur is downsampled by keeping every second pixel in each direction, and it becomes the first '
                    'image of the next octave. Downsampling loses no relevant information, because the image has '
                    'already been smoothed strongly enough, and each octave then costs only a quarter of the one '
                    'before it. The structure is shown in Figure 1.'},
           {'prov': [{'page': 3, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': '',
            'file': 'p0003.png',
            'width': 30,
            'height': 28},
           {'prov': [{'page': 3, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': 'Figure 1: Scale-space pyramid with three octaves and three intervals per octave. Adjacent '
                       'Gaussian images are subtracted to obtain the difference-of-Gaussians images, and each new '
                       'octave starts from a downsampled image.',
            'file': 'p0004.png',
            'width': 789,
            'height': 494},
           {'prov': [{'page': 3, 'charspan': [0, 219]}],
            'kind': 'text',
            'label': 'caption',
            'text': 'Figure 1: Scale-space pyramid with three octaves and three intervals per octave. Adjacent '
                    'Gaussian images are subtracted to obtain the difference-of-Gaussians images, and each new '
                    'octave starts from a downsampled image.',
            'orig': 'Figure 1: Scale-space pyramid with three octaves and three intervals per octave. Adjacent '
                    'Gaussian images are subtracted to obtain the difference-of-Gaussians images, and each new '
                    'octave starts from a downsampled image.'},
           {'prov': [{'page': 3, 'charspan': [0, 93]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Subtracting two neighbouring levels of the pyramid gives the difference-of-Gaussians function',
            'orig': 'Subtracting two neighbouring levels of the pyramid gives the difference-of-Gaussians function'},
           {'prov': [{'page': 3, 'charspan': [0, 42]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'D ( x , y , \\sigma ) = L ( x , y , k \\sigma ) - L ( x , y , \\sigma ) .',
            'orig': 'D(x, y, σ) = L(x, y, kσ) - L(x, y, σ). (8)'},
           {'prov': [{'page': 3, 'charspan': [0, 383]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Since the Gaussian images are needed anyway, the difference of Gaussians costs only one image '
                    'subtraction per level. Six Gaussian images per octave give five difference images, and extrema '
                    'can be detected in the three inner ones. Its usefulness follows from the heat diffusion '
                    'equation ∂G/∂σ = σ∇2G, which the Gaussian satisfies. Replacing the derivative by a finite '
                    'difference gives',
            'orig': 'Since the Gaussian images are needed anyway, the difference of Gaussians costs only one image '
                    'subtraction per level. Six Gaussian images per octave give five difference images, and extrema '
                    'can be detected in the three inner ones. Its usefulness follows from the heat diffusion '
                    'equation ∂G/∂σ = σ∇2G, which the Gaussian satisfies. Replacing the derivative by a finite '
                    'difference gives'},
           {'prov': [{'page': 3, 'charspan': [0, 131]}],
            'kind': 'formula',
            'label': 'formula',
            'text': '\\sigma \\nabla ^ { 2 } G = \\frac { \\partial G } { \\partial \\sigma } \\approx \\frac { G ( '
                    'x , y , k \\sigma ) - G ( x , y , \\sigma ) } { k \\sigma - \\sigma } , \\\\ G ( x , y , k '
                    '\\sigma ) - G ( x , y , \\sigma ) \\approx ( k - 1 ) \\, \\sigma ^ { 2 } \\nabla ^ { 2 } G , '
                    '\\\\ D ( x , y , \\sigma ) \\approx ( k - 1 ) \\, \\sigma ^ { 2 } \\nabla ^ { 2 } L ( x , y , '
                    '\\sigma ) .',
            'orig': 'σ∇2G = ∂G ∂σ ≈ G(x, y, kσ) - G(x, y, σ) kσ - σ , G(x, y, kσ) - G(x, y, σ) ≈ (k - 1) σ2∇2G, D(x, '
                    'y, σ) ≈ (k - 1) σ2∇2L(x, y, σ). (9)'},
           {'prov': [{'page': 3, 'charspan': [0, 384]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The difference of Gaussians therefore approximates the scale-normalised Laplacian of Gaussian '
                    'up to a constant factor. The normalisation by the squared blur is what makes responses at '
                    'different scales comparable, since the amplitude of plain derivatives decreases with increasing '
                    'smoothing. Because the factor is the same at all levels, it does not change the location of the '
                    'extrema.',
            'orig': 'The difference of Gaussians therefore approximates the scale-normalised Laplacian of Gaussian '
                    'up to a constant factor. The normalisation by the squared blur is what makes responses at '
                    'different scales comparable, since the amplitude of plain derivatives decreases with increasing '
                    'smoothing. Because the factor is the same at all levels, it does not change the location of the '
                    'extrema.'},
           {'prov': [{'page': 3, 'charspan': [0, 563]}, {'page': 4, 'charspan': [564, 738]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The difference of Gaussians acts as a blob detector with a centre-surround shape. For an '
                    'isotropic Gaussian blob with standard deviation σb, the magnitude of the response at the blob '
                    'centre is largest when σ√k = σb, that is, when the geometric mean of the two blur levels equals '
                    'the size of the blob. Figure 2 illustrates this behaviour for three blob sizes. The scale at '
                    'which the response peaks is called the characteristic scale of the structure. A bright blob on '
                    'a dark background produces a minimum of the difference of Gaussians, and a dark blob on a '
                    'bright background produces a maximum. Many implementations first double the size of the input '
                    'image by linear interpolation, which roughly quadruples the number of stable keypoints.',
            'orig': 'The difference of Gaussians acts as a blob detector with a centre-surround shape. For an '
                    'isotropic Gaussian blob with standard deviation σb, the magnitude of the response at the blob '
                    'centre is largest when σ√k = σb, that is, when the geometric mean of the two blur levels equals '
                    'the size of the blob. Figure 2 illustrates this behaviour for three blob sizes. The scale at '
                    'which the response peaks is called the characteristic scale of the structure. A bright blob on '
                    'a dark background produces a minimum of the difference of Gaussians, and a dark blob on a '
                    'bright background produces a maximum. Many implementations first double the size of the input '
                    'image by linear interpolation, which roughly quadruples the number of stable keypoints.'},
           {'prov': [{'page': 4, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': '',
            'file': 'p0005.png',
            'width': 30,
            'height': 28},
           {'prov': [{'page': 4, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': 'Figure 2: Response of the difference of Gaussians to a blob. Panel (a) shows cross-sections '
                       'of a blob of size 4 after increasing amounts of blur, and panel (b) shows the response '
                       'magnitude at the blob centre for three blob sizes, with a marker at each maximum.',
            'file': 'p0006.png',
            'width': 893,
            'height': 362},
           {'prov': [{'page': 4, 'charspan': [0, 260]}],
            'kind': 'text',
            'label': 'caption',
            'text': 'Figure 2: Response of the difference of Gaussians to a blob. Panel (a) shows cross-sections of '
                    'a blob of size 4 after increasing amounts of blur, and panel (b) shows the response magnitude '
                    'at the blob centre for three blob sizes, with a marker at each maximum.',
            'orig': 'Figure 2: Response of the difference of Gaussians to a blob. Panel (a) shows cross-sections of '
                    'a blob of size 4 after increasing amounts of blur, and panel (b) shows the response magnitude '
                    'at the blob centre for three blob sizes, with a marker at each maximum.'},
           {'prov': [{'page': 4, 'charspan': [0, 23]}],
            'kind': 'text',
            'label': 'section_header',
            'text': '3 Keypoint localisation',
            'orig': '3 Keypoint localisation'},
           {'prov': [{'page': 4, 'charspan': [0, 481]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Candidate keypoints are the local extrema of the difference-of-Gaussians function over both '
                    'position and scale. Each sample is compared with its eight neighbours in the same level and '
                    'with the nine neighbours in each of the two adjacent levels, which makes 26 neighbours in '
                    'total. A sample is kept as a candidate only if it is larger than all of its neighbours or '
                    'smaller than all of them. Most samples are rejected after the first few comparisons, so the '
                    'test is cheap on average.',
            'orig': 'Candidate keypoints are the local extrema of the difference-of-Gaussians function over both '
                    'position and scale. Each sample is compared with its eight neighbours in the same level and '
                    'with the nine neighbours in each of the two adjacent levels, which makes 26 neighbours in '
                    'total. A sample is kept as a candidate only if it is larger than all of its neighbours or '
                    'smaller than all of them. Most samples are rejected after the first few comparisons, so the '
                    'test is cheap on average.'},
           {'prov': [{'page': 4, 'charspan': [0, 236]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The extremum of the sampled function rarely coincides with the extremum of the underlying '
                    'continuous function. The position is therefore refined with a quadratic model around the '
                    'sample, written in terms of the offset δ = (δx, δy, δσ)⊤,',
            'orig': 'The extremum of the sampled function rarely coincides with the extremum of the underlying '
                    'continuous function. The position is therefore refined with a quadratic model around the '
                    'sample, written in terms of the offset δ = (δx, δy, δσ)⊤,'},
           {'prov': [{'page': 4, 'charspan': [0, 31]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'D ( \\delta ) \\approx D _ { 0 } + g ^ { \\top } \\delta + \\frac { 1 } { 2 } \\, \\delta ^ { '
                    '\\top } \\, H \\, \\delta ,',
            'orig': 'D(δ) ≈ D0 + g⊤δ + 12 δ⊤Hδ, (10)'},
           {'prov': [{'page': 4, 'charspan': [0, 133]}],
            'kind': 'text',
            'label': 'text',
            'text': 'where D0 is the value at the sample and the gradient g and the Hessian H collect the first and '
                    'second derivatives of D at the sample,',
            'orig': 'where D0 is the value at the sample and the gradient g and the Hessian H collect the first and '
                    'second derivatives of D at the sample,'},
           {'prov': [{'page': 4, 'charspan': [0, 69]}],
            'kind': 'formula',
            'label': 'formula',
            'text': '\\mathfrak { g } = \\begin{pmatrix} D _ { x } \\\\ D _ { y } \\\\ D _ { \\sigma } '
                    '\\end{pmatrix} , \\quad \\mathbf H = \\begin{pmatrix} D _ { x x } & D _ { x y } & D _ { x '
                    '\\sigma } \\\\ D _ { x y } & D _ { y y } & D _ { y \\sigma } \\\\ D _ { x \\sigma } & D _ { y '
                    '\\sigma } & D _ { \\sigma \\sigma } \\end{pmatrix} .',
            'orig': 'g = \uf8eb\uf8edDx Dy Dσ \uf8f6\uf8f8, H= \uf8eb\uf8edDxx Dxy Dxσ Dxy Dyy Dyσ Dxσ Dyσ Dσσ '
                    '\uf8f6\uf8f8 . (11)'},
           {'prov': [{'page': 4, 'charspan': [0, 113]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Setting the derivative of the model to zero gives the offset of the extremum and the value of '
                    'the function there,',
            'orig': 'Setting the derivative of the model to zero gives the offset of the extremum and the value of '
                    'the function there,'},
           {'prov': [{'page': 4, 'charspan': [0, 17]}],
            'kind': 'formula',
            'label': 'formula',
            'text': '\\hat { \\delta } = - H ^ { - 1 } g ,',
            'orig': 'ˆ δ = -H-1g, (12)'},
           {'prov': [{'page': 4, 'charspan': [0, 28]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'D ( \\hat { \\delta } ) = D _ { 0 } + \\frac { 1 } { 2 } \\, g ^ { \\top } \\hat { \\delta } .',
            'orig': 'D(ˆ δ) = D0 + 12 g⊤ˆ δ. (13)'},
           {'prov': [{'page': 4, 'charspan': [0, 284]}, {'page': 5, 'charspan': [285, 433]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The derivatives are estimated with finite differences of neighbouring samples, so the fit '
                    'requires only the solution of a linear system with three unknowns. If the offset exceeds half a '
                    'sample in any dimension, the extremum lies closer to a neighbouring sample and the fit is '
                    'repeated there. The final offset is added to the sample position, which gives a keypoint '
                    'location with an accuracy better than one pixel and one scale level.',
            'orig': 'The derivatives are estimated with finite differences of neighbouring samples, so the fit '
                    'requires only the solution of a linear system with three unknowns. If the offset exceeds half a '
                    'sample in any dimension, the extremum lies closer to a neighbouring sample and the fit is '
                    'repeated there. The final offset is added to the sample position, which gives a keypoint '
                    'location with an accuracy better than one pixel and one scale level.'},
           {'prov': [{'page': 6, 'charspan': [0, 181]}, {'page': 7, 'charspan': [182, 354]}],
            'kind': 'text',
            'label': 'text',
            'text': 'A descriptor converts the normalised patch around a keypoint into a vector that can be compared '
                    'quickly. It should tolerate small errors in the keypoint parameters, moderate changes of '
                    'viewpoint and changes of illumination. Two families dominate in practice: histograms of '
                    'gradients with real-valued elements, and binary strings of intensity comparisons.',
            'orig': 'A descriptor converts the normalised patch around a keypoint into a vector that can be compared '
                    'quickly. It should tolerate small errors in the keypoint parameters, moderate changes of '
                    'viewpoint and changes of illumination. Two families dominate in practice: histograms of '
                    'gradients with real-valued elements, and binary strings of intensity comparisons.'},
           {'prov': [{'page': 7, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': '',
            'file': 'p0011.png',
            'width': 30,
            'height': 28},
           {'prov': [{'page': 7, 'charspan': [0, 44]}],
            'kind': 'text',
            'label': 'section_header',
            'text': '5.1 Gradient histograms in the style of SIFT',
            'orig': '5.1 Gradient histograms in the style of SIFT'},
           {'prov': [{'page': 7, 'charspan': [0, 820]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The SIFT descriptor is computed on a window of 16 by 16 samples that is rotated to the keypoint '
                    'orientation and scaled to the keypoint scale. The window is divided into a grid of 4 by 4 '
                    'cells, and in each cell the gradient directions are accumulated in a histogram with 8 bins. '
                    'Concatenating the 16 histograms gives a vector with 128 elements. The gradient magnitudes are '
                    'weighted by a Gaussian whose standard deviation is half the width of the window, as sketched in '
                    'Figure 5. Each gradient sample is distributed over neighbouring cells and neighbouring '
                    'direction bins by trilinear interpolation, which prevents abrupt changes when a sample crosses '
                    'a boundary. Storing histograms instead of pixel values allows a gradient to shift by a few '
                    'samples inside its cell with only a small and gradual change of the descriptor.',
            'orig': 'The SIFT descriptor is computed on a window of 16 by 16 samples that is rotated to the keypoint '
                    'orientation and scaled to the keypoint scale. The window is divided into a grid of 4 by 4 '
                    'cells, and in each cell the gradient directions are accumulated in a histogram with 8 bins. '
                    'Concatenating the 16 histograms gives a vector with 128 elements. The gradient magnitudes are '
                    'weighted by a Gaussian whose standard deviation is half the width of the window, as sketched in '
                    'Figure 5. Each gradient sample is distributed over neighbouring cells and neighbouring '
                    'direction bins by trilinear interpolation, which prevents abrupt changes when a sample crosses '
                    'a boundary. Storing histograms instead of pixel values allows a gradient to shift by a few '
                    'samples inside its cell with only a small and gradual change of the descriptor.'},
           {'prov': [{'page': 7, 'charspan': [0, 25]}],
            'kind': 'text',
            'label': 'caption',
            'text': '16 by 16 gradient samples',
            'orig': '16 by 16 gradient samples'},
           {'prov': [{'page': 7, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': '4 by 4 cells with 8 orientation bins',
            'file': 'p0012.png',
            'width': 689,
            'height': 328},
           {'prov': [{'page': 7, 'charspan': [0, 36]}],
            'kind': 'text',
            'label': 'caption',
            'text': '4 by 4 cells with 8 orientation bins',
            'orig': '4 by 4 cells with 8 orientation bins'},
           {'prov': [{'page': 7, 'charspan': [0, 188]}],
            'kind': 'text',
            'label': 'caption',
            'text': 'Figure 5: Construction of a gradient histogram descriptor. Weighted gradient samples of a '
                    'synthetic patch on the left are accumulated into 16 cells with 8 direction bins each on the '
                    'right.',
            'orig': 'Figure 5: Construction of a gradient histogram descriptor. Weighted gradient samples of a '
                    'synthetic patch on the left are accumulated into 16 cells with 8 direction bins each on the '
                    'right.'},
           {'prov': [{'page': 7, 'charspan': [0, 79]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The raw vector d is finally made robust to illumination changes in three steps,',
            'orig': 'The raw vector d is finally made robust to illumination changes in three steps,'},
           {'prov': [{'page': 7, 'charspan': [0, 49]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'u = \\frac { \\text {d} } { \\| d \\| _ { 2 } } , \\quad v _ { i } = \\min ( u _ { i } , \\, 0 '
                    '. 2 ) , \\quad \\hat { d } = \\frac { v } { \\| v \\| _ { 2 } } .',
            'orig': 'u = d ∥d∥2 , vi =min(ui, 0.2), ˆd = v ∥v∥2 . (19)'},
           {'prov': [{'page': 7, 'charspan': [0, 500]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Normalising the vector to unit length cancels a multiplicative change of image contrast, and a '
                    'constant added to the brightness has no effect because gradients ignore it. Clamping the '
                    'elements at 0.2 limits the influence of a few very large gradients, which are typically caused '
                    'by illumination effects that are not linear. The SURF descriptor follows the same idea with '
                    'cheaper operations: it sums wavelet responses in a grid of 4 by 4 cells and stores four values '
                    'per cell, which gives 64 elements.',
            'orig': 'Normalising the vector to unit length cancels a multiplicative change of image contrast, and a '
                    'constant added to the brightness has no effect because gradients ignore it. Clamping the '
                    'elements at 0.2 limits the influence of a few very large gradients, which are typically caused '
                    'by illumination effects that are not linear. The SURF descriptor follows the same idea with '
                    'cheaper operations: it sums wavelet responses in a grid of 4 by 4 cells and stores four values '
                    'per cell, which gives 64 elements.'},
           {'prov': [{'page': 7, 'charspan': [0, 22]}],
            'kind': 'text',
            'label': 'section_header',
            'text': '5.2 Binary descriptors',
            'orig': '5.2 Binary descriptors'},
           {'prov': [{'page': 7, 'charspan': [0, 217]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Binary descriptors replace histograms by a string of bits, each of which is the result of '
                    'comparing two intensities in the smoothed patch. For a patch centred at p and a pair of offsets '
                    'a and b, one test is defined as',
            'orig': 'Binary descriptors replace histograms by a string of bits, each of which is the result of '
                    'comparing two intensities in the smoothed patch. For a patch centred at p and a pair of offsets '
                    'a and b, one test is defined as'},
           {'prov': [{'page': 7, 'charspan': [0, 54]}],
            'kind': 'formula',
            'label': 'formula',
            'text': '\\tau ( p ; a , b ) = \\begin{cases} 1 & \\text {if } I ( p + a ) < I ( p + b ) , \\\\ 0 & '
                    '\\text {otherwise} , \\end{cases} ( 2 0 )',
            'orig': 'τ (p; a, b) = {1 if I(p+a) < I(p+b), 0 otherwise, (20)'},
           {'prov': [{'page': 8, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': '',
            'file': 'p0013.png',
            'width': 29,
            'height': 28},
           {'prov': [{'page': 8, 'charspan': [0, 72]}],
            'kind': 'text',
            'label': 'text',
            'text': 'and n tests with a fixed set of offset pairs are packed into one number,',
            'orig': 'and n tests with a fixed set of offset pairs are packed into one number,'},
           {'prov': [{'page': 8, 'charspan': [0, 40]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'f _ { n } ( \\mathbf p ) = \\sum _ { i = 1 } ^ { n } 2 ^ { i - 1 } \\, \\tau ( \\mathbf p ; a _ '
                    '{ i } , b _ { i } ) .',
            'orig': 'fn(p) = n∑ i=1 2 i-1 τ (p; ai, bi). (21)'},
           {'prov': [{'page': 8, 'charspan': [0, 505]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The patch has to be smoothed before the tests, because comparisons of single pixels are very '
                    'sensitive to noise. The BRIEF descriptor uses a fixed random pattern of test pairs and '
                    'typically 256 bits, which occupy only 32 bytes. BRIEF is not invariant to rotation, since the '
                    'pattern is always applied in the same orientation. The ORB descriptor adds an orientation '
                    'estimate that is based on the intensity centroid of the patch P. With coordinates relative to '
                    'the patch centre, the moments and the angle are',
            'orig': 'The patch has to be smoothed before the tests, because comparisons of single pixels are very '
                    'sensitive to noise. The BRIEF descriptor uses a fixed random pattern of test pairs and '
                    'typically 256 bits, which occupy only 32 bytes. BRIEF is not invariant to rotation, since the '
                    'pattern is always applied in the same orientation. The ORB descriptor adds an orientation '
                    'estimate that is based on the intensity centroid of the patch P. With coordinates relative to '
                    'the patch centre, the moments and the angle are'},
           {'prov': [{'page': 8, 'charspan': [0, 56]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'm _ { p q } = \\sum _ { ( x , y ) \\in P } x ^ { p } y ^ { q } \\, I ( x , y ) , \\quad \\theta '
                    '_ { c } = \\tan 2 ( m _ { 0 1 } , m _ { 1 0 } ) .',
            'orig': 'mpq = ∑ (x,y)∈P xpyq I(x, y), θc = atan2(m01, m10). (22)'},
           {'prov': [{'page': 8, 'charspan': [0, 482]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The ORB descriptor rotates the test pattern by this angle and selects test pairs that have high '
                    'variance and low mutual correlation. BRISK and FREAK produce descriptors with 512 bits from '
                    'circular sampling patterns, in which points far from the centre are smoothed more strongly. A '
                    'SIFT descriptor needs 512 bytes when each element is stored as a 32-bit number, sixteen times '
                    'more than a 256-bit binary descriptor. Table 1 compares the descriptors that are mentioned in '
                    'these notes.',
            'orig': 'The ORB descriptor rotates the test pattern by this angle and selects test pairs that have high '
                    'variance and low mutual correlation. BRISK and FREAK produce descriptors with 512 bits from '
                    'circular sampling patterns, in which points far from the centre are smoothed more strongly. A '
                    'SIFT descriptor needs 512 bytes when each element is stored as a 32-bit number, sixteen times '
                    'more than a 256-bit binary descriptor. Table 1 compares the descriptors that are mentioned in '
                    'these notes.'},
           {'prov': [{'page': 8, 'charspan': [0, 0]}],
            'kind': 'table',
            'rows': [['Descriptor', 'Dimension', 'Type', 'Distance measure'],
                     ['SIFT RootSIFT SURF BRIEF ORB BRISK FREAK',
                      '128 128 64 256 bits 256 bits 512 bits 512 bits',
                      'real-valued real-valued real-valued binary binary binary binary',
                      'Euclidean Euclidean Euclidean Hamming Hamming Hamming Hamming']]},
           {'prov': [{'page': 8, 'charspan': [0, 88]}],
            'kind': 'text',
            'label': 'caption',
            'text': 'Table 1: Comparison of common local descriptors by dimension, type and distance measure.',
            'orig': 'Table 1: Comparison of common local descriptors by dimension, type and distance measure.'},
           {'prov': [{'page': 8, 'charspan': [0, 267]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Binary descriptors are faster to compute and to compare and need less memory, whereas gradient '
                    'histograms are usually more distinctive under large changes of viewpoint and scale. The choice '
                    'between the two families is therefore a trade between accuracy and resources.',
            'orig': 'Binary descriptors are faster to compute and to compare and need less memory, whereas gradient '
                    'histograms are usually more distinctive under large changes of viewpoint and scale. The choice '
                    'between the two families is therefore a trade between accuracy and resources.'},
           {'prov': [{'page': 8, 'charspan': [0, 28]}],
            'kind': 'text',
            'label': 'section_header',
            'text': '5.3 Practical considerations',
            'orig': '5.3 Practical considerations'},
           {'prov': [{'page': 8, 'charspan': [0, 734]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The size of the described patch is proportional to the keypoint scale, so a keypoint found at a '
                    'coarse level is described from a correspondingly larger image region. Because the patch is '
                    'taken from the Gaussian image closest to the keypoint scale, the descriptor of a large '
                    'structure is computed from a strongly smoothed image. Keypoints that lie too close to the image '
                    'border are discarded, because their patch would extend beyond the image. Invariance to scale '
                    'and rotation comes from the keypoint frame, whereas robustness to illumination comes from the '
                    'use of gradients and from normalisation. Neither family is invariant to strong perspective '
                    'distortion, so matching becomes unreliable for large changes of the viewing direction.',
            'orig': 'The size of the described patch is proportional to the keypoint scale, so a keypoint found at a '
                    'coarse level is described from a correspondingly larger image region. Because the patch is '
                    'taken from the Gaussian image closest to the keypoint scale, the descriptor of a large '
                    'structure is computed from a strongly smoothed image. Keypoints that lie too close to the image '
                    'border are discarded, because their patch would extend beyond the image. Invariance to scale '
                    'and rotation comes from the keypoint frame, whereas robustness to illumination comes from the '
                    'use of gradients and from normalisation. Neither family is invariant to strong perspective '
                    'distortion, so matching becomes unreliable for large changes of the viewing direction.'},
           {'prov': [{'page': 8, 'charspan': [0, 595]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The number of keypoints per image is usually limited to the strongest few thousand responses in '
                    'order to bound memory use and matching time. An image with 2000 keypoints yields a descriptor '
                    'matrix with 2000 rows and 128 columns in the case of SIFT. For compact storage the elements of '
                    'a SIFT descriptor are often multiplied by 512, limited to 255 and stored as single bytes, which '
                    'reduces the size to 128 bytes. Learned descriptors follow the same interface: they map a '
                    'normalised patch to a vector, so the matching and verification stages of the following sections '
                    'apply to them without change.',
            'orig': 'The number of keypoints per image is usually limited to the strongest few thousand responses in '
                    'order to bound memory use and matching time. An image with 2000 keypoints yields a descriptor '
                    'matrix with 2000 rows and 128 columns in the case of SIFT. For compact storage the elements of '
                    'a SIFT descriptor are often multiplied by 512, limited to 255 and stored as single bytes, which '
                    'reduces the size to 128 bytes. Learned descriptors follow the same interface: they map a '
                    'normalised patch to a vector, so the matching and verification stages of the following sections '
                    'apply to them without change.'},
           {'prov': [{'page': 15, 'charspan': [0, 0]}],
            'kind': 'picture',
            'caption': '',
            'file': 'p0024.png',
            'width': 30,
            'height': 28},
           {'prov': [{'page': 15, 'charspan': [0, 580]}],
            'kind': 'text',
            'label': 'text',
            'text': 'For Gaussian measurement noise, a threshold of 5.99 times the noise variance on the squared '
                    'transfer error in one image accepts 95 per cent of the true inliers of a homography, and a '
                    'threshold of 3.84 times the variance on the Sampson distance does the same for a fundamental '
                    'matrix. The symmetric transfer error adds two such terms and therefore needs a correspondingly '
                    'larger threshold. The sample size is the smallest number of matches that determines the model: '
                    'four for a homography and seven or eight for a fundamental matrix. The complete procedure is '
                    'given in Algorithm 1.',
            'orig': 'For Gaussian measurement noise, a threshold of 5.99 times the noise variance on the squared '
                    'transfer error in one image accepts 95 per cent of the true inliers of a homography, and a '
                    'threshold of 3.84 times the variance on the Sampson distance does the same for a fundamental '
                    'matrix. The symmetric transfer error adds two such terms and therefore needs a correspondingly '
                    'larger threshold. The sample size is the smallest number of matches that determines the model: '
                    'four for a homography and seven or eight for a fundamental matrix. The complete procedure is '
                    'given in Algorithm 1.'},
           {'prov': [{'page': 15, 'charspan': [0, 56]}],
            'kind': 'text',
            'label': 'section_header',
            'text': 'Algorithm 1 RANSAC with an adaptive number of iterations',
            'orig': 'Algorithm 1 RANSAC with an adaptive number of iterations'},
           {'prov': [{'page': 15, 'charspan': [0, 67]}],
            'kind': 'text',
            'label': 'text',
            'text': 'Require: set of n matches, sample size s, threshold t, confidence p',
            'orig': 'Require: set of n matches, sample size s, threshold t, confidence p'},
           {'prov': [{'page': 15, 'charspan': [0, 404]}],
            'kind': 'formula',
            'label': 'formula',
            'text': '\\frac { \\overline { \\text {Algorithm 1 RANSAC with an adaptive number of iterations} } } { '
                    '\\overline { \\text {Require: set of n matches, sample size s, threshold t, confidence p} } } & '
                    '\\\\ \\text {Ensure: model $\\theta$* and inlier set $\\mathcal{T}^{*}$} \\\\ 1 \\colon '
                    '\\mathbb { I } ^ { * } & \\left ( \\emptyset , \\ \\ N \\leftarrow \\infty , \\ \\ c '
                    '\\leftarrow 0 \\\\ 2 \\colon \\text {while $c < N$ do} \\\\ 3 \\colon \\text {draw s different '
                    'matches uniformly at random} \\\\ 4 \\colon \\text {fit a hypothesis $\\theta$ to the sample} '
                    '\\\\ 5 \\colon \\text {I< - \\{ i \\colon e _ { i } ( \\theta) < t ^ { 2 } \\} } \\\\ 6 \\colon '
                    '\\text {if | \\mathcal{I} | > | \\mathcal{I}^{\\ast} | then} \\\\ 7 \\colon \\quad \\mathcal { '
                    'I } ^ { * } \\leftarrow \\mathcal { I } , \\quad \\theta ^ { * } \\leftarrow \\theta \\\\ 8 '
                    '\\colon \\quad w \\leftarrow | \\mathcal { I } ^ { * } | / n \\\\ 9 \\colon \\quad N '
                    '\\leftarrow \\lceil \\log ( 1 - p ) / \\log ( 1 - w ^ { 8 } ) \\rceil \\\\ \\text {end if} \\\\ '
                    '1 \\colon \\quad c \\leftarrow c + 1 \\\\ 2 \\colon \\end{white} \\\\ 1 3 \\colon \\text '
                    '{estimate $\\theta^{\\ast}$ again from all matches in $\\mathcal{I}^{\\ast}$ by least squares} '
                    '\\\\ \\frac { 14 } { 1 } \\text { return $\\theta^{\\ast}$ and $\\mathcal{I}^{\\ast}$} \\\\ '
                    '\\text {How many samples are needed? Let $n_{i}$ of the $n$ matches be inliers, so} \\\\ \\text '
                    '{is $w = p _ { i } / n$. The probability that a sample of $s$ different matches contains}',
            'orig': 'Ensure: model θ∗ and inlier set I ∗ 1: I ∗ ← ∅, N ←∞, c ← 0 2: while c < N do 3: draw s '
                    'different matches uniformly at random 4: fit a hypothesis θ to the sample 5: I ← { i : ei(θ) < '
                    't2 } 6: if |I| > |I ∗ | then 7: I ∗ ← I, θ∗ ← θ 8: w ← |I ∗ |/n 9: N ← ⌈log(1 - p)/ log(1 - ws '
                    ')⌉ 10: end if 11: c ← c + 1 12: end while 13: estimate θ∗ again from all matches in I ∗ by '
                    'least squares 14: return θ∗ and I ∗'},
           {'prov': [{'page': 15, 'charspan': [0, 185]}],
            'kind': 'text',
            'label': 'text',
            'text': 'How many samples are needed? Let nin of the n matches be inliers, so that the inlier fraction '
                    'is w = nin/n. The probability that a sample of s different matches contains only inliers is',
            'orig': 'How many samples are needed? Let nin of the n matches be inliers, so that the inlier fraction '
                    'is w = nin/n. The probability that a sample of s different matches contains only inliers is'},
           {'prov': [{'page': 15, 'charspan': [0, 42]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'P _ { g o o d } = \\prod _ { i = 0 } ^ { s - 1 } \\frac { n _ { \\text {in} } - i } { n - i } '
                    '\\approx w ^ { s } .',
            'orig': 'Pgood = s-1 ∏ i=0 nin - i n- i ≈ ws . (40)'},
           {'prov': [{'page': 15, 'charspan': [0, 151]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The probability that N independent samples all contain at least one outlier is (1 -ws )N . '
                    'Requiring that this failure probability is at most 1-p gives',
            'orig': 'The probability that N independent samples all contain at least one outlier is (1 -ws )N . '
                    'Requiring that this failure probability is at most 1-p gives'},
           {'prov': [{'page': 15, 'charspan': [0, 81]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'p ( p s b s b ( N ) \\ a b s { N } ) & = p ( p s b s ) \\\\ & ( 1 - w ^ { s } ) ^ { N } \\leq 1 '
                    '- p , \\\\ N \\log ( 1 - w ^ { s } ) & \\leq \\log ( 1 - p ) , \\\\ N & \\geq \\frac { \\log ( '
                    '1 - p ) } { \\log ( 1 - w ^ { s } ) } .',
            'orig': '(1 - ws )N ≤ 1 - p, N log(1 - ws ) ≤ log(1 - p), N ≥ log(1-p) log(1 - ws ) . (41)'},
           {'prov': [{'page': 15, 'charspan': [0, 230]}],
            'kind': 'text',
            'label': 'text',
            'text': 'The inequality changes direction in the last step because the logarithm of a number below one '
                    'is negative.1 In practice the inlier fraction is unknown, and it is replaced by the fraction of '
                    'the best consensus set I ∗ found so far,',
            'orig': 'The inequality changes direction in the last step because the logarithm of a number below one '
                    'is negative.1 In practice the inlier fraction is unknown, and it is replaced by the fraction of '
                    'the best consensus set I ∗ found so far,'},
           {'prov': [{'page': 15, 'charspan': [0, 55]}],
            'kind': 'formula',
            'label': 'formula',
            'text': 'N = \\left \\lceil \\frac { \\log ( 1 - p ) } { \\log \\left ( 1 - \\left ( \\frac { | '
                    '\\mathcal { I } ^ { * } | } { n } \\right ) ^ { s } \\right ) } \\right \\rceil .',
            'orig': 'N = \uf8ee\uf8ef\uf8ef\uf8ef log(1 - p) log (1 - ( |I ∗ | n )s) \uf8f9\uf8fa\uf8fa\uf8fa . '
                    '(42)'},
           {'prov': [{'page': 15, 'charspan': [0, 426]}],
            'kind': 'text',
            'label': 'text',
            'text': 'With the approximation of the sampling probability by a power of the inlier fraction, the '
                    'number of iterations does not depend on the total number of matches, only on the inlier '
                    'fraction, the sample size and the desired confidence. It grows very quickly when the sample '
                    'size increases or the inlier fraction drops, which is why solvers with small samples are '
                    'preferred. Table 3 lists the values for the models of this lecture.',
            'orig': 'With the approximation of the sampling probability by a power of the inlier fraction, the '
                    'number of iterations does not depend on the total number of matches, only on the inlier '
                    'fraction, the sample size and the desired confidence. It grows very quickly when the sample '
                    'size increases or the inlier fraction drops, which is why solvers with small samples are '
                    'preferred. Table 3 lists the values for the models of this lecture.'},
           {'prov': [{'page': 15, 'charspan': [0, 79]}],
            'kind': 'text',
            'label': 'footnote',
            'text': '1The base of the logarithm does not matter, because it cancels in the quotient.',
            'orig': '1The base of the logarithm does not matter, because it cancels in the quotient.'}]}


def images() -> dict[str, bytes]:
    """One PNG per picture of the recorded result, of the size the worker reported."""
    return {item["file"]: png(item["width"], item["height"])
            for item in RAW["items"] if item["kind"] == "picture" and item["file"]}
