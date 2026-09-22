# ReviewIQ — Database Schema

## Table: `reviews`
| Column | Type | Nullable | Purpose |
|---|---|---|---|
| id | UUID | No | Primary key |
| product_name | TEXT | No | Product identifier/display name |
| review_text | TEXT | No | Original review for traceability |
| rating | INTEGER | Yes | Validated rating from 1–5 |
| rating_source | TEXT | No | explicit/inferred/not_found |
| summary | TEXT | No | Validated summary |
| created_at | TIMESTAMP | No | Creation timestamp |

## Table: `review_points`
| Column | Type | Nullable | Purpose |
|---|---|---|---|
| id | UUID | No | Primary key |
| review_id | UUID | No | Foreign key to reviews.id |
| type | TEXT | No | PRO or CON |
| point | TEXT | No | Extracted insight |
| evidence | TEXT | No | Supporting review evidence |

## Constraints
- Foreign key from `review_points.review_id` to `reviews.id`.
- `rating` is null or between 1 and 5.
- `rating_source` uses the approved enum.
- Only validated AI output is persisted.
- Add indexes based on measured query needs, especially product name and created timestamp.
