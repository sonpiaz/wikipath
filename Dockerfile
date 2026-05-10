FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/wikipath-serve ./cmd/serve

FROM scratch
WORKDIR /app
COPY --from=builder /out/wikipath-serve /app/wikipath-serve
COPY graph.json /app/graph.json
EXPOSE 8080
ENV PORT=8080
ENTRYPOINT ["/app/wikipath-serve"]
