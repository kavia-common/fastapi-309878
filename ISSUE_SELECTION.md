# FastAPI issue selected to work on

## Selected issue
**Will FastAPI support QUERY http method? `app.query`**  
https://github.com/fastapi/fastapi/issues/12965

## Why this is suitable
- Labeled **good first issue**.
- Clear, bounded scope: add support for a new HTTP method (`QUERY`) and ensure it works across routing and OpenAPI generation.
- Prior attempts and context are linked from the issue (multiple PRs), reducing discovery time.
- Can be progressed via code + tests + docs without needing extended design debate.

## Proposed implementation steps (high level)
1. Validate ASGI/server compatibility for method `QUERY` (e.g., httptools-based servers).
2. Add/confirm a first-class decorator (`app.query` / `router.query`) and ensure it wires through `APIRoute` correctly.
3. Ensure OpenAPI schema generation includes the operation and that docs tooling can display it (Swagger UI/Redoc constraints).
4. Add unit/integration tests for:
   - routing dispatch
   - request body acceptance
   - OpenAPI output
5. Update documentation to describe support and any limitations/caveats.
