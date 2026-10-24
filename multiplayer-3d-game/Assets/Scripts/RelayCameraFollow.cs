using UnityEngine;

namespace RelayArena
{
    public sealed class RelayCameraFollow : MonoBehaviour
    {
        [SerializeField, Min(0.1f)] private float distance = 8f;
        [SerializeField, Min(0.1f)] private float height = 6f;
        [SerializeField, Min(0.1f)] private float smoothTime = 0.12f;
        private static Transform target;
        private Vector3 velocity;

        public static void SetTarget(Transform player)
        {
            target = player;
        }

        public static void ClearTarget(Transform player)
        {
            if (target == player) target = null;
        }

        private void LateUpdate()
        {
            if (target == null) return;
            var desired = target.position + new Vector3(0f, height, -distance);
            transform.position = Vector3.SmoothDamp(transform.position, desired, ref velocity, smoothTime);
            transform.LookAt(target.position + Vector3.up);
        }
    }
}
