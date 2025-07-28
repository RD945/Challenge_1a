import json
from pathlib import Path
import fitz  # PyMuPDF
import pdfplumber
import regex as re
from collections import Counter

def get_document_title(doc):
    """Extracts and cleans the document title from metadata."""
    if doc.metadata and doc.metadata.get('title'):
        title = doc.metadata['title'].strip()
        if 'Microsoft Word -' in title:
            title = title.replace('Microsoft Word -', '').strip()
        return Path(title).stem
    return ""

def extract_form_fields(doc):
    """Extracts all interactive form fields."""
    fields = []
    for page in doc:
        for field in page.widgets():
            fields.append({
                "name": field.field_name, "type": field.field_type_string,
                "value": field.field_value, "page": page.number + 1
            })
    return fields

def extract_static_form_fields(full_text):
    """
    Extracts form-like fields from static text content using a multilingual regex,
    while actively avoiding table of contents and appendixes.
    """
    fields = []
    pattern = re.compile(
        r"^(?!(?:table of contents|appendix)\b)\s*(\p{N}+[\.\)])\s+(.+)$",
        re.IGNORECASE | re.MULTILINE
    )
    for match in pattern.finditer(full_text):
        field_number_str = match.group(1)
        label = match.group(2).strip().replace('\n', ' ')
        try:
            field_number = int(re.sub(r'\D', '', field_number_str))
        except (ValueError, TypeError):
            continue
        fields.append({
            "field_number": field_number, "label": label,
            "type": "text_input", "required": True
        })
    return fields

def extract_tables_with_pdfplumber(pdf_path):
    """
    Extracts and cleans tables, ignoring tables that are likely just page layout columns.
    """
    tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                for table_data in page.extract_tables():
                    if len(table_data) <= 1 and all(len(row) <= 1 for row in table_data):
                        continue
                    
                    cleaned_rows = [
                        ["" if item is None else str(item).strip() for item in row]
                        for row in table_data
                    ]
                    non_empty_rows = [row for row in cleaned_rows if any(row)]
                    if not non_empty_rows: continue

                    max_cols = max(len(row) for row in non_empty_rows)
                    padded_rows = [row + [''] * (max_cols - len(row)) for row in non_empty_rows]
                    transposed = list(zip(*padded_rows))
                    non_empty_col_indices = {idx for idx, col in enumerate(transposed) if any(col)}
                    
                    final_table = [
                        [cell for idx, cell in enumerate(row) if idx in non_empty_col_indices]
                        for row in padded_rows
                    ]
                    if final_table:
                        tables.append({"page": i + 1, "data": final_table})
    except Exception as e:
        print(f"Could not process {pdf_path.name} with pdfplumber for tables: {e}")
    return tables

def classify_content_block(block_text):
    """Applies semantic analysis to classify a text block."""
    text_lower = block_text.lower()
    if re.search(r'www\..+\.com', text_lower):
        return "website"
    if "address:" in text_lower or re.search(r'\d+\s+[a-z\s]+,\s+[a-z]{2}\s+\d+', text_lower):
        return "address"
    if "rsvp:" in text_lower:
        return "rsvp"
    return "paragraph"


def extract_content_and_outline(doc):
    """
    Performs the ultimate extraction of content, outlines, lists, and semantic types.
    """
    styles, all_blocks, full_text = Counter(), [], ""
    bullet_pattern = re.compile(r"^\s*([•●\uf0b7-])\s+(.*)")

    for page_num, page in enumerate(doc):
        full_text += page.get_text() + "\n"
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT)["blocks"]
        for block in blocks:
            if block['type'] == 0:
                span_texts = [span['text'] for line in block['lines'] for span in line['spans']]
                block_text = " ".join(span_texts).strip()
                if not block_text: continue
                
                span = block['lines'][0]['spans'][0]
                style_key = (round(span['size']), span['flags'] & 1)
                styles[style_key] += len(block_text)
                all_blocks.append({'style': style_key, 'text': block_text, 'page': page_num + 1, 'bbox': block['bbox']})

    if not styles: return [], [], full_text.strip(), []

    body_style = styles.most_common(1)[0][0]
    heading_styles = {s for s in styles if s[0] > body_style[0] or (s[0] == body_style[0] and s[1] > body_style[1])}
    sorted_heading_sizes = sorted({s[0] for s in heading_styles}, reverse=True)
    level_map = {size: f"H{i+1}" for i, size in enumerate(sorted_heading_sizes)}

    content_sections, outline, lists = [], [], []
    for block in all_blocks:
        # Ignore ToC dotted lines
        if all(c == '.' for c in block['text'].strip()):
            continue

        is_heading = block['style'] in heading_styles
        level = 0
        
        # Split block into lines to find list items
        lines = block['text'].split('\n')
        list_items = [bullet_pattern.match(line.strip()) for line in lines]

        if any(list_items):
            for line in lines:
                match = bullet_pattern.match(line.strip())
                if match:
                    item_text = match.group(2).strip()
                    lists.append({"page": block['page'], "items": [item_text]})
                    content_sections.append({
                        "type": "list_item", "content": item_text, "page": block['page'],
                        "bbox": block['bbox'], "level": level
                    })
        elif is_heading:
            level = len(level_map) - sorted_heading_sizes.index(block['style'][0])
            outline.append({"level": f"H{level}", "text": block['text'], "page": block['page']})
            content_sections.append({
                "type": "heading", "content": block['text'], "page": block['page'],
                "bbox": block['bbox'], "level": level
            })
        else:
            semantic_type = classify_content_block(block['text'])
            content_sections.append({
                "type": semantic_type, "content": block['text'], "page": block['page'],
                "bbox": block['bbox'], "level": level
            })
    
    toc = doc.get_toc()
    if toc: outline = [{"level": f"H{level}", "text": title, "page": page} for level, title, page in toc]
        
    return content_sections, outline, full_text.strip(), lists

def process_single_pdf(pdf_path, output_dir):
    """Processes a single PDF with our ultimate, enhanced extraction engine."""
    try:
        doc = fitz.open(pdf_path)
        title = get_document_title(doc)
        form_fields = extract_form_fields(doc)
        content_sections, outline, full_text, lists = extract_content_and_outline(doc)
        static_form_fields = extract_static_form_fields(full_text)
        tables = extract_tables_with_pdfplumber(pdf_path)

        if not title and outline:
            title = sorted(outline, key=lambda x: (x['level'], x['page']))[0]['text'] if outline else ""

        output_data = {
            "title": title if title else pdf_path.stem,
            "outline": outline, "content_sections": content_sections,
            "full_text": full_text, "tables": tables,
            "form_fields": form_fields, "static_form_fields": static_form_fields
        }

        with open(output_dir / f"{pdf_path.stem}.json", "w") as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Processed {pdf_path.name} -> {pdf_path.stem}.json")
    except Exception as e:
        print(f"Error processing {pdf_path.name}: {e}")
    finally:
        if 'doc' in locals() and doc: doc.close()

def process_pdfs():
    """Processes all PDFs in the input directory."""
    input_dir, output_dir = Path("/app/input"), Path("/app/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found.")
        return
    for pdf_file in pdf_files:
        process_single_pdf(pdf_file, output_dir)

if __name__ == "__main__":
    print("Starting Ultimate PDF Processing Engine...")
    process_pdfs()
    print("PDF processing completed.")