# Spartan Study Hub — Normalization Through BCNF

## Sources and scope

This analysis uses the finalized [DBML ER schema](../er_diagram/SpartanHub_ER_Diagram.dbml) and [relational schema](../relational_schema/SpartanHub_Relational_Schema.md). It evaluates the existing 10 relations without changing their columns, keys, or relationships.

Normalization depends on business rules as well as declared constraints. The functional dependencies below follow from the declared keys and the intended meaning of each relation. Additional dependencies are not inferred merely because two columns currently have matching values. The BCNF conclusions are relative to this stated dependency set; any additional business rules would need to be checked separately.

## Notation and criteria

A functional dependency (FD), `X → Y`, means that equal values of `X` require equal values of `Y` in every valid instance of the relation. A **candidate key** is a minimal set of attributes that determines the entire row; a **superkey** may contain additional attributes.

- **1NF:** Each column holds one value from its domain, with no repeating groups or lists of separate facts in a cell.
- **2NF:** The relation is in 1NF, and every non-prime attribute depends on each whole candidate key, with no dependency on a proper subset of a key. A prime attribute belongs to a candidate key.
- **3NF:** The relation is in 2NF, and for each nontrivial FD `X → A`, either `X` is a superkey or `A` is prime.
- **BCNF:** For every nontrivial FD `X → Y`, `X` must be a superkey. A nontrivial FD determines at least one attribute outside its determinant.

The FD lists give the important dependencies; trivial dependencies and dependencies implied by them are omitted. The alternate keys `email`, `department_code`, and `course_code` are all declared both UNIQUE and NOT NULL in the DBML. Foreign keys enforce references between relations; they do not automatically make the referencing columns determinants of other columns in the same relation.

## 1. User

**Primary key:** `(user_id)`.  
**Candidate keys:** `(user_id)`, `(email)`.

**Important functional dependencies:**

- `user_id → first_name, last_name, email, password_hash, role, created_at`
- `email → user_id`, which also makes `email` determine every other attribute.

**1NF:** Each row represents one user. Names, email, password hash, role, and creation timestamp each occupy a single column value.

**2NF:** Both candidate keys contain one attribute, so no non-prime attribute can depend on only part of a candidate key.

**3NF:** The stated determinants, `user_id` and `email`, are candidate keys. No dependency such as `role → password_hash` is part of the design.

**BCNF:** Yes, under the stated dependencies. Every nontrivial determinant is a superkey. **No further decomposition is required.**

## 2. Department

**Primary key:** `(department_id)`.  
**Candidate keys:** `(department_id)`, `(department_code)`.

**Important functional dependencies:**

- `department_id → department_name, department_code`
- `department_code → department_id`, which also determines `department_name`.

**1NF:** A row stores one department with one identifier, name, and code.

**2NF:** Both candidate keys are single attributes; there is no partial-key dependency.

**3NF:** All stated nontrivial determinants are candidate keys. The schema does not declare `department_name` unique, so it is not assumed to be a candidate key.

**BCNF:** Yes, under the stated dependencies. Both determinants are superkeys. **No further decomposition is required.**

## 3. Course

**Primary key:** `(course_id)`.  
**Candidate keys:** `(course_id)`, `(course_code)`.

**Important functional dependencies:**

- `course_id → department_id, course_code, course_title, description`
- `course_code → course_id`, which also determines the remaining attributes.

**1NF:** Each course has a single department reference, course code, title, and optional description. The description is one text value.

**2NF:** Both candidate keys are single attributes, so there are no partial-key dependencies.

**3NF:** The stated determinants are candidate keys. Department details are stored in `Department`; the `department_id` reference does not determine a course title or description within `Course`, because one department can offer many courses.

**BCNF:** Yes, under the stated dependencies. Each determinant is a superkey. **No further decomposition is required.**

## 4. Enrollment

**Primary key and only candidate key under the stated dependencies:** `(user_id, course_id)`.

**Important functional dependency:**

- `(user_id, course_id) → enrollment_date`

**1NF:** Each row represents one user's enrollment in one course, with a single enrollment date. A user's courses are represented by separate rows.

**2NF:** The enrollment date describes the specific user–course pair. Neither `user_id → enrollment_date` nor `course_id → enrollment_date` is assumed: a user may enroll in different courses on different dates, and different users may enroll in the same course on different dates. The date therefore depends on the whole composite key.

**3NF:** The only non-key attribute is `enrollment_date`; there is no non-key-to-non-key dependency. User and course details remain in their own relations.

**BCNF:** Yes, under the stated dependencies. The determinant `(user_id, course_id)` is the complete candidate key. Neither component alone identifies an enrollment. **No further decomposition is required.**

## 5. StudyGroup

**Primary key and only candidate key under the stated dependencies:** `(group_id)`.

**Important functional dependency:**

- `group_id → course_id, created_by, group_name, description, member_limit, created_at`

**1NF:** Each row stores one group, one course reference, one creator reference, and single-valued group details. Group members are represented separately in `GroupMember`.

**2NF:** The candidate key is a single attribute, so partial-key dependencies do not arise.

**3NF:** No additional dependency among non-key attributes is specified. A course can have multiple groups, and a user can create multiple groups. Neither `course_id` nor `created_by` determines the group details.

