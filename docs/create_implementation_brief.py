"""Create the accompanying thesis implementation brief DOCX."""
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT = Path(__file__).with_name("Hallufix_Implementation_Brief.docx")

def font(run, size=11, bold=False, color=None):
    run.font.name = "Calibri"; run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri"); run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(size); run.bold = bold
    if color: run.font.color.rgb = RGBColor(*color)

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tcPr.append(shd)

def add_heading(doc, text, level=1):
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(16 if level == 1 else 12); p.paragraph_format.space_after = Pt(7 if level == 1 else 5)
    r = p.add_run(text); font(r, 16 if level == 1 else 13, True, (46,116,181)); return p

def add_body(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(6); p.paragraph_format.line_spacing = 1.1; p.add_run(text); return p

def add_bullets(doc, lines):
    for line in lines:
        p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(4); p.paragraph_format.left_indent = Inches(.5); p.paragraph_format.first_line_indent = Inches(-.25); p.add_run(line)

doc = Document(); sec = doc.sections[0]
sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Inches(1)
styles = doc.styles
styles["Normal"].font.name = "Calibri"; styles["Normal"].font.size = Pt(11)

# memo_masthead pattern; standard_business_brief tokens
header = sec.header.paragraphs[0]; header.text = "HALLUFIX  |  IMPLEMENTATION BRIEF"; header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
for r in header.runs: font(r, 8, False, (89,89,89))
footer = sec.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER; footer.add_run("Hallufix — thesis project companion document")
for r in footer.runs: font(r, 8, False, (89,89,89))

p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
r = p.add_run("IMPLEMENTATION BRIEF"); font(r, 23, True, (11,37,69))
p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(14); r = p.add_run("HALLUFIX: A Verification and Abstention Layer for Reducing AI Hallucination in RAG"); font(r, 14, False, (55,55,55))

meta = doc.add_table(rows=4, cols=2); meta.alignment = WD_TABLE_ALIGNMENT.LEFT; meta.autofit = False
for i, (key, value) in enumerate([("Project type", "Undergraduate CS final-year project"), ("Domain", "University handbook question answering"), ("Primary objective", "Reduce unsupported answers while preserving evidence traceability"), ("Runtime target", "MacBook Pro M1 Pro; CPU embeddings; API-based LLM inference")]):
    meta.cell(i,0).width = Inches(1.55); meta.cell(i,1).width = Inches(4.95)
    shade(meta.cell(i,0), "F2F4F7"); meta.cell(i,0).text = key; meta.cell(i,1).text = value
    for cell in meta.rows[i].cells:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs: font(run, 10.5, cell is meta.cell(i,0))

add_heading(doc, "What is being built")
add_body(doc, "Hallufix is a retrieval-augmented generation (RAG) application that answers questions from a university handbook and makes reliability decisions visible. It ingests PDF or TXT documents, embeds handbook chunks locally, retrieves the five most relevant chunks, generates a context-bound answer, verifies each answer sentence, and records an auditable result.")
add_bullets(doc, ["FastAPI backend with normal local chat and Hallufix answer endpoints plus a Streamlit interface.", "FAISS vector database and all-MiniLM-L6-v2 embeddings for lightweight CPU retrieval.", "Ollama with the local llama3.2:3b model for normal conversation, grounded generation, and claim verification; no API key is required.", "Append-only JSON audit trail containing question, evidence, original answer, verified answer, verdicts, and confidence."])

add_heading(doc, "Why the verification layer is necessary")
add_body(doc, "Retrieval alone does not guarantee that every sentence in an answer is supported. A model can combine adjacent facts, infer missing policy details, or confidently answer an unrelated question when retrieval is weak. In a handbook setting these failures can mislead students about academic decisions. Hallufix reduces this risk through two controls: it abstains before generation when retrieval evidence is weak, and it removes post-generation claims judged unsupported by the retrieved evidence.")

add_heading(doc, "Approach and data flow")
add_bullets(doc, ["Ingest — clean PDF/TXT content into 500-character chunks with 100-character overlap, retaining source, page, and chunk ID; retrieve the top five local FAISS cosine matches.", "Gate and generate — compare the best score with the configurable 0.35 threshold; when adequate, prompt the LLM to use only the retrieved evidence.", "Verify and audit — judge each generated sentence against that evidence, then persist chunks, raw/final answers, verdicts, and confidence in JSON."])

add_heading(doc, "Architectural decisions")
add_bullets(doc, ["Local MiniLM embeddings keep document indexing private, inexpensive, and practical on the target MacBook; no model training is needed.", "FAISS normalized inner-product search is a simple, inspectable implementation of cosine similarity and supports offline retrieval.", "The abstention test happens before the LLM call, preventing weak evidence from turning into a fluent but unsafe answer and saving API cost.", "The verifier receives the retrieved chunks rather than the full handbook, so the claim decision remains linked to the evidence actually available to the generator.", "A temperature of zero and JSON-only verification response reduce output variance and simplify auditability."])

add_heading(doc, "Evaluation plan")
add_body(doc, "The included benchmark has 50 questions: answerable handbook questions, deliberately unanswerable questions, and misleading questions that tempt an incorrect inference. Compare normal local conversation with Hallufix RAG under the same local model. Report latency, retrieval confidence, abstention rate, claims supported, unsupported-claim rate, and human-reviewed answer quality. RAGAS is an optional future evaluator rather than a runtime dependency.")

add_heading(doc, "Limitations and thesis-safe claims")
add_body(doc, "Hallufix is a risk-reduction layer, not a guarantee of truth. Similarity thresholds require calibration, PDF extraction can be imperfect, and an LLM verifier can make mistakes. The thesis should claim that Hallufix is evaluated for improved reliability on the chosen corpus—not that it eliminates hallucination universally. Future work can add entailment models, span-level citations, threshold tuning, human annotation, and multiple handbook datasets.")

add_heading(doc, "How to run and demonstrate")
add_bullets(doc, ["Create a virtual environment, install requirements, copy .env.example to .env, then install Ollama and run `ollama pull llama3.2:3b` once.", "Run `python -m backend.build_index data`, then start `uvicorn backend.api:app --reload` and `streamlit run frontend/app.py`. Upload multiple TXT/PDF sources; demonstrate normal chat plus answerable, unrelated, and misleading Hallufix questions."])

doc.save(OUT)
print(OUT)
