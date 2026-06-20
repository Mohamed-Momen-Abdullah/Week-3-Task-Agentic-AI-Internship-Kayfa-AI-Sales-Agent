import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Define the path to the data directory (relative to this file)
DATA_DIR = Path(__file__).parent.parent / "data"

class KayfaKnowledgeBase:
    """
    In-memory knowledge base for Kayfa courses, roadmaps, and policies.
    This acts as the single source of truth to prevent agent hallucination.
    """
    def __init__(self):
        self.courses: List[Dict[str, Any]] = self._load_json("kayfa_courses.json")
        self.roadmaps: List[Dict[str, Any]] = self._load_json("kayfa_roadmaps.json")
        self.documents: Dict[str, str] = self._load_markdown_docs()

    def _load_json(self, filename: str) -> List[Dict[str, Any]]:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"⚠️ Warning: {filename} not found in {DATA_DIR}")
            return []
        
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_markdown_docs(self) -> Dict[str, str]:
        """Loads all Markdown files into a dictionary keyed by filename."""
        docs = {}
        if not DATA_DIR.exists():
            return docs
            
        for filepath in DATA_DIR.glob("*.md"):
            with open(filepath, "r", encoding="utf-8") as f:
                # Store the content using the filename (without .md) as the key
                docs[filepath.stem] = f.read()
        return docs

    # --- Tool Functions for the Agent ---

    def search_courses(self, query: str, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches the JSON catalog for individual courses."""
        query = query.lower()
        results = []
        
        for course in self.courses:
            # Search across multiple fields for robustness
            search_text = f"{course.get('name', '')} {course.get('summary', '')} {course.get('track', '')}".lower()
            
            if query in search_text:
                if level and course.get('level', '').lower() != level.lower():
                    continue
                results.append(course)
                
        return results

    def search_roadmaps(self, query: str) -> List[Dict[str, Any]]:
        """Searches the JSON catalog for full roadmaps/diplomas."""
        query = query.lower()
        results = []
        
        for roadmap in self.roadmaps:
            search_text = f"{roadmap.get('name', '')} {roadmap.get('skills', '')}".lower()
            if query in search_text:
                results.append(roadmap)
                
        return results

    def get_document_content(self, doc_keyword: str) -> str:
        """
        Fetches text from markdown files (Pricing, FAQs, Sales Pitches).
        Example keywords: 'pricing', 'diploma', 'faq', 'policy'
        """
        doc_keyword = doc_keyword.lower()
        matched_content = []
        
        for filename, content in self.documents.items():
            if doc_keyword in filename.lower():
                matched_content.append(f"--- SOURCE: {filename} ---\n{content}\n")
                
        if not matched_content:
            return f"No document found matching '{doc_keyword}'. Please direct the user to support."
            
        return "\n".join(matched_content)

# Initialize a global instance to be imported and used by the agent context
kayfa_db = KayfaKnowledgeBase()