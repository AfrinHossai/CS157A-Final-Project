# Spartan Study Hub — Relational Schema

Source: [SpartanHub_ER_Diagram.dbml](../er_diagram/SpartanHub_ER_Diagram.dbml).

This document presents the 10 relations defined in the DBML source, preserving table names, column names, column order, primary keys, foreign keys, and UNIQUE constraints.

**Notation:** `PK` denotes a primary-key column, `FK` denotes a foreign-key column, and `UNIQUE` denotes a uniqueness constraint. Multiple `PK` markings in a relation form a single composite primary key. Foreign-key targets are written as `ReferencedTable(referenced_column)`.

## 1. User

```text
User(
    user_id PK,
    first_name,
    last_name,
    email UNIQUE,
    password_hash,
    role,
    created_at
)
```

- **Primary key:** `(user_id)`.
- **Foreign keys:** None.
- **UNIQUE constraints:** `email`.

## 2. Department

```text
Department(
    department_id PK,
    department_name,
    department_code UNIQUE
)
```

- **Primary key:** `(department_id)`.
- **Foreign keys:** None.
- **UNIQUE constraints:** `department_code`.

## 3. Course

```text
Course(
    course_id PK,
    department_id FK,
    course_code UNIQUE,
    course_title,
    description
)
```

- **Primary key:** `(course_id)`.
- **Foreign keys:** `department_id` → `Department(department_id)`.
- **UNIQUE constraints:** `course_code`.

## 4. Enrollment

```text
Enrollment(
    user_id PK FK,
    course_id PK FK,
    enrollment_date
)
```

- **Primary key:** `(user_id, course_id)` (composite).
- **Foreign keys:** `user_id` → `User(user_id)`; `course_id` → `Course(course_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.

## 5. StudyGroup

```text
StudyGroup(
    group_id PK,
    course_id FK,
    created_by FK,
    group_name,
    description,
    member_limit,
    created_at
)
```

- **Primary key:** `(group_id)`.
- **Foreign keys:** `course_id` → `Course(course_id)`; `created_by` → `User(user_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.

## 6. GroupMember

```text
GroupMember(
    group_id PK FK,
    user_id PK FK,
    join_date,
    member_role
)
```

- **Primary key:** `(group_id, user_id)` (composite).
- **Foreign keys:** `group_id` → `StudyGroup(group_id)`; `user_id` → `User(user_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.

## 7. StudySession

```text
StudySession(
    session_id PK,
    group_id FK,
    created_by FK,
    session_date,
    start_time,
    location,
    topic,
    description
)
```

- **Primary key:** `(session_id)`.
- **Foreign keys:** `group_id` → `StudyGroup(group_id)`; `created_by` → `User(user_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.

## 8. Resource

```text
Resource(
    resource_id PK,
    course_id FK,
    uploaded_by FK,
    title,
    description,
    resource_type,
    resource_url,
    created_at
)
```

- **Primary key:** `(resource_id)`.
- **Foreign keys:** `course_id` → `Course(course_id)`; `uploaded_by` → `User(user_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.

## 9. Message

```text
Message(
    message_id PK,
    group_id FK,
    sender_id FK,
    message_text,
    sent_at
)
```

- **Primary key:** `(message_id)`.
- **Foreign keys:** `group_id` → `StudyGroup(group_id)`; `sender_id` → `User(user_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.

## 10. Notification

```text
Notification(
    notification_id PK,
    user_id FK,
    notification_type,
    notification_text,
    is_read,
    created_at
)
```

- **Primary key:** `(notification_id)`.
- **Foreign keys:** `user_id` → `User(user_id)`.
- **UNIQUE constraints:** None beyond primary-key uniqueness.
