"""Django optimization focus areas."""

FOCUS = """
Focus areas for Django:

-- Existing patterns --
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

-- Rule catalog (apply low-risk first) --

Rule DJ-N1-001 — N+1 queries via ForeignKey traversal in loops
  Anti-pattern : `for obj in qs: print(obj.related_model.field)` where `related_model`
                 is a ForeignKey/OneToOne and the queryset does not use select_related
  Detection    : Python AST — attribute access `obj.X.Y` inside a for-loop body where
                 X is an FK field name found in the model's Meta; queryset call chain
                 lacks `.select_related('X')` or `.prefetch_related('X')`
  Patch (medium): Add `.select_related('related_field')` to the queryset; use
                 `.prefetch_related` for ManyToMany or reverse FK relations
  Validate     : Django test assertNumQueries(1, lambda: list(qs)); integration tests
  Rollback if  : JOIN introduces unacceptable row multiplication; wrong data returned
  Do NOT apply : relation is already eagerly loaded; queryset is further filtered by
                 the related object (join already present)

Rule DJ-IDX-002 — Missing database index on filtered / ordered columns
  Anti-pattern : `Model.objects.filter(email=x)` or `order_by('created_at')` where
                 the field has no `db_index=True` and no migration adds an index
  Detection    : Python AST + migration files — `filter(field=` or `order_by('field'`
                 call where `field` in the model definition has no `db_index=True`
                 and no `Index` in `Meta.indexes`; exclude PKs and existing unique fields
  Patch (medium): Add `db_index=True` to the field, or add `models.Index(fields=['field'])`
                 in `Meta.indexes`; generate migration with `makemigrations`
  Validate     : `EXPLAIN ANALYZE` query; confirm Seq Scan → Index Scan
  Rollback if  : index causes write slowdown on insert-heavy table
  Do NOT apply : table is small (< 10k rows); column has very low cardinality (bool, status)

Rule DJ-PAGINATE-003 — Unpaginated queryset in API or template view
  Anti-pattern : `Model.objects.all()` or `.filter(...)` returned directly to a
                 DRF serializer or template without `.paginate_queryset` or slicing
  Detection    : Python AST — queryset result assigned/returned directly to
                 `serializer(queryset, many=True)` or passed to template context
                 without any `.paginate_queryset` call or `[:N]` slice
  Patch (medium): Add DRF `PageNumberPagination` to the view; or add explicit
                 `.order_by('id')[:PAGE_SIZE]` slicing with cursor-based pagination
  Validate     : Load test response time + memory usage for large tables
  Rollback if  : pagination changes API contract that clients rely on
  Do NOT apply : queryset is intentionally small and bounded by filter conditions

Rule DJ-DEFER-004 — Over-fetching with .all() when only a few fields are used
  Anti-pattern : `Model.objects.all()` followed by accessing only 1-3 fields on
                 each object — loads all columns unnecessarily
  Detection    : Python AST — `.objects.all()` or `.objects.filter()` result iterated;
                 only `obj.field_a` and `obj.field_b` accessed in the loop body
  Patch (low/medium): Replace with `.values('field_a', 'field_b')` for dicts,
                 `.values_list('field_a', flat=True)` for a single column,
                 or `.only('field_a', 'field_b')` to defer unused columns
  Validate     : EXPLAIN output; Django debug toolbar SQL panel
  Rollback if  : deferred field accessed later in code path (raises `SuspiciousOperation`)
  Do NOT apply : all fields are used; model has few columns

Rule DJ-CACHE-005 — Uncached aggregate queries in user-agnostic views
  Anti-pattern : View function calling `Model.objects.aggregate(...)` or
                 `.count()` / `.annotate(...)` on every request for data that
                 does not vary by user or request parameters
  Detection    : Python AST — view function body contains `.aggregate(` or
                 `.annotate(` call with no `cache.get/set` wrapper and no
                 `@cache_page` decorator; function not inside a class with
                 per-user queryset filtering
  Patch (medium): Wrap with `cache.get_or_set('key', lambda: qs.aggregate(...), TTL)`;
                 or add `@cache_page(60 * 15)` for full-page caching
  Validate     : Cache hit rate; data freshness under acceptable TTL
  Rollback if  : TTL too long causes stale aggregates visible to users
  Do NOT apply : aggregate varies by authenticated user; real-time accuracy required

Rule DJ-DRF-006 — DRF SerializerMethodField containing a DB query
  Anti-pattern : `SerializerMethodField` method that directly queries the DB:
                 `def get_count(self, obj): return obj.related_set.count()`
  Detection    : Python AST — method decorated as `get_<field>` in a Serializer
                 subclass containing `.objects.`, `.filter(`, `.count()`, or
                 attribute traversal that would trigger a DB query
  Patch (medium): Push the computation into the queryset as `.annotate(count=Count(...))`;
                 reference the annotation in the serializer field definition
  Validate     : assertNumQueries in serializer tests
  Rollback if  : annotation semantics differ from method logic (e.g. conditional logic)
  Do NOT apply : computation cannot be expressed as a DB annotation
"""
