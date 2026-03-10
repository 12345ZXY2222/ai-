
import re
from collections import Counter

def analyze_sources(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Define keywords for venues
    venues = {
        "NeurIPS": ["NeurIPS", "Neural Information Processing Systems"],
        "ICML": ["ICML", "International Conference on Machine Learning"],
        "ICLR": ["ICLR", "International Conference on Learning Representations"],
        "ACL": ["ACL", "Association for Computational Linguistics"],
        "EMNLP": ["EMNLP", "Empirical Methods in Natural Language Processing"],
        "AAAI": ["AAAI", "Association for the Advancement of Artificial Intelligence"],
        "IJCAI": ["IJCAI", "International Joint Conference on Artificial Intelligence"],
        "CVPR": ["CVPR", "Computer Vision and Pattern Recognition"],
        "Nature": ["Nature"],
        "Science": ["Science"],
        "PNAS": ["PNAS", "Proceedings of the National Academy of Sciences"],
        "ArXiv": ["arXiv", "arxiv"],
        "WWW": ["The Web Conference", "WWW"],
        "KDD": ["KDD", "Knowledge Discovery and Data Mining"]
    }

    stats = Counter()
    
    # Read the whole content
    content = content.replace('\n', ' ') # Merge lines to make regex easier
    
    # Split by reference markers like [1], [2], etc.
    # We use a regex lookahead to split but keep the delimiter, or just findall
    # Actually, splitting by `[\d+]` is easier
    refs = re.split(r'\[\d+\]', content)
    
    total_refs = len(refs) - 1 # First element is usually empty or header
    
    for ref in refs:
        if not ref.strip(): continue
        
        matched = False
        for venue, keywords in venues.items():
            for kw in keywords:
                if kw.lower() in ref.lower(): # Case insensitive check
                    stats[venue] += 1
                    matched = True
                    break
            if matched:
                break
        if not matched:
            # print(f"Unmatched: {ref[:50]}...") # Debug
            stats["Other"] += 1

    print(f"Total References Found: {total_refs}")
    print("-" * 30)
    for venue, count in stats.most_common():
        print(f"{venue}: {count}")

if __name__ == "__main__":
    analyze_sources("all_references_extracted.txt")
