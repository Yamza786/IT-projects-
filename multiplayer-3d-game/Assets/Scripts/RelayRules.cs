using UnityEngine;

namespace RelayArena
{
    public static class RelayRules
    {
        public const int PlayersToWin = 3;
        public const float CaptureRadius = 2.25f;
        public const float CaptureCooldownSeconds = 2.5f;
        public const float MaximumInputMagnitude = 1f;

        public static bool CanCapture(float distance, float radius)
        {
            return IsFinite(distance) && IsFinite(radius) && distance >= 0f && radius > 0f && distance <= radius;
        }

        public static Vector2 ClampInput(Vector2 input)
        {
            if (!IsFinite(input.x) || !IsFinite(input.y)) return Vector2.zero;
            return Vector2.ClampMagnitude(input, MaximumInputMagnitude);
        }

        public static int TeamForClient(ulong clientId)
        {
            return (int)(clientId % 2UL);
        }

        private static bool IsFinite(float value)
        {
            return !float.IsNaN(value) && !float.IsInfinity(value);
        }
    }
}
