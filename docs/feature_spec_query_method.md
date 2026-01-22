# Feature Spec: Support `QUERY` HTTP Method in FastAPI

## 1. Summary & goals

This feature adds first-class support in FastAPI for the `QUERY` HTTP method, as requested in FastAPI issue #12965. The goal is to allow developers to register routes using `QUERY` via the same ergonomics as existing built-in HTTP methods (e.g., `app.get()`, `app.post()`), while preserving compatibility with existing generic APIs (`api_route`, `add_api_route`, and Starlette-compatible `Router.add_route`).

This spec defines how FastAPI should behave for routing, request parsing, dependency injection, and OpenAPI generation when a route uses the `QUERY` method.

### Goals

FastAPI should:

1. Support route registration with `methods=["QUERY"]` via `app.api_route()` and `app.add_api_route()`, and via `APIRouter.api_route()` and `APIRouter.add_api_route()`.
2. Provide convenience decorators `app.query()` and `router.query()` with signatures consistent with existing path operation methods (e.g., `app.get()`).
3. Treat `QUERY` as a method that may include a request body for FastAPI’s request parsing and OpenAPI `requestBody` generation, similar to `POST`/`PUT`/`PATCH`.
4. Ensure dependency injection and parameter extraction work identically for `QUERY` as for other methods.
5. Generate OpenAPI output that includes the `query` operation under the path item, even if tooling (Swagger UI/Redoc) has limitations.
6. Provide clear documentation guidance and fallbacks when OpenAPI tooling or clients do not recognize `QUERY`.

## 2. Non-goals

1. This feature does not attempt to change the OpenAPI Specification itself. OpenAPI 3.x defines a fixed set of Path Item operation keys (`get`, `put`, `post`, `delete`, `options`, `head`, `patch`, `trace`). It does not define `query` as a standard operation key.
2. This feature does not guarantee that Swagger UI, ReDoc, or client generators will render or generate clients for `QUERY` operations. Instead, FastAPI will generate the best-possible schema and provide documentation notes and recommended workarounds.
3. This feature does not add new behavior to ASGI servers (Uvicorn/Hypercorn/etc.). ASGI servers pass through unknown methods as strings; they are already capable of receiving `QUERY` as `scope["method"]`.
4. This feature does not enforce semantics for `QUERY` (e.g., read-only semantics). It merely enables routing and documentation.

## 3. Background/context

### 3.1 Current handling of custom HTTP methods in FastAPI/Starlette

FastAPI builds routing on Starlette. Starlette routes match requests by `scope["method"]` (a string) against a route’s configured `methods` set.

In FastAPI’s `APIRoute` implementation, `methods` are normalized to uppercase:

- In `fastapi/routing.py`, `APIRoute.__init__` defaults `methods` to `["GET"]` and then sets:
  `self.methods = {method.upper() for method in methods}`.

This means custom methods can already be used by supplying them via generic route registration methods (e.g., `api_route(..., methods=["FOO"])`) so long as Starlette allows matching them.

### 3.2 Current FastAPI method decorators and signature tests

FastAPI and APIRouter provide built-in decorators for standard methods (e.g., `get`, `post`, `put`, `delete`, `options`, `head`, `patch`, `trace`). There is a test (`tests/test_operations_signatures.py`) that asserts these method decorators have consistent signatures between `FastAPI` and `APIRouter` by enumerating a list of method names.

Adding `query()` must maintain this design, including signature consistency and test updates.

### 3.3 Current OpenAPI generation and method-related behavior

FastAPI OpenAPI generation uses `fastapi/openapi/utils.py`. The OpenAPI generator reads FastAPI `APIRoute` objects and builds `paths` entries for each `route.path_format`.

FastAPI also defines `METHODS_WITH_BODY` in `fastapi/openapi/constants.py`:

```python
METHODS_WITH_BODY = {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"}
```

This set is used when deciding whether to generate a request body for a given operation. The current set does not include `TRACE`, and does not include `QUERY`.

For `QUERY` support, this constant needs to be updated to include `"QUERY"` if the intended semantics allow request bodies.

## 4. Detailed requirements

### 4.1 Routing API design

#### 4.1.1 New decorators: `app.query()` and `router.query()`

FastAPI must expose a new path operation decorator:

- `FastAPI.query(path: str, **kwargs) -> Callable[[DecoratedCallable], DecoratedCallable]`
- `APIRouter.query(path: str, **kwargs) -> Callable[[DecoratedCallable], DecoratedCallable]`

The signature must be identical to `get()` (and other built-in methods), differing only in the HTTP method used internally (`methods=["QUERY"]`).

This is required to maintain usability parity and provide first-class support consistent with existing patterns.

#### 4.1.2 Compatibility with `methods=["QUERY"]`

