defmodule CollabWeb.RoomChannel do
  use Phoenix.Channel
  import Ecto.Query
  alias Collab.{Repo, RoomEvent}
  alias CollabWeb.Presence

  @impl true
  def join("room:" <> room_id, _payload, socket) do
    identity = socket.assigns.identity

    if room_id == identity.room_id do
      send(self(), :after_join)
      {:ok, assign(socket, :room_id, room_id)}
    else
      {:error, %{reason: "not_authorized"}}
    end
  end

  @impl true
  def handle_info(:after_join, socket) do
    topic = "room:" <> socket.assigns.room_id
    user_id = socket.assigns.identity.user_id
    {:ok, _} = Presence.track(self(), topic, user_id, %{online_at: System.system_time(:second)})
    push(socket, "presence_state", Presence.list(topic))

    recent =
      from(event in RoomEvent,
        where: event.room_id == ^socket.assigns.room_id,
        order_by: [desc: event.inserted_at, desc: event.id],
        limit: 50
      )
      |> Repo.all()
      |> Enum.reverse()
      |> Enum.map(&serialize/1)

    push(socket, "history", %{events: recent})
    {:noreply, socket}
  end

  @impl true
  def handle_in("message", payload, socket) do
    with {:ok, body} <- validate_body(payload),
         {:ok, client_event_id} <- validate_event_id(payload),
         {:ok, event} <- persist_message(socket, body, client_event_id) do
      broadcast!(socket, "message", serialize(event))
      {:reply, {:ok, %{id: event.id, accepted: true}}, socket}
    else
      {:error, reason} -> {:reply, {:error, %{reason: reason}}, socket}
    end
  end

  defp validate_body(%{"body" => body}) when is_binary(body) do
    clean = String.trim(body)
    if clean != "" and byte_size(clean) <= 4_000, do: {:ok, clean}, else: {:error, "invalid_body"}
  end

  defp validate_body(_), do: {:error, "invalid_body"}

  defp validate_event_id(%{"client_event_id" => id}) when is_binary(id) do
    case Ecto.UUID.cast(id) do
      {:ok, uuid} -> {:ok, uuid}
      :error -> {:error, "invalid_client_event_id"}
    end
  end

  defp validate_event_id(_), do: {:error, "invalid_client_event_id"}

  defp persist_message(socket, body, client_event_id) do
    identity = socket.assigns.identity

    attrs = %{
      room_id: socket.assigns.room_id,
      user_id: identity.user_id,
      kind: "message",
      body: body,
      client_event_id: client_event_id
    }

    case Repo.insert(RoomEvent.changeset(%RoomEvent{}, attrs)) do
      {:ok, event} ->
        {:ok, event}

      {:error, %Ecto.Changeset{errors: errors}} ->
        if Keyword.has_key?(errors, :client_event_id),
          do: find_duplicate(attrs),
          else: {:error, "invalid_message"}
    end
  end

  defp find_duplicate(attrs) do
    case Repo.get_by(RoomEvent,
           room_id: attrs.room_id,
           user_id: attrs.user_id,
           client_event_id: attrs.client_event_id
         ) do
      nil -> {:error, "message_not_saved"}
      event -> {:ok, event}
    end
  end

  defp serialize(event),
    do: %{
      id: event.id,
      room_id: event.room_id,
      user_id: event.user_id,
      kind: event.kind,
      body: event.body,
      inserted_at: event.inserted_at
    }
end
