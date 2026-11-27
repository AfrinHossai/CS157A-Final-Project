# Spartan Study Hub: backend implementation plan

## Scope and decisions

Build a Flask JSON API and MySQL database for the agreed 14-relation BCNF schema in `docs/relational_schema/`. This plan specifies future implementation; it does not claim that the database, routes or tests have already been built or passed. Inspect the repository before moving existing files and keep one canonical schema document.

- **Account type:** registered student. Permissions come from membership, derived group leadership and ownership of content.
- **Schema:** retain all 14 relations and 59 physical columns from the canonical schema. Do not add account-role flags or an `auth_version` column.
- **Catalog:** Department and Course are seeded and maintained through the database setup/maintenance workflow. The application exposes read-only catalog endpoints and has no catalog-write privileges.
- **API:** JSON REST under `/api/v1`; a same-origin HTML/CSS/JS and Bootstrap front end calls it with `fetch()`.
- **Database access:** parameterized SQL in repositories. Public lifecycle procedures own their transactions; internal helpers participate in the caller's transaction.
- **Permissions:** only the current leader edits or deletes a group; session creators manage their own sessions; message senders and resource uploaders manage their own content. Joining or creating a group does not require saving its course to a profile.

The companion [ARCHITECTURE.md](ARCHITECTURE.md) contains the data model, layering and lifecycle sequences.

## 1. Target repository layout

```text
compose.yaml                    # MySQL 8.4, healthcheck, persistent volume, ordered initialization
.env.example                    # DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT,
                                # MYSQL_ROOT_PASSWORD, SECRET_KEY, DB_POOL_SIZE
database/
  00_accounts.sh                # safely provision app and routine-definer DB identities
  01_schema.sql                 # 14 tables, keys, checks, indexes, GroupLeader view
  02_procedures.sql             # public procedures and private _in_tx helpers
  03_grants.sql                 # explicit table/column grants and per-routine EXECUTE grants
  04_sample_data.sql            # student accounts and catalog; valid lifecycle seed data
  queries.sql                   # demonstration queries and execution-plan checks
backend/
  wsgi.py                       # app = create_app()
  app/
    __init__.py                 # configuration, pool, blueprints, JSON error handlers
    config.py                   # development/test/production configuration
    db.py                       # pool checkout, transaction(), call_proc(), cleanup/retries
    errors.py                   # custom and ordinary database error mapping
    auth.py                     # login_required, credential tags, ownership helpers
    csrf.py                     # session-bound CSRF token issue/validation
    validation.py               # field allowlists, lengths, enums, dates and URLs
    repositories/               # users, courses, groups, sessions, resources,
                                # messages and notifications; parameterized SQL
    routes/                     # thin Flask blueprints
scripts/
  backup.sh
  restore.sh
tests/
  conftest.py                   # isolated MySQL test database and API fixtures
  test_auth.py
  test_groups.py
  test_sessions.py
  test_messages.py
  test_notifications.py
  test_grants.py
  test_concurrency.py
docs/
  IMPLEMENTATION_PLAN.md
  ARCHITECTURE.md
  API.md
  relational_schema/            # canonical schema README and ER source
```

Keep credentials out of committed SQL and logs. The initialization wrapper provisions accounts with properly encoded values from the environment; MySQL does not interpolate environment variables inside `.sql` files. Do not configure Docker's automatically privileged `MYSQL_USER` as the application account. `ssh_app` is created explicitly with the permissions below. A dedicated locked database definer, `ssh_definer`, is provisioned before its procedures are created; it is a technical execution identity, not an application user.

Initialization runs in filename order on a fresh volume. Existing volumes require an explicit, reviewed migration/setup command; restarting a container does not reapply initialization scripts. Use a database healthcheck before starting the API.

## 2. Physical database

### 2.1 Schema and domains

Use MySQL 8.4, InnoDB and `utf8mb4`. Preserve the canonical table/column names, including consistently quoting `User` in SQL. Use matching `BIGINT UNSIGNED` types on each referenced and referencing ID.

Only independent single-column IDs are generated. The composite keys in UserCourse and SessionParticipation copy parent IDs. GroupNotification, MessageNotification and SessionNotification reuse Notification.notification_id; they do not generate independent IDs.