**BCNF:** Yes, under the stated dependencies. The determinant is the candidate key `group_id`. A group name is not declared unique. **No further decomposition is required.**

## 6. GroupMember

**Primary key and only candidate key under the stated dependencies:** `(group_id, user_id)`.

**Important functional dependency:**

- `(group_id, user_id) → join_date, member_role`

**1NF:** Each row represents one user's membership in one group, with one join date and one membership role.

**2NF:** Both non-key attributes depend on the whole membership pair. A user may join different groups on different dates and hold different roles in them. A group may contain members with different join dates and roles. Thus neither `user_id` nor `group_id` alone determines `join_date` or `member_role`.

**3NF:** No dependency between `join_date` and `member_role` is specified. The `member_role` describes a role within a particular group; `User.role` describes the user's application role. No equality or derivation between these two roles is assumed.

**BCNF:** Yes, under the stated dependencies. The only stated nontrivial determinant is the complete composite candidate key. **No further decomposition is required.**

## 7. StudySession

**Primary key and only candidate key under the stated dependencies:** `(session_id)`.

**Important functional dependency:**

- `session_id → group_id, created_by, session_date, start_time, location, topic, description`

**1NF:** Each row records one session with one group, creator, date, start time, location, topic, and optional description.

**2NF:** The candidate key has one attribute, so there are no partial-key dependencies.

**3NF:** No non-key determinant is specified. A group can have multiple sessions, and the schema does not require all sessions in a group to have the same creator, date, time, or location.

**BCNF:** Yes, under the stated dependencies. The determinant `session_id` is a candidate key. A combination such as `(group_id, session_date, start_time)` is not declared unique and is not assumed to be another key. **No further decomposition is required.** A possible additional business rule is discussed below.

## 8. Resource

**Primary key and only candidate key under the stated dependencies:** `(resource_id)`.

**Important functional dependency:**

- `resource_id → course_id, uploaded_by, title, description, resource_type, resource_url, created_at`

**1NF:** Each row stores one resource with single-valued metadata and one resource URL.

**2NF:** The candidate key is a single attribute; partial-key dependencies do not arise.

**3NF:** No non-key-to-non-key dependency is specified. A course or uploader can be associated with many resources. The schema does not declare a URL unique or require it to determine the title, type, or other metadata.

**BCNF:** Yes, under the stated dependencies. The determinant `resource_id` is a candidate key. **No further decomposition is required.**

## 9. Message

**Primary key and only candidate key under the stated dependencies:** `(message_id)`.

**Important functional dependency:**

- `message_id → group_id, sender_id, message_text, sent_at`

**1NF:** A row represents one message with one group, sender, text value, and sending timestamp.

**2NF:** The candidate key has one attribute, so no partial-key dependency exists.

**3NF:** No additional dependency among non-key attributes is specified. A group can contain many messages, a user can send many messages, and a timestamp is not assumed to identify a message uniquely.

**BCNF:** Yes, under the stated dependencies. The determinant `message_id` is a candidate key. **No further decomposition is required.**

## 10. Notification

**Primary key and only candidate key under the stated dependencies:** `(notification_id)`.

**Important functional dependency:**

- `notification_id → user_id, notification_type, notification_text, is_read, created_at`

**1NF:** A row represents one notification for one user, with one type, text value, read-status value, and creation timestamp.

**2NF:** The candidate key is a single attribute, so partial-key dependencies do not arise.

**3NF:** No non-key-to-non-key dependency is specified. A user can receive many notifications. A notification type may have different text in different notifications; the schema does not define `notification_type → notification_text`.

**BCNF:** Yes, under the stated dependencies. The determinant `notification_id` is a candidate key. **No further decomposition is required.** A possible additional business rule is discussed below.

## Conditional issues to check against business rules

No BCNF violation is established by the two finalized source files. The following are conditional examples of rules that would change the analysis; they are not assumed requirements or schema changes.

- **Session creators:** If every session must be created by its group's original creator, then `group_id → created_by` would hold within `StudySession`. Since `group_id` can identify many sessions and is not a superkey, this would violate BCNF and 3NF. The creator would be derivable through `StudyGroup`, so storing it again would require a design review. The existing schema permits a session creator to differ from the group's creator.
- **Membership roles:** If `GroupMember.member_role` were required to copy a user's single application-wide role, then `user_id → member_role` would hold within `GroupMember`. This would be a partial dependency on the composite key, violating 2NF, 3NF, and BCNF. The present analysis treats membership roles as specific to each user–group pair.
- **Notification templates:** If each notification type always had exactly one fixed text, then `notification_type → notification_text` would hold within `Notification`. The type is not a superkey, so this would violate BCNF and 3NF and suggest separating type-level template text from individual notifications. Personalized notification text does not imply this dependency.

## Normalization result

Under the stated functional dependencies, all 10 relations satisfy 1NF, 2NF, 3NF, and BCNF. The two composite-key relations, `Enrollment` and `GroupMember`, store facts that depend on their complete keys. **No further decomposition is required under the documented design.** Any additional business rule that introduces a non-superkey determinant should be reviewed before implementation.
