# Backend

The FastAPI application: REST routes, Socket.IO namespaces, the ORM models, the handlers they call and the RQ tasks behind them.

## entrances

- http api: every authenticated REST route under /api, registered through protected_route with its required scopes
  handler: protected_route in backend/decorators/auth.py
  trust: user

## invariants

- api routes require auth: Every REST route under /api requires an authenticated caller holding its declared scopes, except the named public routes, each of which checks its caller itself.
  over: every APIRoute registered under /api, walked through the included routers
  via: test_every_api_route_requires_auth_or_is_listed_public
  because: a route registered with a bare router decorator instead of protected_route ships open to the network; the sweep fails on it unless someone adds it to the public list on purpose
  crossing: visitor -> user
  entrances: http api
  kinds: credential, read
  checklist: scoped-reads dismissed: which records a caller sees is the Endpoints invariant hidden entities answer as missing
  checklist: capability-authorization declared as api routes require auth
  checklist: revalidated-permission dismissed: scopes are checked on every request; queued tasks are outside this invariant
  checklist: message-authenticity dismissed: these routes accept no signed external message
  checklist: encrypted-storage dismissed: the invariant persists nothing
  checklist: key-rotation-compatibility dismissed: no encrypted data in scope
  checklist: redaction dismissed: no export scrubbing policy in scope
  checklist: separation-of-duties dismissed: RomM has no requester and approver roles

## folded

- decorators: the protected_route and database session decorators every route and handler wears
- exceptions: the exception classes endpoints raise
- logger: logging setup and formatters
- tools: dev and test scripts outside the app runtime