The following existing APIs must continue to work and explicitly support `"QUERY"`:

- `FastAPI.api_route(..., methods=["QUERY"])`
- `FastAPI.add_api_route(..., methods=["QUERY"])`
- `APIRouter.api_route(..., methods=["QUERY"])`
- `APIRouter.add_api_route(..., methods=["QUERY"])`

No new parameter is needed; the method name is just another string. The behavior should match existing non-standard methods: normalization to uppercase and matching in Starlette.

#### 4.1.3 Mixed-method operations

A route registered with multiple methods including `"QUERY"` should be supported:

- Example: `methods=["GET", "QUERY"]`

OpenAPI generation must create entries for both operations if feasible (see OpenAPI constraints below). If OpenAPI cannot represent mixed methods including `QUERY` in standard fields, FastAPI should still include the `QUERY` operation using a fallback strategy described in section 6.

### 4.2 Request handling

#### 4.2.1 Request body parsing for `QUERY`

FastAPI’s request handling uses `APIRoute.body_field` to determine whether to parse body content, and `get_request_handler()` reads the body when a `body_field` exists.

A `body_field` exists when the endpoint signature includes body parameters (e.g., `item: Item`), which typically depends on method semantics and parameter declarations.

Requirement: `QUERY` should allow request bodies in the same way as `POST`, `PUT`, `PATCH` when the endpoint includes body parameters. Specifically:

1. If the endpoint declares body parameters (e.g., a Pydantic model parameter without `Query()`), FastAPI should parse JSON or form content as normal.
2. For OpenAPI generation, `QUERY` should be treated as body-capable (see 4.4 and 6).

Notes:

- ASGI servers and Starlette `Request` support reading the body for any method. FastAPI already reads request body whenever the route expects it; it does not hardcode parsing by method in the request handler.
- Therefore, the primary method-specific behavior is OpenAPI and potentially any method-based heuristics for body generation.

#### 4.2.2 Dependency injection

Dependency injection must behave identically for `QUERY` as for other HTTP methods:

- Dependencies declared in `dependencies=[Depends(...)]` for the decorator or router must run.
- `Depends()` in endpoint parameters must resolve.
- Dependencies using `yield` must be managed via the AsyncExitStack and behave as they do for other methods.

No method-specific changes are expected in `fastapi/routing.py` request handling, beyond ensuring `QUERY` is treated as a “body-capable” method where relevant to OpenAPI or body-field creation.

### 4.3 Response handling

`QUERY` routes must use all existing response features:

- `response_model`, serialization, validation, and `ResponseValidationError` behavior must work.
- Custom response classes must work.
- Status code and header handling must work.

No special-case response logic is required.

### 4.4 OpenAPI generation behavior

Because OpenAPI does not define a `query` operation key, FastAPI must define a strategy that is both standards-aware and practical.

#### 4.4.1 Standard OpenAPI keys vs. `QUERY`

OpenAPI 3.x Path Item supports only these keys for operations: `get`, `put`, `post`, `delete`, `options`, `head`, `patch`, `trace`.

There is no native `query` key, and many tools assume only those keys exist.

#### 4.4.2 Required FastAPI behavior for OpenAPI output

FastAPI must generate OpenAPI that:

1. Includes the `QUERY` route in the schema output in a predictable and discoverable way.
2. Does not break existing OpenAPI rendering for standard methods.
3. Minimizes the risk of invalid schema objects (as invalid schemas can break docs pages entirely).

Given these constraints, this spec proposes a dual approach:

##### Approach A (primary): Emit a non-standard Path Item operation key `query`

FastAPI will include an additional `query` key under the relevant path item:

```json
"paths": {
  "/items": {
    "query": { ... operation ... }
  }
}
```

This is not standard OpenAPI, but it is a commonly requested pragmatic outcome for custom methods because it keeps the operation colocated with the path.

FastAPI must clearly document that this is an extension and may not be rendered or used by tooling.

##### Approach B (fallback / additional metadata): Add vendor extensions

To improve tooling compatibility and allow downstream tooling to discover custom methods even if it ignores unknown keys, FastAPI should also add vendor extension fields:

- At the operation level: `x-fastapi-method: "QUERY"`
- Optionally at the path item level: `x-fastapi-extra-methods: ["QUERY"]`

For example:

```json
"paths": {
  "/items": {
    "query": {
      "x-fastapi-method": "QUERY",
      "summary": "...",
      ...
    }
  }
}
```

This helps custom tooling and downstream consumers.

#### 4.4.3 Request body support in OpenAPI for `QUERY`

FastAPI currently uses `METHODS_WITH_BODY` to decide when to include `requestBody` in OpenAPI output.

Requirement: `METHODS_WITH_BODY` must be updated to include `"QUERY"` so that, when a `QUERY` endpoint has body parameters, OpenAPI output includes a `requestBody` for the `query` operation.

