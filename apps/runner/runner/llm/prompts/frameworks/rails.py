"""Ruby on Rails optimization focus areas."""

FOCUS = """
Focus areas for Ruby on Rails:

-- Existing patterns --
- N+1 queries (Active Record): accessing association attributes (.author.name, .tags.all,
  .comments.count) in loops without includes(:association) or eager_load; use of
  .count on has_many associations in loops (prefer counter_cache); use .size instead of
  .count when the association may already be loaded.
- Missing indexes: foreign key columns without add_index in migrations; where(column:)
  scopes on unindexed string/integer columns; polymorphic associations without composite
  index on [type, id]; order(column:) without an index (forces filesort).
- Caching: controller actions with DB queries not varying by user without Rails.cache.fetch;
  view partials rendered in loops without cached: true collection rendering; missing
  fresh_when / stale? for HTTP caching headers.
- Callbacks: deliver_now in after_create/after_save callbacks (use deliver_later);
  external HTTP calls (Faraday, HTTParty, Net::HTTP) in ActiveRecord callbacks — move
  to ActiveJob.
- Background jobs: synchronous file processing / PDF generation / CSV export in controller
  actions (offload to ActiveJob); non-idempotent job perform methods that lack
  idempotency checks before side effects.
- .count vs .size vs .length: .count always issues SELECT COUNT(*); .size is smarter
  (uses cached count if association loaded); .length loads the entire association.

-- Rule catalog (apply low-risk first) --

Rule RAILS-N1-001 — N+1 queries via Active Record association access in loops
  Anti-pattern : `posts.each { |p| puts p.author.name }` where `posts` is fetched
                 without `includes(:author)` — one query per post for the author
  Detection    : Ruby AST — method chain `obj.association_name.attribute` inside
                 a `.each`/`.map`/`.select` block where the base collection query
                 lacks `.includes(` or `.eager_load(`
  Patch (medium): Add `.includes(:author)` or `.eager_load(:author)` to the scope;
                 use `.joins(:author).select(...)` if only a few fields are needed
  Validate     : `EXPLAIN` output; Bullet gem N+1 alerts in test suite
  Rollback if  : eager-loaded association changes query ordering or adds unexpected rows
  Do NOT apply : association access is conditional and only occurs for a small subset

Rule RAILS-IDX-002 — Missing index on foreign key column
  Anti-pattern : Migration creates `t.references :user` or `add_column :user_id`
                 without a corresponding `add_index :table, :user_id`
  Detection    : file — migration files with `t.references`, `add_column :*_id`,
                 or `add_foreign_key` that are not followed by `add_index` for
                 the same column
  Patch (medium): Add `add_index :table_name, :user_id` in the migration; or use
                 `t.references :user, index: true` (default in modern Rails)
  Validate     : `EXPLAIN ANALYZE` on FK-constrained query; confirm Index Scan used
  Rollback if  : index causes write slowdown on insert-heavy table
  Do NOT apply : column already has a unique index; table is < 10k rows

Rule RAILS-CACHE-003 — Uncached collection rendering in loops
  Anti-pattern : `<%= render partial: 'item', collection: @items %>` without
                 `cached: true` when partial content does not vary per-request
  Detection    : file — ERB template with `render partial:` and `collection:` option
                 without `cached: true`; partial does not access `current_user`
                 or request-specific data
  Patch (medium): Add `cached: true` to the collection render call; ensure
                 `cache_key` on the model is meaningful (updated_at)
  Validate     : Cache hit rate in logs; response time under load
  Rollback if  : partial contains user-specific content that must not be shared
  Do NOT apply : partial renders vary per-user; items are frequently updated

Rule RAILS-CALLBACK-004 — Synchronous email or HTTP in after_create callback
  Anti-pattern : `after_create :send_welcome_email` where `send_welcome_email` calls
                 `UserMailer.welcome.deliver_now`; or after_save with an external
                 HTTP request via Faraday/HTTParty
  Detection    : Ruby AST — `after_create`/`after_save` callback method body
                 containing `deliver_now` or `Net::HTTP`/`Faraday`/`HTTParty` calls
  Patch (medium): Replace `deliver_now` with `deliver_later`; move external HTTP
                 calls to an ActiveJob `perform` method called via `.perform_later`
  Validate     : Test that callback enqueues a job (not performs inline); mock external calls
  Rollback if  : job queue is unavailable; timing of side effects is critical
  Do NOT apply : environment is a synchronous test setup using inline adapters

Rule RAILS-JOB-005 — Non-idempotent background job
  Anti-pattern : ActiveJob `perform` method that performs side effects (create record,
                 send email, charge card) without checking whether the effect has
                 already occurred
  Detection    : Ruby AST — `perform` method body with `.create!`, `deliver_now`,
                 or payment/API calls that lack a guard like
                 `return if already_processed?(job_id)`
  Patch (medium): Add an idempotency key check before performing side effects;
                 use database unique constraints or a distributed lock
  Validate     : Integration test: enqueue job twice; assert side effect runs once
  Rollback if  : idempotency check introduces locking overhead under high throughput
  Do NOT apply : job is already idempotent by nature (pure computation, no side effects)

Rule RAILS-COUNT-006 — .count called on a possibly-loaded association
  Anti-pattern : `post.comments.count` when `post.comments` may already be loaded
                 in memory (issues a SELECT COUNT(*) even when data is present)
  Detection    : Ruby AST — `.count` method call on an AR association accessor
                 inside a loop or after a scope that could have loaded the association
  Patch (low)  : Replace `.count` with `.size` — uses the cached count if loaded,
                 otherwise falls back to COUNT(*)
  Validate     : Unit tests; query log confirms no extra COUNT query when pre-loaded
  Rollback if  : `.size` triggers full load of the association when not desired
  Do NOT apply : count on a complex scope with additional conditions (must use .count)
"""
