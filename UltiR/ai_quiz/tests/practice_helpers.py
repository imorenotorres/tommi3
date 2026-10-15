"""Shared pieces of the practice tests: a sectioned handout and a course with practice switched on."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from .conftest import BASE
from .pdfs import make_pdf

PRACTICE = f"{BASE}/api/practice"

# A four-page handout with three numbered sections, a subsection in two of them, a numbered list
# whose third item carries the number the next section will have, and a formula line. Each page
# is short enough to be one chunk, so chunk c_000N is page N.
SECTIONED = [
    ["Unit 4 handout",
     "1 Sampling a model",
     "A minimal sample is the smallest set of points that fixes the model completely.",
     "Four correspondences fix a homography and seven correspondences fix a fundamental matrix."],
    ["1.1 Why minimal samples",
     "Small samples are more likely to be free of outliers than large samples are.",
     "2 Counting iterations",
     "The number of iterations grows quickly when the inlier fraction drops.",
     "N = log(1 - p) / log(1 - w^s)"],
    ["Table 1: iterations needed for a success probability of 0.99",
     "A sample of four points with an inlier fraction of 0.5 needs 72 iterations.",
     "1. Draw a sample.",
     "2. Fit the model.",
     "3. Repeat the steps.",
     "3 Scoring a model",
     "Each model is scored by the number of matches that agree with it within a tolerance."],
    ["3.1 Choosing the tolerance",
     "The tolerance should match the expected error of a correct match in the images."],
]
SECTION_TITLES = ["Sampling a model", "Counting iterations", "Scoring a model"]


def sectioned_pdf() -> bytes:
    return make_pdf(SECTIONED)


# A handout with the sentences the two programmed tutors rest on, written as the text reading of sample.pdf has
# them (a hyphen for its minus sign): RANSAC on pages 2 and 3, precision and recall on page 4.
TUTOR_HANDOUT = [
    ["Handout for the tutor tests",
     "1 Matching",
     "Matching links the points of two images that show the same point of a scene."],
    ["2 RANSAC and its iteration count",
     "The sample size is the smallest number of matches that determines the model:",
     "four for a homography and seven or eight for a fundamental matrix.",
     "How many samples are needed? Let nin of the n matches be inliers, so that the inlier",
     "fraction is w = nin/n. The probability that a sample of s different matches contains only",
     "inliers is Pgood. The probability that N independent samples all contain at least one",
     "outlier is (1 - ws)N. Requiring that this failure probability is at most 1 - p gives"],
    ["the bound on the number of samples N.",
     "Rounding up gives 72 iterations for the homography."],
    ["3 Evaluation with precision and recall",
     "Let T Pbe the number of correct matches that are returned.",
     "Precision is the fraction of returned matches that are correct, and recall is the fraction",
     "of all true correspondences that are returned. Precision answers how trustworthy the",
     "output is, while recall answers how complete it is. The harmonic mean is dominated by the",
     "smaller of the two values. As an example, a matcher that returns 200 matches of which 150",
     "are correct, for an image pair with 250 true correspondences, has a precision of 0.75 and",
     "a recall of 0.60."],
]


def tutor_pdf() -> bytes:
    return make_pdf(TUTOR_HANDOUT)


def run(coroutine):
    """Run a coroutine to its end on a thread of its own. The browser tests leave an event loop running in the
    main thread (Playwright's synchronous API), and asyncio.run refuses to start inside one."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


class PracticeCourse:
    """A course with the sectioned handout uploaded and, unless told otherwise, practice switched on."""

    def __init__(self, client, launch, course="course-A", switch_on=True, pdf=None, name="unit4.pdf"):
        self.client, self.launch, self.course = client, launch, course
        self.instructor = launch.token(role="Instructor", course=course, user="teacher-1")
        response = client.post(f"{BASE}/api/documents", params={"token": self.instructor},
                               files={"file": (name, pdf or sectioned_pdf())})
        assert response.status_code == 201, response.text
        self.doc = response.json()
        if switch_on:
            self.settings(enabled=True)

    def learner(self, user="student-1"):
        return self.launch.token(role="Learner", course=self.course, user=user)

    def settings(self, **body):
        response = self.client.put(f"{PRACTICE}/settings", params={"token": self.instructor}, json=body)
        assert response.status_code == 200, response.text
        return response.json()

    def topics(self, token=None):
        response = self.client.get(f"{PRACTICE}/topics", params={"token": token or self.learner()})
        assert response.status_code == 200, response.text
        return response.json()["topics"]
