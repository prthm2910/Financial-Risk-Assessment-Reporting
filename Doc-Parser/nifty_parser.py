from dotenv import load_dotenv
# --- Load environment variables FIRST to ensure redirection to D: Drive ---
load_dotenv()

import os
import io
import json
import base64
import logging
import time
import threading
import random
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

# --- Pydantic Schema for Industrial-Grade Forensic Accuracy ---
class ForensicMetadata(BaseModel):
    structural_cues: str = Field(description="Indentation, alignment, and hierarchical markers found in the layout.")
    forensic_artifacts: str = Field(description="Objective markers like stamps, signatures, or physical document anomalies.")
    factual_esg_data: str = Field(description="Hard numerical ESG data points extracted from the element.")
    integrity_observations: str = Field(description="Technical document quality issues (e.g., blur, truncation).")

    @field_validator('*', mode='before')
    @classmethod
    def sanitize_metadata(cls, v):
        if isinstance(v, str):
            # Enforce Standard UTF-8 and strip problematic characters for Windows compatibility
            return v.encode('utf-8', 'ignore').decode('utf-8')
        return v

class ForensicTableAudit(BaseModel):
    core_table: str = Field(description="The full numerical/text data extracted into a clean Markdown table.")
    metadata: ForensicMetadata

    @field_validator('core_table')
    @classmethod
    def sanitize_table(cls, v):
        return v.encode('utf-8', 'ignore').decode('utf-8')

# --- Logging Configuration ---
# Logs to both pipeline_debug.log and the console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler("pipeline_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Nifty50-Forensic-Parser")

print("DEBUG: Loading Nifty50 Forensic Pipeline...", flush=True)

try:
    # Docling v2.x Imports
    from docling.document_converter import DocumentConverter, PdfFormatOption, ConversionResult, InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
        AcceleratorOptions,
        AcceleratorDevice,
    )
    from docling_ocr_onnxtr import OnnxtrOcrOptions # OpenVINO OCR Plugin
    from docling_core.types.doc.document import DoclingDocument, TableItem, PictureItem, TextItem
    from docling_core.types.doc.labels import DocItemLabel
    from docling_core.types.doc import ContentLayer
    print("DEBUG: Docling Modules Loaded Successfully.", flush=True)
except Exception as e:
    print(f"DEBUG: Critical Import Failure: {e}", flush=True)
    raise e

# 1. Configuration & Global Setup
VLM_API_KEY = os.getenv("NVIDIA_API_KEY")
VLM_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
VLM_MODEL = "moonshotai/kimi-k2.5" # Kimi K2.5 on NVIDIA NIM

client = OpenAI(api_key=VLM_API_KEY, base_url=VLM_BASE_URL)
CONFIDENCE_THRESHOLD = 0.92 # High-precision threshold for financial data

class RateLimiter:
    """
    Simple Thread-Safe Thread-Blocking Rate Limiter.
    Ensures at least (60/RPM) seconds between requests.
    """
    def __init__(self, rpm: int):
        self.interval = 60.0 / rpm
        self.last_call = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                # Add a tiny bit of jitter to avoid "thundering herd" if many threads wait
                time.sleep(sleep_time + random.uniform(0.05, 0.2))
            self.last_call = time.time()

