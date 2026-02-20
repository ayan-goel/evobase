# Agent Optimization Strategy — Ruby on Rails

Rails is a convention-over-configuration MVC framework for Ruby. Like Django, the dominant performance issue is the ORM (Active Record) — N+1 queries, missing indexes, and over-fetching. Rails also has a rich caching infrastructure (Russian Doll caching, low-level cache, HTTP caching) that is frequently underutilized.

---

## Detection

| Signal | Confidence |
|---|---|
| `rails` gem in `Gemfile` | 0.95 |
| `config/application.rb` exists | 0.9 |
| `app/models/application_record.rb` | confirms Rails 5+ |
| `rails-api` or `grape` gem | Rails API mode |

Package manager: `bundle install`. Test: `bundle exec rspec` or `bundle exec rails test`.

---

## Category 1 — N+1 Queries (Active Record)

### Why it matters

Active Record's lazy loading means every relationship access that wasn't preloaded triggers a new SQL query. This is the most common and damaging Rails performance problem.

### What to look for

1. **`.each` / `.map` over a collection that accesses an association**:
   ```ruby
   # BAD: N+1 — 1 query for posts, N queries for authors
   posts = Post.all
   posts.each { |post| puts post.author.name }

   # GOOD: eager load
   posts = Post.includes(:author).all
   posts.each { |post| puts post.author.name }
   ```

2. **`has_many` relationships accessed in loops** — same issue for `has_many` / `has_many :through`:
   ```ruby
   # BAD: 1 + N queries
   users = User.all
   users.each { |user| puts user.posts.count }

   # GOOD: use counter_cache or joins + select
   users = User.select("users.*, COUNT(posts.id) as posts_count")
               .left_joins(:posts)
               .group("users.id")
   ```

3. **`includes` vs `joins` vs `eager_load`**:
   - `includes` → 2 queries (preferred for in-memory access)
   - `eager_load` → 1 LEFT JOIN (use when filtering on the association)
   - `joins` → INNER JOIN, no loading (use when you only need to filter)
   - `preload` → always 2 queries regardless of conditions

4. **The Bullet gem** can detect N+1 queries automatically in development — flag if it's not present in the Gemfile.

### Agent rules

- Flag association attribute access inside `.each`, `.map`, `.select` blocks on an ActiveRecord collection.
- Suggest `includes(:association)` for has_many/belongs_to accessed after the collection is loaded.

---

## Category 2 — Missing Database Indexes

### Why it matters

Active Record migrations create models without indexes by default. Foreign keys, polymorphic type/id columns, and frequently filtered columns must be indexed explicitly.

### What to look for

1. **Foreign key columns without an `add_index`** in migrations:
   ```ruby
   # BAD: user_id has no index
   create_table :posts do |t|
     t.integer :user_id
     t.string :title
   end

   # GOOD
   create_table :posts do |t|
     t.references :user, null: false, foreign_key: true  # auto-adds index
   end
   # or explicitly:
   add_index :posts, :user_id
   ```

2. **`where(column: value)` in scopes or controller methods** on columns without an index — especially `status`, `published_at`, `deleted_at`.

3. **Polymorphic columns** (`type`, `id`) without a composite index:
   ```ruby
   # Polymorphic association needs composite index
   add_index :comments, [:commentable_type, :commentable_id]
   ```

4. **`order(:column)` without an index** forces a filesort.

### Agent rules

- Flag `where(column: ...)` calls on columns that aren't the primary key or don't appear in a migration's `add_index` call.
- Flag polymorphic associations without a composite index on `[type_col, id_col]`.

---

## Category 3 — Caching Strategies

### Why it matters

Rails ships with a robust caching stack (Redis/Memcached backends, Russian Doll fragment caching, low-level `Rails.cache`). Most Rails apps under-utilize it.

### What to look for

1. **Controller actions that query the same data for all users** without `caches_action` or `Rails.cache.fetch`:
   ```ruby
   # BAD: hits DB on every request
   def index
     @categories = Category.all.to_a
   end

   # GOOD
   def index
     @categories = Rails.cache.fetch("categories", expires_in: 1.hour) do
       Category.all.to_a
     end
   end
   ```

2. **View partials rendered in loops** without `cache` blocks (Russian Doll caching):
   ```erb
   <%# BAD: renders each post without cache %>
   <% @posts.each do |post| %>
     <%= render "post", post: post %>
   <% end %>

   <%# GOOD: each post partial is individually cached %>
   <% @posts.each do |post| %>
     <% cache post do %>
       <%= render "post", post: post %>
     <% end %>
   <% end %>

   <%# EVEN BETTER: collection caching %>
   <%= render partial: "post", collection: @posts, cached: true %>
   ```

