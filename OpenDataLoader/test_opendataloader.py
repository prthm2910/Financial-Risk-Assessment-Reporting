import opendataloader_pdf

# Convert using the local hybrid server
opendataloader_pdf.convert(
    input_path=r"data/Tata_Motors/tata-motor-IAR-2024-25_removed.pdf",
    output_dir=r"OpenDataLoader/OpenDataLoaderResults",
    format="markdown,json",
    hybrid="docling-fast",       # This tells the library to use the hybrid server
    hybrid_mode="full"           # Use "full" to include formulas and image descriptions
)