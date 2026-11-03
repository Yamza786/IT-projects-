using System.Collections.Generic;
using Unity.Netcode;
using UnityEngine;

namespace RelayArena
{
    [RequireComponent(typeof(NetworkObject))]
    public sealed class RelayMatchManager : NetworkBehaviour
    {
        public static RelayMatchManager Instance { get; private set; }

        [SerializeField] private Transform beacon;
        private readonly NetworkVariable<int> blueScore = new(0);
        private readonly NetworkVariable<int> redScore = new(0);
        private readonly NetworkVariable<bool> finished = new(false);
        private readonly Dictionary<ulong, float> lastCaptureByClient = new();
        private float nextTeamCaptureAt;

        public int BlueScore => blueScore.Value;
        public int RedScore => redScore.Value;
        public bool IsFinished => finished.Value;

        public bool IsNearBeacon(Vector3 position)
        {
            return beacon != null && RelayRules.CanCapture(
                Vector3.Distance(position, beacon.position), RelayRules.CaptureRadius);
        }

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        public override void OnNetworkDespawn()
        {
            if (Instance == this) Instance = null;
        }

        public void TryCapture(RelayPlayerMotor player)
        {
            if (!IsServer || finished.Value || player == null || beacon == null ||
                !player.IsSpawned || player.Team < 0 ||
                !IsNearBeacon(player.transform.position))
                return;

            var now = Time.time;
            if (now < nextTeamCaptureAt ||
                (lastCaptureByClient.TryGetValue(player.OwnerClientId, out var previous) &&
                 now - previous < RelayRules.CaptureCooldownSeconds))
                return;

            lastCaptureByClient[player.OwnerClientId] = now;
            nextTeamCaptureAt = now + RelayRules.CaptureCooldownSeconds;
            if (player.Team == 0) blueScore.Value++;
            else redScore.Value++;

            if (blueScore.Value >= RelayRules.PlayersToWin || redScore.Value >= RelayRules.PlayersToWin)
                finished.Value = true;
        }

        public void ResetMatch()
        {
            if (!IsServer) return;
            blueScore.Value = 0;
            redScore.Value = 0;
            finished.Value = false;
            nextTeamCaptureAt = 0f;
            lastCaptureByClient.Clear();
        }
    }
}