This aligns the documentation with actual runtime behavior (FastAPI can parse a body for QUERY).

#### 4.4.4 OperationId and uniqueness

Operation IDs must follow existing patterns and remain unique.

For `QUERY`, the operationId generation should work exactly as for other methods, producing suffix `_query` for default generated ids (based on the existing behavior demonstrated in tests for methods like `trace`).

If any code assumes method names are limited to a predefined set, it must be updated to include `query`.

### 4.5 FastAPI CLI / ASGI server considerations

FastAPI’s in-repo CLI entrypoint (`fastapi/cli.py` and `fastapi/__main__.py`) delegates to `fastapi_cli` when installed. This feature does not require CLI changes. However:

- Documentation should note that ASGI servers must be used/configured to allow unknown methods (most do by default).
- Any middleware or proxy (e.g., Nginx, API gateways) may block unknown methods unless configured.

FastAPI itself will simply match `scope["method"] == "QUERY"` and run the endpoint.

## 5. API surface & examples

### 5.1 New decorator examples

#### Example: Simple QUERY endpoint

```python
from fastapi import FastAPI

app = FastAPI()

@app.query("/items")
def query_items(q: str):
    return {"q": q}
```

Expected runtime behavior:

- Requests with method `QUERY /items?q=foo` are routed to `query_items`.
- Query parameters behave as usual.

#### Example: QUERY with request body

```python
from fastapi import FastAPI
from pydantic import BaseModel

class Filter(BaseModel):
    category: str
    limit: int = 10

app = FastAPI()

@app.query("/items/search")
def query_items(filter: Filter):
    return {"category": filter.category, "limit": filter.limit}
```

Expected runtime behavior:

- Requests with method `QUERY /items/search` and JSON body parse into `Filter`.
- Validation errors produce the standard 422 response.

### 5.2 Existing API compatibility examples

#### Using `api_route` explicitly

```python
from fastapi import FastAPI

app = FastAPI()

@app.api_route("/items", methods=["QUERY"])
def query_items():
    return {"ok": True}
```

#### Using `add_api_route`

```python
from fastapi import FastAPI

app = FastAPI()

def handler():
    return {"ok": True}

app.add_api_route("/items", handler, methods=["QUERY"])
```

## 6. OpenAPI / Docs behavior with fallbacks

### 6.1 Expected OpenAPI output

When a `QUERY` route exists, FastAPI should include it under the relevant path:

- Path item has a `query` key with an operation object.
- Operation object includes `x-fastapi-method: "QUERY"`.

### 6.2 Swagger UI / ReDoc limitations

Swagger UI and ReDoc primarily follow standard OpenAPI operation keys. They may:

- Ignore the `query` operation entirely.
- Fail validation or rendering if encountering unexpected keys (behavior varies by version).

Because FastAPI serves Swagger UI via `fastapi/openapi/docs.py` by loading the generated `openapi.json`, problems here can impact developer experience.

#### Requirement: Documentation note and workarounds

FastAPI documentation should explain:

1. The OpenAPI spec does not list `QUERY` as a standard operation.
2. Tools such as Swagger UI/Redoc may not render the operation.
3. Users can still call the endpoint with clients (curl/httpx/etc.) and use FastAPI’s runtime.
4. Workarounds include:
   - Exposing the same operation also as `POST` (if appropriate) strictly for docs/clients.
   - Providing a custom OpenAPI schema transformation that maps `QUERY` to `post` for documentation-only environments (with a clear warning about semantic mismatch).
   - Using vendor extensions and custom tooling.

This spec does not require implementing a special UI mapping, but it should guide users.

### 6.3 “Docs-only mapping” (optional enhancement)

If maintainers prefer to improve Swagger UI rendering, FastAPI could offer an opt-in mechanism (not required in this initial spec) to remap `QUERY` operations to a standard key (likely `post`) in a modified schema served at `/openapi.json` or in `/docs`.

This would be a separate feature; this spec only requires documenting the limitation.

## 7. Validation and error handling

### 7.1 Request validation

`QUERY` endpoints must produce the same request validation behavior as other HTTP methods:

- Invalid body payloads produce `RequestValidationError` with 422.
- Invalid JSON produces a 422 `json_invalid`-style error consistent with current behavior.
- Missing required query/path params produce 422.

### 7.2 Method mismatch behavior

If a client sends a `GET` request to a `QUERY`-only route, routing must behave as normal:

- The route should not match.
- FastAPI should return 405 Method Not Allowed if the path matches but method does not, following Starlette behavior.
- `Allow` header should include `QUERY` if Starlette includes it from the route methods.

### 7.3 OpenAPI schema validation

FastAPI’s OpenAPI output will contain non-standard keys. This can cause some validators to fail.

