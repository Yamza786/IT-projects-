defmodule CollabWeb.Router do
  use Phoenix.Router

  get "/health", CollabWeb.HealthController, :show
end
