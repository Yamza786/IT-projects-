defmodule Collab.RoomEvent do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id
  schema "room_events" do
    field :room_id, :string
    field :user_id, :string
    field :kind, :string
    field :body, :string
    field :client_event_id, :binary_id
    timestamps(type: :utc_datetime_usec, updated_at: false)
  end

  def changeset(event, attrs) do
    event
    |> cast(attrs, [:room_id, :user_id, :kind, :body, :client_event_id])
    |> validate_required([:room_id, :user_id, :kind, :body, :client_event_id])
    |> validate_length(:room_id, min: 1, max: 96)
    |> validate_length(:user_id, min: 1, max: 96)
    |> validate_length(:kind, is: 7)
    |> validate_inclusion(:kind, ["message"])
    |> validate_length(:body, min: 1, max: 4_000)
    |> validate_change(:body, fn :body, body ->
      if String.contains?(body, <<0>>), do: [body: "may not contain NUL"], else: []
    end)
    |> unique_constraint([:room_id, :user_id, :client_event_id], name: :room_events_client_id_unique)
  end
end
