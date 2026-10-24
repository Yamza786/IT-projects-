defmodule Collab.RoomEventTest do
  use ExUnit.Case, async: true

  test "event schema bounds fields and rejects NUL content" do
    attrs = %{
      room_id: "room-a",
      user_id: "member-a",
      kind: "message",
      body: "hello",
      client_event_id: Ecto.UUID.generate()
    }
    assert Collab.RoomEvent.changeset(%Collab.RoomEvent{}, attrs).valid?
    refute Collab.RoomEvent.changeset(%Collab.RoomEvent{}, %{attrs | body: "bad" <> <<0>>}).valid?

    refute Collab.RoomEvent.changeset(%Collab.RoomEvent{}, %{
             attrs
             | body: String.duplicate("x", 4_001)
           }).valid?
  end
end
