# My PDF Data Extraction Engine - Challenge 1a

This repository contains my submission for Challenge 1a of the Adobe India Hackathon 2025. I have developed a high-precision, containerized PDF processing engine that extracts structured data from a wide variety of documents, from technical manuals to event flyers.

The solution goes far beyond simple text extraction. It performs a deep, multi-layered analysis of each document to intelligently identify and structure its content, including:

-   **Document Metadata:** Title and author information.
-   **Hierarchical Outlines:** Reconstructs the document's structure from both embedded Tables of Contents and stylistic cues (font size, weight).
-   **Content-Aware Classification:** Semantically identifies and tags content blocks such as headings, paragraphs, lists, addresses, websites, and RSVP sections.
-   **Advanced Table Extraction:** Detects and parses tabular data, automatically cleaning empty rows and columns for pristine output.
-   **Form Field Recognition:** Captures both interactive form fields and static, numbered fields from the text body.
-   **Full Text Indexing:** Provides the complete, raw text of the document for searchability.

The entire process is self-contained within a lightweight, optimized Docker image, ensuring consistent and performant execution in any environment while adhering strictly to all hackathon constraints.

---

## Technical Approach & Implementation

My development process was iterative, starting with foundational features and progressively adding layers of intelligence and refinement.

### 1. Foundational Text & Metadata Extraction
I began by using the `PyMuPDF` library, a powerful and efficient toolkit for core PDF operations. The initial implementation focused on two key areas:
-   **Metadata:** Extracting the document's `title` from its metadata properties.
-   **Embedded Outline:** Pulling the `Table of Contents` directly from the PDF's bookmarks, which provides a highly accurate, pre-structured outline when available.

### 2. Heuristic Outline Reconstruction
Recognizing that many PDFs lack an embedded ToC, I developed a sophisticated fallback mechanism. This system analyzes the stylistic properties of every text block on a page:
-   **Statistical Font Analysis:** I calculate the frequency of every font style (size and weight combination) in the document. The most common style is designated as the "body" text.
-   **Heading Detection:** Any style that is statistically larger or bolder than the body text is classified as a heading.
-   **Hierarchy Assignment:** Headings are assigned levels (H1, H2, etc.) based on their font size, creating a logical, structured outline even when one isn't explicitly defined in the document.

### 3. Advanced Table Extraction & Cleaning
For table data, I integrated the `pdfplumber` library, which is excellent at identifying cell boundaries in complex layouts. However, raw extraction often includes layout artifacts. To solve this, I implemented a two-pass cleaning process:
1.  **Row Pruning:** All completely empty rows are discarded.
2.  **Column Pruning:** After removing empty rows, the data is transposed to analyze columns. Any column that contains only empty cells is removed.
This ensures the final JSON output contains only meaningful, clean, and dense tabular data.

### 4. Semantic Content Intelligence
This is where the engine truly shines. To provide the richest possible output, I built a custom classification layer that goes beyond simple text blocks.
-   **List Detection:** Using the `regex` library for its superior Unicode support, the engine identifies bulleted (`•`, `●`) and numbered (`1.`, `a)`) list items, separating each into a distinct `list_item` in the JSON.
-   **ToC Dotted Leader Removal:** On Table of Contents pages, the stream of `.` characters used as leaders is identified and intelligently discarded, preventing noise in the output.
-   **Pattern-Based Classification:** Regular expressions are used to semantically identify and tag specific content types. For example, it detects patterns for:
    -   `website`: `www.domain.com`
    -   `address`: `123 Street Name, City, ST 12345`
    -   `rsvp`: Lines containing "RSVP"

### 5. Form Field Extraction (Interactive & Static)
The solution captures two types of form data:
-   **Interactive Fields:** Using PyMuPDF's `widgets` API, it extracts fillable form fields, capturing their name, type, and current value.
-   **Static Form Fields:** Leveraging the `regex` library's Unicode-aware pattern matching (`\p{N}`), it finds numbered lines in the body text (e.g., "1. Full Name: \_\_\_") that represent non-interactive form questions, a common feature in many documents.

---

## Libraries & Tools

-   **`PyMuPDF` (`fitz`):** The core engine for high-performance text, metadata, and interactive form extraction.
-   **`pdfplumber`:** Used for its excellent table detection and extraction capabilities.
-   **`regex`:** A superior alternative to Python's standard `re` module, chosen for its powerful and reliable Unicode character property support (`\p{N}`), which was critical for robustly detecting numbered lists and fields across different languages and encodings.
-   **Docker:** For containerization, ensuring a reproducible and isolated runtime environment. I used a `python:3.10-slim` base image to significantly reduce the final image size and improve deployment efficiency.

---

## How to Build and Run the Solution

### Prerequisites
-   [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### Build the Docker Image
Navigate to the project's root directory and run the following command. This will build the container with all necessary dependencies.

```bash
docker build --platform linux/amd64 -t pdf-processor .
```

### Run the Extractor
Execute the following command to run the container. It will:
1.  Mount your local `sample_dataset/pdfs` directory as a read-only input volume.
2.  Mount your local `sample_dataset/outputs` directory as the output volume.
3.  Process all PDF files and save the resulting `.json` files to the output directory.

```bash
# On Windows (using PowerShell/CMD)
docker run --rm -v ${PWD}/sample_dataset/pdfs:/app/input:ro -v ${PWD}/sample_dataset/outputs:/app/output --network none pdf-processor

# On macOS/Linux
docker run --rm -v $(pwd)/sample_dataset/pdfs:/app/input:ro -v $(pwd)/sample_dataset/outputs:/app/output --network none pdf-processor
```
*Note: The `--network none` flag is included to adhere to the hackathon constraint of no internet access at runtime.*

### Create a Portable Image Archive (Optional)
To save the Docker image as a single, distributable `.tar` file, use the `docker save` command:

```bash
docker save -o pdf-processor.tar pdf-processor:latest
```
This `pdf-processor.tar` file can then be loaded on another machine using `docker load -i pdf-processor.tar`. 