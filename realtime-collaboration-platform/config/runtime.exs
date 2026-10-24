import Config

if config_env() == :prod do
  secret = System.get_env("COLLAB_SECRET_KEY_BASE") || raise "COLLAB_SECRET_KEY_BASE is required"
  database_url = System.get_env("DATABASE_URL") || raise "DATABASE_URL is required"
  port = String.to_integer(System.get_env("PORT", "4000"))

  config :collab, Collab.Repo,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE", "10"))

  config :collab, CollabWeb.Endpoint,
    secret_key_base: secret,
    http: [ip: {0, 0, 0, 0}, port: port],
    server: true
end
