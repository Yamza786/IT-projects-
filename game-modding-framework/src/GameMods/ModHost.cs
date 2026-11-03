using MoonSharp.Interpreter;

namespace GameMods;

public sealed record ModManifest(string Id, int ApiVersion, string EntryPoint);
public sealed record ModEvent(string Name, string Payload);

public sealed class ModHost
{
    public const int ApiVersion = 1;
    public const int MaxScriptBytes = 64 * 1024;
    private readonly List<ModEvent> _events = [];

    public IReadOnlyList<ModEvent> Events => _events.AsReadOnly();

    public IReadOnlyList<ModEvent> Load(ModManifest manifest, string source)
    {
        if (!System.Text.RegularExpressions.Regex.IsMatch(manifest.Id, "^[a-z0-9][a-z0-9._-]{0,63}$"))
            throw new ArgumentException("Mod ID must be a lowercase slug.", nameof(manifest));
        if (manifest.ApiVersion != ApiVersion)
            throw new InvalidOperationException($"Mod API {manifest.ApiVersion} is incompatible with host API {ApiVersion}.");
        if (manifest.EntryPoint != "main.lua")
            throw new ArgumentException("Only the packaged main.lua entry point is supported.", nameof(manifest));
        if (System.Text.Encoding.UTF8.GetByteCount(source) > MaxScriptBytes)
            throw new ArgumentException("Script exceeds 64 KiB.", nameof(source));

        _events.Clear();
        // This deliberately small Lua subset excludes libraries and unbounded constructs.
        if (System.Text.RegularExpressions.Regex.IsMatch(source, @"\b(while|for|repeat|function)\b"))
            throw new ArgumentException("Loops and function declarations are outside the bounded mod subset.", nameof(source));
        var script = new Script(CoreModules.Basic);
        script.Globals["emit"] = (Action<string, string>)((name, payload) =>
        {
            if (name.Length is < 1 or > 64 || payload.Length > 512)
                throw new ScriptRuntimeException("Event name or payload exceeds host limits.");
            _events.Add(new ModEvent(name, payload));
            if (_events.Count > 100) throw new ScriptRuntimeException("Mod event quota exceeded.");
        });
        script.DoString(source, null, manifest.Id);
        return Events;
    }
}
