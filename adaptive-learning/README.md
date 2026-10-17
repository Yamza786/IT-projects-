# Adaptive Learning and Tutoring Platform

See [ACCESSIBILITY.md](ACCESSIBILITY.md) for the UI review, measured color contrast, and remaining manual assistive-technology checks.

A small learning workspace with lessons, multiple-choice practice, saved attempts, and topic suggestions based on missed answers. The sample lesson content is intentionally general; question generation is not performed by an AI model.

Add lessons and reviewed questions with `POST /api/lessons`. Every answer schedules a follow-up using a simple spaced-repetition interval; missed answers return to a one-day interval. `GET /api/review-due` lists questions due today without exposing answer keys.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open the home page for the sample lesson. API documentation is at `/docs`; set `LEARNING_DB` to move the SQLite file.

## Learning model

Lessons contain short reviewed material and tagged questions. Attempts are stored locally. The recommendation endpoint prioritizes tags where the learner has answered incorrectly most often; it reports the reason so recommendations can be understood. This is not a validated assessment instrument.
