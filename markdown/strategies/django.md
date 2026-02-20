# Agent Optimization Strategy — Django

Django is a batteries-included Python web framework with a powerful ORM, admin interface, template engine, and middleware system. The dominant performance issues are almost always in the ORM — specifically N+1 queries, missing database indexes, and fetching more columns/rows than needed. Django's sync-first architecture also means it struggles under high concurrency unless paired with async views (Django 4.1+) or Gunicorn with multiple workers.

---

## Detection

| Signal | Confidence |
|---|---|
| `django` in `requirements.txt` / `pyproject.toml` | 0.95 |
| `manage.py` exists | 0.9 |
| `settings.py` with `INSTALLED_APPS` | confirms Django |
| `django-rest-framework` or `djangorestframework` | flags as Django REST API |

---

## Category 1 — N+1 Query Problems (The #1 Django Issue)

### Why it matters

The Django ORM makes it dangerously easy to write queries that look fine in Python but translate to N+1 (or worse) SQL queries. A queryset that accesses a related object for each row triggers one query per row.

### What to look for

1. **Accessing a ForeignKey relation in a loop** without `select_related`:
   ```python
   # BAD: 1 + N queries (1 for posts, N for each post's author)
   posts = Post.objects.all()
   for post in posts:
       print(post.author.name)  # triggers a new query per post

   # GOOD: 2 queries total (JOIN)
   posts = Post.objects.select_related("author").all()
   ```

2. **Accessing a ManyToMany or reverse FK relation in a loop** without `prefetch_related`:
   ```python
   # BAD: 1 + N queries
   users = User.objects.all()
   for user in users:
       print(user.tags.all())  # triggers a new query per user

   # GOOD: 2 queries total
   users = User.objects.prefetch_related("tags").all()
   ```

3. **Using `select_related` for ManyToMany** (only works for FK/OneToOne) or `prefetch_related` for simple FK (works but is less efficient than `select_related` for FK).

4. **Nested related access** that requires chained `select_related`:
   ```python
   # BAD
   posts = Post.objects.select_related("author")
   for post in posts:
       print(post.author.profile.avatar)  # author is loaded, profile is not

   # GOOD
   posts = Post.objects.select_related("author__profile")
   ```

5. **`Prefetch` objects with custom querysets** for fine-grained control when the related queryset needs filtering.

### Agent rules

- Flag any `.all()` or `.filter()` queryset access inside a `for` loop where the loop variable's related attributes are accessed.
- Trace FK/ManyToMany field access patterns to suggest appropriate `select_related` / `prefetch_related` chains.

---

## Category 2 — Fetching Too Much Data

### Why it matters

`Model.objects.all()` fetches every column and every row. For wide tables or large datasets, this is expensive in both memory and I/O.

### What to look for

1. **`objects.all()` or `objects.filter()` followed by accessing only a few fields** — use `.values()` or `.only()`:
   ```python
   # BAD: loads all columns into Python objects
   users = User.objects.all()
   for user in users:
       send_email(user.email)  # only email needed

   # GOOD: loads only email from DB
   emails = User.objects.values_list("email", flat=True)
   for email in emails:
       send_email(email)
   ```

2. **`objects.all()` in views that display paginated data** without `.paginator` or slicing — loads entire table:
   ```python
   # BAD: loads all 100,000 rows
   users = User.objects.all()
   return render(request, "users.html", {"users": users[:20]})

   # GOOD: paginate at DB level
   users = User.objects.all()[:20]  # or use Django Paginator
   ```

3. **`defer()` vs `only()`** — `only()` is usually clearer and correct for fetching a subset of fields.

### Agent rules

- Flag `objects.all()` querysets where only 1–3 fields are accessed — suggest `.values()` or `.only()`.
- Flag views that pass unpaginated querysets to templates or serializers.

---

## Category 3 — Missing Database Indexes

### Why it matters

Without an index, every `filter()` or `order_by()` on a non-primary-key column performs a full table scan. This scales O(n) with row count.

### What to look for

1. **`filter(field=value)` on fields without `db_index=True`** — especially on large tables:
   ```python
   # Suspicious: status is filtered frequently but has no index
   Order.objects.filter(status="pending")

   # Model field should have:
   status = models.CharField(max_length=20, db_index=True)
   ```

2. **`order_by("field")` on fields without an index** — ordering without an index forces a filesort.

3. **`filter()` on ForeignKey fields** — Django automatically creates an index for FK columns, but composite indexes may be needed for multi-field filter queries:
   ```python
   # If this is frequent, a composite index on (user_id, status) would help
   Order.objects.filter(user=user, status="pending")
   ```

4. **`unique=True` fields already have an implicit index** — no need to add `db_index=True`.

### Agent rules

- Flag `filter()` calls on CharField, IntegerField, or DateTimeField that lack `db_index=True` or `unique=True`.
- Suggest composite indexes for `filter()` calls with multiple field conditions.

---

## Category 4 — View and Serializer Inefficiency (DRF)

