# Game Modding and Scripting Framework

A small C# host embeds Lua mods through MoonSharp. Mods receive only the `emit` callback; the Lua core library excludes operating-system and filesystem access. The host validates a versioned manifest, limits source size, rejects loop and function declarations to keep this MVP's script subset bounded, and bounds event names, payloads, and counts. The sample emits a harmless weather event.

## Run

Install .NET 8, then run `dotnet test tests/GameMods.Tests`. The library API is `ModHost.Load(ModManifest, source)`; callers should load mod files from a trusted package boundary and decide which emitted events the game accepts.

## Limits

The syntax restrictions and missing standard libraries reduce abuse risk; they are not a process isolation boundary. Do not run untrusted mods in a privileged host, expose unrestricted callbacks, or treat client-emitted events as authoritative game state. API version 1 is intentionally small; persistence, package signing, and hot reload are future work.

## Contributing and license

Keep host capabilities explicit and cover new API surface with tests. This project is provided under the repository MIT license.
