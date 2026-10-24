defmodule CollabWeb.HealthController do
  use Phoenix.Controller, formats: [:json]

  def show(conn, _params), do: json(conn, %{status: "ok"})
end

defmodule CollabWeb.ErrorJSON do
  def render(template, _assigns),
    do: %{errors: %{detail: Phoenix.Controller.status_message_from_template(template)}}
end