All fields are required except Notification.read_at. Datetimes use `DATETIME(6)`, with the connection time zone set to UTC. Creation, joining, sending and response timestamps are database/backend-assigned. `joined_at` cannot be updated through application operations.

Enforce:

- Unique User.email, Department.department_code and Course.course_code.
- GroupMember UNIQUE(group_id, user_id).
- StudySession.ends_at > starts_at.
- RSVP values: going, tentative, declined.
- Resource types: notes, link, guide, practice_material.
- Exactly the foreign keys and deletion actions listed in the canonical schema, including StudySession(group_id, created_by) referencing GroupMember(group_id, user_id).

Normalize email with trimming and lowercasing at the write/lookup boundary, and normalize catalog codes consistently in the seed/maintenance workflow. Use one documented case-insensitive comparison policy for email lookup. If canonical lowercase storage is also enforced with a CHECK, compare using binary/case-sensitive semantics: equality under a case-insensitive collation does not prove that the stored text is lowercase.

### 2.2 Indexes and searches

Use the canonical README's baseline indexes; the following list is explicit so implementation does not silently substitute a different access pattern. Every primary key already has its index. Do not create duplicate ordinary indexes on the same key.

| Relation | Additional baseline indexes |
|---|---|
| User | UNIQUE(email) |
| Department | UNIQUE(department_code) |
| Course | UNIQUE(course_code); (department_id, title, course_id); FULLTEXT(title, description) |
| UserCourse | (course_id, user_id) |
| StudyGroup | (course_id, created_at, group_id) |
| GroupMember | UNIQUE(group_id, user_id); (user_id, group_id); (group_id, joined_at, membership_id) |
| StudySession | (group_id, starts_at, session_id); (group_id, created_by, session_id) |
| SessionParticipation | (user_id, session_id) |
| Resource | (course_id, created_at, resource_id); (uploaded_by, created_at, resource_id); FULLTEXT(title, description) |
| Message | (group_id, sent_at, message_id); (sender_id) |
| Notification | (recipient_id, created_at, notification_id); (recipient_id, read_at, created_at, notification_id) |
| GroupNotification | (group_id) |
| MessageNotification | (message_id) |
| SessionNotification | (session_id) |

The session creator's composite foreign key requires an index beginning with `(group_id, created_by)`; an index on `created_by` alone is not a replacement. Keep both notification feed indexes: the unread index does not provide creation-time ordering across both read and unread rows. Keep the course-wide chronological Resource index even if a type-filtered index is later added.

The optional indexes remain `(course_id, resource_type, created_at, resource_id)` on Resource and `(session_id, rsvp_status, user_id)` on SessionParticipation, added only after measurement.

Course-code exact/prefix searches use the unique course-code index. Word-based course and resource search uses the listed FULLTEXT columns. If the UI supports short terms or substring matching, document and bound that fallback; FULLTEXT token rules do not promise arbitrary substring matching. Escape wildcard characters when a prefix/fallback is intended to treat user input literally. Apply pagination and record representative execution plans.

### 2.3 Derived leader

GroupLeader is a view, not a fifteenth table. Within each group, order current GroupMember rows by `(joined_at, membership_id)` and choose the first row. The creator is inserted as the first member during group creation. Rejoining creates a new membership and resets seniority.

Use this view for display. For protected changes, take the group lock first and read the current first membership with a locking/current read. Do not authorize from a cached leader value or an earlier transaction snapshot. Deleting the current leader's membership automatically changes the derived result.

## 3. Transaction and locking contract

### 3.1 One transaction owner

Each public lifecycle procedure starts one transaction, installs an exception handler that rolls back and rethrows, and commits only after every required write succeeds. Business-rule failures use stable error codes through SIGNAL SQLSTATE '45000'.

Private helpers use an `_in_tx` suffix. They assume an active caller-owned transaction and **never issue START TRANSACTION, COMMIT or ROLLBACK**. They propagate errors to the public owner. MySQL does not provide nested transactions: starting another transaction would commit existing work.

Examples:

- `sp_post_message` owns the transaction; `_sp_notify_in_tx` inserts notifications inside it.
- `sp_leave_group` owns the transaction; `_sp_leave_group_in_tx` and `_sp_delete_group_in_tx` share it.
- `sp_delete_user` owns one transaction for the entire account deletion and calls only private cleanup helpers. It never calls an independently committing public leave/delete procedure.

