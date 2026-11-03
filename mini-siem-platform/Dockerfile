FROM node:24-alpine AS ui-build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src/ui.ts ./src/ui.ts
COPY src/api/web ./src/api/web
RUN npm run build

FROM golang:1.23-alpine AS service-build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY src ./src
COPY --from=ui-build /src/src/api/web/app.js ./src/api/web/app.js
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/siem ./cmd/siem

FROM alpine:3.21
RUN addgroup -S siem && adduser -S -G siem siem && mkdir -p /var/lib/siem && chown siem:siem /var/lib/siem
COPY --from=service-build /out/siem /usr/local/bin/siem
ENV SIEM_BIND=0.0.0.0:8090 SIEM_DATA_FILE=/var/lib/siem/events.jsonl
USER siem
EXPOSE 8090
VOLUME ["/var/lib/siem"]
ENTRYPOINT ["/usr/local/bin/siem"]
