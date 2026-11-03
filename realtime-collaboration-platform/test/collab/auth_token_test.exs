defmodule Collab.AuthTokenTest do
  use ExUnit.Case, async: true

  test "signed room token carries the scoped identity" do
    token = Collab.AuthToken.issue("member-1", "room-7")
    assert {:ok, %{user_id: "member-1", room_id: "room-7"}} = Collab.AuthToken.verify(token)
    assert {:error, _} = Collab.AuthToken.verify(token <> "tampered")
  end

  test "non-token values are rejected" do
    assert {:error, :invalid_token} = Collab.AuthToken.verify(nil)
  end
end