`call_proc()` must run on a connection with no active transaction. Do not wrap it in Flask's direct-write `transaction()` context manager. `call_proc()` accepts only procedure names selected by repository code, not arbitrary names from requests.

### 3.2 Lock hierarchy and account deletion

Group operations serialize through the same StudyGroup row. After entering the transaction, obtain the actor's existing User row with a shared lock as an account-existence guard, then lock the StudyGroup row for update. Perform no authorization-sensitive membership/leader read before that group lock. Then obtain affected membership/content rows with current reads as needed.

This rule covers joining, leaving, updating/deleting a group, creating/updating/deleting a session, RSVPs, posting/updating/deleting messages, and group notification creation. For a session/message ID, first resolve its group without treating that lookup as authorization; lock that group and re-read the source to confirm it still exists and belongs there.

Group creation first guards the actor, inserts the group and its initial membership, then commits; another request cannot join that uncommitted group. Its create/join path never consults UserCourse as an eligibility requirement.

`sp_delete_user` instead locks its User row exclusively so concurrent writes by that actor cannot create new memberships or content during deletion. Discover every affected group, including groups containing retained messages sent before a prior departure. Lock those groups in ascending group_id order, re-read the affected records, and run private cleanup helpers. Direct UserCourse and Resource writes also guard the actor's User row within their transaction. This makes an actor write either complete before deletion or fail after the account disappears.

Foreign-key checks and notification fan-out can still produce deadlocks; lock ordering reduces them but does not guarantee their absence. On a deadlock or lock timeout, the owner rolls back the entire operation. Retry the whole operation at most twice with short jittered backoff on a fresh transaction. Do not retry an arbitrary connection failure after a possibly successful commit unless an idempotency mechanism proves that replay is safe.

### 3.3 Departure and deletion order

Under the group lock, verify the departing membership and determine whether it is the last member **before deleting it**.

- **Last member:** remove all Notification parents associated with the group through any of the three target types, then delete StudyGroup. Memberships, messages, sessions and RSVPs cascade. Commit. Do not invoke a leader-authorized public delete procedure after removing the last membership.
- **Members remain:** delete Notification parents targeting any session created by the departing member in this group; delete that recipient's own notifications for this group across all three target types; remove their RSVPs in the group; delete their GroupMember row. This deletes all of their sessions in the group, including past ones, and the affected session RSVPs. The oldest remaining membership now determines the leader. Optionally create the agreed departure GroupNotifications within this same transaction.

For an explicit source deletion, remove affected Notification parents before the source. Their subtype rows cascade from Notification. Subtype-to-source references use RESTRICT; they must not silently delete only the subtype and leave its Notification parent orphaned. Private cleanup helpers discover notification IDs through GroupNotification directly, MessageNotification joined to Message, and SessionNotification joined to StudySession. Treat these as separate branches; do not inner-join all three subtype tables together.

Ordinary departure retains the student's messages and course resources. Account deletion additionally removes all of their retained messages and resources. Course resources remain after a group is deleted.

### 3.4 Public procedures and private helpers

Actor/user parameters are supplied from the authenticated Flask user, never accepted as a browser-selected identity. Every public procedure validates the relevant ownership or membership rule itself. Private helpers are not granted directly to `ssh_app`.

