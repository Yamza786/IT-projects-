using RelayArena;
using UnityEngine;

var checks = 0;
Check(RelayRules.CanCapture(0f, 2.25f), "capture accepts the beacon center");
Check(RelayRules.CanCapture(2.25f, 2.25f), "capture accepts the radius boundary");
Check(!RelayRules.CanCapture(2.26f, 2.25f), "capture rejects out-of-range positions");
Check(!RelayRules.CanCapture(-1f, 2.25f), "capture rejects negative distances");
Check(!RelayRules.CanCapture(float.NaN, 2.25f), "capture rejects NaN distances");
Check(!RelayRules.CanCapture(1f, float.PositiveInfinity), "capture rejects infinite radii");
Check(!RelayRules.CanCapture(1f, 0f), "capture rejects a zero radius");

var clamped = RelayRules.ClampInput(new Vector2(3f, 4f));
Check(MathF.Abs(clamped.magnitude - 1f) < 0.0001f, "movement input is clamped to unit magnitude");
Check(MathF.Abs(clamped.x - 0.6f) < 0.0001f && MathF.Abs(clamped.y - 0.8f) < 0.0001f,
    "clamped movement preserves direction");
var invalid = RelayRules.ClampInput(new Vector2(float.NaN, 1f));
Check(invalid.x == 0f && invalid.y == 0f, "non-finite movement input becomes zero");
Check(RelayRules.TeamForClient(0) == 0 && RelayRules.TeamForClient(1) == 1 &&
      RelayRules.TeamForClient(2) == 0, "teams are assigned deterministically");

Console.WriteLine($"Passed {checks} RelayRules checks.");

void Check(bool condition, string name)
{
    if (!condition) throw new InvalidOperationException($"FAIL: {name}");
    checks++;
    Console.WriteLine($"PASS: {name}");
}
