"""
Optimized Multi-Modal PDF Ingest (UPDATED)
- Adds Unstructured SDK PDF-splitting parameters to speed up large PDFs/batches
- Exposes split_pdf_page, split_pdf_concurrency_level, split_pdf_allow_failed, split_pdf_page_range
- Keeps the "fast" vs "hi_res" strategy, but runs split-mode when requested
- Minimal, drop-in helpers that mirror the original file structure

Notes:
- This file is intended as a patch/replace for the extract_multimodal + ingest flow.
- It does not change your downstream embedding/storage logic — it simply adds the split/batch options
  and better defaults for large documents.
"""

import os
import uuid
import tempfile
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from unstructured.partition.pdf import partition_pdf  # type: ignore
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.services.embeddings import get_embeddings
from app.services.ingest import get_user_collection
from app.logger import setup_logger
logger = setup_logger()

def describe_images(images_base64: List[str], max_images: int = 2) -> List[str]:
    """Describe images using a concise GPT chain. Keeps default=2 for speed."""
    if not images_base64:
        return []

    images_to_process = images_base64[:max_images]
    if len(images_base64) > max_images:
        logger.info(f"  ⚠️  Processing only {max_images}/{len(images_base64)} images for speed")

    prompt_template = ("Describe this image briefly and searchably. "
                       "Focus on: charts, diagrams, key data, main concepts. "
                       "Keep it concise (2-3 sentences).")

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
    chain = prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0) | StrOutputParser() # type: ignore

    logger.info(f"  🤖 Describing {len(images_to_process)} images.")
    inputs = [{"image": img} for img in images_to_process]
    image_summaries = chain.batch(inputs, {"max_concurrency": 10})
    return image_summaries


def summarize_tables(tables_html: List[str], min_table_size: int = 100) -> List[str]:
    if not tables_html:
        return []

    results = []
    tables_to_summarize = []
    table_indices = []

    for i, table in enumerate(tables_html):
        if len(table) < min_table_size:
            results.append(table)
        else:
            results.append(None)
            tables_to_summarize.append(table)
            table_indices.append(i)

    if not tables_to_summarize:
        logger.info(f"  📊 All {len(tables_html)} tables are small, skipping summarization")
        return tables_html

    logger.info(f"  📊 Summarizing {len(tables_to_summarize)}/{len(tables_html)} tables.")
    prompt_text = """Concise table summary (2-3 sentences max):\n\nTable: {element}\n"""
    prompt = ChatPromptTemplate.from_template(prompt_text)
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini")
    summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()

    summaries = summarize_chain.batch(tables_to_summarize, {"max_concurrency": 10})
    for idx, summary in zip(table_indices, summaries):
        results[idx] = summary

    return results


def chunk_texts_fast(texts: List[str], chunk_size: int = 800, overlap: int = 100) -> List[str]:
    chunks = []
    for text in texts:
        if len(text) <= chunk_size:
            chunks.append(text)
            continue
        sentences = text.replace('. ', '.|').replace('! ', '!|').replace('? ', '?|').split('|')
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
    return chunks