| Public procedure | Contract |
|---|---|
| `sp_create_group(actor, course, name, description, OUT group_id)` | Guard the actor; create the group and first membership atomically. |
| `sp_join_group(actor, group)` | Lock and check; reject duplicate membership; add the actor and notify existing members. |
| `sp_update_group(actor, group, name, description)` | Lock, resolve the current leader, and update only if the actor is that leader. |
| `sp_leave_group(actor, group)` | Lock and delegate to the private departure helper, including the last-member branch. |
| `sp_delete_group(actor, group)` | Lock and verify the current leader, then delegate to private group cleanup. |
| `sp_create_session(actor, group, topic, starts, ends, location, OUT id)` | Verify current membership, insert, and notify other current members atomically. |
| `sp_update_session(actor, session, ...)` | Lock and verify that actor is the session creator; preserve source group/creator/ID; notify eligible responding members as appropriate. |
| `sp_delete_session(actor, session)` | Lock and verify creator ownership; delete source notifications, then the session and its RSVPs. |
| `sp_rsvp(actor, session, status)` | Lock the group, verify current membership and the session, then insert/update the actor's response and response timestamp. |
| `sp_clear_rsvp(actor, session)` | Lock, verify current membership and session existence, then remove only the actor's response. An already absent response is a successful no-op. |
| `sp_post_message(actor, group, content, OUT id)` | Lock and verify membership; insert the message and one parent/target pair for each other member. |
| `sp_update_message(actor, message, content)` | Lock the source group and verify sender ownership; change content only. |
| `sp_delete_message(actor, message)` | Lock and verify sender ownership; remove source notifications before deleting the message. |
| `sp_delete_notification(actor, notification)` | Verify recipient ownership and delete the Notification parent; its one target row cascades. A concurrent source cleanup may make it already absent. |
| `sp_delete_user(actor)` | Lock the account and all affected groups, run private leave/message cleanup, delete owned resources, then delete the account. The API first verifies the current password. All work is one transaction. |

The message sender retains ownership of an existing message after departure; editing/deleting that message does not grant access to the rest of the former group. Session creators cannot edit after departure because their sessions are deleted. The group leader has no override for another student's sessions, messages or resources.

Private helpers include `_sp_notify_in_tx`, `_sp_delete_group_notifications_in_tx`, `_sp_delete_session_notifications_in_tx`, `_sp_delete_message_notifications_in_tx`, `_sp_delete_message_in_tx`, `_sp_leave_group_in_tx` and `_sp_delete_group_in_tx`. Their names and signatures are internal implementation details and may be refined without exposing new API capabilities. Account cleanup suppresses unnecessary departure fan-out until the account operation succeeds.

`_sp_notify_in_tx` validates the target kind before inserting anything, verifies that the typed source belongs to the already locked group and the recipient is eligible, then inserts Notification plus exactly one of GroupNotification, MessageNotification or SessionNotification. No internal commit occurs. A failed subtype insert rolls back the entire public operation, including its source write and any earlier fan-out rows.

## 4. Database permissions

Use `ssh_app` for API requests from the first implementation phase onward; do not develop the routes using an unrestricted account and postpone grant testing.

| Object | Application permissions |
|---|---|
| Tables and GroupLeader view | SELECT as needed by repositories; use explicit column lists in all responses. |
| User | INSERT of name/email/password_hash; UPDATE of name/email/password_hash. No direct DELETE, primary-key mutation or other user-management capability. |
| UserCourse | INSERT of user_id/course_id and DELETE; no key-changing UPDATE or timestamp override. |
| Resource | INSERT of course_id/uploaded_by/title/description/resource_type/resource_url; UPDATE of title/description/resource_type/resource_url; DELETE. Ownership predicates are required. |
| Notification | UPDATE(read_at) only for recipient-filtered mark-read operations; no direct INSERT or DELETE. |
| StudyGroup, GroupMember, StudySession, SessionParticipation, Message, and notification targets | No direct INSERT/UPDATE/DELETE; use approved public procedures. |
| Department and Course | Read-only to the application account. |
| Public procedures in section 3.4 | Individual EXECUTE grants. |
| Private `_in_tx` helpers | No EXECUTE grant to the application account. |

These grants restrict database capabilities, not individual end-user rows. The Flask backend is trusted to bind the authenticated actor and all direct-write ownership predicates. A common database service account does not automatically know which student made a request. Use field allowlists and immutable ID/owner/group columns; never mass-assign arbitrary request properties.

The locked `ssh_definer` receives only the table/helper permissions required by the routines. The separate setup/maintenance credentials create schema objects and seed the catalog. Backup/restore uses separately authorized operator credentials rather than broadening `ssh_app`.

## 5. Flask implementation contract

