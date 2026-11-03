defmodule CollabWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :collab

  socket "/socket", CollabWeb.UserSocket,
    websocket: [connect_info: [:peer_data]],
    longpoll: false

  plug Plug.RequestId
  plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]
  plug Plug.Parsers, parsers: [:urlencoded, :multipart, :json], pass: ["*/*"], json_decoder: Jason
  plug Plug.MethodOverride
  plug Plug.Head
  plug CollabWeb.Router
end
