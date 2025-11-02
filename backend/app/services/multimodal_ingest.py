"""
Simple Multi-Modal PDF Ingest using Unstructured + LangChain
"""
import os
import uuid
import tempfile
from typing import Dict, List
from unstructured.partition.pdf import partition_pdf # type: ignore
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection


def describe_images(images_base64: List[str], max_images: int = 5) -> List[str]:
    """Describe images using  via LangChain (with limit for speed)"""
    if not images_base64:
        return []
    
    # LIMIT IMAGES FOR SPEED (most important ones first)
    images_to_process = images_base64[:max_images]
    
    if len(images_base64) > max_images:
        print(f"  ⚠️  Limiting to first {max_images} images (found {len(images_base64)})")
    
    prompt_template = """Describe this image in detail. 
    Be specific about what you see - charts, diagrams, text, graphs, etc.
    Make it searchable and informative."""
    
    messages = [
        (
            "user",
            [
                {"type": "text", "text": prompt_template},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,{image}"},
                },
            ],
        )
    ]
    
    prompt = ChatPromptTemplate.from_messages(messages)
    chain = prompt | ChatOpenAI(model="gpt-4o-mini") | StrOutputParser()
    
    print(f"  🤖 Describing {len(images_to_process)} images with ...")
    
    # BATCH PROCESSING for speed (max_concurrency)
    # chain.batch expects a list of dicts mapping prompt variables to values,
    # so wrap each base64 image in a dict with the "image" key used in the prompt template.
    inputs = [{"image": img} for img in images_to_process]
    image_summaries = chain.batch(inputs, {"max_concurrency": 5})
    
    return image_summaries