def extract_multimodal(
    pdf_bytes: bytes,
    fast_mode: bool = True,
    # New splitting/batching parameters (mirror Unstructured SDK options)
    split_pdf_page: bool = True,
    split_pdf_concurrency_level: int = 5,
    split_pdf_allow_failed: bool = True,
    split_pdf_page_range: Optional[List[int]] = None,
) -> Dict:
    """Extract text, tables and images from PDF using unstructured.partition.pdf

    New: passes split/batch parameters to partition_pdf so large documents are pre-split
    and processed in parallel by the SDK. This is the recommended performance path from
    the Unstructured docs for large files and batches.
    """

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        temp_path = f.name

    try:
        # Common args
        common_args = dict(
            filename=temp_path,
            infer_table_structure=True,
            include_page_breaks=False,
        )

        # Strategy-based args
        if fast_mode:
            strategy_args = dict(
                strategy="fast",
                extract_image_block_types=["Image"],
                extract_image_block_to_payload=True,
            )
        else:
            strategy_args = dict(
                strategy="hi_res",
                extract_image_block_types=["Image", "Table"],
                extract_image_block_to_payload=True,
                extract_tables_with_text=True,
            )

        # Split/batch args (only include them if split_pdf_page=True)
        split_args = {}
        if split_pdf_page:
            split_args = dict(
                split_pdf_page=True,
                split_pdf_concurrency_level=split_pdf_concurrency_level,
                split_pdf_allow_failed=split_pdf_allow_failed,
            )
            if split_pdf_page_range and isinstance(split_pdf_page_range, (list, tuple)) and len(split_pdf_page_range) == 2:
                split_args["split_pdf_page_range"] = split_pdf_page_range # type: ignore

        # Merge args and call partition_pdf
        call_args = {**common_args, **strategy_args, **split_args}
        logger.info(f"  🔎 Calling partition_pdf with args: strategy={call_args.get('strategy')}, split_page={split_pdf_page}, concurrency={split_pdf_concurrency_level}")

        elements = partition_pdf(**call_args)

        # Separate content types
        texts: List[str] = []
        tables: List[str] = []
        images: List[str] = []

        for element in elements:
            element_type = str(type(element))

            if "Table" in element_type:
                table_html = getattr(element.metadata, 'text_as_html', None)
                table_text = str(element).strip()
                if table_html and len(table_html) > len(table_text):
                    tables.append(table_html)
                else:
                    tables.append(table_text)

            elif "Image" in element_type:
                if hasattr(element.metadata, 'image_base64'):
                    images.append(element.metadata.image_base64)

            else:
                text = str(element).strip()
                if text:
                    texts.append(text)

        logger.info(f"  📄 {len(texts)} text blocks, 📊 {len(tables)} tables, 🖼️  {len(images)} images")

        return {"texts": texts, "tables": tables, "images": images}

    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def ingest_multimodal_pdf(
    pdf_bytes: bytes,
    user_id: str,
    filename: str,
    max_images: int = 2,
    fast_mode: bool = True,
    # New passthrough split args
    split_pdf_page: bool = True,
    split_pdf_concurrency_level: int = 5,
    split_pdf_allow_failed: bool = True,
    split_pdf_page_range: Optional[List[int]] = None,
) -> Dict:
    """Wrapper ingestion function that uses extract_multimodal with split options."""
    start = time.time()
    filename = filename.lower()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"FAST MULTIMODAL INGEST: {filename}")
    logger.info(f"Mode: {'FAST' if fast_mode else 'HIGH-RES'} | split_page={split_pdf_page} | concurrency={split_pdf_concurrency_level}")
    logger.info(f"{'='*60}")

    step1_start = time.time()
    extracted = extract_multimodal(
        pdf_bytes,
        fast_mode=fast_mode,
        split_pdf_page=split_pdf_page,
        split_pdf_concurrency_level=split_pdf_concurrency_level,
        split_pdf_allow_failed=split_pdf_allow_failed,
        split_pdf_page_range=split_pdf_page_range,
    )
    step1_end = time.time()
    logger.info(f"  ⏱️  Extraction time: {step1_end - step1_start:.2f} seconds")

    # Process images and tables in parallel
    step2_start = time.time()
    image_descriptions: List[str] = []
    table_summaries: List[str] = []
    num_workers = 6
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_images = None
        future_tables = None

        if extracted['images']:
            future_images = executor.submit(describe_images, extracted['images'], max_images)

        if extracted['tables']:
            future_tables = executor.submit(summarize_tables, extracted['tables'], 100)

        if future_images:
            image_descriptions = future_images.result()
        if future_tables:
            table_summaries = future_tables.result()

    step2_end = time.time()
    logger.info(f"  ⏱️  Image/Table processing time: {step2_end - step2_start:.2f} seconds")

    step3_start = time.time()
    text_chunks = chunk_texts_fast(extracted['texts'], chunk_size=800)
    step3_end = time.time()
    logger.info(f"  ⏱️  Text chunking time: {step3_end - step3_start:.2f} seconds")

    logger.info(f"\n📄 Text chunks: {len(text_chunks)}")
    logger.info("#" * 100)
    logger.info(f"📊 Table summaries: {len(table_summaries)}")
    # for txt in text_chunks:
    #     logger.info(txt + "\n")
    # logger.info("#" * 100)

    logger.info(f"🖼️  Image descriptions: {len(image_descriptions)}")

    # Prepare documents for embedding
    all_docs: List[str] = []
    all_metas: List[Dict] = []
    all_ids: List[str] = []

    for i, text in enumerate(text_chunks):
        all_docs.append(text)
        all_metas.append({"type": "text", "source": filename, "user_id": user_id})
        all_ids.append(str(uuid.uuid4()))

    for i, (summary, original_table) in enumerate(zip(table_summaries, extracted['tables'])):
        all_docs.append(f"[TABLE {i+1}] {summary}")
        all_metas.append({
            "type": "table",
            "source": filename,
            "user_id": user_id,
            "table_index": i,
            "original_table": original_table[:300],
        })
        all_ids.append(str(uuid.uuid4()))

    for i, (description, img_b64) in enumerate(zip(image_descriptions, extracted['images'][:len(image_descriptions)])):
        all_docs.append(f"[IMAGE {i+1}] {description}")
        all_metas.append({"type": "image", "source": filename, "user_id": user_id, "image_index": i})
        all_ids.append(str(uuid.uuid4()))

    # Embeddings
    logger.info(f"\n🔢 Generating embeddings for {len(all_docs)} items.")
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future = executor.submit(get_embeddings, all_docs)
        embeddings = future.result()

    # Store
    collection = get_user_collection(user_id)
    logger.info(f"📊 Collection count before: {collection.count()}")
    collection.add(ids=all_ids, documents=all_docs, metadatas=all_metas, embeddings=embeddings) # type: ignore
    logger.info(f"📊 Collection count after: {collection.count()}")


    logger.info(f"✅ Stored {len(all_docs)} items in {collection.count()} total")
    end = time.time()
    logger.info(f"Total ingestion time: {end - start:.2f} seconds")

    return {
        "n_chunks": len(text_chunks),
        "n_tables": len(table_summaries),
        "n_images": len(image_descriptions),
        "total_items": collection.count()
        }
