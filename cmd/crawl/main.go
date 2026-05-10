package main

import (
	"flag"
	"log"

	"github.com/sonpiaz/wikipath/internal/crawl"
)

func main() {
	seedsPath := flag.String("seeds", "seeds.txt", "path to seed names file")
	out := flag.String("out", "graph.json", "path to write the graph JSON")
	workers := flag.Int("workers", 4, "concurrent workers")
	flag.Parse()

	seeds, set, err := crawl.ReadSeeds(*seedsPath)
	if err != nil {
		log.Fatalf("read seeds: %v", err)
	}
	log.Printf("loaded %d seeds from %s", len(seeds), *seedsPath)

	if err := crawl.Run(seeds, set, *workers, *out); err != nil {
		log.Fatalf("crawl: %v", err)
	}
}
