FROM hexpm/elixir:1.17.3-erlang-27.2-alpine AS build
WORKDIR /app
RUN apk add --no-cache build-base
RUN mix local.hex --force && mix local.rebar --force
COPY mix.exs .formatter.exs ./
RUN mix deps.get
COPY config config
COPY lib lib
COPY priv priv
RUN MIX_ENV=dev mix compile

FROM hexpm/elixir:1.17.3-erlang-27.2-alpine
WORKDIR /app
ENV MIX_ENV=dev
COPY --from=build /app/_build /app/_build
COPY --from=build /app/deps /app/deps
COPY mix.exs .formatter.exs ./
COPY config config
COPY lib lib
COPY priv priv
USER 10001:10001
EXPOSE 4000
CMD ["sh", "-c", "mix ecto.migrate && mix run --no-halt"]
