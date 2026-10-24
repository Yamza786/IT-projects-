defmodule Collab.AuthToken do
  @salt "room auth"
  @max_age 3_600

  def issue(user_id, room_id) when is_binary(user_id) and is_binary(room_id) do
    Phoenix.Token.sign(CollabWeb.Endpoint, @salt, %{user_id: user_id, room_id: room_id})
  end

  def verify(token) when is_binary(token) do
    Phoenix.Token.verify(CollabWeb.Endpoint, @salt, token, max_age: @max_age)
  end

  def verify(_), do: {:error, :invalid_token}
end
