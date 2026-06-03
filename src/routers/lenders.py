from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import json
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lenders", tags=["Lenders"])

# Resolve catalog path relative to the root src directory
CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lenders_catalog.json")

@router.get("", response_model=List[Dict[str, Any]])
async def get_lenders():
    """
    Fetch the list of lender products from the JSON catalog.
    """
    try:
        if not os.path.exists(CATALOG_PATH):
            logger.warning(f"Lenders catalog file not found at {CATALOG_PATH}, returning empty list.")
            return []
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Error reading lenders catalog: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read lenders catalog: {str(e)}")

@router.post("", response_model=Dict[str, str])
async def save_lenders(lenders: List[Dict[str, Any]]):
    """
    Overwrite the lenders catalog JSON file with updated data.
    """
    try:
        # Simple validation: ensure it's a list
        if not isinstance(lenders, list):
            raise HTTPException(status_code=400, detail="Invalid payload: Expected a list of lender products.")
            
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(lenders, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Lenders catalog updated successfully with {len(lenders)} entries.")
        return {"status": "success", "message": f"Catalog updated successfully with {len(lenders)} entries."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error saving lenders catalog: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save lenders catalog: {str(e)}")
