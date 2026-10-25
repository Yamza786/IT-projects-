namespace UnityEngine;

public readonly struct Vector2(float x, float y)
{
    public float x { get; } = x;
    public float y { get; } = y;
    public float magnitude => MathF.Sqrt((x * x) + (y * y));

    public static Vector2 zero => new(0f, 0f);

    public static Vector2 ClampMagnitude(Vector2 vector, float maxLength)
    {
        var magnitude = vector.magnitude;
        return magnitude > maxLength && magnitude > 0f
            ? new Vector2(vector.x * maxLength / magnitude, vector.y * maxLength / magnitude)
            : vector;
    }
}
