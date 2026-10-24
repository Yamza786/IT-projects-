defmodule Collab.MixProject do
  use Mix.Project

  def project do
    [app: :collab, version: "0.1.0", elixir: "~> 1.16", start_permanent: Mix.env() == :prod, deps: deps()]
  end

  def application do
    [extra_applications: [:logger, :runtime_tools], mod: {Collab.Application, []}]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7.14"},
      {:phoenix_ecto, "~> 4.6"},
      {:ecto_sql, "~> 3.12"},
      {:postgrex, "~> 0.19"},
      {:plug_cowboy, "~> 2.7"},
      {:jason, "~> 1.4"},
      {:phoenix_pubsub, "~> 2.1"}
    ]
  end
end