- `create_app(config)` builds the pool, registers blueprints, configures cookie/request limits and installs JSON error handlers.
- Configure pooled connections with autocommit enabled for ordinary reads, UTC session time zone and a consistent connection reset policy. `get_db()` checks out one connection into `flask.g`; teardown rolls back any unexpected active transaction, closes cursors and returns the connection. Reapply required session settings on checkout.
- Direct writes use `transaction()`: reject accidental nesting, start an explicit transaction, take any required account guard, commit once on success and roll back on failure. Do not call public lifecycle procedures inside it.
- `call_proc()` rejects an active transaction, calls only a repository-selected public procedure, consumes all result sets/OUT parameters and leaves the connection in a clean state. The procedure owns commit/rollback. Retry only the explicitly rollback-safe errors described above.
- Repositories use parameterized values. Any dynamic sort/column identifiers come from fixed allowlists, not request text.
- Error payload: `{"error":{"code":"NOT_A_MEMBER","message":"..."}}`. Do not expose SQL statements, passwords, hashes or raw database error text.

| Failure | Response |
|---|---|
| Invalid input, malformed JSON, invalid enum, oversized field | 400 |
| Missing/invalid login or invalidated credential tag | 401 |
| Ownership/leadership/membership or CSRF failure | 403 |
| Missing group/session/message/notification | 404, subject to the endpoint's documented idempotency policy |
| Duplicate email/membership or deletion blocked by a foreign key | 409 |
| Invalid session interval | 422 |
| Exhausted rollback-safe deadlock/lock-timeout retries | 503 with a stable retryable error code |

Map ordinary duplicate-key, foreign-key, CHECK and length errors in addition to custom SIGNAL codes. A CHECK failure on an enum maps consistently to 400 and a session interval failure to 422. Tests should identify the actual failing constraint/error number rather than parse arbitrary localized SQL text.

Accept timezone-aware ISO 8601 input; reject missing/invalid offsets. Convert to UTC before binding to MySQL and emit UTC ISO 8601 with `Z`. Preserve microseconds where supplied. Never interpret a naive input timestamp using the server's local timezone.

List endpoints default to 20 rows with a maximum of 100. Catalog/resource lists may use bounded limit/offset. Message and notification feeds order by `(sent_at, message_id)` or `(created_at, notification_id)` respectively, descending. Their opaque `before` cursor carries that timestamp and ID; validate it and apply the matching lexicographic boundary. Do not combine timestamp ordering with an ID-only cursor. A cursor is a position, not authorization: reapply membership/recipient filters on every page.

## 6. Authentication and authorization

### 6.1 Student sessions and password changes

Use Flask's signed-cookie session with HTTPOnly and SameSite=Lax, Secure in production, a seven-day maximum lifetime with session.permanent enabled on login, and a strong environment-provided SECRET_KEY. Store only user_id, a credential tag and the CSRF nonce needed for the authenticated state. A signed cookie is readable by its holder; do not store plaintext passwords or password_hash in it.

To remove the undefined auth_version while preserving the existing schema, derive a credential tag from the existing User.password_hash. On login, compute HMAC-SHA256 keyed by SECRET_KEY over a domain-separated, unambiguous encoding of `session-credential-v1`, user_id and the current password_hash; store only its hexadecimal tag in the signed session. On every authenticated request, load the current User row and recompute/compare the tag with `hmac.compare_digest`. Reject missing users, malformed tags and mismatches with 401. This is a proposed application helper, not a database field or a built-in Flask feature.

Use the standard-library HMAC implementation; keep this domain separate from CSRF tokens and other signatures. Changing the stored password hash invalidates previously issued credential tags, including cookies from other browsers, without adding a table or column. Tests must verify that behavior. Explicit logout clears the current browser's cookie; it does not claim to revoke a copied cookie elsewhere unless the password changes or the cookie expires.

Use Werkzeug generate_password_hash/check_password_hash with an explicitly selected supported scrypt method. Normalize emails before storage and lookup. Registration accepts only name, email and password. Profile updates accept only name and email. Require at least eight password characters, validate lengths before hashing/binding, use generic login failures, and apply login throttling in deployment configuration. The password-change route verifies the current password, updates the hash in one direct-write transaction, clears the current session, and requires login again.

### 6.2 CSRF and browser behavior

CSRF protection is required for every state-changing route, including registration, login, logout, password changes and DELETE requests. GET `/auth/csrf` creates an unpredictable session-bound nonce if none exists and otherwise returns the current one to same-origin JavaScript. Send it in `X-CSRF-Token`; compare it against the value in the verified signed session using a constant-time comparison. Reject missing/mismatched tokens. Rotate the nonce when establishing a new authenticated session; return or refetch the replacement before the next write.

