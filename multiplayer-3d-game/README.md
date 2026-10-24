# Relay Arena — Multiplayer 3D Game

Relay Arena is a small networked arena game for two or more local players. Teams compete to capture the center beacon; the first team to three captures wins. The host simulates movement and validates capture distance, team, match state and cooldowns. Clients send only bounded movement input and capture requests.

## Features

- Host and client session controls with configurable host address and UDP port.
- Server-authoritative player movement and capture scoring.
- Deterministic team assignment, bounded movement input, capture-distance validation and per-team cooldown.
- Match end and host-controlled restart.
- EditMode tests for input bounds, team assignment and capture rules.

This is a local-network learning prototype. It does not use a matchmaking service, relay, account system, anti-cheat service or production-grade transport security. Do not expose the default UDP listener to untrusted networks.

## Requirements

- Unity Editor 6000.0 LTS.
- Netcode for GameObjects 2.13.3 and Unity Transport 2.6.0 are pinned in `Packages/manifest.json`.
- Two Unity Editor instances or one Editor plus a built player for a two-client smoke test.

## Scene setup

1. Open this folder in Unity 6000.0 and let Package Manager resolve the manifest.
2. Create a `RelayArena` scene. Add a Plane at `(0, 0, 0)`, a Sphere beacon at `(0, 0.5, 0)`, four Cube walls around the plane, a directional light and a camera.
3. Create a player prefab from a Capsule. Add `NetworkObject`, `NetworkTransform`, `CharacterController` and `RelayPlayerMotor`; assign the capsule renderer to `Body Renderer`.
4. In `NetworkTransform`, leave **Authority Mode** set to **Server**. Set the player prefab as the `Player Prefab` on a scene `NetworkManager` with `UnityTransport`; register the prefab in its Network Prefabs list. Set the transport port to `7777`. The host binds to `0.0.0.0`; clients enter the host’s reachable LAN address. In **Project Settings → Player → Other Settings**, set **Active Input Handling** to **Input Manager (Old)** or **Both**.
5. Add `RelayMatchManager` to a scene object (it also needs `NetworkObject`) and assign the beacon transform. Add `RelaySessionHud` to another scene object. Add `RelayCameraFollow` to the scene camera.
6. Add the scene to Build Profiles so NGO can synchronize the in-scene match manager. Start the host in one instance, then choose **Join host** in the other and enter the host machine’s LAN address. Use the HUD to play; use WASD/arrow keys and press E near the beacon. A disconnected client can reconnect by joining the active host again.

The prefab and scene are configured in the Unity Editor because Unity serializes network-prefab identifiers into scene assets. No generated binary scene is included.

## Tests

Open **Window → General → Test Runner**, select **EditMode**, and run `RelayRulesTests`. For gameplay verification, run a host and client and confirm server movement replication, a capture only inside the beacon radius, rejection of rapid duplicate capture, match end at three, and host restart. The manual GitHub Actions workflow `Unity multiplayer verification` runs EditMode tests and a Linux player build after a `UNITY_LICENSE` repository secret is configured.

Unity Editor and C# build tools are not installed in the Termux environment used to author this milestone. The EditMode suite, package resolution, two-client session and player build have **not** been run here. The project is source-complete for the documented MVP setup, pending those Unity checks.

## Architecture and limitations

`RelayRules` holds deterministic validation. `RelayPlayerMotor` owns local input capture but applies movement on the server; its server RPCs require ownership. `RelayMatchManager` is the sole score writer and rejects captures outside the beacon radius or during the team cooldown. `RelayCameraFollow` follows only the local player. `RelaySessionHud` exposes host/client startup without a third-party UI dependency.

Movement is a prototype with no prediction or lag compensation. The server rate-limits movement input RPCs, but there is no dedicated-server operations model or anti-cheat layer. Team assignment uses client ID parity and is intended for a local demonstration, not ranked matchmaking.

## License and contributions

Source is provided under the repository’s MIT license. Contributions should include a reproducible Unity test or two-client verification note and must not commit Unity `Library`, build output, account credentials or real player data.