Requirement: FastAPI should not raise errors during schema generation. The schema output must still be JSON-serializable and stable.

## 8. Backward compatibility

This change must be backward compatible.

1. Adding `app.query()` and `router.query()` should not break existing code.
2. Adding `"QUERY"` to `METHODS_WITH_BODY` changes OpenAPI generation behavior only for routes explicitly registered with `"QUERY"`. Existing routes are unaffected.
3. Updating signature consistency tests must be done carefully; it should expand the method list without changing existing signatures.
4. OpenAPI generation changes must not alter standard method output.

## 9. Testing strategy

Tests should be added/updated to cover:

### 9.1 API surface tests

- Update `tests/test_operations_signatures.py` to include `"query"` in the list of `method_names` and verify `FastAPI.query` and `APIRouter.query` signatures match `APIRouter.get`/base signature.

### 9.2 Routing behavior tests

Add a new test module (or extend `tests/test_extra_routes.py`) to verify:

1. A `QUERY` route can be registered with `@app.query("/items")` and called via `client.request("QUERY", "/items")`.
2. A `QUERY` route registered via `methods=["QUERY"]` works equivalently.
3. 405 behavior is correct when using wrong methods.

### 9.3 Request body tests

Add tests verifying that:

- A `QUERY` endpoint with a Pydantic model body parses JSON and validates.
- Validation errors produce 422.

### 9.4 OpenAPI generation tests

Add tests verifying that OpenAPI schema output:

- Includes a `query` entry under the relevant path.
- Includes `requestBody` when the `QUERY` endpoint declares a body.
- Includes vendor extension(s) if implemented (e.g., `x-fastapi-method`).

Given existing tests assert OpenAPI output for various methods (see `tests/test_extra_routes.py`), new tests should follow that style but focus on the `query` operation.

## 10. Rollout plan

1. Implement `app.query()` and `router.query()`.
2. Update `METHODS_WITH_BODY` to include `"QUERY"` so OpenAPI includes request bodies for `QUERY`.
3. Implement OpenAPI operation emission strategy for `QUERY` (non-standard `query` key plus vendor extension).
4. Add/adjust tests.
5. Document limitations and usage guidance.
6. Release in the next minor FastAPI version, with release notes highlighting:
   - New `query()` decorator.
   - OpenAPI tooling limitations.

## 11. Risks and mitigations

### Risk: OpenAPI tooling breaks when encountering `query` key

Some tools may error on unknown operation keys.

Mitigation:

- Ensure schema generation remains valid JSON and does not break standard methods.
- Add documentation warning.
- Consider adding vendor extension-only mode or docs-only mapping as a follow-up if tool breakage is reported.

### Risk: Client/proxy rejects unknown methods

Some proxies/load balancers block custom methods by default.

Mitigation:

- Document the requirement to allow custom methods in intermediaries.
- Suggest fallback of mapping to POST where needed.

### Risk: Semantic confusion with “query parameters” vs “QUERY method”

Developers may confuse `QUERY` with query parameters.

Mitigation:

- Documentation should emphasize “HTTP method named QUERY” and show explicit examples of use.

## 12. Acceptance criteria

This feature is complete when:

1. Developers can define a route using `@app.query("/path")` and `@router.query("/path")`.
2. Developers can define routes using `methods=["QUERY"]` in `api_route` / `add_api_route`.
3. A request using method `QUERY` is correctly routed and processed, including dependency injection.
4. Request body parsing and validation work for `QUERY` endpoints when a body is declared.
5. OpenAPI schema generation includes the `QUERY` operation in a consistent, documented way, and includes requestBody when applicable.
6. Tests cover the new decorator, routing behavior, request body parsing, and OpenAPI output.
7. Documentation includes a clear note that OpenAPI/Swagger UI/Redoc may not support `QUERY` fully and provides practical workarounds.

## Sources (code references)

This specification is based on the current FastAPI codebase behavior observed in:

- `fastapi/routing.py`: `APIRoute` method normalization, request parsing, dependency execution, and the structure of `APIRouter` method decorators.
- `fastapi/openapi/constants.py`: `METHODS_WITH_BODY` constant used for OpenAPI request body behavior.
- `fastapi/openapi/utils.py`: OpenAPI schema generation pipeline and how routes are processed into `paths`.
- `fastapi/openapi/docs.py`: Swagger UI and ReDoc HTML generation and limitations implied by external tooling.
- `fastapi/cli.py` and `fastapi/__main__.py`: CLI entrypoints and why no direct changes are required.
- `tests/test_operations_signatures.py`: Signature consistency checks for existing HTTP method decorators.
- `tests/test_extra_routes.py`: How methods like `TRACE` are tested and how OpenAPI output is asserted in tests.