### Why it matters

Django REST Framework's generic views are convenient but can hide performance problems. The serializer layer is separate from the queryset — misconfiguration causes redundant queries.

### What to look for

1. **Serializers that access nested relationships without corresponding `select_related`/`prefetch_related` on the viewset queryset**:
   ```python
   class PostSerializer(serializers.ModelSerializer):
       author_name = serializers.CharField(source="author.name")  # accesses author

   class PostViewSet(viewsets.ModelViewSet):
       queryset = Post.objects.all()  # BAD: no select_related("author")
   ```

2. **`SerializerMethodField` that performs a database query inside the method** for each object:
   ```python
   class UserSerializer(serializers.ModelSerializer):
       post_count = serializers.SerializerMethodField()

       def get_post_count(self, obj):
           return Post.objects.filter(author=obj).count()  # N queries!
   ```
   Should use `.annotate(post_count=Count("post"))` on the queryset.

3. **`ListSerializer` without explicit prefetching** for nested `many=True` serializers.

### Agent rules

- Match serializer fields that traverse ForeignKey/ManyToMany with the viewset's queryset — flag missing `select_related` / `prefetch_related`.
- Flag `SerializerMethodField` methods that contain DB queries — suggest annotating the queryset instead.

---

## Category 5 — Caching

### Why it matters

Django's view caching, per-site caching, and low-level cache API can dramatically reduce DB load for read-heavy endpoints. Many Django apps do not use caching at all.

### What to look for

1. **Views that return the same data for all users** without `@cache_page`:
   ```python
   # Uncached: hits DB on every request
   def product_list(request):
       products = Product.objects.all()
       return render(request, "products.html", {"products": products})

   # GOOD: cache for 5 minutes
   @cache_page(60 * 5)
   def product_list(request):
       ...
   ```

2. **Repeated expensive calculations** (aggregate queries, third-party API calls) without low-level `cache.set()` / `cache.get()`.

3. **N+1 queries inside template tags** — Django templates can trigger queries; `{% for post in posts %}{{ post.author.name }}{% endfor %}` is the classic trap.

### Agent rules

- Flag views that perform aggregate/count queries with no cache and are not user-specific.
- Flag template tags / templatetag libraries that perform DB queries.

---

## Category 6 — Async Views (Django 4.1+)

### Why it matters

Django added async view support in Django 3.1 (limited) and full ORM async in 4.1+. For I/O-bound views (outbound API calls, external service integrations), async views allow Django to handle more concurrent requests per process.

### What to look for

1. **Sync views that call external APIs** using `requests` — these block the server process for the duration of the network call:
   ```python
   # BAD: blocks one gunicorn worker for the full API call duration
   def webhook_data(request):
       response = requests.get("https://external-api.com/data")
       return JsonResponse(response.json())

   # GOOD: async view
   async def webhook_data(request):
       async with httpx.AsyncClient() as client:
           response = await client.get("https://external-api.com/data")
       return JsonResponse(response.json())
   ```

2. **Sync ORM calls in async views** — Django raises a `SynchronousOnlyOperation` error but developers sometimes wrap with `sync_to_async`:
   ```python
   # GOOD: use async ORM methods
   async def user_detail(request, pk):
       user = await User.objects.aget(pk=pk)
       return JsonResponse({"name": user.name})
   ```

### Agent rules

- Flag sync views that call `requests.*` or `urllib.*` — suggest `httpx.AsyncClient` + async views.
- Flag `sync_to_async(lambda: queryset.all())` patterns — suggest native async ORM calls (`.aget()`, `.afilter()`, etc.).

---

## System Prompt

```
Focus areas for Django:
- N+1 queries: accessing ForeignKey attributes (post.author.name) in loops without
  select_related(); accessing ManyToMany or reverse FK in loops without prefetch_related();
  nested related field access requiring chained select_related("a__b__c").
- Over-fetching: Model.objects.all() when only 1-3 fields are needed (use .values() or
  .only()); unpaginated querysets passed to templates or serializers.
- Missing indexes: filter() on CharField/IntegerField/DateTimeField without db_index=True;
  order_by() on unindexed columns; multi-field filter patterns needing composite indexes.
- DRF: serializers that traverse FK/M2M without corresponding queryset prefetching;
  SerializerMethodField methods containing DB queries (use queryset .annotate() instead).
- Caching: user-agnostic views performing aggregate DB queries without @cache_page or
  low-level cache.set(); repeated expensive computations without caching.
- Async: sync views calling requests.get() or urllib (blocking server workers); use
  httpx.AsyncClient + async def views for outbound I/O.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| N+1 fix | Query count per request | `django-debug-toolbar` |
| .only() / .values() | Data transfer (KB) | `EXPLAIN ANALYZE` |
| Index addition | Query plan (seq scan → index scan) | `EXPLAIN ANALYZE` |
| @cache_page | DB calls per minute | Django cache stats |
| Async views | Concurrent request throughput | `locust` |
