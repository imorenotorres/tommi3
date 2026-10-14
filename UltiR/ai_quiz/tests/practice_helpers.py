"""Shared pieces of the practice tests: a sectioned handout and a course with practice switched on."""

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