def summarize_tables(tables_html: List[str], skip_small_tables: bool = True) -> List[str]:
    """Summarize tables using LangChain (skip very small tables for speed)"""
    if not tables_html:
        return []
    
    # SKIP SMALL TABLES (< 50 chars) - they don't need summarization
    tables_to_process = []
    original_tables = []
    
    for table in tables_html:
        if skip_small_tables and len(table) < 50:
            # Small table - use as-is without summarization
            tables_to_process.append(table)
            original_tables.append(table)
        else:
            # Large table - needs summarization
            tables_to_process.append(table)
            original_tables.append(None)  # Will be summarized
    
    # Only summarize tables that need it
    tables_needing_summary = [(i, t) for i, t in enumerate(tables_to_process) 
                               if original_tables[i] is None]
    
    if not tables_needing_summary:
        print(f"  📊 All {len(tables_html)} tables are small, skipping summarization")
        return tables_html
    
    print(f"  📊 Summarizing {len(tables_needing_summary)} large tables (skipping {len(tables_html) - len(tables_needing_summary)} small ones)...")
    
    prompt_text = """You are an assistant tasked with summarizing tables.
    Give a concise summary of the table that captures the key information.
    
    Respond only with the summary, no additional comment.
    Just give the summary as it is.
    
    Table: {element}
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_text)
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini")
    summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()
    
    # Batch summarize only the large tables
    large_tables = [t for _, t in tables_needing_summary]
    summaries = summarize_chain.batch(large_tables, {"max_concurrency": 5})
    
    # Reconstruct full list
    result = []
    summary_idx = 0
    for i, orig in enumerate(original_tables):
        if orig is None:
            result.append(summaries[summary_idx])
            summary_idx += 1
        else:
            result.append(orig)
    
    return result


def extract_multimodal(pdf_bytes: bytes) -> Dict:
    """Extract text, tables, and images from PDF using unstructured"""
    
    # Save to temp file (unstructured needs file path)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        temp_path = f.name
    
    try:
        # Extract everything with unstructured - NO CHUNKING FIRST
        elements = partition_pdf(
            filename=temp_path,
            infer_table_structure=True,
            strategy="hi_res",
            extract_image_block_types=["Image", "Table"],
            extract_image_block_to_payload=True,
            # IMPROVED TABLE EXTRACTION SETTINGS
            extract_tables_with_text=True,  # Keep table text even if structure fails
            include_page_breaks=False,
        )
        
        # Separate into text, tables, images
        texts = []
        tables = []
        images = []
        
        for element in elements:
            element_type = str(type(element))
            
            # Check for Table elements - GET BOTH HTML AND TEXT
            if "Table" in element_type:
                # Try to get HTML first (best structure)
                table_html = None
                if hasattr(element.metadata, 'text_as_html'):
                    table_html = element.metadata.text_as_html
                
                # Fallback to plain text if HTML is bad/empty
                table_text = str(element).strip()
                
                # Use whichever has more content
                if table_html and len(table_html) > len(table_text):
                    tables.append(table_html)
                else:
                    # Store as markdown-style text for better readability
                    tables.append(table_text)
                
                print(f"  Found table: {len(table_text)} chars")
            
            # Check for images
            elif "Image" in element_type:
                if hasattr(element.metadata, 'image_base64'):
                    images.append(element.metadata.image_base64)
            
            # Everything else is text
            else:
                text = str(element).strip()
                if text:
                    texts.append(text)
        
        print(f"  📝 {len(texts)} text elements")
        print(f"  📊 {len(tables)} tables")
        print(f"  🖼️  {len(images)} images")
        
        return {
            "texts": texts,
            "tables": tables, 
            "images": images
        }
    
    finally:
        os.unlink(temp_path)


def chunk_texts(texts: List[str], chunk_size: int = 1000) -> List[str]:
    """Chunk long texts into smaller pieces"""
    chunks = []
    for text in texts:
        words = text.split()
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            if chunk.strip():
                chunks.append(chunk)
    return chunks


def ingest_multimodal_pdf(pdf_bytes: bytes, user_id: str, filename: str, max_images: int = 5) -> Dict:
    """Ingest PDF with multi-modal extraction
    
    Args:
        pdf_bytes: PDF file content
        user_id: User identifier
        filename: Name of the file
        max_images: Maximum images to process with  (default: 5 for speed)
    """
    
    print(f"\n{'='*60}")
    print(f"MULTIMODAL INGEST: {filename}")
    print(f"{'='*60}")
    
    # Step 1: Extract
    extracted = extract_multimodal(pdf_bytes)
    
    # Step 2: Describe images with  (LIMITED for speed)
    image_descriptions = []
    if extracted['images']:
        image_descriptions = describe_images(extracted['images'], max_images=max_images)
    
    # Step 3: Summarize tables (SKIP small ones for speed)
    table_summaries = []
    if extracted['tables']:
        table_summaries = summarize_tables(extracted['tables'], skip_small_tables=True)
    
    # Step 4: Chunk texts
    text_chunks = chunk_texts(extracted['texts'])
    
    print(f"\n📝 Text chunks: {len(text_chunks)}")
    print(f"📊 Table summaries: {len(table_summaries)}")
    print(f"🖼️  Image descriptions: {len(image_descriptions)}")
    
    # Step 5: Prepare for ChromaDB
    all_docs = []
    all_metas = []
    all_ids = []
    
    # Add text chunks
    for i, text in enumerate(text_chunks):
        all_docs.append(text)
        all_metas.append({
            "type": "text",
            "source": filename,
            "user_id": user_id
        })
        all_ids.append(str(uuid.uuid4()))
    
    # Add table summaries (searchable) + original table (in metadata)
    for i, (summary, original_table) in enumerate(zip(table_summaries, extracted['tables'])):
        # Store summary as searchable text
        all_docs.append(f"[TABLE {i+1}] {summary}")
        all_metas.append({
            "type": "table",
            "source": filename,
            "user_id": user_id,
            "table_index": i,
            "original_table": original_table[:500]  # Store first 500 chars
        })
        all_ids.append(str(uuid.uuid4()))
    
    # Add image descriptions (searchable) + base64 (in metadata)
    for i, (description, img_b64) in enumerate(zip(image_descriptions, extracted['images'][:len(image_descriptions)])):
        # Store description as searchable text
        all_docs.append(f"[IMAGE {i+1}] {description}")
        all_metas.append({
            "type": "image",
            "source": filename,
            "user_id": user_id,
            "image_index": i,
            "image_data": img_b64[:200]  # Store truncated base64
        })
        all_ids.append(str(uuid.uuid4()))
    
    # Step 6: Generate embeddings
    print(f"\n🔢 Generating embeddings for {len(all_docs)} items...")
    embeddings = get_embeddings(all_docs)
    
    # Step 7: Store in ChromaDB
    collection = get_user_collection(user_id)
    collection.add(
        ids=all_ids,
        documents=all_docs,
        metadatas=all_metas,
        embeddings=embeddings
    )
    
    print(f"✅ Stored {len(all_docs)} items")
    print(f"{'='*60}\n")
    
    return {
        "n_chunks": len(text_chunks),
        "n_tables": len(table_summaries),
        "n_images": len(image_descriptions),
        "total_items": collection.count()
    }   