import asyncio
import os
import json
import logging
import sys
import time
import threading
import random
import re
import base64
import io
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import litellm

# --- Force UTF-8 for Windows Console ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# --- Load Environment Variables ---
load_dotenv()

# --- PageIndex Path Setup ---
sys.path.append(os.path.join(os.getcwd(), 'PageIndex'))

# --- Beautiful Logging System ---
class PipelineLogger:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def __init__(self, name="Forensic-Pipeline"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # File Handler
        fh = logging.FileHandler("pipeline_execution.log", encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)

    def header(self, msg):
        print(f"\n{self.BOLD}{self.CYAN}🚀 {'='*10} {msg.upper()} {'='*10}{self.RESET}")
        self.logger.info(f"PHASE START: {msg}")

    def info(self, msg):
        print(f"{self.BLUE}ℹ [INFO]{self.RESET} {msg}")
        self.logger.info(msg)

    def success(self, msg):
        print(f"{self.GREEN}✔ [SUCCESS]{self.RESET} {msg}")
        self.logger.info(f"SUCCESS: {msg}")

    def warning(self, msg):
        print(f"{self.YELLOW}⚠ [WARNING]{self.RESET} {msg}")
        self.logger.warning(msg)

    def error(self, msg):
        print(f"{self.RED}✖ [ERROR]{self.RESET} {self.BOLD}{msg}{self.RESET}")
        self.logger.error(msg)

    def step(self, msg):
        print(f"  {self.CYAN}→{self.RESET} {msg}")

plog = PipelineLogger()

# --- Imports from PageIndex & Docling ---
try:
    from PageIndex.utils import _global_limiter, llm_acompletion
    from PageIndex.page_index_md import md_to_tree
    from docling.document_converter import DocumentConverter, PdfFormatOption, InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions, TableFormerMode, AcceleratorOptions, AcceleratorDevice
    )
    from docling_ocr_onnxtr import OnnxtrOcrOptions
    from docling_core.types.doc.document import TextItem, PictureItem, TableItem
    from docling_core.types.doc.labels import DocItemLabel
    from docling_core.types.doc import ContentLayer
except Exception as e:
    plog.error(f"Import Failure: {e}")
    sys.exit(1)

litellm.api_base = "https://integrate.api.nvidia.com/v1"
litellm.api_key = os.getenv("NVIDIA_API_KEY")

# --- Pydantic Models ---
class ForensicMetadata(BaseModel):
    structural_cues: str
    forensic_artifacts: str
    factual_esg_data: str
    integrity_observations: str

    @field_validator('*', mode='before')
    @classmethod
    def sanitize(cls, v):
        return v.encode('utf-8', 'ignore').decode('utf-8') if isinstance(v, str) else v

class ForensicTableAudit(BaseModel):
    core_table: str
    metadata: ForensicMetadata

    @field_validator('core_table')
    @classmethod
    def sanitize_table(cls, v):
        return v.encode('utf-8', 'ignore').decode('utf-8')

# --- Imports from PageIndex (After path append) ---
try:
    from PageIndex.page_index_md import md_to_tree
    from docling.document_converter import DocumentConverter, PdfFormatOption, InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions, TableFormerMode, AcceleratorOptions, AcceleratorDevice
    )
    from docling_ocr_onnxtr import OnnxtrOcrOptions
    from docling_core.types.doc.document import TextItem, PictureItem, TableItem
    from docling_core.types.doc.labels import DocItemLabel
    from docling_core.types.doc import ContentLayer
except Exception as e:
    plog.error(f"Import Failure: {e}")
    sys.exit(1)