Use the standard secrets module for nonce generation. Keep GET/HEAD routes side-effect free except issuing authentication/CSRF state; do not perform application-data mutations through them. Require JSON where a route accepts a JSON body, verify the expected same origin for browser writes, and keep SameSite as an additional control. Do not rely on JSON content type or SameSite alone as the complete CSRF policy. Same-origin hosting is the baseline; cross-origin cookie access is outside this plan until an explicit origin allowlist and equivalent protections are specified.

### 6.3 Permission matrix

| Action | Allowed student |
|---|---|
| Browse/search catalog, group summaries and course resources | Any logged-in student |
| Save/remove a course on a profile | That student only |
| Create or join a group | Any logged-in student; saving the course is not required |
| Edit group name/description or delete group | Current derived leader only |
| Leave a group | That membership's student |
| Read a group's messages, sessions and member list | Current members only |
| Create a session or post a message | Current members only |
| Update/delete a session | Its creator only; its membership must still exist |
| Submit/change/clear an RSVP | The responding student, while a current member |
| Update/delete a message | Its sender only |
| Create a resource | Any logged-in student, for an existing course |
| Update/delete a resource | Its uploader only |
| Read/mark/delete notifications | Their recipient only |
| Change password, edit profile or delete an account | That student only; sensitive changes require current-password verification |

Flask checks authentication/CSRF and validates inputs. Procedures recheck lifecycle ownership/membership under their locks; direct repositories include the actor in ownership predicates. Front-end visibility flags are convenience only.

## 7. API routes (`/api/v1`)

All routes below require login except registration, login, CSRF bootstrap and a minimal health endpoint. Group summaries are visible to logged-in students; protected content is member-only. All state-changing routes require CSRF validation. Actor IDs come from the authenticated session.

### Auth and account

| Method | Path | Contract |
|---|---|---|
| GET | `/health` | Minimal process/database status; no configuration or credentials. |
| GET | `/auth/csrf` | Issue/read the current session-bound CSRF token. |
| POST | `/auth/register` | `{name,email,password}`; 201; establish login and rotate the CSRF nonce. |
| POST | `/auth/login` | `{email,password}`; establish login and rotate the CSRF nonce. |
| POST | `/auth/logout` | Clear the current session/cookie. |
| GET | `/auth/me` | Current public account fields or 401. |
| PATCH | `/users/me` | `{name?,email?}` only; verify current password when changing email. |
| PUT | `/users/me/password` | `{current_password,new_password}`; clear current session after success. |
| DELETE | `/users/me` | Verify current password; call `sp_delete_user`; clear session after commit. |
| GET | `/users/:id` | Logged-in access to that student's public name and saved courses only. |

The email-change route may accept a separate current_password verification field; it is never persisted as profile data. Reject unknown fields in all account payloads.

### Catalog and saved courses

| Method | Path | Contract |
|---|---|---|
| GET | `/departments` | Read-only catalog. |
| GET | `/courses?q=&department=&limit=&offset=` | Code exact/prefix lookup and documented title/description word search. |
| GET | `/courses/:id` | Course details and independently aggregated group/resource counts. |
| GET | `/users/me/courses` | Current student's saved courses. |
| PUT | `/users/me/courses/:course_id` | Idempotent save for the actor. |
| DELETE | `/users/me/courses/:course_id` | Idempotent removal; does not leave any group. |

There are no application endpoints for creating, editing or deleting departments/courses. Maintain the catalog through the authorized setup/maintenance workflow and respect existing RESTRICT relationships, including saved-course references.

### Study groups

| Method | Path | Contract |
|---|---|---|
| GET | `/groups?course_id=&q=&mine=true&limit=&offset=` | Logged-in group summaries; do not expose messages/member details here. |
| POST | `/groups` | `{course_id,name,description}` → `sp_create_group`. |
| GET | `/groups/:id` | Summary, leader, member count and actor's is_member/is_leader flags. |
| PATCH | `/groups/:id` | Leader only → `sp_update_group`. |
| DELETE | `/groups/:id` | Leader only → `sp_delete_group`. |
| GET | `/groups/:id/members` | Current members only. |
| POST | `/groups/:id/members` | Join self → `sp_join_group`; duplicate membership is 409. |
| DELETE | `/groups/:id/members/me` | Leave self → `sp_leave_group`; group may be deleted if last member. |

