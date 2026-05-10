package main

import (
	"embed"
	"flag"
	"io/fs"
	"log"
	"net/http"
	"os"

	"github.com/sonpiaz/wikipath/internal/graph"
	"github.com/sonpiaz/wikipath/internal/server"
)

//go:embed all:web
var embedded embed.FS

func main() {
	graphPath := flag.String("graph", "graph.json", "path to graph JSON")
	addr := flag.String("addr", ":8080", "listen address")
	flag.Parse()

	if env := os.Getenv("PORT"); env != "" {
		*addr = ":" + env
	}

	g, err := graph.Load(*graphPath)
	if err != nil {
		log.Fatalf("load graph: %v", err)
	}
	log.Printf("loaded graph: %d nodes", len(g))

	webFS, err := fs.Sub(embedded, "web")
	if err != nil {
		log.Fatalf("sub fs: %v", err)
	}

	s := server.New(g, webFS)
	log.Printf("listening on %s", *addr)
	log.Fatal(http.ListenAndServe(*addr, s.Routes()))
}