# --- Core Pipeline Logic ---
class ForensicPipeline:
    def __init__(self):
        self.vlm_client = OpenAI(api_key=os.getenv("NVIDIA_API_KEY"), base_url="https://integrate.api.nvidia.com/v1")
        self.vlm_model = "moonshotai/kimi-k2.5"

    def _init_converter(self):
        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        # Switched to FAST mode to save significant memory over ACCURATE mode
        options.table_structure_options.mode = TableFormerMode.FAST
        options.generate_page_images = True
        
        # --- ULTRA-LIGHT SCALING ---
        # 0.8 scale provides ~36% fewer pixels than 1.0, drastically reducing RAM spikes
        # while remaining perfectly legible for VLM and OCR.
        options.images_scale = 0.8 
        
        options.allow_external_plugins = True
        options.ocr_options = OnnxtrOcrOptions(
            providers=[("CPUExecutionProvider", {})]
        )
        # RESTORED SPEED: Increased threads to 4
        options.accelerator_options = AcceleratorOptions(num_threads=4, device=AcceleratorDevice.CPU)
        return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

    async def _vlm_audit(self, img, context):
        # Using the library's global async limiter for pacing
        from PageIndex.utils import _global_limiter
        await _global_limiter.await_wait()
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        prompt = f"Forensic Audit Task. Context: {context}. Return ONLY JSON per schema: {ForensicTableAudit.model_json_schema()}"
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: self.vlm_client.chat.completions.create(
                model=self.vlm_model,
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}]}],
                response_format={"type": "json_object"}
            ))
            audit = ForensicTableAudit(**json.loads(res.choices[0].message.content))
            return (f"\n<vlm_audit>\n{audit.core_table}\n\n| Attribute | Note |\n|---|---|\n"
                    f"| Structural | {audit.metadata.structural_cues} |\n"
                    f"| Forensic | {audit.metadata.forensic_artifacts} |\n"
                    f"| ESG | {audit.metadata.factual_esg_data} |\n"
                    f"| Integrity | {audit.metadata.integrity_observations} |\n</vlm_audit>\n")
        except Exception as e:
            return f"\n> [VLM Audit Failed: {e}]\n"

    async def execute(self, pdf_path, company_name):
        plog.header(f"Starting Industrial Pipeline: {company_name}")
        start_time = time.time()
        
        # PHASE 1: PDF to Markdown (SPE + VLM + CITATIONS)
        plog.info("Phase 1: Forensic Extraction & Physical Mapping")
        converter = self._init_converter()
        result = converter.convert(pdf_path)
        doc = result.document
        plog.step(f"Docling conversion complete. Pages: {len(result.pages)}")

        current_page = -1
        vlm_queue = []
        last_text = ""
        cid_map = {} # CID -> {page, bbox}
        cid_counter = 0

        # We iterate items to inject Page Markers and Citation Anchors
        for item, _ in doc.iterate_items():
            cid_counter += 1
            cid = f"CID_{cid_counter:05d}"
            anchor = f"{{{cid}}}"

            # Capture Physical Coordinates (Provenance)
            if item.prov and len(item.prov) > 0:
                p = item.prov[0]
                page_no = p.page_no
                cid_map[cid] = {
                    "page": page_no,
                    "bbox": [round(p.bbox.l, 2), round(p.bbox.t, 2), round(p.bbox.r, 2), round(p.bbox.b, 2)]    
                }

                # Inject Physical Page Marker if we cross a page boundary
                if page_no != current_page:
                    current_page = page_no
                    doc.insert_text(
                        label=DocItemLabel.PARAGRAPH,
                        text=f"<!-- PHYSICAL_PAGE_{current_page} -->",
                        sibling=item
                    )

            # --- ELEGANT ANCHOR INJECTION ---
            if hasattr(item, 'text') and item.text:
                item.text = f"{anchor} {item.text}"
            elif isinstance(item, (PictureItem, TableItem)):
                doc.insert_text(sibling=item, label=DocItemLabel.CAPTION, text=anchor)

            if isinstance(item, TextItem): last_text = item.text[:400]
            if isinstance(item, (PictureItem, TableItem)):
                img = item.get_image(doc)
                if img: vlm_queue.append((item, img, last_text, cid))

        if vlm_queue:
            plog.info(f"Phase 1.5: Running Concurrent VLM Audits on {len(vlm_queue)} elements...")

            async def run_audit(item, img, ctx, idx, parent_cid):
                plog.step(f"Launching Audit {idx}/{len(vlm_queue)}...")
                audit_result = await self._vlm_audit(img, ctx)
                # Link the audit to the same physical coordinate anchor
                audit_with_anchor = f"{audit_result}\n{{{parent_cid}}}"
                doc.insert_text(sibling=item, label=DocItemLabel.CAPTION, text=audit_with_anchor)
                plog.success(f"Audit {idx} Complete.")

            tasks = [run_audit(item, img, ctx, i, pcid) for i, (item, img, ctx, pcid) in enumerate(vlm_queue, 1)]
            await asyncio.gather(*tasks)
        # Ensure organized output directories exist
        os.makedirs("results/md", exist_ok=True)
        os.makedirs("results/json", exist_ok=True)
        
        md_path = f"results/md/{company_name}_Forensic_Report.md"
        final_md = doc.export_to_markdown(included_content_layers={ContentLayer.BODY})
        # Clean up spacing for page markers
        final_md = re.sub(r'(<!-- PHYSICAL_PAGE_\d+ -->)', r'\n\1\n', final_md)
        with open(md_path, "w", encoding="utf-8") as f: f.write(final_md)
        plog.success(f"Markdown saved with physical anchors: {md_path}")

        # PHASE 2: PageIndex Construction
        plog.info("Phase 2: Hierarchical Indexing (Markdown -> JSON Tree)")
        tree_path = f"results/json/{company_name}_PageIndex_Tree.json"

        # OPTIMIZATION: Switched to 8B model for summarizing nodes (much faster than 70B)
        tree_result_raw = await md_to_tree(
            md_path=md_path, if_thinning=False, model="openai/meta/llama-3.1-8b-instruct",
            if_add_node_summary='yes', if_add_node_text='yes'
        )
        # PageIndex MD returns a dict with a 'structure' key which is a list
        tree_data = tree_result_raw.get("structure", [])
        if not isinstance(tree_data, list): tree_data = [tree_data]
        plog.success(f"Tree Index constructed.")
        # PHASE 3: Final Cleanup & Physical Citation Binding
        plog.info("Phase 3: Final Forensic Hardening & Citation Binding")
        final_path = f"results/json/{company_name}_Final_RAG_Tree.json"

        def process_node_recursive(node):
            # 1. Character Repair & Title cleanup
            for field in ["title", "summary", "text"]:
                if field in node and node[field]:
                    # Fix Rupee symbol encoding artifacts
                    node[field] = node[field].replace('â‚¹', '₹').replace('â\x82¹', '₹').replace('â\x82\x19', '₹')
            
            # 2. Extract Citations from {CID_XXXXX}
            node_text = node.get("text", "")
            node_title = node.get("title", "")
            combined_search_area = f"{node_title}\n{node_text}"
            
            # Match {CID_00001} or \{CID\_00001\}
            found_cids = re.findall(r'\{CID(?:\\)?_(\d{5})\}', combined_search_area)
            
            citations = []
            for cid_num in set(found_cids):
                cid_key = f"CID_{cid_num}"
                if cid_key in cid_map:
                    citations.append(cid_map[cid_key])
            
            node["citations"] = citations
            
            # 3. Final Text Scrub (Remove the anchors from final RAG view)
            # This cleans both {CID_00001} and \&lt;!-- CID\_00001 --\&gt; if any leftovers exist
            anchor_pattern = r'\{CID(?:\\)?_\d{5}\}'
            cid_pattern_legacy = r'(&lt;|<|\\<)!-- CID(?:\\)?_\d{5} --(&gt;|>|\\>)'
            
            if "title" in node:
                node["title"] = re.sub(anchor_pattern, '', node["title"])
                node["title"] = re.sub(cid_pattern_legacy, '', node["title"]).strip()
            if "text" in node:
                node["text"] = re.sub(anchor_pattern, '', node["text"])
                node["text"] = re.sub(cid_pattern_legacy, '', node["text"]).strip()

            # 4. Recurse
            if "nodes" in node and node["nodes"]:
                for child in node["nodes"]:
                    process_node_recursive(child)

        for root_node in tree_data:
            process_node_recursive(root_node)

        # Wrap in final envelope
        final_output = {
            "doc_name": company_name,
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "structure": tree_data
        }


        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
        
        total_time = time.time() - start_time
        plog.header(f"Pipeline Success for {company_name}")
        plog.success(f"Total Execution Time: {total_time:.2f}s")
        plog.step(f"Final Artifact with PDF Citations: {final_path}")

if __name__ == "__main__":
    # Configure your run here
    PDF = r"data/Godrej_Finance_Limited/Credit_Report/202507120723_Godrej_Finance_Limited.pdf"
    NAME = "Godrej_Finance_Limited"
    
    pipeline = ForensicPipeline()
    asyncio.run(pipeline.execute(PDF, NAME))