### Sessions and RSVPs

| Method | Path | Contract |
|---|---|---|
| GET | `/groups/:id/sessions?from=&to=&limit=&offset=` | Current members only. |
| POST | `/groups/:id/sessions` | `{topic,starts_at,ends_at,location}` → `sp_create_session`. |
| GET | `/sessions/:id` | Current members only; include RSVP counts and actor's response. |
| PATCH | `/sessions/:id` | Creator only → `sp_update_session`; immutable group and creator. |
| DELETE | `/sessions/:id` | Creator only → `sp_delete_session`. |
| PUT | `/sessions/:id/rsvp` | `{status}` → `sp_rsvp`. |
| DELETE | `/sessions/:id/rsvp` | Clear own response → `sp_clear_rsvp`. |
| GET | `/users/me/sessions?upcoming=true&limit=&offset=` | Sessions across current memberships; optionally filter by the actor's RSVP. |

### Resources

| Method | Path | Contract |
|---|---|---|
| GET | `/resources?course_id=&type=&q=&uploaded_by=&limit=&offset=` | Documented FULLTEXT search with bounded short-term fallback. |
| POST | `/resources` | `{course_id,title,description,resource_type,resource_url}`; uploader is the actor; URL must be http(s). |
| GET | `/resources/:id` | Logged-in access to course-scoped resource metadata. |
| PATCH | `/resources/:id` | Uploader only; title/description/type/URL only. |
| DELETE | `/resources/:id` | Uploader only. |

### Messages

| Method | Path | Contract |
|---|---|---|
| GET | `/groups/:id/messages?before=&limit=` | Current members only; cursor matches `(sent_at,message_id)` descending order. |
| POST | `/groups/:id/messages` | `{content}` → `sp_post_message`. |
| PATCH | `/messages/:id` | Sender only → `sp_update_message`. |
| DELETE | `/messages/:id` | Sender only → `sp_delete_message`. |

### Notifications

| Method | Path | Contract |
|---|---|---|
| GET | `/notifications?unread=true&before=&limit=` | Actor's rows only; return kind, target_id and derived group_id using separate typed branches. |
| GET | `/notifications/unread-count` | Actor's count only. |
| POST | `/notifications/:id/read` | Recipient-filtered update; fill read_at if absent. |
| POST | `/notifications/read-all` | Mark only the actor's unread rows. |
| DELETE | `/notifications/:id` | Recipient only → `sp_delete_notification`; parent deletion cascades its target. |

Notification queries combine the three target branches without requiring all of them to exist for one parent. All list/count queries preserve recipient filtering, and target/group derivation does not grant access to protected content after membership ends.

## 8. Seed data, setup, backups and front end

Seed about five departments, twenty courses and ten ordinary student accounts using development-only password hashes and clearly documented non-production credentials. Create lifecycle objects through public procedures with valid student actors. Privileged seed/setup scripts may perform catalog/account inserts, but must not bypass lifecycle invariants. Do not call public procedures from inside another seed-owned transaction.

Demonstration queries cover course search, saved courses, groups, current leader, sessions, RSVP aggregates, resources, messages and all/unread notifications. Aggregate independent one-to-many counts before joining them so group/resource counts are not multiplied accidentally.

Backups use a separately authorized operator identity, capture a consistent InnoDB snapshot plus routines, views and necessary metadata, exclude credentials from logs, and use shell pipeline failure detection so a failed dump is not reported as a valid archive. Restore and execute the routines in a test environment with the required definer identity/permissions. Check a restore rather than only checking that a file exists. Keep backup archives and secrets out of version control. Document a cron/launchd schedule as a deployment step; this document does not create a scheduled task.

The static front end is served from the same origin as Flask or behind the same-origin reverse proxy. Pages cover login/register, dashboard, course search/details, group details, sessions/RSVPs, resource search, messages, notifications and own-account settings. Bootstrap CSRF state first, then include cookies and X-CSRF-Token on writes; refresh the token after login/registration. On 401 return to login. Render user text using textContent, validate http(s) resource links, and use safe external-link attributes. Convert UTC times for display and submit timezone-aware ISO 8601. Treat permission flags as display hints only. Poll bounded unread/message endpoints for near-real-time updates; WebSockets are outside this scope.

