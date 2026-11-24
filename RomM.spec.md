# RomM

A self-hosted ROM manager and player: scans a game library off disk, enriches it with metadata, serves it over a REST and Socket.IO API to a Vue web UI, and plays it in the browser.
owners: rommapp

## trust levels

- visitor (outside): an unauthenticated caller on the network: login, registration, password reset, device pairing and invite links
- user (outside): an authenticated caller (session cookie, bearer token, basic auth, client token) whose requests and uploads are still untrusted input
- device (outside): a registered device client (RetroArch, handhelds, companion apps) authenticating with a device or client token
- provider (outside): responses from external metadata providers and webhooks
- library: the files an admin placed in the library folder on disk
- worker: background jobs RomM itself enqueued on RQ
- storage: database rows and the asset files under the resources and assets folders
