# RoMM SFU Netplay Architecture

**Last Updated:** 2026-01-09  
**Status:** Active Development

## Overview

This document describes the architecture of the RoMM SFU-based netplay system, which replaces traditional P2P netplay with a scalable, cloud-friendly Selective Forwarding Unit (SFU) server using mediasoup.

## System Components

### 1. **romm-sfu-server** (Node.js/mediasoup)
- High-performance, scalable media and data relay server
- Built with mediasoup for WebRTC SFU functionality
- Handles:
  - WebRTC media streams (video/audio) for emulator screen sharing
  - Data channels for netplay input synchronization
  - Room management and player coordination
  - Multi-worker scaling for large rooms
  - Fan-out support for spectator-heavy rooms

**Key Features:**
- **Persistent Identity**: Overwrites random `UserID` with `PlayerID` sourced from RoMM
- **Authentication**: JWT-based auth via RoMM internal API
- **Room Registry**: Multi-node support via Redis-backed room discovery
- **Worker Pool**: Horizontal scaling across CPU cores
- **WebRtcServer**: Single-port UDP/TCP for simplified firewall rules

**Configuration:**
- Port: 3001 (configurable via `PORT`)
- WebRTC ports: 20000+ (configurable via `WEBRTC_PORT`)
- Worker count: Auto-detected from CPU cores (configurable via `SFU_WORKER_COUNT`)

### 2. **EmulatorJS-SFU** (Fork of EmulatorJS)
- Custom fork with fully rebuilt netcode
- Designed to work with the SFU server architecture
- Replaces traditional P2P netplay with SFU-based signaling
- **Current State**: Netcode embedded in 15,000+ line `emulator.js` file
- **Future Goal**: Compartmentalize netcode into portable, shareable modules

**Integration Points:**
- Uses `window.EJS_netplayUrl` to connect to SFU server
- Authenticates via JWT token stored in `window.EJS_netplayToken` or cookie
- Communicates via Socket.IO for signaling
- Uses mediasoup-client for WebRTC transport

### 3. **romm** (Python/FastAPI + Vue.js)
- Main ROM management application
- Provides authentication and token minting for SFU access
- Manages persistent netplay identity and metadata

**Key Endpoints:**
- `POST /api/sfu/token` - Mints short-lived JWT tokens (30s TTL) for SFU access
- `POST /api/sfu/internal/verify` - SFU server calls this to verify tokens (internal API)
- `POST /api/sfu/internal/rooms/upsert` - Room registry updates (internal API)
- `GET /api/sfu/internal/rooms/list` - List active rooms (internal API)
- `GET /api/sfu/internal/rooms/resolve` - Resolve room to SFU node (internal API)

**Redis Storage:**
- `sfu:auth:jti:<jti>` - JWT allowlist entries (hash with sub, netplay_username, etc.)
- `sfu:room:<room_name>` - Room registry entries (JSON, TTL 60s)
- All SFU-related data under `sfu:*` prefix for isolation

**User Data:**
- Netplay username stored in `users.ui_settings.netplay_username`
- Future: Dedicated `users.netplay_username` column (planned)

## Authentication Flow

1. **Client requests token:**
   - User opens emulator in RoMM frontend
   - Frontend calls `POST /api/sfu/token` (requires authenticated session)
   - RoMM mints JWT with:
     - `iss`: `romm:sfu`
     - `sub`: `<romm_username>`
     - `jti`: unique token ID
     - `exp`: 30 seconds from now
   - RoMM stores allowlist entry in Redis: `sfu:auth:jti:<jti>`
   - Token returned to client

2. **Client connects to SFU:**
   - Client stores token in cookie: `romm_sfu_token`
   - EmulatorJS-SFU connects to SFU via Socket.IO
   - Socket.IO middleware extracts token from cookie/query/auth header
   - SFU calls `POST /api/sfu/internal/verify` with token
   - RoMM verifies JWT signature and checks Redis allowlist
   - RoMM returns `sub` (username) and `netplay_username`
   - SFU binds socket to authenticated `userid` (replaces random UserID)

3. **Identity Binding:**
   - SFU's `bindUseridToSocket()` enforces stable identity per connection
   - `applyAuthToExtra()` overwrites any client-provided userid
   - `netplay_username` from RoMM used as display name
   - All room operations use authenticated `userid`, not client claims

## Room Management

### Room Lifecycle
1. **Open Room**: Host calls `open-room` with room metadata
   - SFU creates room, assigns to least-loaded worker
   - Registers room in Redis via RoMM API (if multi-node enabled)
   - Owner socket pinned to room's primary worker

