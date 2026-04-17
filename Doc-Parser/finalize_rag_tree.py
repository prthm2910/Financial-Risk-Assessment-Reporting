import json
import os

def finalize_tree(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Recursive character cleanup (fixing common encoding issues like ₹)
    def clean_text(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = clean_text(v)
        elif isinstance(obj, list):
            return [clean_text(i) for i in obj]
        elif isinstance(obj, str):
            # Fix the 'â‚¹' or 'â\x82¹' artifacts back to '₹'
            return obj.replace('â‚¹', '₹').replace('â\x82¹', '₹')
        return obj

    cleaned_data = clean_text(data)

    # 2. Final Save
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
    
    print(f"SUCCESS: Finalized RAG-Ready Tree saved to {output_path}")

if __name__ == "__main__":
    finalize_tree("results/Tata_Motors_PageIndex_Tree.json", "Tata_Motors_Final_RAG_Tree.json")
