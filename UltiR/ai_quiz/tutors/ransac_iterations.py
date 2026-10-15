"""Tutor: the number of RANSAC iterations, N = ⌈log(1 − p) / log(1 − wˢ)⌉ (sample.pdf, pp. 15–16).

What is reviewed is in ransac_iterations.toml; this module only computes. Levels:

    basico      w, s and p are given; p = 0.99
    intermedio  the counts of matches and of correct ones are given, and the model is named: the student has to
                know its sample size; p = 0.99
    avanzado    as intermedio, with p = 0.95 or 0.999 and the two fundamental-matrix solvers more often
"""

import math

# The models of the handout and their minimal sample sizes (p. 15): line 2, homography 4, fundamental 7 or 8.
SAMPLE = {"line": 2, "homography": 4, "fundamental7": 7, "fundamental8": 8}
# The sample size a student gives a model by mistake: the degrees of freedom of a homography (8, p. 13), or
# the other of the two fundamental-matrix solvers. A line has no such confusion in the handout.
CONFUSED = {"line": None, "homography": 8, "fundamental7": 8, "fundamental8": 7}
FRACTIONS = [round(0.30 + 0.05 * k, 2) for k in range(13)]          # 0.30 ... 0.90


def draw(level: str, rng, aim: str | None) -> dict:
    models = list(SAMPLE)
    if level == "avanzado" or aim == "sample_size":
        models = ["fundamental7", "fundamental8", "homography"]
    model = rng.choice(models)
    if level == "basico":
        return {"model": model, "s": SAMPLE[model], "w": rng.choice(FRACTIONS[4:]), "p": 0.99, "counts": False}
    n = rng.choice(range(100, 401, 20))
    w = rng.choice(FRACTIONS)
    n_in = round(w * n)
    p = 0.99 if level == "intermedio" else rng.choice([0.95, 0.999])
    return {"model": model, "s": SAMPLE[model], "n": n, "n_in": n_in, "w": n_in / n, "p": p, "counts": True}


def _iterations(p: float, fraction: float, s: int) -> float:
    """log(1 − p) / log(1 − fractionˢ), before rounding."""
    return math.log(1 - p) / math.log(1 - fraction ** s)


def _up(x: float) -> int:
    """⌈x⌉, where a value a hair above a whole number from rounding errors is that whole number."""
    return round(x) if abs(x - round(x)) < 1e-9 else math.ceil(x)


def solve(params: dict) -> float:
    return float(_up(_iterations(params["p"], params["w"], params["s"])))


def form(params: dict) -> str:
    return "integer"


def mistakes(params: dict) -> dict:
    p, w, s = params["p"], params["w"], params["s"]
    x = _iterations(p, w, s)
    confused = CONFUSED[params["model"]] if params["counts"] else None    # s is given at the basic level
    return {
        # the probability that one match is an inlier, w, used for the probability that a whole sample is
        "w_not_ws": float(_up(math.log(1 - p) / math.log(1 - w))),
        # rounded down where the inequality asks for the next whole number up
        "round_down": float(math.floor(x)) if abs(x - round(x)) >= 1e-9 else None,
        # another sample size than the model's
        "sample_size": float(_up(_iterations(p, w, confused))) if confused else None,
        # the share of wrong matches taken for w
        "outlier_fraction": float(_up(_iterations(p, 1 - w, s))) if w != 0.5 else None,
        # log p where the failure probability 1 − p belongs
        "log_p": float(_up(math.log(p) / math.log(1 - w ** s))),
    }


def values(params: dict) -> dict:
    """The numbers the statement and the worked solution are written with."""
    x = _iterations(params["p"], params["w"], params["s"])
    return {"s": params["s"], "w": params["w"], "p": params["p"], "n": params.get("n"), "n_in": params.get("n_in"),
            "ws": params["w"] ** params["s"], "log1p": math.log(1 - params["p"]),
            "log1ws": math.log(1 - params["w"] ** params["s"]), "x": x, "N": _up(x),
            "s_wrong": CONFUSED[params["model"]], "w_out": 1 - params["w"]}
