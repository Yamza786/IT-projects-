defmodule CollabWeb.UserSocket do
  use Phoenix.Socket

  channel "room:*", CollabWeb.RoomChannel

  @impl true
  def connect(%{"token" => token}, socket, _connect_info) do
    case Collab.AuthToken.verify(token) do
      {:ok, %{user_id: user_id, room_id: room_id}} ->
        {:ok, assign(socket, :identity, %{user_id: user_id, room_id: room_id})}
      _ -> :error
    end
  end

  def connect(_params, _socket, _connect_info), do: :error

  @impl true
  def id(%Phoenix.Socket{assigns: %{identity: %{user_id: user_id}}}), do: "user:#{user_id}"
  def id(_socket), do: nil
end
