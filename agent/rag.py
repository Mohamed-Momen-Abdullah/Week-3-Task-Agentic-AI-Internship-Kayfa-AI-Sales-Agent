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
                docs[filepath.stem] = f.read()
        return docs

    # --- Tool Functions for the Agent ---

    def search_courses(self, query: str, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches the JSON catalog for individual courses."""
        query = query.lower()
        results = []
        for course in self.courses:
            track_text = " ".join(course.get('track', []))
            search_text = f"{course.get('name', '')} {course.get('summary', '')} {track_text}".lower()
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
            track_text = " ".join(roadmap.get('track', []))
            skills_text = " ".join(roadmap.get('skills', []))
            search_text = f"{roadmap.get('name', '')} {skills_text} {track_text}".lower()
            if query in search_text:
                results.append(roadmap)
        return results

    def get_document_content(self, doc_keyword: str) -> str:
        """
        Fetches text from markdown files (Pricing, FAQs, Sales Pitches).
        If multiple documents match a broad keyword, it forces the agent to be specific.
        """
        doc_keyword = doc_keyword.lower()
        matched_files = [fname for fname in self.documents.keys() if doc_keyword in fname.lower()]
                
        if not matched_files:
            return (
                "SYSTEM CRITICAL ERROR: No document found in the database. "
                "RULE OVERRIDE: Do not attempt to answer the question using outside knowledge. "
                "You MUST reply that you do not have the specific details and offer to connect them with a human agent."
            )
               
        if len(matched_files) > 1 and doc_keyword in ['diploma', 'track', 'course']:
            return f"SYSTEM ALERT: Multiple documents found ({', '.join(matched_files)}). To save tokens, DO NOT guess. Ask the user to clarify which specific diploma or track they mean, then call this tool again with the specific name."
            
        content = self.documents[matched_files[0]]
        return f"--- SOURCE: {matched_files[0]} ---\n{content}\n"


# Initialize a global instance to be imported and used by the agent context
kayfa_db = KayfaKnowledgeBase()