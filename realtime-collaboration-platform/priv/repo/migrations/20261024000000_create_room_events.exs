defmodule Collab.Repo.Migrations.CreateRoomEvents do
  use Ecto.Migration

  def change do
    create table(:room_events, primary_key: false) do
      add :id, :uuid, primary_key: true
      add :room_id, :string, null: false, size: 96
      add :user_id, :string, null: false, size: 96
      add :kind, :string, null: false, size: 16
      add :body, :text, null: false
      add :client_event_id, :uuid, null: false
      add :inserted_at, :utc_datetime_usec, null: false, default: fragment("CURRENT_TIMESTAMP")
    end

    create constraint(:room_events, :room_events_kind_check, check: "kind IN ('message')")
    create constraint(:room_events, :room_events_body_size_check, check: "char_length(body) BETWEEN 1 AND 4000")
    create unique_index(:room_events, [:room_id, :user_id, :client_event_id], name: :room_events_client_id_unique)
    create index(:room_events, [:room_id, :inserted_at, :id])
  end
end
