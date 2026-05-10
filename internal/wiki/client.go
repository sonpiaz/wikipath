package wiki

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const userAgent = "wikipath/0.1 (https://github.com/sonpiaz/wikipath; learning project)"

const apiBase = "https://en.wikipedia.org/w/api.php"

var httpClient = &http.Client{
	Timeout: 30 * time.Second,
	Transport: &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 10,
		IdleConnTimeout:     90 * time.Second,
	},
}

type linksResponse struct {
	Continue struct {
		Plcontinue string `json:"plcontinue"`
	} `json:"continue"`
	Query struct {
		Pages map[string]struct {
			Title string `json:"title"`
			Links []struct {
				Ns    int    `json:"ns"`
				Title string `json:"title"`
			} `json:"links"`
		} `json:"pages"`
	} `json:"query"`
}

func FetchOutboundLinks(title string) ([]string, error) {
	var all []string
	plcontinue := ""

	for {
		q := url.Values{}
		q.Set("action", "query")
		q.Set("prop", "links")
		q.Set("format", "json")
		q.Set("plnamespace", "0")
		q.Set("pllimit", "max")
		q.Set("titles", title)
		if plcontinue != "" {
			q.Set("plcontinue", plcontinue)
		}

		body, err := getWithRetry(apiBase + "?" + q.Encode())
		if err != nil {
			return nil, err
		}

		var parsed linksResponse
		if err := json.Unmarshal(body, &parsed); err != nil {
			return nil, fmt.Errorf("decode response for %q: %w", title, err)
		}

		for _, page := range parsed.Query.Pages {
			for _, link := range page.Links {
				if link.Ns == 0 {
					all = append(all, link.Title)
				}
			}
		}

		if parsed.Continue.Plcontinue == "" {
			return all, nil
		}
		plcontinue = parsed.Continue.Plcontinue
	}
}

func getWithRetry(reqURL string) ([]byte, error) {
	const maxAttempts = 3
	delay := time.Second

	for attempt := 1; attempt <= maxAttempts; attempt++ {
		req, err := http.NewRequest(http.MethodGet, reqURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("User-Agent", userAgent)
		req.Header.Set("Accept", "application/json")

		resp, err := httpClient.Do(req)
		if err != nil {
			if attempt == maxAttempts {
				return nil, fmt.Errorf("network error after %d attempts: %w", maxAttempts, err)
			}
			time.Sleep(delay)
			delay *= 2
			continue
		}

		ct := resp.Header.Get("Content-Type")
		body, readErr := readAndClose(resp)

		if resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500 {
			if attempt == maxAttempts {
				return nil, fmt.Errorf("status %d after %d attempts", resp.StatusCode, maxAttempts)
			}
			wait := delay
			if resp.StatusCode == http.StatusTooManyRequests {
				wait *= 2
			}
			time.Sleep(wait)
			delay *= 2
			continue
		}

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("status %d for %s", resp.StatusCode, reqURL)
		}

		if !strings.Contains(ct, "application/json") {
			return nil, fmt.Errorf("non-JSON content type %q", ct)
		}

		if readErr != nil {
			return nil, fmt.Errorf("read body: %w", readErr)
		}
		return body, nil
	}

	return nil, fmt.Errorf("retry loop exited unexpectedly")
}

func readAndClose(resp *http.Response) ([]byte, error) {
	defer resp.Body.Close()
	const maxBytes = 16 * 1024 * 1024
	buf := make([]byte, 0, 64*1024)
	tmp := make([]byte, 32*1024)
	for {
		n, err := resp.Body.Read(tmp)
		if n > 0 {
			buf = append(buf, tmp[:n]...)
			if len(buf) > maxBytes {
				return nil, fmt.Errorf("response too large")
			}
		}
		if err != nil {
			if err.Error() == "EOF" {
				return buf, nil
			}
			return buf, err
		}
	}
}
