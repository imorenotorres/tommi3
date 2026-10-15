"""Tutor: precision, recall and F1 from matching counts (sample.pdf, p. 17).

What is reviewed is in precision_recall.toml; this module only computes. One value is asked per exercise, as a
decimal between 0 and 1 with three places. Levels:

    basico      TP, FP and FN are given; precision or recall is asked
    intermedio  as in the handout's example: matches returned, correct ones among them, true correspondences
                of the pair; precision or recall is asked
    avanzado    the same counts; F1 is asked
"""

MEASURES = ("P", "R", "F1")
# A percentage is written with a hundred times less precision than the decimal: "66,7" for 0.667.
SCALE = {"percent": 100}


def draw(level: str, rng, aim: str | None) -> dict:
    asks = "F1" if level == "avanzado" else rng.choice(["P", "R"])
    if aim in ("swapped", "complement", "ratio") and asks == "F1":
        asks = rng.choice(["P", "R"])             # the next exercise practises the mistake made: P or R has it
    if aim in ("arithmetic_mean", "no_two"):
        asks = "F1"
    tp = rng.randrange(40, 301)
    fp = rng.randrange(5, 151)
    fn = rng.randrange(5, 201)
    if level == "basico":
        return {"tp": tp, "fp": fp, "fn": fn, "asks": asks, "counts": False}
    return {"tp": tp, "fp": fp, "fn": fn, "asks": asks, "counts": True,
            "returned": tp + fp, "correct": tp, "true": tp + fn}


def _measures(params: dict) -> tuple[float, float, float]:
    tp, fp, fn = params["tp"], params["fp"], params["fn"]
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    return precision, recall, 2 * precision * recall / (precision + recall)


def solve(params: dict) -> float:
    return dict(zip(MEASURES, _measures(params)))[params["asks"]]


def form(params: dict) -> str:
    return "fraction3"


def mistakes(params: dict) -> dict:
    tp, fp, fn, asks = params["tp"], params["fp"], params["fn"], params["asks"]
    precision, recall, f1 = _measures(params)
    answer = solve(params)
    return {
        # the other of the two measures: the recall given for the precision, or the other way round
        "swapped": {"P": recall, "R": precision}.get(asks),
        # the share of what went wrong: incorrect among returned, or missed among true
        "complement": {"P": fp / (tp + fp), "R": fn / (tp + fn)}.get(asks),
        # correct against incorrect, not against all
        "ratio": {"P": tp / fp, "R": tp / fn}.get(asks),
        # the arithmetic mean of the two in place of the harmonic mean
        "arithmetic_mean": (precision + recall) / 2 if asks == "F1" else None,
        # the harmonic mean without its factor 2
        "no_two": precision * recall / (precision + recall) if asks == "F1" else None,
        # a percentage where a decimal between 0 and 1 is asked
        "percent": answer * 100,
    }


def values(params: dict) -> dict:
    precision, recall, f1 = _measures(params)
    tp, fp, fn = params["tp"], params["fp"], params["fn"]
    return {"tp": tp, "fp": fp, "fn": fn, "tp_fp": tp + fp, "tp_fn": tp + fn,
            "returned": params.get("returned"), "correct": params.get("correct"), "true": params.get("true"),
            "P": round(precision, 3), "R": round(recall, 3), "F1": round(f1, 3), "PR": round(precision + recall, 3),
            "answer": round(solve(params), 3)}
