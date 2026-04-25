"""
Process raw knowledge base files into formatted, ready-to-embed documents
"""

import json
import os
import stat
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _validate_scenario_schema(scenario: dict) -> bool:
    """
    Validate scenario has required fields.
    
    Args:
        scenario: Scenario dictionary to validate
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = {'id', 'title', 'content'}
    return all(field in scenario and scenario[field] for field in required_fields)

def _validate_faq_schema(faq: dict) -> bool:
    """
    Validate FAQ has required fields.
    
    Args:
        faq: FAQ dictionary to validate
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = {'id', 'question', 'answer'}
    return all(field in faq and faq[field] for field in required_fields)

def _set_secure_permissions(file_path: Path):
    """
    Set restrictive file permissions (0o600 - owner read/write only).
    
    Args:
        file_path: Path to file to secure
    """
    try:
        os.chmod(str(file_path), stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        logger.debug(f"Set secure permissions on {file_path}")
    except Exception as e:
        logger.warning(f"Could not set permissions on {file_path}: {e}")

class DataProcessor:
    def __init__(self):
        self.raw_dir = Path("src/data/raw")
        self.processed_dir = Path("src/data/processed")
        
        # Create processed directory if it doesn't exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
    
    def process_scenarios(self):
        """Process raw scenarios into formatted documents."""
        raw_file = self.raw_dir / "scenarios_raw.json"
        processed_file = self.processed_dir / "scenarios.json"
        
        if not raw_file.exists():
            logger.warning(f"Raw scenarios file not found: {raw_file}")
            return []
        
        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_scenarios = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in scenarios file: {e}")
            return []
        
        processed_scenarios = []
        for scenario in raw_scenarios:
            # Validate schema
            if not _validate_scenario_schema(scenario):
                logger.warning(f"Invalid scenario schema, skipping: {scenario.get('id', 'unknown')}")
                continue
            
            processed = {
                "id": scenario.get("id"),
                "title": scenario.get("title"),
                "content": scenario.get("content"),
                "category": scenario.get("category"),
                "severity": scenario.get("severity"),
                "keywords": self._extract_keywords(
                    f"{scenario.get('title')} {scenario.get('content')}"
                ),
                "processed_at": datetime.utcnow().isoformat()
            }
            processed_scenarios.append(processed)
        
        try:
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_scenarios, f, indent=2, ensure_ascii=False)
            
            # Set secure permissions on the file
            _set_secure_permissions(processed_file)
            
            logger.info(f"Processed {len(processed_scenarios)} scenarios")
            return processed_scenarios
        except IOError as e:
            logger.error(f"Error writing processed scenarios: {e}")
            return []
    
    def process_faqs(self):
        """Process raw FAQs into formatted documents."""
        raw_file = self.raw_dir / "faqs_raw.json"
        processed_file = self.processed_dir / "faqs.json"
        
        if not raw_file.exists():
            logger.warning(f"Raw FAQs file not found: {raw_file}")
            return []
        
        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_faqs = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in FAQs file: {e}")
            return []
        
        processed_faqs = []
        for faq in raw_faqs:
            # Validate schema
            if not _validate_faq_schema(faq):
                logger.warning(f"Invalid FAQ schema, skipping: {faq.get('id', 'unknown')}")
                continue
            
            processed = {
                "id": faq.get("id"),
                "question": faq.get("question"),
                "answer": faq.get("answer"),
                "category": faq.get("category", "general"),
                "tags": faq.get("tags", []),
                "processed_at": datetime.utcnow().isoformat()
            }
            processed_faqs.append(processed)
        
        try:
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_faqs, f, indent=2, ensure_ascii=False)
            
            # Set secure permissions on the file
            _set_secure_permissions(processed_file)
            
            logger.info(f"Processed {len(processed_faqs)} FAQs")
            return processed_faqs
        except IOError as e:
            logger.error(f"Error writing processed FAQs: {e}")
            return []
    
    def process_system_prompt(self):
        """Process raw system prompt."""
        raw_file = self.raw_dir / "system_prompt_raw.md"
        processed_file = self.processed_dir / "system_prompt.md"
        
        if not raw_file.exists():
            logger.warning(f"Raw system prompt not found: {raw_file}")
            return None
        
        try:
            with open(raw_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            processed_content = content.strip()
            
            with open(processed_file, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            # Set secure permissions on the file
            _set_secure_permissions(processed_file)
            
            logger.info("Processed system prompt")
            return processed_content
        except IOError as e:
            logger.error(f"Error processing system prompt: {e}")
            return None
    
    def process_all(self):
        """Process all raw data into processed format."""
        logger.info("Starting data processing...")
        
        self.process_scenarios()
        self.process_faqs()
        self.process_system_prompt()
        
        logger.info("Data processing complete!")
    
    @staticmethod
    def _extract_keywords(text: str, limit: int = 10):
        """Extract keywords from text."""
        words = text.lower().split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w.strip('.,!?;:') for w in words 
                   if len(w) > 3 and w not in stop_words]
        return list(set(keywords))[:limit]

if __name__ == "__main__":
    processor = DataProcessor()
    processor.process_all() 