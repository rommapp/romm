# Endpoints

The FastAPI routers and Socket.IO event handlers: parse the request, check scopes and visibility, call handlers, shape the response schema.

## entrances

- login: a visitor exchanges username and password over HTTP Basic for a session cookie
  handler: login in backend/endpoints/auth.py
  trust: visitor
- logout: a caller ends its login session and disconnects the sockets it opened
  handler: logout in backend/endpoints/auth.py
  trust: visitor
- token: a visitor exchanges credentials or a refresh token for OAuth2 access and refresh tokens
  handler: token in backend/endpoints/auth.py
  trust: visitor
- request password reset: a visitor asks for a reset link for a username or email
  handler: request_password_reset in backend/endpoints/auth.py
  trust: visitor
- reset password: a visitor sets a new password with a reset token
  handler: reset_password in backend/endpoints/auth.py
  trust: visitor
- login via openid: a visitor starts the OIDC login redirect
  handler: login_via_openid in backend/endpoints/auth.py
  trust: visitor
- auth openid: the OIDC provider redirects back with an authorization code that becomes a session
  handler: auth_openid in backend/endpoints/auth.py
  trust: provider
- create user from invite: a visitor creates an account from an invite token
  handler: create_user_from_invite in backend/endpoints/user.py
  trust: visitor
- exchange pair code: a device trades a short pairing code for a client token
  handler: exchange_pair_code in backend/endpoints/client_tokens.py
  trust: device
- device auth init: a device starts the device authorization flow
  handler: device_auth_init in backend/endpoints/device/auth.py
  trust: device
- device token: a device polls for and receives its token once a user approved it
  handler: token in backend/endpoints/device/auth.py
  trust: device
- heartbeat: anyone reads the server's version and public configuration
  handler: heartbeat in backend/endpoints/heartbeat.py
  trust: visitor
- metadata heartbeat: anyone checks whether one metadata provider answers, rate limited per IP
  handler: metadata_heartbeat in backend/endpoints/heartbeat.py
  trust: visitor
- retroarch sync: RetroArch and generic WebDAV clients read and write roms, saves and states through the DAV verbs, each checked by one authorizer
  handler: _authorize in backend/endpoints/sync/retroarch.py
  trust: device

## invariants

- hidden entities answer as missing: A rom, platform or firmware hidden from a user, directly, through its platform or by age limit, answers every route that takes its id exactly as an id that does not exist would.
  over: every method of every /api route keyed on a rom, platform or firmware id, each called with a hidden id and with a missing id
  via: test_every_entity_route_answers_a_hidden_id_like_a_missing_one
  because: visibility is access control in RomM; a route that answers a hidden id differently from a missing one leaks the game, or lets the user act on it
  crossing: user -> storage
  entrances: http api
  kinds: read
  checklist: scoped-reads declared as hidden entities answer as missing
  checklist: redaction dismissed: no export scrubbing policy in scope
- save fetch by id stays in its router: A save is changed only by its owner and read by another user only when its owner made it public, both only while the reader can see its rom; the unscoped fetch by id is reached only from the saves router, which applies that check.
  protects: get_save_by_id in backend/handler/database/saves_handler.py
  chokepoint: backend/endpoints/saves.py
  because: get_save_by_id ignores the owner, so a call from any other module would serve or overwrite another user's save
  crossing: user -> storage
  kinds: read
  checklist: scoped-reads declared as save fetch by id stays in its router
  checklist: redaction dismissed: no export scrubbing policy in scope
- state fetch by id stays in its router: A state is changed only by its owner and read by another user only when its owner made it public, both only while the reader can see its rom; the unscoped fetch by id is reached only from the states router, which applies that check.
  protects: get_state_by_id in backend/handler/database/states_handler.py
  chokepoint: backend/endpoints/states.py
  because: get_state_by_id ignores the owner, so a call from any other module would serve or overwrite another user's state
  crossing: user -> storage
  kinds: read
  checklist: scoped-reads declared as state fetch by id stays in its router
  checklist: redaction dismissed: no export scrubbing policy in scope
- screenshot fetch by id stays in its router: A screenshot is changed only by its owner and read by another user only when its owner made it public, both only while the reader can see its rom; the unscoped fetch by id is reached only from the screenshots router, which applies that check.
  protects: get_screenshot_by_id in backend/handler/database/screenshots_handler.py
  chokepoint: backend/endpoints/screenshots.py
  because: get_screenshot_by_id ignores the owner, so a call from any other module would serve or overwrite another user's screenshot
  crossing: user -> storage
  kinds: read
  checklist: scoped-reads declared as screenshot fetch by id stays in its router
  checklist: redaction dismissed: no export scrubbing policy in scope

## folded

- device: the device pairing and install routers
- sync: the RetroArch WebDAV router
- forms: request form models the routers share
- responses/**: the response schemas the routers return
- roms: the per-rom sub-routers (files, manuals, uploads, notes, patches)
- sockets: the Socket.IO event handlers behind the socket events and netplay events entrances