class Nifty50Parser:
    """
    Single Source of Truth Parser for Nifty 50 Financial Documents.
    Combines Docling's structural parsing with Kimi K2.5 visual reasoning.
    """
    def __init__(self):
        logger.info("Initializing Nifty50 Forensic Parser Engine...")
        self.vlm_client = client
        self.converter = self._init_converter()
        # NVIDIA NIM Free tier is ~40 RPM. Setting to 35 for safety.
        self.rate_limiter = RateLimiter(rpm=35)

    def _init_converter(self) -> DocumentConverter:
        """Configures Docling for Intel Iris Xe + OpenVINO Acceleration."""
        logger.info("Configuring Docling Pipeline with OpenVINO acceleration (Iris Xe).")
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        pipeline_options.allow_external_plugins = True # Enables the OpenVINO-optimized OCR plugin
        pipeline_options.generate_page_images = True # Required for get_image()
        pipeline_options.generate_picture_images = True # Required for picture extraction
        
        # 1. Configure OpenVINO for OCR specifically (Iris Xe)
        pipeline_options.ocr_options = OnnxtrOcrOptions(
            providers=[
                (
                    "OpenVINOExecutionProvider",
                    {
                        "device_type": "GPU", # Force Iris Xe GPU
                        "precision": "FP16",   # Optimized for Intel iGPUs
                    }
                ),
                ("CPUExecutionProvider", {})
            ]
        )

        # 2. Hardware optimization: AUTO for Torch models (falls back to CPU if XPU is missing)
        acc_options = AcceleratorOptions(
            num_threads=8, 
            device=AcceleratorDevice.AUTO 
        )
        pipeline_options.accelerator_options = acc_options
        logger.debug(f"Accelerator Device: {acc_options.device}")
        
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def _get_vlm_analysis(self, element_id: str, element_image: Image.Image, context: str) -> str:
        """
        Sends element to Kimi K2.5 with strict forensic and Pydantic validation.
        """
        self.rate_limiter.wait()
        start_time = time.time()
        
        buffered = io.BytesIO()
        element_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Prompt referencing the Pydantic Schema for 100% compliance
        prompt = f"""
        You are a Senior Forensic Auditor. 
        SURROUNDING TEXT CONTEXT: "{context}"

        TASK: 
        1. DATA EXTRACTION: Extract numerical/text data into a clean Markdown Table. 
        2. STRUCTURAL AESTHETICS: Preserve functional layout cues like indentation and alignment.
        3. INTEGRITY: Capture signatures, stamps, or document anomalies.

        STRICT RULE: No subjective analysis. Use ONLY standard UTF-8 characters. 
        Return data following this JSON schema:
        {ForensicTableAudit.model_json_schema()}
        """

        try:
            response = self.vlm_client.chat.completions.create(
                model=VLM_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_str}"}}
                    ]
                }],
                response_format={"type": "json_object"}
            )
            
            # Use Pydantic to parse, validate, and sanitize the response
            raw_data = json.loads(response.choices[0].message.content)
            audit = ForensicTableAudit(**raw_data)
            
            latency = time.time() - start_time
            logger.info(f"VLM SUCCESS: {element_id} (Pydantic Validated) in {latency:.2f}s")

            return (
                f"\n<vlm_forensic_audit>\n"
                f"### [VLM Objective Audit]\n"
                f"{audit.core_table}\n\n"
                f"| Forensic Attribute | Observation |\n"
                f"|---|---|\n"
                f"| Structural Cues | {audit.metadata.structural_cues} |\n"
                f"| Forensic Marks | {audit.metadata.forensic_artifacts} |\n"
                f"| ESG Factuals | {audit.metadata.factual_esg_data} |\n"
                f"| Integrity Notes | {audit.metadata.integrity_observations} |\n"
                f"</vlm_forensic_audit>\n"
            )
        except Exception as e:
            logger.error(f"VLM/Pydantic FAILURE for {element_id}: {str(e)}")
            return f"\n> [ERROR: Validated VLM extraction failed for this element.]\n"

    def process_document(self, pdf_path: str, output_path: str):
        """
        Executes the full forensic pipeline.
        1. Docling Conversion
        2. Confidence-based VLM Trigger
        3. Image Replacement via Caption Injection
        4. Furniture Removal (Headers/Footers)
        5. Export to Markdown
        """
        doc_start = time.time()
        logger.info(f"PIPELINE START: Processing forensic source: {pdf_path}")
        
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"FATAL: Source PDF not found at {pdf_path}")
                return

            # 1. Base Conversion
            result: ConversionResult = self.converter.convert(pdf_path)
            doc: DoclingDocument = result.document
            logger.info(f"Docling Base Conversion Complete. Pages: {len(result.pages)}")
            
            # 2. Identification of Enhancement Targets & SPE Injection
            current_page = -1
            vlm_queue = []
            last_text = "Financial document segment"
            
            # We iterate through the document to track pages and find VLM targets
            # Note: doc.iterate_items() is used to find transition points
            for item, _ in doc.iterate_items():
                # --- SPE INJECTION: Track Physical Page ---
                if item.prov and len(item.prov) > 0:
                    page_no = item.prov[0].page_no
                    if page_no != current_page:
                        current_page = page_no
                        # Inject invisible marker before the first element of each new page
                        doc.insert_text(
                            sibling=item,
                            label=DocItemLabel.PARAGRAPH,
                            text=f"<!-- PHYSICAL_PAGE_{current_page} -->",
                            before=True
                        )

                needs_vlm = False
                trigger_reason = ""
                
                if isinstance(item, TextItem):
                    last_text = item.text[:600]

                if isinstance(item, PictureItem):
                    needs_vlm = True
                    trigger_reason = "Visual Element (Figure/Infographic)"
                elif isinstance(item, TableItem):
                    needs_vlm = True
                    trigger_reason = "Table Element (Forensic Audit)"

                if needs_vlm:
                    element_id = f"{type(item).__name__}_{getattr(item, 'self_ref', 'N/A')}"
                    context = last_text
                    element_img = item.get_image(doc)
                    
                    if element_img:
                        vlm_queue.append((element_id, item, element_img, context))

            # 3. Parallel Visual Reasoning Phase
            # ... (rest of the parallel logic)
            if vlm_queue:
                logger.info(f"Launching Parallel Enhancement for {len(vlm_queue)} items via Kimi K2.5.")
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {
                        executor.submit(self._get_vlm_analysis, eid, img, ctx): item 
                        for eid, item, img, ctx in vlm_queue
                    }
                    
                    for future in futures:
                        target_item = futures[future]
                        enhanced_capsule = future.result()
                        
                        doc.insert_text(
                            sibling=target_item,
                            label=DocItemLabel.CAPTION,
                            text=enhanced_capsule
                        )

            # 4. Final Export Layering
            # Included ContentLayer.BODY ensures page furniture (headers/footers) is omitted.
            final_md = doc.export_to_markdown(included_content_layers={ContentLayer.BODY})
            
            # --- SPE Formatting Polish ---
            # Ensure markers are on their own lines to be easily caught by PageIndex
            import re
            final_md = re.sub(r'(<!-- PHYSICAL_PAGE_\d+ -->)', r'\n\1\n', final_md)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_md)
            
            total_duration = time.time() - doc_start
            logger.info(f"PIPELINE SUCCESS: {output_path} is RAG-Ready. Processed in {total_duration:.2f}s.")

        except Exception as e:
            logger.critical(f"PIPELINE CRASH: {str(e)}", exc_info=True)

if __name__ == "__main__":
    print("--- NIFTY 50 FORENSIC PARSER (SINGLE SOURCE OF TRUTH) ---", flush=True)
    
    # Path Configuration
    INPUT_PDF = r"data\Tata_Motors\tata-motor-IAR-2024-25_removed.pdf"
    OUTPUT_MD = r"Tata_Motors_Forensic_Report.md"
    
    parser = Nifty50Parser()
    parser.process_document(INPUT_PDF, OUTPUT_MD)
    
    print("--- PIPELINE FINISHED ---", flush=True)
