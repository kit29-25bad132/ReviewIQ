# ReviewIQ — Demo and Evaluation

## Recommended Demo
1. Introduce the problem.
2. Show a raw customer review.
3. Submit the review.
4. Explain the request lifecycle.
5. Show structured output.
6. Explain Pydantic validation.
7. Show evidence grounding.
8. Show persisted data.
9. Show dashboard and deterministic insights.
10. Demonstrate a failure case.
11. Explain AI evaluation methodology.
12. Explain limitations and future work.

## Questions to Prepare
### AI
- Why Gemini?
- Why structured output?
- Why Pydantic?
- How are invented ratings prevented?
- How is evidence grounded?
- What happens when Gemini fails?
- How was the model evaluated?
- Why is fine-tuning not required for V1?

### Backend/Data
- Why FastAPI?
- How does a request travel through the system?
- Why PostgreSQL?
- How are tables related?
- How are database errors handled?

### Frontend
- Why Next.js and React?
- How does state work?
- How are loading and error states handled?
- How does the frontend call the API?

### Engineering
- Why deterministic analytics?
- Why retain original review text?
- How are secrets protected?
- What is tested?
- How do changes avoid breaking other modules?

## Evaluation Rule
Answers must describe the actual implementation and measured evidence, not assumptions or invented claims.
