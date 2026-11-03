defmodule CollabWeb.RoomChannelTest do
  use ExUnit.Case, async: false
  import Phoenix.ChannelTest

  alias Collab.{Repo, RoomEvent}
  alias CollabWeb.{RoomChannel, UserSocket}

  @endpoint CollabWeb.Endpoint

  setup do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(Repo)
    Ecto.Adapters.SQL.Sandbox.mode(Repo, {:shared, self()})
    token = Collab.AuthToken.issue("member-1", "room-a")
    {:ok, authenticated_socket} = UserSocket.connect(%{"token" => token}, %Phoenix.Socket{}, %{})
    socket = socket(UserSocket, "user:member-1", authenticated_socket.assigns)
    {:ok, _, socket} = subscribe_and_join(socket, RoomChannel, "room:room-a")
    %{socket: socket}
  end

  test "persists and broadcasts a bounded message", %{socket: socket} do
    client_id = Ecto.UUID.generate()
    ref = push(socket, "message", %{"body" => "hello room", "client_event_id" => client_id})
    assert_reply ref, :ok, %{accepted: true}
    assert_broadcast "message", %{body: "hello room", user_id: "member-1", room_id: "room-a"}
    assert Repo.aggregate(RoomEvent, :count) == 1
  end

  test "requires authentication and denies joining a different room" do
    assert :error = UserSocket.connect(%{}, %Phoenix.Socket{}, %{})
    token = Collab.AuthToken.issue("member-1", "room-a")
    {:ok, authenticated_socket} = UserSocket.connect(%{"token" => token}, %Phoenix.Socket{}, %{})
    socket = socket(UserSocket, "user:member-1", authenticated_socket.assigns)

    assert {:error, %{reason: "not_authorized"}} =
             subscribe_and_join(socket, RoomChannel, "room:room-b")
  end

  test "rejects blank and oversized messages", %{socket: socket} do
    for body <- ["  ", String.duplicate("x", 4_001)] do
      ref = push(socket, "message", %{"body" => body, "client_event_id" => Ecto.UUID.generate()})
      assert_reply ref, :error, %{reason: "invalid_body"}
    end

    assert Repo.aggregate(RoomEvent, :count) == 0
  end

  test "retries with the same event ID do not create duplicate durable events", %{socket: socket} do
    client_id = Ecto.UUID.generate()

    for body <- ["first send", "retry with changed content"] do
      ref = push(socket, "message", %{"body" => body, "client_event_id" => client_id})
      assert_reply ref, :ok, %{accepted: true}
    end

    assert Repo.aggregate(RoomEvent, :count) == 1
  end
end
