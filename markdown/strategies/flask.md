# Agent Optimization Strategy — Flask

Flask is a micro-framework — it provides routing, a request context, and a development server, and leaves everything else (ORM, validation, auth) to extensions. This minimalism is its strength and its risk: there are fewer guardrails, so application-level patterns are more variable. The optimization concerns are largely about application context misuse, SQLAlchemy session management, blueprint organization, and the same N+1 / over-fetching problems as Django.

---

## Detection

| Signal | Confidence |
|---|---|
| `flask` in `requirements.txt` / `pyproject.toml` | 0.95 |
| `from flask import Flask` in source | 0.9 |
| `flask-sqlalchemy` or `flask-migrate` in deps | confirms Flask + SQLAlchemy stack |
| `flask-restful` / `flask-restx` | Flask REST API |

---

## Category 1 — Application and Request Context Misuse

### Why it matters

Flask's application context (`g`, `current_app`) and request context (`request`, `session`) are thread-local (or async-local) proxies. Accessing them outside a request (in background threads, scheduled jobs, CLI commands) raises `RuntimeError: Working outside of application context`. Developers often work around this incorrectly, creating bugs.

### What to look for

1. **Accessing `g`, `request`, or `session` inside a background thread or subprocess** without pushing an application context:
   ```python
   # BAD: RuntimeError in background thread
   import threading
   def background_task():
       user_id = g.user_id  # RuntimeError!

   @app.post("/trigger")
   def trigger():
       thread = threading.Thread(target=background_task)
       thread.start()

   # GOOD: push app context explicitly
   def background_task(app):
       with app.app_context():
           do_work()
   ```

2. **`current_app` accessed at import time** (module level) instead of inside a function — the app context doesn't exist at import time.

3. **`g` used to cache data across requests** — `g` is reset on every request; use `flask_caching` or a module-level cache for cross-request data.

### Agent rules

- Flag any access to `g`, `request`, `session`, or `current_app` in a function that doesn't have a request context (thread functions, CLI commands, class methods called from background jobs).
- Flag `g.something = value` where `something` suggests cross-request caching intent.

---

## Category 2 — SQLAlchemy Session Management

### Why it matters

Flask-SQLAlchemy provides a scoped session tied to the request context. Improper use causes transactions to leak across requests, stale data, or connection pool exhaustion.

### What to look for

1. **Creating SQLAlchemy sessions manually** (`Session()`) instead of using `db.session`:
   ```python
   # BAD: creates an unmanaged session outside Flask-SQLAlchemy's scoping
   session = Session(bind=engine)
   users = session.query(User).all()

   # GOOD: use the managed session
   users = db.session.query(User).all()
   ```

2. **Not committing or rolling back transactions** in error branches — the session is left in a dirty state:
   ```python
   # BAD: if an error occurs after db.session.add, the session is dirty on next request
   @app.post("/user")
   def create_user():
       user = User(name=request.json["name"])
       db.session.add(user)
       # no commit!
       return jsonify({"id": user.id})  # user.id is None
   ```

3. **N+1 queries** — same as Django. Flask-SQLAlchemy has the same `select_related` / `joinedload` / `subqueryload` solutions via SQLAlchemy's query options:
   ```python
   # BAD: N+1
   posts = Post.query.all()
   for post in posts:
       print(post.author.name)

   # GOOD: eager load
   from sqlalchemy.orm import joinedload
   posts = Post.query.options(joinedload(Post.author)).all()
   ```

4. **`db.session.close()` called explicitly** in routes — Flask-SQLAlchemy's scoped session handles this automatically at request teardown. Explicit closes can cause problems.

### Agent rules

- Flag `Session()` instantiation outside of `db.session` usage.
- Flag `db.session.add()` not followed by `db.session.commit()` or `db.session.rollback()` within the same function.
- Flag relationship attribute access in loops without `joinedload`/`subqueryload` (same N+1 detection as Django).

---

## Category 3 — Blueprint Organization

### Why it matters

Flask applications that register all routes directly on `app` (without Blueprints) are harder to test and scale. More concretely, large `app.py` / `routes.py` files cause slow import times and make it impossible to lazy-load route modules.

### What to look for

1. **All routes in a single file** without Blueprints — especially when the file is > 200 lines.

2. **Before/after request hooks registered on `app`** that only apply to a subset of routes:
   ```python
   # BAD: rate limiting runs on all routes including health checks
   @app.before_request
   def rate_limit():
       check_rate_limit(request.remote_addr)

   # GOOD: apply to a blueprint
   api_bp = Blueprint("api", __name__)

   @api_bp.before_request
   def rate_limit():
       check_rate_limit(request.remote_addr)
   ```

