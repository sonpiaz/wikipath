package crawl

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sort"
	"sync"

	"github.com/sonpiaz/wikipath/internal/wiki"
)

type result struct {
	name      string
	neighbors []string
	err       error
}

func ReadSeeds(path string) ([]string, map[string]bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, nil, err
	}
	defer f.Close()

	var seeds []string
	set := make(map[string]bool)
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}
		seeds = append(seeds, line)
		set[line] = true
	}
	if err := scanner.Err(); err != nil {
		return nil, nil, err
	}
	return seeds, set, nil
}

func Run(seeds []string, set map[string]bool, workers int, outPath string) error {
	jobs := make(chan string, 64)
	results := make(chan result, 64)
	var wg sync.WaitGroup

	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for name := range jobs {
				links, err := wiki.FetchOutboundLinks(name)
				if err != nil {
					results <- result{name: name, err: err}
					continue
				}
				var filtered []string
				seen := make(map[string]bool)
				for _, link := range links {
					if !set[link] || seen[link] || link == name {
						continue
					}
					seen[link] = true
					filtered = append(filtered, link)
				}
				results <- result{name: name, neighbors: filtered}
			}
		}(i)
	}

	go func() {
		for _, name := range seeds {
			jobs <- name
		}
		close(jobs)
	}()

	go func() {
		wg.Wait()
		close(results)
	}()

	graph := make(map[string][]string)
	processed := 0
	failures := 0
	total := len(seeds)
	for r := range results {
		processed++
		if r.err != nil {
			failures++
			log.Printf("[%d/%d] %s: %v", processed, total, r.name, r.err)
			graph[r.name] = nil
			continue
		}
		sort.Strings(r.neighbors)
		graph[r.name] = r.neighbors
		log.Printf("[%d/%d] %s -> %d neighbors", processed, total, r.name, len(r.neighbors))
	}

	for _, name := range seeds {
		if _, ok := graph[name]; !ok {
			graph[name] = nil
		}
	}

	data, err := json.MarshalIndent(graph, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal graph: %w", err)
	}
	if err := os.WriteFile(outPath, data, 0o644); err != nil {
		return fmt.Errorf("write %s: %w", outPath, err)
	}

	log.Printf("done: %d processed (%d failures), wrote %s", processed, failures, outPath)
	return nil
}
