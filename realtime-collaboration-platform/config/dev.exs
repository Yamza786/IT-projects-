import Config

config :collab, Collab.Repo, url: System.get_env("DATABASE_URL", "ecto://postgres:postgres@localhost/collab_dev")
config :collab, CollabWeb.Endpoint, http: [ip: {127, 0, 0, 1}, port: 4000], server: true
