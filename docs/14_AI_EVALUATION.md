# ReviewIQ — AI Evaluation

## Dataset
Create approximately 30–50 manually labeled reviews covering positive, negative, mixed, short, long, explicit rating, missing rating, ambiguous language, and multiple pros/cons.

Each record should include:
- Input review
- Expected rating
- Expected rating source
- Expected pros
- Expected cons
- Expected evidence
- Optional notes on ambiguity

## Metrics
Evaluate separately:
1. Rating extraction accuracy
2. Rating-source classification accuracy
3. Pros extraction quality
4. Cons extraction quality
5. Evidence grounding
6. Structured-output validity
7. Failure rate and retry rate

## Evaluation Process
Dataset → baseline prompt/model → outputs → compare against labels → record failures → revise prompt/schema/checks → rerun the same dataset → document changes.

Never report invented percentages. Clearly distinguish exact-match metrics, human judgment, and qualitative observations.
