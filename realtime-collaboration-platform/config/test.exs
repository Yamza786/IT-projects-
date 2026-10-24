import Config

config :collab, Collab.Repo,
  url: System.get_env("DATABASE_URL", "ecto://postgres:postgres@localhost/collab_test"),
  pool: Ecto.Adapters.SQL.Sandbox

config :collab, CollabWeb.Endpoint, server: false
