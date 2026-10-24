using Unity.Netcode;
using Unity.Netcode.Transports.UTP;
using UnityEngine;

namespace RelayArena
{
    public sealed class RelaySessionHud : MonoBehaviour
    {
        private string address = "127.0.0.1";
        private ushort port = 7777;
        private string status = "Start a host, or connect to a host on your local network.";

        private void OnGUI()
        {
            GUILayout.BeginArea(new Rect(16, 16, 360, 260), GUI.skin.box);
            GUILayout.Label("RELAY ARENA", GUI.skin.GetStyle("boldLabel"));
            var manager = NetworkManager.Singleton;

            if (manager == null || !manager.IsListening)
            {
                GUILayout.Label("Host address");
                address = GUILayout.TextField(address);
                GUILayout.Label("UDP port");
                ushort.TryParse(GUILayout.TextField(port.ToString()), out port);
                if (GUILayout.Button("Host local match")) StartHost();
                if (GUILayout.Button("Join host")) StartClient();
            }
            else
            {
                GUILayout.Label(manager.IsHost ? "Hosting" : "Connected");
                GUILayout.Label($"Players: {manager.ConnectedClientsIds.Count}");
                var match = RelayMatchManager.Instance;
                if (match != null)
                {
                    GUILayout.Label($"Blue {match.BlueScore} : {match.RedScore} Red");
                    GUILayout.Label(match.IsFinished ? "Match finished — first to 3 captures" : "Move: WASD / arrows   Capture: E");
                    if (manager.IsServer && match.IsFinished && GUILayout.Button("Play again")) match.ResetMatch();
                }
                if (GUILayout.Button("Disconnect"))
                {
                    manager.Shutdown();
                    status = "Disconnected.";
                }
            }

            GUILayout.Label(status, GUI.skin.GetStyle("wordWrappedLabel"));
            GUILayout.EndArea();
        }

        private void StartHost()
        {
            var manager = NetworkManager.Singleton;
            if (manager == null || manager.NetworkConfig.NetworkTransport is not UnityTransport transport)
            {
                status = "Add UnityTransport to the scene NetworkManager.";
                return;
            }
            transport.SetConnectionData(address.Trim(), port, "0.0.0.0");
            status = manager.StartHost()
                ? "Host started and listening for LAN clients."
                : "Host could not start. Check the scene NetworkManager, player prefab and UDP port.";
        }

        private void StartClient()
        {
            var manager = NetworkManager.Singleton;
            if (manager == null || manager.NetworkConfig.NetworkTransport is not UnityTransport transport)
            {
                status = "Add UnityTransport to the scene NetworkManager.";
                return;
            }
            transport.SetConnectionData(address.Trim(), port);
            status = manager.StartClient() ? "Connecting…" : "Client could not start.";
        }
    }
}
