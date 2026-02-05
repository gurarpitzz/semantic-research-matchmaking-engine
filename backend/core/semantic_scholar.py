import requests
import os
import time

class SemanticScholarClient:
    def __init__(self):
        self.api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.headers = {"x-api-key": self.api_key} if self.api_key else {}

    def get_author_papers(self, author_name, university=None, limit=30):
        # Clean name (remove titles, suffixes)
        clean_name = author_name.split(',')[0].strip()
        
        # Strategy: 1. Try with University, 2. Fallback to just name
        queries = [f"{clean_name} {university}" if university else clean_name, clean_name]
        
        for query in queries:
            for attempt in range(2): # 2 attempts per query strategy
                try:
                    search_url = f"{self.base_url}/author/search?query={query}&limit=3&fields=authorId,name,papers.paperId,papers.title,papers.abstract,papers.year,papers.citationCount,papers.url"
                    
                    response = requests.get(search_url, headers=self.headers, timeout=10)
                    
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 10))
                        time.sleep(retry_after + (attempt * 5))
                        continue
                        
                    response.raise_for_status()
                    data = response.json()
                    
                    if not data.get('data'):
                        break # Try next query strategy
                        
                    # Find the best author match (simple name match)
                    authors = data['data']
                    best_papers = []
                    
                    for author in authors:
                        papers = author.get('papers', [])
                        if papers:
                            best_papers = papers
                            break # Take the first author that actually has papers
                    
                    if best_papers:
                        return best_papers[:limit]
                    
                    break # Try next query if no papers in any of these authors
                except Exception as e:
                    print(f"⚠️ Error fetching papers (Query: {query}, Attempt: {attempt+1}): {e}")
                    time.sleep(2)
        return []

# Global client instance
ss_client = SemanticScholarClient()
