"""Flask optimization focus areas."""

FOCUS = """
Focus areas for Flask:

-- Existing patterns --
- Application context: accessing g, request, session, or current_app in background
  threads or CLI commands without pushing an explicit app context; g used for
  cross-request caching (g is reset per request).
- SQLAlchemy sessions: manual Session() instantiation instead of db.session; db.session.
  add() without a commit or rollback in the same function; N+1 relationship access in
  loops without joinedload/subqueryload.
- Blueprint organization: before_request/after_request hooks on app that only apply to
  a subset of routes (scope to a Blueprint); 20+ routes in a single file without Blueprints.
- Template rendering: lazy relationship loading triggered inside {% for %} loops
  (pre-load in view with joinedload); complex filter chains in templates (pre-compute
  in the view function).
- Caching: non-user-specific view functions querying the DB without @cache.cached or
  flask-caching; missing Cache-Control headers on public endpoints.
- Error handling: JSON API without @app.errorhandler(404) and @app.errorhandler(500)
  returning JSON; request.json["key"] without None check.

-- Rule catalog (apply low-risk first) --

Rule FL-CTX-001 — Application context not pushed in background threads
  Anti-pattern : `threading.Thread(target=worker)` or `concurrent.futures.ThreadPoolExecutor`
                 calling code that accesses `current_app`, `g`, or DB session without
                 explicitly pushing an app context
  Detection    : Python AST — `threading.Thread` or `executor.submit` call; target
                 function body references `current_app`, `g`, or `db.session`
                 without `with app.app_context():`
  Patch (medium): Wrap the target function body in `with app.app_context(): ...`
                 or pass needed values as arguments instead of relying on context proxies
  Validate     : Integration tests running the background function; confirm no
                 RuntimeError("Working outside of application context")
  Rollback if  : context pushes have unexpected side effects (e.g. multiple sessions)
  Do NOT apply : code already uses `app.app_context()` or passes explicit app reference

Rule FL-N1-002 — N+1 SQLAlchemy queries from lazy relationship loading
  Anti-pattern : `for obj in db.session.query(Model).all(): print(obj.relation.field)`
                 where `relation` is a lazy-loaded relationship
  Detection    : Python AST — attribute access `obj.relation.field` inside a for-loop
                 where `obj` comes from a SQLAlchemy query that lacks `.options(
                 joinedload(Model.relation))` or `.options(subqueryload(...))`
  Patch (medium): Add `.options(joinedload(Model.relation))` or use
                 `selectinload` for collections to eager-load the relationship
  Validate     : SQLAlchemy query event counter; assertNumQueries equivalent
  Rollback if  : joined load causes Cartesian product for multi-level relationships
  Do NOT apply : relationship accessed conditionally (only sometimes needed)

Rule FL-CACHE-003 — Uncached view querying stable data on every request
  Anti-pattern : View function calling `db.session.query(Model).all()` or aggregate
                 queries for data that does not change per user or request
  Detection    : Python AST — view function contains DB query call; no
                 `@cache.cached` decorator from flask-caching; function
                 not guarded by login_required or similar user-context check
  Patch (medium): Add `@cache.cached(timeout=300, key_prefix='view_key')`;
                 or use `cache.get/set` for finer-grained caching
  Validate     : Cache hit rate; response time comparison; data freshness
  Rollback if  : stale data causes incorrect behaviour for any user
  Do NOT apply : view data is user-specific; real-time accuracy required

Rule FL-BLUEPRINT-004 — app-level before_request hook for route-subset logic
  Anti-pattern : `@app.before_request` hook that checks `request.endpoint` to limit
                 execution to a subset of routes — should be a Blueprint hook
  Detection    : Python AST — `@app.before_request` function body with an early
                 `if request.endpoint not in (...)` or `if request.endpoint.startswith`
                 guard indicating it only applies to some routes
  Patch (medium): Move the logic into a Blueprint's `@bp.before_request` hook;
                 register the blueprint for the affected route group
  Validate     : Integration tests for both affected and unaffected routes
  Rollback if  : blueprint refactor breaks request context sharing
  Do NOT apply : hook genuinely applies to all routes

Rule FL-ERR-005 — JSON API without structured error handlers
  Anti-pattern : Flask app serving a JSON API without `@app.errorhandler(404)`
                 and `@app.errorhandler(500)` that return JSON responses
  Detection    : file — app factory or main file has no `@app.errorhandler(404)`
                 and `@app.errorhandler(500)` registered; app returns HTML error
                 pages by default
  Patch (low)  : Register error handlers returning `jsonify({"error": description})`
                 with the correct status code
  Validate     : Integration test 404 and 500 responses; confirm JSON content-type
  Rollback if  : some routes intentionally serve HTML (mixed app)
  Do NOT apply : app is not a JSON API; intentional HTML error pages
"""