3. **HTTP caching: missing `stale?` / `fresh_when` in controller actions** — allows browsers and CDNs to use cached responses:
   ```ruby
   def show
     @post = Post.find(params[:id])
     fresh_when(@post)  # returns 304 if post hasn't changed
   end
   ```

### Agent rules

- Flag controller actions with DB queries that don't vary by user and have no `Rails.cache` usage.
- Flag `.each do |item| render partial: ...` without `cached: true` in the `render` call.

---

## Category 4 — Counter Caches

### Why it matters

`Model.count` on an association triggers a `SELECT COUNT(*)` query. A counter cache stores the count as a column on the parent record, making it an O(1) read instead of O(n).

### What to look for

1. **`post.comments.count` or `user.posts.count`** called in views or serializers, especially in loops:
   ```ruby
   # BAD: SELECT COUNT(*) per user
   users.each { |user| puts user.posts.count }

   # GOOD: add counter_cache to the association
   class Post < ApplicationRecord
     belongs_to :user, counter_cache: true
   end
   # Then: user.posts_count is a fast column read
   ```

2. **`association.size` vs `association.count`**:
   - `.count` always hits the DB
   - `.size` uses the cached count if the association is already loaded, otherwise hits DB
   - `.length` always loads the entire association into memory

### Agent rules

- Flag `.count` on `has_many` associations in views or serializers when called repeatedly.
- Distinguish between `.count`, `.size`, `.length` and suggest the appropriate one.

---

## Category 5 — Callbacks and Observers

### Why it matters

Rails callbacks (`before_save`, `after_create`, etc.) run synchronously in the request-response cycle. Heavy callbacks (email sending, external API calls, file processing) block the response.

### What to look for

1. **Email delivery in `after_create` callbacks**:
   ```ruby
   # BAD: blocks the response, fails silently if mailer errors
   after_create :send_welcome_email

   def send_welcome_email
     UserMailer.welcome(self).deliver_now  # synchronous!
   end

   # GOOD: deliver_later uses ActiveJob + a background queue
   def send_welcome_email
     UserMailer.welcome(self).deliver_later
   end
   ```

2. **External API calls in callbacks** — webhooks, analytics events, push notifications.

3. **Heavy file processing** (image resizing, PDF generation) in `after_save`.

### Agent rules

- Flag `deliver_now` in `after_*` callbacks — suggest `deliver_later`.
- Flag external HTTP calls (`Net::HTTP`, `Faraday`, `HTTParty`) in ActiveRecord callbacks.

---

## Category 6 — Background Jobs (ActiveJob / Sidekiq)

### Why it matters

Rails applications often process long-running work synchronously when they should offload to a background queue.

### What to look for

1. **Controller actions that perform file processing, PDF generation, or CSV exports** inline and make the user wait.

2. **`ActiveJob` jobs that are not idempotent** — if a job fails and is retried, duplicate side effects occur (double emails, double charges).

3. **N+1 queries inside background jobs** — same Active Record patterns but often missed because they're not in request logs.

### Agent rules

- Flag controller actions > 2 seconds of estimated processing time that don't use `ActiveJob`.
- Flag ActiveJob `perform` methods that call external APIs or perform DB writes without idempotency checks.

---

## System Prompt

```
Focus areas for Ruby on Rails:
- N+1 queries (Active Record): accessing association attributes (.author.name, .tags.all,
  .comments.count) in loops without includes(:association) or eager_load; use of
  .count on has_many associations in loops (prefer counter_cache).
- Missing indexes: foreign key columns without add_index; where(column:) scopes on
  unindexed string/integer columns; polymorphic associations without composite index
  on [type, id]; order(column:) without an index.
- Caching: controller actions with DB queries not varying by user without Rails.cache.
  fetch; view partials rendered in loops without cached: true collection rendering;
  missing fresh_when / stale? for HTTP caching.
- Callbacks: deliver_now in after_create/after_save callbacks (use deliver_later);
  external HTTP calls (Faraday, HTTParty) in ActiveRecord callbacks.
- Background jobs: synchronous file processing / PDF generation in controller actions
  (offload to ActiveJob); non-idempotent job perform methods.
- .count vs .size vs .length: .count always hits DB; .size is smarter; .length loads
  the entire association.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| N+1 fix | Query count per request | `bullet` gem / `rack-mini-profiler` |
| Index addition | Query plan | `EXPLAIN ANALYZE` |
| Counter cache | DB query eliminated | Application logs |
| Fragment caching | Cache hit rate | `Rails.cache.stats` |
| deliver_later | Request response time | Application logs |
| Background jobs | Job throughput | Sidekiq Web UI |
