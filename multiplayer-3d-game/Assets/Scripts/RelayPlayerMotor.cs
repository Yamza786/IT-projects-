using Unity.Netcode;
using Unity.Netcode.Components;
using UnityEngine;

namespace RelayArena
{
    [RequireComponent(typeof(NetworkObject), typeof(NetworkTransform), typeof(CharacterController))]
    public sealed class RelayPlayerMotor : NetworkBehaviour
    {
        [SerializeField, Min(0.1f)] private float moveSpeed = 5f;
        [SerializeField] private Renderer bodyRenderer;

        private readonly NetworkVariable<int> team = new(
            -1, NetworkVariableReadPermission.Everyone, NetworkVariableWritePermission.Server);
        private Vector2 latestInput;
        private float nextInputSendAt;
        private float nextAcceptedInputAt;
        private CharacterController controller;

        public int Team => team.Value;

        public override void OnNetworkSpawn()
        {
            controller = GetComponent<CharacterController>();
            if (IsServer)
            {
                team.Value = RelayRules.TeamForClient(OwnerClientId);
                var lane = (int)(OwnerClientId / 2UL);
                transform.position = new Vector3((team.Value == 0 ? -4f : 4f), 1f, lane * 1.5f);
                controller.enabled = true;
            }
            else
            {
                controller.enabled = false;
            }
            team.OnValueChanged += ApplyTeamColor;
            ApplyTeamColor(-1, team.Value);
            if (IsOwner) RelayCameraFollow.SetTarget(transform);
        }

        public override void OnNetworkDespawn()
        {
            team.OnValueChanged -= ApplyTeamColor;
            if (IsOwner) RelayCameraFollow.ClearTarget(transform);
        }

        private void Update()
        {
            if (!IsOwner || !IsSpawned || RelayMatchManager.Instance == null || RelayMatchManager.Instance.IsFinished)
                return;

            latestInput = new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical"));
            if (Time.unscaledTime >= nextInputSendAt)
            {
                SubmitMovementRpc(RelayRules.ClampInput(latestInput));
                nextInputSendAt = Time.unscaledTime + 0.05f;
            }

            if (Input.GetKeyDown(KeyCode.E) && RelayMatchManager.Instance.IsNearBeacon(transform.position))
                RequestCaptureRpc();
        }

        private void FixedUpdate()
        {
            if (!IsServer || controller == null || !controller.enabled || RelayMatchManager.Instance == null ||
                RelayMatchManager.Instance.IsFinished) return;

            var direction = new Vector3(latestInput.x, 0f, latestInput.y);
            controller.Move(direction * (moveSpeed * Time.fixedDeltaTime));
            if (direction.sqrMagnitude > 0.001f)
                transform.rotation = Quaternion.LookRotation(direction, Vector3.up);
        }

        [Rpc(SendTo.Server, RequireOwnership = true)]
        private void SubmitMovementRpc(Vector2 input)
        {
            if (Time.time < nextAcceptedInputAt) return;
            nextAcceptedInputAt = Time.time + 0.03f;
            latestInput = RelayRules.ClampInput(input);
        }

        [Rpc(SendTo.Server, RequireOwnership = true)]
        private void RequestCaptureRpc()
        {
            RelayMatchManager.Instance?.TryCapture(this);
        }

        private void ApplyTeamColor(int previous, int current)
        {
            if (bodyRenderer == null) return;
            bodyRenderer.material.color = current == 0
                ? new Color(0.2f, 0.55f, 1f)
                : new Color(1f, 0.35f, 0.25f);
        }
    }
}
