from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Query, Depends
from typing import Optional
from app.services.ingest import ingest_pdf
from app.services.multimodal_ingest import ingest_multimodal_pdf
from app.services.text_only_ingest import ingest_text_only_pdf
from app.services.pdf_complexity_analyzer import (
    analyze_pdf_complexity, 
    get_recommended_settings
)
from app.core.auth import validate_api_key
from app.logger import setup_logger
from app.database_service.db_service import load_chat_from_db, save_chat_to_db

logger = setup_logger()

router = APIRouter(dependencies=[Depends(validate_api_key)])


@router.post("/pdf/auto")
async def upload_pdf_auto(
    file: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    preset: str = Query("balanced", description="Processing preset: 'speed_first', 'balanced', or 'quality_first'")
):
    """
    Smart auto-detection upload - analyzes PDF and chooses optimal mode
    
    Presets:
    - 'speed_first': Prioritize speed, use text mode for most docs
    - 'balanced': Balance speed and quality (default)
    - 'quality_first': Prioritize quality, use multimodal when possible
    
    This is the RECOMMENDED endpoint - it automatically optimizes based on content!
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Auth required")
    
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    
    filename = filename.lower()
    # Read file contents
    contents = await file.read()
    
    # print("received user_id:", user_id)
    # Validate preset
    if preset not in ["speed_first", "balanced", "quality_first"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid preset. Use 'speed_first', 'balanced', or 'quality_first'"
        )
    
    try:
        # Analyze PDF and get recommendations
        recommendations = get_recommended_settings(contents, preset=preset)
        
        mode = recommendations["mode"]
        max_images = recommendations["max_images"]
        
        logger.info(f"\n🔍 PDF Analysis for {filename}:")
        logger.info(f"   Complexity: {recommendations['complexity_score']}/100")
        logger.info(f"   Analysis: {recommendations['analysis']}")
        logger.info(f"   Recommended: {mode} mode with max_images={max_images}")
        logger.info(f"   Estimated time: {recommendations['estimated_time']}")
        
        # Process based on recommended mode
        if mode == "text":
            result = ingest_text_only_pdf(contents, user_id, filename)
        elif mode == "fast":
            result = ingest_multimodal_pdf(
                contents, user_id, filename,
                max_images=max_images,
                fast_mode=True
            )
        else:  # full
            result = ingest_multimodal_pdf(
                contents, user_id, filename,
                max_images=max_images,
                fast_mode=False
            )

        uploaded_filename = filename  # or wherever you get the filename
        normalized_name = uploaded_filename.lower()

        # Check if chat history already exists
        existing_chat = await load_chat_from_db(user_id, normalized_name)

        if not existing_chat:
            # Only create empty record if no history exists
            await save_chat_to_db(
                user_id=user_id, 
                document_name=normalized_name,
                messages=[]  # Empty array for new document
            )
            logger.info(f"Created empty chat record for new document: {normalized_name}")
        else:
            logger.info(f"Document {normalized_name} already has chat history, preserving it")
        
        return {
            "status": "indexed",
            "mode_used": mode,
            "complexity_score": recommendations["complexity_score"],
            "analysis": recommendations["analysis"],
            "text_chunks": result.get("n_chunks", 0),
            "tables": result.get("n_tables", 0),
            "images": result.get("n_images", 0),
            "total_items": result.get("total_items", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/pdf/analyze")
async def analyze_pdf_endpoint(
    file: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Analyze PDF complexity without processing it
    Useful for showing users what to expect before upload
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Auth required")
    
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    
    contents = await file.read()
    
    try:
        # Analyze for all presets
        analysis = analyze_pdf_complexity(contents)
        speed_settings = get_recommended_settings(contents, "speed_first")
        balanced_settings = get_recommended_settings(contents, "balanced")
        quality_settings = get_recommended_settings(contents, "quality_first")
        
        return {
            "filename": file.filename,
            "page_count": analysis["page_count"],
            "complexity_score": analysis["complexity_score"],
            "analysis": analysis["analysis"],
            "has_images": analysis["has_images"],
            "has_tables": analysis["has_tables"],
            "recommendations": {
                "speed_first": {
                    "mode": speed_settings["mode"],
                    "max_images": speed_settings["max_images"],
                    "estimated_time": speed_settings["estimated_time"]
                },
                "balanced": {
                    "mode": balanced_settings["mode"],
                    "max_images": balanced_settings["max_images"],
                    "estimated_time": balanced_settings["estimated_time"]
                },
                "quality_first": {
                    "mode": quality_settings["mode"],
                    "max_images": quality_settings["max_images"],
                    "estimated_time": quality_settings["estimated_time"]
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    mode: str = Query("auto", description="Ingest mode: 'auto', 'text', 'fast', or 'full'"),
    max_images: int = Query(2, description="Max images to process (0-10, only used if mode != 'auto')"),
    preset: str = Query("balanced", description="Auto-detection preset (only used if mode='auto')")
):
    """
    Flexible upload endpoint with manual or auto mode selection
    
    Modes:
    - 'auto': Smart detection (recommended) - uses preset to decide
    - 'text': Ultra-fast text-only extraction
    - 'fast': Optimized multimodal with fast extraction
    - 'full': Full multimodal with high-res extraction
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Auth required")
    
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    
    contents = await file.read()
    
    # Validate parameters
    if mode not in ["auto", "text", "fast", "full"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid mode. Use 'auto', 'text', 'fast', or 'full'"
        )
    
    if max_images < 0 or max_images > 10:
        raise HTTPException(status_code=400, detail="max_images must be between 0 and 10")
    
    try:
        # If auto mode, detect complexity and choose
        if mode == "auto":
            recommendations = get_recommended_settings(contents, preset=preset)
            mode = recommendations["mode"]
            max_images = recommendations["max_images"]
            complexity_info = {
                "complexity_score": recommendations["complexity_score"],
                "analysis": recommendations["analysis"]
            }
            logger.info(f"🔍 Auto-detected: {mode} mode (complexity: {recommendations['complexity_score']}/100)")
        else:
            complexity_info = {}
        
        # Process based on mode
        if mode == "text":
            result = ingest_text_only_pdf(contents, user_id, filename)
            
        elif mode == "fast":
            result = ingest_multimodal_pdf(
                contents, user_id, filename,
                max_images=max_images,
                fast_mode=True
            )
            
        else:  # mode == "full"
            result = ingest_multimodal_pdf(
                contents, user_id, filename,
                max_images=max_images,
                fast_mode=False
            )
        
        return {
            "status": "indexed",
            "mode_used": mode,
            **complexity_info,
            "text_chunks": result.get("n_chunks", 0),
            "tables": result.get("n_tables", 0),
            "images": result.get("n_images", 0),
            "total_items": result.get("total_items", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/pdf/simple")
async def upload_pdf_simple(
    file: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Simple endpoint - always uses fast text-only mode
    Best for simple documents where you just need searchable text
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Auth required")
    
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    
    contents = await file.read()
    
    try:
        result = ingest_text_only_pdf(contents, user_id, filename)
        
        return {
            "status": "indexed",
            "indexed_chunks": result["n_chunks"],
            "total_items": result["total_items"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")