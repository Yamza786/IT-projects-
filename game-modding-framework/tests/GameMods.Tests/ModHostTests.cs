using GameMods;

namespace GameMods.Tests;

public class ModHostTests
{
    [Fact]
    public void LoadsValidModAndCollectsEvents()
    {
        var host = new ModHost();
        var events = host.Load(new("sample.weather", 1, "main.lua"), "emit('weather.changed', 'rain')");
        Assert.Equal(new ModEvent("weather.changed", "rain"), Assert.Single(events));
    }

    [Fact]
    public void RejectsIncompatibleAndInvalidManifests()
    {
        var host = new ModHost();
        Assert.Throws<InvalidOperationException>(() => host.Load(new("x", 2, "main.lua"), ""));
        Assert.Throws<ArgumentException>(() => host.Load(new("../escape", 1, "main.lua"), ""));
        Assert.Throws<ArgumentException>(() => host.Load(new("x", 1, "other.lua"), ""));
    }

    [Fact]
    public void SandboxOmitsFileSystemAndBoundsExecution()
    {
        var host = new ModHost();
        Assert.ThrowsAny<Exception>(() => host.Load(new("x", 1, "main.lua"), "io.open('/etc/passwd')"));
        Assert.Throws<ArgumentException>(() => host.Load(new("x", 1, "main.lua"), "while true do end"));
        Assert.Throws<ArgumentException>(() => host.Load(new("x", 1, "main.lua"), "function loop() end"));
        Assert.Throws<ArgumentException>(() => host.Load(new("x", 1, "main.lua"), new string('a', ModHost.MaxScriptBytes + 1)));
    }
}
