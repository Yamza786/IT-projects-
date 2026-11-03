import Config

config :collab,
  ecto_repos: [Collab.Repo],
  generators: [timestamp_type: :utc_datetime_usec]

config :collab, CollabWeb.Endpoint,
  url: [host: "localhost"],
  render_errors: [formats: [json: CollabWeb.ErrorJSON], layout: false],
  pubsub_server: Collab.PubSub,
  server: false,
  secret_key_base: String.duplicate("development-only-change-me-", 4)

config :phoenix, :json_library, Jason

import_config "#{config_env()}.exs"