3. **Repeated `@login_required` decorators** that could be a blueprint-level `before_request`.

### Agent rules

- Flag `before_request` / `after_request` hooks on `app` that don't need to apply to every route — suggest scoping to a Blueprint.
- Flag files with 20+ route definitions that lack Blueprint organization.

---

## Category 4 — Template Rendering Efficiency

### Why it matters

Jinja2 template rendering is synchronous and runs on the main thread. Expensive template logic (N+1 queries triggered by template loops, complex filters) stalls response time.

### What to look for

1. **ORM queries triggered inside Jinja2 templates** via lazy relationship loading:
   ```html
   <!-- BAD: triggers a query for each post -->
   {% for post in posts %}
     {{ post.author.name }}
   {% endfor %}
   ```
   The solution is always to pre-load the data in the view function.

2. **Complex Python logic in template files** — loops with conditionals, multiple filters chained — that should be pre-computed in the view:
   ```html
   <!-- BAD: slow filter chain in template -->
   {{ items | selectattr("active") | sort(attribute="name") | list }}
   ```

3. **Large template inheritance chains** (5+ levels) that Jinja2 has to compile on first render.

### Agent rules

- Flag relationship attribute access in `{% for %}` loops when the base queryset doesn't have eager loading — suggest adding `joinedload()` / `options()` in the view.

---

## Category 5 — Response Caching and ETags

### Why it matters

Flask has no built-in caching — `flask-caching` must be added explicitly. Even simple responses (reference data, public pages) often hit the database on every request.

### What to look for

1. **View functions that query the same data repeatedly** without caching:
   ```python
   # Uncached: every request hits the DB
   @app.get("/categories")
   def list_categories():
       return jsonify(Category.query.all())

   # GOOD: cache with flask-caching
   @app.get("/categories")
   @cache.cached(timeout=300)
   def list_categories():
       return jsonify(Category.query.all())
   ```

2. **Missing `Cache-Control` headers** on API responses — every response is treated as private no-cache by CDNs.

3. **No ETag support** for list endpoints — clients must re-download the full response even when nothing changed.

### Agent rules

- Flag view functions with DB queries that are not user-specific and have no `@cache.cached` or `cache.get`/`cache.set` — suggest `flask-caching`.

---

## Category 6 — Error Handling

### Why it matters

Flask's default error handling returns HTML error pages for 404/500 errors in JSON APIs, confusing clients. Missing `@app.errorhandler` registrations mean errors surface as unstructured HTML.

### What to look for

1. **No `@app.errorhandler(404)` / `@app.errorhandler(500)` in a JSON API**:
   ```python
   # GOOD: JSON error responses
   @app.errorhandler(404)
   def not_found(e):
       return jsonify({"error": "Not found"}), 404

   @app.errorhandler(Exception)
   def handle_exception(e):
       app.logger.exception("Unhandled exception: %s", e)
       return jsonify({"error": "Internal server error"}), 500
   ```

2. **Route handlers that swallow exceptions** without logging.

3. **Missing validation of `request.json`** — if the content type is not JSON or the body is malformed, `request.json` returns `None` silently, causing `TypeError` downstream.

### Agent rules

- Flag missing global error handlers in JSON API applications.
- Flag `request.json["field"]` without a `None` check or `request.get_json(force=True)` + validation.

---

## System Prompt

```
Focus areas for Flask:
- Application context: accessing g, request, session, or current_app in background
  threads or CLI commands without pushing an explicit app context; g used for
  cross-request caching (g is reset per request).
- SQLAlchemy sessions: manual Session() instantiation instead of db.session; db.session.
  add() without a commit or rollback in the same function; N+1 relationship access in
  loops without joinedload/subqueryload.
- Blueprint organization: before_request/after_request hooks on app that only apply to
  a subset of routes (scope to a Blueprint); 20+ routes in a single file without Blueprints.
- Template rendering: lazy relationship loading triggered inside {%  for %} loops
  (pre-load in view with joinedload); complex filter chains in templates (pre-compute
  in the view function).
- Caching: non-user-specific view functions querying the DB without @cache.cached or
  flask-caching; missing Cache-Control headers on public endpoints.
- Error handling: JSON API without @app.errorhandler(404) and @app.errorhandler(500)
  returning JSON; request.json["key"] without None check.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| N+1 fix (SQLAlchemy) | Query count per request | `flask-sqlalchemy` echo / `flask-debugtoolbar` |
| Session management | Transaction error rate | App logs |
| Caching | DB calls per minute | Redis hit rate / cache stats |
| Blueprint scoping | Middleware execution per route | Flask profiler |
| Error handling | 500 error rate | Application logs |
