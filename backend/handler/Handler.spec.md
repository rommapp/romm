# Handler

The business logic the endpoints and tasks call: database access, filesystem, scanning, metadata providers, auth, sockets, sync and streaming.

## entrances

- socket events: authenticated browser sessions emit events on the /ws Socket.IO namespace (scan, activity, devices, logs)
  handler: socket_handler in backend/handler/socket_handler.py
  trust: user
- netplay events: authenticated players open, join and relay netplay rooms on the /netplay namespace
  handler: netplay_socket_handler in backend/handler/socket_handler.py
  trust: user
