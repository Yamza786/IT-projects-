defmodule Collab.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      Collab.Repo,
      {Phoenix.PubSub, name: Collab.PubSub},
      CollabWeb.Presence,
      CollabWeb.Endpoint
    ]

    Supervisor.start_link(children, strategy: :one_for_one, name: Collab.Supervisor)
  end

  @impl true
  def config_change(changed, _new, removed),
    do: CollabWeb.Endpoint.config_change(changed, removed)
end
