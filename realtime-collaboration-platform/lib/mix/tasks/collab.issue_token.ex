defmodule Mix.Tasks.Collab.IssueToken do
  use Mix.Task

  @shortdoc "Issues a short-lived token scoped to one user and room"

  @impl Mix.Task
  def run([user_id, room_id]) do
    if byte_size(user_id) not in 1..96 or byte_size(room_id) not in 1..96 do
      Mix.raise("user and room IDs must be 1..96 bytes")
    end

    Mix.Task.run("app.start")
    Mix.shell().info(Collab.AuthToken.issue(user_id, room_id))
  end

  def run(_), do: Mix.raise("usage: mix collab.issue_token USER_ID ROOM_ID")
end
