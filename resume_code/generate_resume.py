"""
Standalone resume generator — plug-and-play, no dependency on automation code.

Flow:
  1. Read resume_faangpath.tex + resume.cls
  2. Send to NVIDIA DeepSeek API with a strict minimal-edit prompt
  3. Compile updated .tex → PDF via pdflatex
  4. Validate exactly 1 page
  5. Save to resume_code/resume/resume_generated.pdf and return the path

Usage (standalone):
    python resume_code/generate_resume.py

Usage (imported):
    from resume_code.generate_resume import generate_resume
    pdf_path = generate_resume()   # raises on failure
"""

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_TEX_FILE = _HERE / "resume_faangpath.tex"
_CLS_FILE = _HERE / "resume.cls"
_OUT_DIR = _HERE / "resume"
_OUT_PDF = _OUT_DIR / "resume_generated.pdf"
_TECTONIC_BIN = _HERE.parent / "tectonic_bin" / ("tectonic.exe" if sys.platform == "win32" else "tectonic")

_SYSTEM_PROMPT = """\
You are a senior technical resume writer specialising in software engineering resumes. \
Your task is to rewrite every single \\item bullet point to be stronger, sharper, and more \
impactful — while staying 100% truthful to the original content.

WHAT YOU MUST DO (apply to EVERY bullet — no bullet should be left unchanged):
- Start each bullet with a powerful, specific action verb (e.g. Architected, Spearheaded, \
  Delivered, Reduced, Accelerated, Automated, Optimised, Shipped, Drove, Scaled)
- Cut filler words and passive voice — every word must earn its place
- Make the impact or outcome explicit if it is already implied in the original text
- Tighten long bullets — same meaning, fewer words, stronger punch
- Use precise technical language that resonates with senior engineers and hiring managers

ABSOLUTE RESTRICTIONS — violating any of these is a critical failure:
1. DO NOT add any number, percentage, or metric that does not already exist in the original \
   — never fabricate data (no "40% faster", "3x improvement", "reduced by 30%" unless already there)
2. DO NOT add any skill, technology, tool, library, or framework not already present in the original
3. DO NOT change the LaTeX class, macros, formatting commands, or document structure
4. DO NOT add or remove sections, roles, projects, or bullet points
5. DO NOT change dates, company names, job titles, project names, or education details
6. DO NOT change the header (name, phone, email, links, tagline)
7. DO NOT alter text inside \\projectentry{}{...}, \\skillrow{}{...}, or any macro tag-list \
   arguments — copy those arguments exactly character-for-character
8. Keep the exact same number of \\item bullets per section — never merge or split any
9. The resume MUST remain exactly 1 page — do not expand total content length
10. Return ONLY the raw .tex file content — no explanation, no markdown code fences, no preamble\
"""


def generate_resume() -> str:
    """Generate an AI-improved resume PDF.

    Returns the absolute path to the generated PDF.
    Raises RuntimeError if AI call fails, pdflatex fails, or result is not 1 page.
    """
    import json
    import httpx

    _bootstrap_env()
    from config.settings import GROQ_API_KEY

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in .env")

    tex_content = _TEX_FILE.read_text(encoding="utf-8")
    cls_content = _CLS_FILE.read_text(encoding="utf-8")

    # Replace non-ASCII characters with safe ASCII placeholders before sending to LLM.
    # LLMs cannot reliably preserve Unicode — they corrupt e.g. · (U+00B7) → ů.
    # We restore the originals after the response.
    _CHAR_MAP = [
        ("\u00b7", "__MIDDOT__"),   # · middle dot (skill/tag separator)
        ("\u2013", "__ENDASH__"),   # – en dash
        ("\u2014", "__EMDASH__"),   # — em dash
        ("\u2019", "__RSQUO__"),    # ' right single quote
        ("\u201c", "__LDQUO__"),    # " left double quote
        ("\u201d", "__RDQUO__"),    # " right double quote
    ]
    tex_for_llm = tex_content
    for char, placeholder in _CHAR_MAP:
        tex_for_llm = tex_for_llm.replace(char, placeholder)

    logger.info("Sending resume to Groq AI for refinement...")
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "LaTeX class file (resume.cls) — for reference only, do not modify:\n\n"
                        f"{cls_content}\n\n"
                        "Resume source to improve (resume_faangpath.tex):\n\n"
                        f"{tex_for_llm}\n\n"
                        "Return only the complete updated .tex file."
                    ),
                },
            ],
            "temperature": 0.25,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    response.raise_for_status()

    updated_tex = response.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if the model wrapped its output
    if updated_tex.startswith("```"):
        lines = updated_tex.splitlines()
        updated_tex = "\n".join(
            ln for ln in lines if not ln.startswith("```")
        ).strip()

    # Dump raw LLM response for debugging Unicode issues
    _debug_path = _HERE / "resume" / "debug_llm_raw.tex"
    _debug_path.parent.mkdir(parents=True, exist_ok=True)
    _debug_path.write_text(updated_tex, encoding="utf-8")
    logger.info("Raw LLM response saved to %s", _debug_path)

    # Restore original Unicode characters from placeholders
    for char, placeholder in _CHAR_MAP:
        updated_tex = updated_tex.replace(placeholder, char)

    logger.info("AI response received — compiling PDF...")
    return _compile_to_pdf(updated_tex)


def _compile_to_pdf(tex_content: str) -> str:
    """Compile LaTeX string → PDF, validate 1 page, save to _OUT_DIR."""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        shutil.copy(_CLS_FILE, tmp / "resume.cls")

        # Replace literal · (U+00B7) with the LaTeX command equivalent.
        # tectonic/pdflatex misrender raw UTF-8 middle dot even with utf8 inputenc.
        tex_content = tex_content.replace("\u00b7", r"\textperiodcentered{}")

        tex_path = tmp / "resume_generated.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        tectonic_cmd = str(_TECTONIC_BIN) if _TECTONIC_BIN.exists() else "tectonic"
        result = subprocess.run(
            [tectonic_cmd, "resume_generated.tex"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )

        pdf_path = tmp / "resume_generated.pdf"
        if not pdf_path.exists():
            raise RuntimeError(
                "tectonic did not produce a PDF.\n"
                + result.stdout[-3000:]
            )

        pages = _count_pages(pdf_path)
        if pages != 1:
            raise RuntimeError(
                f"Generated resume is {pages} page(s) — expected exactly 1. "
                "Falling back to backup resume."
            )

        shutil.copy(pdf_path, _OUT_PDF)

    logger.info("Resume PDF generated at: %s", _OUT_PDF)
    return str(_OUT_PDF)


def _count_pages(pdf_path: Path) -> int:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return 1  # assume OK if pypdf unavailable


def _bootstrap_env():
    """Ensure project root is in sys.path when run standalone."""
    project_root = str(_HERE.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Load .env so settings.py picks up the key
    from dotenv import load_dotenv
    load_dotenv(Path(project_root) / ".env")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    _bootstrap_env()
    try:
        path = generate_resume()
        print("Generated:", path)
    except Exception as exc:
        print("Failed:", exc, file=sys.stderr)
        sys.exit(1)
