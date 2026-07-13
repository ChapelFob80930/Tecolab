# Tecolab — Course Generation Agent

A LangGraph-based, human-in-the-loop agent that generates a full multi-module course from a single natural-language request. The agent produces a course outline, pauses for your approval or edits, then generates each module one at a time — pausing after every module so you can approve, request changes, or move on — and finally assembles and persists the completed course.

Branch: `backend_agent_maybe_final`

---

## How it works

The agent is a LangGraph `StateGraph` with two human-in-the-loop interrupt points:

1. **Outline generation** — the agent parses your request and produces a full course outline (title, modules, prerequisites, estimated time, etc.) as structured JSON, then pauses.
2. **Outline review** — you either approve it or ask for changes ("add a module on X", "remove Y"). The agent re-generates the outline against your edit request and pauses again, looping until you approve.
3. **Module generation** — once approved, the agent expands each module in the outline into full lesson content (explanations, code examples, real-world applications, exercises, resource links), one module at a time, pausing after each one.
4. **Module review** — for each module, you approve (moves to the next module) or reject with feedback (the agent revises *that specific module's generated content*, not the outline stub, and pauses again).
5. **Completion** — once every module has been approved, the agent joins all module content into the final course, persists it (and its embeddings) to the database, and returns a completion signal along with a `course_id` you can use to fetch the finished course.

State persists across all of this via a custom Postgres-backed LangGraph checkpointer, so you can start a course, come back later, and resume exactly where you left off using the `thread_id`.

---

## API Endpoints

All endpoints require a valid admin JWT (`Authorization: Bearer <token>`).

### 1. Start a course

```
POST /course_agent/start
```

**Body:**
```json
{
  "human_request": "Create a course on DSA for interviews for beginner developers. Target audience: developers preparing for coding interviews. Estimated duration: 4 weeks. Include code examples: Yes."
}
```

**Response:**
```json
{
  "thread_id": "thread_...",
  "run_status": "user_feedback",
  "assistant_response": "{...generated course outline as JSON...}",
  "course_id": "course_..."
}
```

`run_status: "user_feedback"` means the agent is paused waiting for your review of the outline. Save `thread_id` — you'll need it for every subsequent call on this course.

---

### 2. Approve or edit the outline

```
POST /course_agent/resume
```

**Approve and move to module generation:**
```json
{
  "thread_id": "thread_...",
  "review_action": "approve",
  "user_edit_request": "This looks great, please proceed to module generation."
}
```

**Request changes to the outline:**
```json
{
  "thread_id": "thread_...",
  "review_action": "reject",
  "user_edit_request": "Add a new module on Dynamic Programming, placed immediately after the Recursion and Backtracking module. Also remove the Hash Tables and Hashing Techniques module entirely."
}
```

Be specific — reference modules that actually exist in the current outline. Vague or unresolvable instructions (e.g. referencing a module that isn't there) will be partially or silently ignored rather than erroring.

On approval, the response will contain the first module's full generated lesson content, with `run_status: "user_feedback"` again (now paused for module review).

---

### 3. Approve or edit a module

Same endpoint, same payload shape, used repeatedly — once per module:

**Approve and move to the next module:**
```json
{
  "thread_id": "thread_...",
  "review_action": "approve",
  "user_edit_request": "Looks good, continue to the next module."
}
```

**Request a revision to the current module:**
```json
{
  "thread_id": "thread_...",
  "review_action": "reject",
  "user_edit_request": "Add a section comparing linear search and binary search performance with a benchmark code example."
}
```

Repeat this call once per module until every module in the outline has been approved.

---

### 4. Check status

```
GET /course_agent/status/{thread_id}
```

Returns the current `run_status` (`"user_feedback"` or `"finished"`) for a thread without advancing the graph — useful for polling.

---

### 5. Get the finished course

```
GET /course_agent/result/{course_id}
```

Once the final module has been approved and `run_status` returns `"finished"`, use the `course_id` (returned on every `/start` and `/resume` response) to fetch the assembled course:

**Response:**
```json
{
  "user_id": "user_...",
  "course_id": "course_...",
  "final_course": "# Module: Introduction to Data Structures and Algorithms\n\n...",
  "final_course_outline": "{...final approved outline JSON...}"
}
```

This endpoint only returns courses belonging to the authenticated user — you cannot fetch another user's course by guessing its `course_id`.

---

## Full demo walkthrough

A complete run against a fresh course looks like this:

1. `POST /course_agent/start` → get `thread_id` and `course_id`, review the generated outline.
2. `POST /course_agent/resume` (`review_action: "approve"`) → outline confirmed, module 1 generated.
3. `POST /course_agent/resume` (`review_action: "approve"` or `"reject"` with feedback) → repeat once per module until all modules are approved.
4. Final `POST /course_agent/resume` call returns `run_status: "finished"` and `assistant_response: "All modules generated!"`.
5. `GET /course_agent/result/{course_id}` → retrieve the full assembled course.

---

## Environment Variables

Create a `.env` file in the project root with the following:

```env
# Primary (Neon) database — users, projects, auth
database_hostname=
database_port=
database_password=
database_name=
database_username=

# Auth
secret_key=
algorithm=
access_token_expire_minutes=
trusted_admin_emails=admin@gmail.com

# Pinecone (project recommendation search)
pinecone_api_key=
pinecone_dense_index_host=
index_name=
namespace_name=

# OpenAI (course generation LLM + embeddings)
openai_api_key=

# Supabase (agent checkpoints + agent memory)
supabase_database_username=
supabase_database_password=
supabase_database_hostname=
supabase_database_port=
supabase_database_name=
```

**Notes:**
- `trusted_admin_emails` should be set to `admin@gmail.com` for local/demo testing — only emails in this list can access the `/course_agent/*` endpoints (all gated behind `oauth2.admin_only`).
- The project uses **two separate Postgres databases**: Neon (`database_*` variables) for users/auth/projects, and Supabase (`supabase_database_*` variables) for LangGraph checkpoints and `agent_memory`. Each has its own Alembic migration environment (`alembic_migrations/` for Neon, `alembic_migrations_supabase/` for Supabase) — don't run migrations against the wrong one.
- If your database password contains special characters (`@`, `%`, etc.), make sure they're handled correctly wherever the connection string is built — unescaped `%` characters will break Alembic's `configparser`-based config loading.

---

## Database setup

Two Supabase-side tables are required beyond what your standard app migrations create:

- **`checkpoints`** / **`checkpoint_writes`** — created automatically by `SupabaseCheckpointSaver.setup()` on startup; back LangGraph's thread state persistence.
- **`agent_memory`** — stores the final course, outline, and their embeddings per user/course, with a unique constraint on `(user_id, course_id)`. Requires the Postgres `vector` extension:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
  Created via the Supabase Alembic environment:
  ```bash
  alembic -c alembic_supabase.ini upgrade head
  ```

---

## Getting a JWT for testing

All `/course_agent/*` endpoints require an admin-authenticated JWT (checked via `oauth2.admin_only`, based on the user's `role`).

**1. Register a user** whose email is either `admin@gmail.com` (matches `trusted_admin_emails`) or ends in `@tecolab.in` (auto-promoted to admin regardless of the allowlist):

```
POST /users/
```
```json
{
  "email": "admin@gmail.com",
  "first_name": "Admin",
  "last_name": "User",
  "password": "yourpassword123"
}
```

**2. Log in** — note this endpoint expects **form-encoded data** (`OAuth2PasswordRequestForm`), not JSON. In Postman, use the `x-www-form-urlencoded` body type with `username` and `password` fields (the form's `username` field maps to the user's email):

```
POST /login
```
Form body:
```
username=admin@gmail.com
password=yourpassword123
```

**Response:**
```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

**3. Use the token** on every `/course_agent/*` request:
```
Authorization: Bearer <access_token>
```

Note: the admin allowlist is read via `os.getenv("TRUSTED_ADMIN_EMAILS", ...)` rather than through the shared `settings` object used elsewhere in the codebase — a minor inconsistency worth tidying up eventually, but confirmed working as-is.

---

## Known Limitations & Things to Keep in Mind

While the platform is fully functional, there are a few behaviors worth being aware of:

- **Outline edits may not always apply exactly as requested.** If an edit refers to a module or section that doesn't exist in the current outline (for example, asking to insert content before a section that isn't present), the system may only apply the parts it can resolve. In some cases, no changes may be made and no error message will be shown. It's a good idea to review the updated outline after making edits to confirm the requested changes were applied.

- **Module editing is designed to follow the generation flow.** Editing works best for the most recently generated module. Revisiting and modifying older modules after moving ahead in the course creation process is not currently supported and may produce unexpected results.

- **No request throttling is currently in place.** Starting or resuming course generation triggers AI processing each time. Repeatedly sending start or resume requests in quick succession may result in unnecessary processing and increased resource usage.

- **The system uses two separate databases.** User accounts and authentication data are stored separately from course generation memory and agent state. If you're making database or schema changes, ensure they are applied to the correct environment. Migration files should always be reviewed before being executed.

- **A Course ID is assigned and returned throughout the generation process.** The presence of a Course ID does not indicate that course generation is complete. Always check the current run status to determine whether generation is still in progress or has finished.

- **Course results are tied to the account that created them.** A course can only be viewed by the user who generated it. If you're testing with multiple accounts, results will not be shared across users.