2. **Join Room**: Player calls `join-room` with room name
   - SFU verifies room exists (local or via registry)
   - Assigns player to worker (primary for players, distributed for viewers)
   - Handles reconnection: same userid can replace stale socket

3. **Room Registry** (Multi-node):
   - Each SFU node periodically updates room status in Redis
   - Clients can resolve room name to SFU node URL
   - Enables horizontal scaling across multiple SFU servers

### Room State
- **In-memory (SFU)**: Active transports, producers, consumers, worker assignments
- **Redis (RoMM)**: Room metadata, player counts, node assignments
- **Future**: Persistent room history, game metadata, achievement tracking

## Data Flow

### Media Streams
1. Host captures emulator screen/audio
2. Host creates mediasoup producer (VP9/H264/VP8)
3. SFU routes to all consumers in room
4. Viewers/players receive via mediasoup consumers

### Netplay Input
1. Players send input via data channel
2. SFU relays binary data to all room members
3. Host processes inputs and updates emulator state
4. State changes reflected in video stream

### Signaling
- Socket.IO for room management, player lists, pause/resume
- WebRTC for media and data channels
- P2P signaling relay for control-channel WebRTC (legacy support)

## Current Limitations & Future Work

### Immediate Priorities
1. **Documentation**: Comprehensive docs for setup, configuration, API
2. **Performance**: Optimize netplay latency, stabilize connection handling
3. **Code Organization**: Extract netcode from 15,000+ line emulator.js into modules

### Short-term Goals
1. **Persistent Netplay Identity**
   - Store netplay ID in Redis/DB
   - Associate with RetroAchievements
   - Persistent player names across sessions

2. **Room Metadata**
   - Game/ROM associations
   - Room history and statistics
   - Player/spectator seat management
   - Game mode support (tournament, casual, etc.)

3. **Enhanced Room Features**
   - Context-aware rooms (player slots, spectator limits)
   - Room passwords and access control
   - Ban lists (per-room and global)

### Long-term Vision
1. **Rollback Netcode**: Implement deterministic rollback for better latency handling
2. **Parallel Play Rooms**: Conference-call style rooms for multiple simultaneous games
3. **Multi-Emulator Support**: Extend beyond EmulatorJS to other emulators
4. **Federated Network**: 
   - Cross-instance authentication
   - Shared SFU capacity
   - Trusted site federation with public/private keys
   - Alternative to port-forwarding dependent netplay

## Configuration

### Environment Variables

**SFU Server:**
- `PORT` - Signaling port (default: 3001)
- `WEBRTC_PORT` - Base WebRTC port (default: 20000)
- `SFU_WORKER_COUNT` - Worker count (default: auto-detect)
- `ROMM_API_BASE_URL` - RoMM internal API URL
- `ROMM_SFU_INTERNAL_SECRET` - Shared secret for internal API
- `SFU_STUN_SERVERS` - STUN server list
- `SFU_TURN_SERVERS` - TURN server JSON array

**RoMM:**
- `SFU_HOST` / `SFU_PORT` - SFU server location
- `ROMM_SFU_INTERNAL_SECRET` - Shared secret (must match SFU)
- `REDIS_HOST` / `REDIS_PORT` - Redis/Valkey connection
- `ROMM_AUTH_SECRET_KEY` - JWT signing key

## Security Considerations

1. **Token Security**:
   - Short TTL (30s) limits replay window
   - One-time use tokens (optional, via `consume` flag)
   - Redis allowlist prevents arbitrary signed tokens

2. **Identity Enforcement**:
   - SFU never trusts client-provided userid
   - All identity sourced from authenticated JWT
   - Server-side binding prevents impersonation

3. **Internal API**:
   - `x-romm-sfu-secret` header required
   - SFU never accesses Redis directly
   - Least-privilege: SFU only sees `sfu:*` keys via API

4. **Federation (Future)**:
   - Public/private key pairs for trusted sites
   - Signed assertions with nonce replay protection
   - TLS required for all federation traffic

## Deployment

### Single-Node
- SFU server runs alongside RoMM
- Docker Compose includes SFU service
- Nginx reverse-proxies SFU endpoints

### Multi-Node
- Multiple SFU servers behind load balancer
- Room registry in Redis enables node discovery
- Clients resolve room names to specific nodes

### Scaling
- Horizontal: Add more SFU nodes
- Vertical: Increase worker count per node
- Fan-out: Distribute viewers across workers for large rooms

## Related Documentation

- `docs/sfu-auth-design.md` - Detailed authentication design
- `romm-sfu-example-configs/` - Example configurations
- `backend/endpoints/sfu.py` - API implementation
- `romm-sfu-server/index.js` - SFU server implementation
