"""Document processing service for PDF, DOC, and TXT files."""
import hashlib
import os
from pathlib import Path
from typing import List
from io import BytesIO

from PyPDF2 import PdfReader
from docx import Document

from app.config import MAX_CHUNK_LENGTH, CHUNK_OVERLAP, UPLOAD_DIR


class DocumentProcessor:
    """Process PDF, DOC, and TXT documents into chunks."""

    def __init__(self, max_chunk_length: int = MAX_CHUNK_LENGTH, chunk_overlap: int = CHUNK_OVERLAP):
        self.max_chunk_length = max_chunk_length
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        text = ""
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {e}")
        return text

    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        text = ""
        try:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {e}")
        return text

    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        try:
            # Try UTF-8 first
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            # Fallback to other encodings
            for encoding in ["gbk", "gb2312", "latin1"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Failed to decode TXT file with any encoding")
        return text

    def chunk_text(self, text: str, source: str = "unknown") -> List[dict]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + self.max_chunk_length
            chunk_text = text[start:end]

            # Avoid cutting in the middle of a sentence
            if end < len(text):
                last_period = chunk_text.rfind(".")
                last_newline = chunk_text.rfind("\n")
                cut_point = max(last_period, last_newline)
                if cut_point > len(chunk_text) * 0.5:
                    chunk_text = chunk_text[:cut_point + 1]
                    end = start + cut_point + 1

            chunks.append({
                "id": f"chunk_{chunk_id}",
                "text": chunk_text.strip(),
                "source": source,
                "start_pos": start,
                "end_pos": end
            })

            start = end - self.chunk_overlap
            chunk_id += 1

            if start >= len(text):
                break

        return chunks

    def process_file(self, file_path: str, file_name: str) -> List[dict]:
        """Process a file and return chunks."""
        ext = Path(file_name).suffix.lower()

        if ext == ".pdf":
            text = self.extract_text_from_pdf(file_path)
        elif ext in [".doc", ".docx"]:
            text = self.extract_text_from_docx(file_path)
        elif ext == ".txt":
            text = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        return self.chunk_text(text, source=file_name)

    def save_uploaded_file(self, file_content: bytes, file_name: str) -> str:
        """Save uploaded file and return the path."""
        file_hash = hashlib.md5(file_content).hexdigest()[:8]
        ext = Path(file_name).suffix.lower()
        safe_name = f"{file_hash}_{file_name}"
        file_path = UPLOAD_DIR / safe_name

        with open(file_path, "wb") as f:
            f.write(file_content)

        return str(file_path)


# Global processor instance
processor = DocumentProcessor()