## 9. Delivery order

1. Canonical schema and baseline indexes; account provisioning/grants; MySQL healthcheck and isolated integration database.
2. Flask factory, pool checkout/cleanup, errors, explicit transaction boundary helpers and health route.
3. Student authentication, CSRF, credential tags, own-profile and password operations.
4. Read-only catalog and own saved courses.
5. Internal lifecycle helpers, derived leader, public group procedures and concurrency tests.
6. Sessions, RSVPs and creator-only changes with notification helpers already available.
7. Resource CRUD/search, sender-only message changes and recipient-only notifications.
8. Atomic account deletion, failure injection, permission checks, backups and restore verification.
9. API reference, setup documentation and architecture diagrams aligned to this plan.

Dependencies matter: group/session/message procedures need notification helpers before their tests can pass. Use `ssh_app` in API integration tests from the beginning. A separate setup identity may create/reset the isolated database, but test requests must not inherit that identity's privileges.

## 10. Verification and acceptance

These are required future checks, not reported results.

- A fresh MySQL volume initializes all 14 tables, the view, public/private routines, grants and valid seed records. Existing-volume setup behavior is separately documented.
- Table/column types, all keys, all 21 foreign keys and their deletion actions match the canonical schema; no extra account-role/version columns are introduced.
- The UML contains the same 14 tables and marks GroupLeader as a derived view.
- End-to-end API flow: obtain CSRF token, register/login, save a course, create a group, have a second student join without saving that course, create a session, RSVP, post a message, receive/read/delete a notification, leave and delete the final group. Protected routes require the appropriate current actor.
- Nonmembers cannot read group messages/sessions/member lists. Nonleaders cannot change a group. A leader cannot edit another member's session, message or resource. Nonrecipients cannot read/mark/delete another student's notifications.
- Catalog writes and user-management endpoints are absent. Registration rejects unexpected properties. Direct SQL grants deny lifecycle table writes, direct account deletion, catalog writes and direct helper execution; message updates/group updates/notification deletion succeed through the public procedures.
- Duplicate email/membership, invalid enum/length/interval, missing references and restricted deletions produce the specified HTTP errors without exposing SQL details.
- Every Notification has exactly one target row; failure between parent/target insert rolls back both. A failure partway through message fan-out rolls back the source and every earlier notification.
- Leaving removes the actor's notifications from all three group-associated branches, deletes every owned session including past ones, deletes the actor's other RSVPs there, and preserves unrelated groups and course resources.
- Leader departure selects the next-oldest current member. Equal join timestamps have deterministic membership-ID tie breaking. Rejoining resets seniority. Last-member departure succeeds without checking leadership after the membership is gone.
- Account deletion with multiple groups, retained messages and resources is atomic. Inject a failure late in cleanup and verify that memberships, sources and notifications all remain intact after rollback. Check a new write racing with account deletion.
- Run concurrent transactions for two departures, a join versus last-member departure, RSVP versus departure, leader edit versus departure, and message fan-out versus account deletion. Check invariants and bounded whole-operation retries.
- Reused pool connections retain the required UTC/autocommit settings and no unread result sets or open transaction. A direct-write context cannot nest a public procedure call.
- Feed pagination with equal timestamps and inserted rows has no boundary duplicates/skips within its defined order. Cursor validation never substitutes for authorization.
- CSRF validation covers login/register/logout and all other writes. A password change invalidates a previously issued credential cookie in a second client. Cookies never contain the raw password or stored hash. Explicit logout has the documented current-browser scope.
- Use representative data and execution plans for catalog search, group membership/leader lookup, schedules, course-wide/type-filtered resources and both notification feeds. The two-second response goal is measured; indexes and pagination alone are not proof.
- Restore a backup into an isolated database and run schema, view and public-procedure smoke checks.

## References

- [MySQL: implicit commits and transaction nesting](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html)
- [MySQL: InnoDB locking reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html)
- [MySQL Connector/Python: autocommit](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-autocommit.html)
- [Flask security considerations](https://flask.palletsprojects.com/en/stable/web-security/)
- [Python HMAC and constant-time comparison](https://docs.python.org/3/library/hmac.html)
- [OWASP: CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
