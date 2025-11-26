# Smart Task Analyzer

Smart Task Analyzer is a small Django + DRF backend with a lightweight frontend that scores and prioritizes tasks using multiple strategies (Fastest Wins, High Impact, Deadline Driven, Smart Balance). It is designed as a single-user, local tool for exploring trade‑offs in task management and scheduling.

## 1. Setup Instructions

### 1.1. Requirements

- Python 3.8+ (tested with 3.12)
- pip

### 1.2. Install dependencies

From the project root:

```bash
pip install -r requirements.txt
```

This installs:

- Django (5.x)
- Django REST Framework (DRF)
- django-cors-headers

### 1.3. Run database migrations

```bash
python manage.py migrate
```

### 1.4. Run the backend API

```bash
python manage.py runserver 8000
```

This serves the API at `http://127.0.0.1:8000/`.

- `POST /api/tasks/analyze/`
- `GET /api/tasks/suggest/`

### 1.5. Run the frontend

In a second terminal, from the project root, start a simple static server for the frontend:

```bash
python -m http.server 8080
```

Then open the UI in your browser:

- `http://127.0.0.1:8080/frontend/index.html`

The frontend will call the backend directly at `http://127.0.0.1:8000/api/...`.

### 1.6. Run tests

```bash
python manage.py test
```

This runs:

- Endpoint tests for `/api/tasks/analyze/` and `/api/tasks/suggest/`
- At least 3 unit tests focused on the scoring logic in `tasks/scoring.py`

## 2. Algorithm Explanation (Smart Balance)

The scoring pipeline has three main stages: normalization of inputs, dependency graph analysis, and strategy‑specific scoring. All strategies share a common set of normalized components per task: urgency, importance_norm, quick_win, and dep_score. The Smart Balance strategy uses all four to produce a well‑rounded priority score.

First, the backend normalizes raw task data. Due dates are converted to a numerical urgency in \[0, 1] using a 30‑day window: overdue tasks get 1.0, tasks with no due date get a low baseline (0.1), and tasks further in the future decay linearly down toward zero. Importance is provided by the user on a 1–10 scale and normalized to importance_norm = importance / 10. Estimated hours are turned into a quick win score: tasks capped at 8 hours are mapped to an “effort penalty” between 0 and 1, and quick_win = 1 − penalty. This means very small tasks get values close to 1 while large tasks trend toward 0.

Next, the algorithm analyzes dependencies. It builds a directed graph where edges point from a prerequisite task to tasks that depend on it. For each task, num_dependents counts how many others list it as a dependency, and dep_score is computed by normalizing this count against the maximum dependents seen. A standard depth‑first search with a recursion stack is used to detect cycles; all tasks that belong to any cycle are collected for special handling. This keeps the system honest when the dependency data is inconsistent or circular.

Finally, each strategy combines the components with different weights. For Smart Balance, the formula is:

```text
score_smart = 0.35 * urgency
            + 0.35 * importance_norm
            + 0.15 * quick_win
            + 0.15 * dep_score
```

This puts urgency and importance on equal footing, while still rewarding tasks that are quick to complete and that unblock many others. Strategies like Fastest Wins, High Impact, and Deadline Driven use the same components but change the weights (for example, Fastest Wins emphasizes quick_win, and High Impact emphasizes importance_norm). After computing a base score in \[0, 1], any task that is part of a dependency cycle gets a strong penalty (its score is multiplied by 0.2), and the result is scaled to a 0–100 range and rounded. A human‑readable explanation string is built from the components, describing urgency, importance, effort, and dependency impact (e.g., “Very urgent (due in 2 days); Importance 8/10; Quick win (3h); Blocks 2 other task(s); Part of dependency cycle”). This makes the score interpretable rather than a black box.

## 3. Design Decisions & Trade‑offs

- **In‑memory tasks**: The assignment allowed skipping persistent storage. I chose not to create a `Task` model and instead treat the API as pure analysis of request payloads. This keeps the code small and avoids migrations and CRUD concerns that are not central to the scoring problem.
- **Auto‑assigned IDs with editable dependencies**: IDs are assigned incrementally in the frontend once tasks are added. Dependencies are edited afterward, per row, which makes it clear which IDs exist and avoids the user guessing them upfront. The backend still validates that all dependency IDs are known and not self‑referential.
- **Strategy abstraction**: All strategies share common normalized components; each strategy is just a different weighted formula. This keeps the implementation extensible (adding a new strategy is a function and a string constant) and reduces duplication.
- **Cycle handling**: Instead of rejecting cyclic task graphs entirely, tasks in cycles are flagged (`cycle_issue: true`) and penalized in score. This surfaces the problem but still returns a complete ordering, which is more helpful to an end‑user than a hard error.
- **Simple, framework‑free frontend**: The frontend is plain HTML/CSS/JS with `fetch`. For a small assignment, React/Vue would add boilerplate without much benefit. The UI is responsive via CSS grid/flexbox and focuses on clarity rather than heavy styling.

## 4. Time Breakdown (Approximate)

- Backend project setup (Django + DRF, app wiring, endpoints): **~1.0–1.5 hours**
- Scoring algorithm design & implementation (normalization, graph, strategies, explanations): **~2.0–2.5 hours**
- Frontend implementation (layout, task builder, JSON loader, API wiring, styling): **~1.5–2.0 hours**
- Testing & debugging (unit tests, manual browser testing, CORS and local hosting quirks): **~1.0–1.5 hours**
- Documentation (README, comments, polishing): **~0.5–1.0 hours**

These are rough ranges rather than precise time logs.

## 5. Bonus Challenges

I focused on building a clear scoring engine, multi‑strategy support, cycle detection, and a usable UI. I did not implement advanced features such as learning from historical user adjustments, calendar/weekday awareness, or multi‑user authentication. The main “bonus” aspects are:

- Multiple scoring strategies sharing a common component model.
- Human‑readable explanations attached to each scored task.
- Dependency graph analysis with cycle detection and dep_score normalization.

## 6. Future Improvements

- **Calendar awareness**: Incorporate weekends, holidays, and working hours into the urgency calculation so “3 days” over a weekend is treated differently than 3 working days.
- **User tuning / learning**: Allow users to adjust weights for each component or strategy, and optionally learn from which tasks they actually pick next (e.g., a small online learning loop).
- **Richer task model**: Add optional tags (e.g., “deep work”, “admin”), contexts (home/office), or energy levels and extend the scoring formula to honor them.
- **Persistence and history**: Introduce a proper `Task` model and store past analyses so users can compare how priorities evolved over time.
- **Better visualization**: Add charts or timelines (e.g., scatter plot of urgency vs. effort, colored by importance) to complement the card‑based list.
- **Error UX**: Surface validation errors inline in the frontend (by task/field) instead of a single generic message, making it clearer which row needs adjustment.

## 7. Technical Requirements Checklist

- **Python / Django version**: Uses Python 3.12 and Django 5.x (which satisfies the Django 4.0+ requirement).
- **Database**: Default SQLite via Django settings.
- **Local‑only**: No deployment or authentication logic; runs locally with two simple commands for backend and frontend.
- **Tests**: Includes endpoint tests and at least three unit tests explicitly targeting the scoring logic.


