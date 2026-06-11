#!/usr/bin/env python
"""
Novel Translator — Packager CLI
Combines translated chapter txt files into a beautifully formatted EPUB or PDF.
"""

import argparse
import html
import json
import os
import re
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from fpdf import FPDF
from src.config import config
from src.domain.target_language import SUPPORTED_TARGET_LANGUAGES, normalize_target_language
from src.utils.display import RED, GREEN, YELLOW, DIM, RESET


def _get_output_dir(novel_name: str, target_language: str | None = None) -> Path:
    target = normalize_target_language(target_language or config.target_language)
    if config.novel_share_dir:
        base_dir = Path(config.novel_share_dir) / novel_name / "output"
        return base_dir if target == "vi" else base_dir / target
    if target == "vi":
        return Path("output") / novel_name
    return Path("output") / target / novel_name


def _get_default_package_dir(novel_name: str, target_language: str | None = None) -> Path:
    """Return the default directory where EPUB/PDF files are written."""
    target = normalize_target_language(target_language or config.target_language)
    if config.novel_share_dir:
        return Path(config.novel_share_dir) / novel_name
    return Path("output")


def _package_file_stem(novel_name: str, target_language: str | None = None) -> str:
    target = normalize_target_language(target_language or config.target_language)
    return f"{novel_name}.{target}"


def _get_novel_root_dir(novel_name: str) -> Path:
    """Return the root directory for a novel (where metadata.json lives)."""
    if config.novel_share_dir:
        return Path(config.novel_share_dir) / novel_name
    return Path("input") / novel_name


def load_metadata(novel_name: str) -> dict:
    """Load metadata.json from the novel root directory.

    Returns an empty dict if the file doesn't exist or is invalid.
    """
    metadata_path = _get_novel_root_dir(novel_name) / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_book_title(metadata: dict, target_language: str, fallback_novel_name: str) -> str:
    """Resolve book title from metadata with target-language fallback chain.

    Priority: translated[target] -> original title -> formatted novel name.
    """
    translated = metadata.get("translated", {})
    target = normalize_target_language(target_language)
    if target in translated and translated[target]:
        return translated[target]
    if metadata.get("title"):
        return metadata["title"]
    return fallback_novel_name.replace("-", " ").title()


def resolve_cover_image(metadata: dict) -> Path | None:
    """Resolve cover image from metadata.

    Supports web URLs (downloaded to a temp file) and local file paths.
    Returns the Path to the image or None if unavailable.
    """
    illustration_url = metadata.get("illustration_url", "")
    if not illustration_url:
        return None

    # Local file path
    if not illustration_url.startswith(("http://", "https://")):
        local_path = Path(illustration_url)
        return local_path if local_path.exists() else None

    # Web URL — download to temp file
    try:
        req = Request(illustration_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "png" in content_type:
                suffix = ".png"
            elif "webp" in content_type:
                suffix = ".webp"
            else:
                suffix = ".jpg"

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="novel_cover_")
            tmp.write(resp.read())
            tmp.close()
            return Path(tmp.name)
    except (URLError, OSError):
        return None


def find_serif_fonts() -> tuple[str, str]:
    """Find DejaVuSerif fonts on the Linux system for Vietnamese support."""
    candidates = [
        # Debian / Ubuntu / Mint DejaVu paths
        ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        # RHEL / CentOS / Fedora DejaVu paths
        ("/usr/share/fonts/dejavu-serif-fonts/DejaVuSerif.ttf", "/usr/share/fonts/dejavu-serif-fonts/DejaVuSerif-Bold.ttf"),
        # Arch Linux DejaVu paths
        ("/usr/share/fonts/TTF/DejaVuSerif.ttf", "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf"),
        # LiberationSerif fallback paths
        ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold

    # Recursive search as fallback
    for font_path in Path("/usr/share/fonts").glob("**/DejaVuSerif.ttf"):
        bold_path = font_path.parent / "DejaVuSerif-Bold.ttf"
        if bold_path.exists():
            return str(font_path), str(bold_path)

    # Return default Ubuntu path and let FPDF handle error if missing
    return "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def clean_text(text: str) -> str:
    """Clean text by replacing CJK punctuation and removing residual untranslated CJK characters."""
    if not text:
        return ""

    # Replace common CJK punctuation with standard Western/Vietnamese punctuation
    replacements = {
        '『': '"',
        '』': '"',
        '「': '"',
        '」': '"',
        '【': '[',
        '】': ']',
        '〖': '[',
        '〗': ']',
        '—': '-',  # em dash -> hyphen
        '–': '-',  # en dash -> hyphen
        '﹏': '~',  # wavy low line -> tilde
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)

    # Remove any residual Chinese/Korean/Japanese characters
    # (Chinese: \u4e00-\u9fff, Japanese: Hiragana/Katakana, Korean: Hangul syllables/jamo)
    cjk_pattern = re.compile(
        r'[\u4e00-\u9fff'       # Kanji/Hanzi
        r'\u3040-\u309f'       # Hiragana
        r'\u30a0-\u30ff'       # Katakana
        r'\uac00-\ud7af'       # Hangul Syllables
        r'\u1100-\u11ff'       # Hangul Jamo
        r'\u3130-\u318f'       # Hangul Compatibility Jamo
        r'\ufe30-\ufe4f'       # CJK Compatibility Forms
        r']'
    )
    text = cjk_pattern.sub('', text)

    # Remove double spaces that might occur from removing CJK characters
    text = re.sub(r' +', ' ', text)

    return text.strip()


def parse_chapter_file(file_path: Path) -> tuple[str, list[str]]:
    """Parse chapter content. Extracts the cleaned title and paragraphs."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"{RED}✗ Error reading {file_path.name}: {e}{RESET}")
        return f"Chương {file_path.stem}", []

    lines = [line.strip() for line in content.split("\n")]
    lines = [l for l in lines if l]

    if not lines:
        return f"Chương {file_path.stem}", []

    # Detect duplicate/redundant translated titles at the start of the chapter
    header_lines = []
    for idx, line in enumerate(lines[:5]):
        # Match lines starting with Chapter/Chương or containing chapter terms
        if line.startswith("Chương ") or "Chương" in line or line.lower().startswith("chapter"):
            header_lines.append((idx, line))
        else:
            break

    if header_lines:
        # Use the last matched header line as the actual title (cleanest title)
        title_idx, title = header_lines[-1]
        body_start_idx = title_idx + 1
    else:
        title = lines[0]
        body_start_idx = 1

    title = clean_text(title)
    paragraphs = [clean_text(p) for p in lines[body_start_idx:]]
    paragraphs = [p for p in paragraphs if p]

    return title, paragraphs


class EPUBBuilder:
    """Pure Python EPUB generator with zero dependencies."""

    def __init__(self, title: str, author: str = "AI Translator", language: str = "vi", cover_image: Path | None = None):
        self.title = title
        self.author = author
        self.language = language
        self.chapters = []
        self.book_id = f"urn:uuid:{uuid.uuid4()}"
        self.cover_image = cover_image  # Path to cover image (png/jpg)

    def add_chapter(self, title: str, paragraphs: list[str]):
        chapter_id = f"chapter_{len(self.chapters) + 1}"
        content_html = f"<h1>{html.escape(title)}</h1>\n"
        for p in paragraphs:
            content_html += f"<p>{html.escape(p)}</p>\n"
        self.chapters.append({
            "id": chapter_id,
            "title": title,
            "content_html": content_html
        })

    def write(self, output_path: Path):
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. mimetype (MUST be first, uncompressed)
            zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. META-INF/container.xml
            container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
            zf.writestr("META-INF/container.xml", container_xml)

            # 3. OEBPS/style.css
            style_css = """body {
  font-family: "DejaVu Serif", serif;
  margin: 5%;
  line-height: 1.6;
}
h1 {
  text-align: center;
  margin-top: 1em;
  margin-bottom: 2em;
}
p {
  margin-bottom: 0.8em;
  text-align: justify;
}"""
            zf.writestr("OEBPS/style.css", style_css)

            # 4. Cover image (if provided)
            if self.cover_image and self.cover_image.exists():
                suffix = self.cover_image.suffix.lower()
                media_type = "image/png" if suffix == ".png" else "image/jpeg"
                cover_filename = f"cover{suffix}"
                zf.write(str(self.cover_image), f"OEBPS/{cover_filename}")

                # Cover page XHTML
                cover_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{self.language}">
<head>
  <title>Cover</title>
  <style type="text/css">
    body {{ margin: 0; padding: 0; text-align: center; }}
    img {{ max-width: 100%; max-height: 100%; }}
  </style>
</head>
<body>
  <div>
    <img src="{cover_filename}" alt="Cover"/>
  </div>
</body>
</html>"""
                zf.writestr("OEBPS/cover.xhtml", cover_xhtml)

            # 5. OEBPS/chapter_*.xhtml
            for ch in self.chapters:
                ch_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{self.language}">
<head>
  <title>{html.escape(ch['title'])}</title>
  <link rel="stylesheet" href="style.css" type="text/css"/>
</head>
<body>
  {ch['content_html']}
</body>
</html>"""
                zf.writestr(f"OEBPS/{ch['id']}.xhtml", ch_html)

            # 6. OEBPS/toc.ncx
            toc_ncx = self._build_toc_ncx()
            zf.writestr("OEBPS/toc.ncx", toc_ncx)

            # 7. OEBPS/content.opf
            content_opf = self._build_content_opf()
            zf.writestr("OEBPS/content.opf", content_opf)


    def _build_toc_ncx(self) -> str:
        nav_points = []
        for i, ch in enumerate(self.chapters, 1):
            nav_points.append(f"""    <navPoint id="{ch['id']}" playOrder="{i}">
      <navLabel>
        <text>{html.escape(ch['title'])}</text>
      </navLabel>
      <content src="{ch['id']}.xhtml"/>
    </navPoint>""")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.safaribooksonline.com/codex/1.2/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{self.book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{html.escape(self.title)}</text>
  </docTitle>
  <navMap>
{"\n".join(nav_points)}
  </navMap>
</ncx>"""


    def _build_content_opf(self) -> str:
        manifest_items = [
            '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '    <item id="style" href="style.css" media-type="text/css"/>'
        ]
        spine_items = []
        cover_meta = ""

        # Add cover image and cover page to manifest/spine
        if self.cover_image and self.cover_image.exists():
            suffix = self.cover_image.suffix.lower()
            media_type = "image/png" if suffix == ".png" else "image/jpeg"
            cover_filename = f"cover{suffix}"
            manifest_items.append(f'    <item id="cover-image" href="{cover_filename}" media-type="{media_type}"/>')
            manifest_items.append('    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append('    <itemref idref="cover"/>')
            cover_meta = '\n    <meta name="cover" content="cover-image"/>'

        for ch in self.chapters:
            manifest_items.append(f'    <item id="{ch["id"]}" href="{ch["id"]}.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append(f'    <itemref idref="{ch["id"]}"/>')

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="BookId">{self.book_id}</dc:identifier>
    <dc:title>{html.escape(self.title)}</dc:title>
    <dc:creator opf:role="aut">{html.escape(self.author)}</dc:creator>
    <dc:language>{self.language}</dc:language>{cover_meta}
  </metadata>
  <manifest>
{"\n".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
{"\n".join(spine_items)}
  </spine>
</package>"""


class NovelPDF(FPDF):
    """FPDF subclass for formatting novels with customized footers and headers."""

    def __init__(self, title: str, author: str, font_reg: str, font_bold: str, dark_mode: bool = False):
        super().__init__()
        self.book_title = title
        self.book_author = author
        self.font_reg_path = font_reg
        self.font_bold_path = font_bold
        self.dark_mode = dark_mode

        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.dark_mode:
            # Fill the entire page with a dark background
            self.set_fill_color(30, 30, 30)
            self.rect(0, 0, self.w, self.h, "F")

        if self.page_no() > 1:
            self.set_font("DejaVuSerif", size=8)
            if self.dark_mode:
                self.set_text_color(160, 160, 160)
            else:
                self.set_text_color(128, 128, 128)
            self.cell(0, 10, self.book_title, align="R", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("DejaVuSerif", size=9)
            if self.dark_mode:
                self.set_text_color(160, 160, 160)
            else:
                self.set_text_color(128, 128, 128)
            self.cell(0, 10, f"Trang {self.page_no()}", align="C")

    def create_cover(self):
        self.add_page()
        self.add_font("DejaVuSerif", fname=self.font_reg_path)
        self.add_font("DejaVuSerif-Bold", fname=self.font_bold_path)

        if self.dark_mode:
            self.set_text_color(240, 240, 240)
        else:
            self.set_text_color(0, 0, 0)

        # Title Page Layout
        self.set_y(80)
        self.set_font("DejaVuSerif-Bold", size=24)
        self.multi_cell(0, 12, self.book_title, align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(15)
        self.set_font("DejaVuSerif", size=14)
        if self.dark_mode:
            self.set_text_color(200, 200, 200)
        self.cell(0, 10, f"Tác giả: {self.book_author}", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_y(-40)
        self.set_font("DejaVuSerif", size=10)
        if self.dark_mode:
            self.set_text_color(160, 160, 160)
        else:
            self.set_text_color(128, 128, 128)
        self.cell(0, 10, "Được đóng gói tự động bằng AI Novel Translator", align="C")

    def add_chapter(self, title: str, paragraphs: list[str]):
        self.add_page()
        self.set_font("DejaVuSerif-Bold", size=16)
        if self.dark_mode:
            self.set_text_color(245, 230, 211)  # Warm cream text for titles
        else:
            self.set_text_color(0, 0, 0)
        self.multi_cell(0, 10, title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

        self.set_font("DejaVuSerif", size=11)
        if self.dark_mode:
            self.set_text_color(220, 220, 220)  # Light grey text for body
        else:
            self.set_text_color(0, 0, 0)

        for p in paragraphs:
            text = p.strip()
            if not text:
                continue
            self.multi_cell(w=0, h=6.5, text=text, align="J", new_x="LMARGIN", new_y="NEXT")
            self.ln(3.5)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="📦 Novel Translator Packager — Package output text files into EPUB/PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "novel",
        help="Novel name (must match directory in share/ or output/)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["epub", "pdf", "all"],
        default="all",
        help="Packaging format (default: all)",
    )
    parser.add_argument(
        "-t", "--title",
        default="",
        help="Custom book title (defaults to novel name)",
    )
    parser.add_argument(
        "-a", "--author",
        default="AI Translator",
        help="Author name in book metadata (default: AI Translator)",
    )
    parser.add_argument(
        "--target",
        choices=sorted(SUPPORTED_TARGET_LANGUAGES),
        default=config.target_language,
        help="Target language to package (default: vi)",
    )
    parser.add_argument(
        "-o", "--output",
        default="",
        help="Custom output directory to save EPUB/PDF",
    )
    parser.add_argument(
        "--dark",
        action="store_true",
        help="Enable dark mode for PDF (dark background, light text)",
    )

    args = parser.parse_args()
    novel_name = args.novel
    config.target_language = args.target

    # Get output directory of translation
    novel_output_dir = _get_output_dir(novel_name, args.target)
    if not novel_output_dir.exists():
        print(f"{RED}✗ Translation output folder not found: {novel_output_dir}{RESET}")
        sys.exit(1)

    # Scan for translated chapter files
    chapter_files = {}
    pattern = re.compile(r"^chapter_(\d+)\.txt$")
    for f in novel_output_dir.iterdir():
        if f.is_file():
            match = pattern.match(f.name)
            if match:
                chapter_files[int(match.group(1))] = f

    if not chapter_files:
        print(f"{RED}✗ No translated chapter files (chapter_*.txt) found in {novel_output_dir}{RESET}")
        sys.exit(1)

    sorted_chapters = sorted(chapter_files.items())
    print(f"{GREEN}✓ Found {len(sorted_chapters)} translated chapters.{RESET}")

    # Load metadata and resolve book info
    metadata = load_metadata(novel_name)
    book_title = args.title if args.title else resolve_book_title(metadata, args.target, novel_name)
    book_author = args.author if args.author != "AI Translator" else metadata.get("author", args.author)

    # Resolve cover image from metadata
    cover_image = resolve_cover_image(metadata)
    downloaded_cover = cover_image and str(cover_image).startswith(tempfile.gettempdir())

    if cover_image:
        print(f"{GREEN}✓ Cover image: {cover_image.name}{RESET}")
    elif metadata.get("illustration_url"):
        print(f"{YELLOW}⚠ Could not load cover image from: {metadata['illustration_url']}{RESET}")
    else:
        print(f"{DIM}No cover image (set illustration_url in metadata.json){RESET}")

    print(f"{DIM}📖 Title: {book_title}{RESET}")
    print(f"{DIM}✍  Author: {book_author}{RESET}")

    # Determine final packaging output dir
    output_dir = Path(args.output) if args.output else _get_default_package_dir(novel_name, args.target)
    output_dir.mkdir(parents=True, exist_ok=True)
    package_stem = _package_file_stem(novel_name, args.target)

    # Load chapters contents
    loaded_chapters = []
    for num, path in sorted_chapters:
        print(f"  {DIM}Reading Chapter {num:03d}...{RESET}")
        title, paragraphs = parse_chapter_file(path)
        loaded_chapters.append((title, paragraphs))

    try:
        # Compile EPUB
        if args.format in ("epub", "all"):
            epub_file = output_dir / f"{package_stem}.epub"
            print(f"\n📦 {YELLOW}Packaging EPUB...{RESET}")

            builder = EPUBBuilder(title=book_title, author=book_author, language=args.target, cover_image=cover_image)
            for title, paras in loaded_chapters:
                builder.add_chapter(title, paras)
            builder.write(epub_file)
            print(f"  {GREEN}✓ EPUB file saved to: {epub_file}{RESET}")

        # Compile PDF
        if args.format in ("pdf", "all"):
            pdf_file = output_dir / f"{package_stem}.pdf"
            print(f"\n📦 {YELLOW}Packaging PDF...{RESET}")
            font_reg, font_bold = find_serif_fonts()
            if not os.path.exists(font_reg):
                print(f"  {RED}⚠ Warning: System DejaVuSerif fonts not found. Standard PDF fallback may crash on Vietnamese accents.{RESET}")

            try:
                pdf = NovelPDF(title=book_title, author=book_author, font_reg=font_reg, font_bold=font_bold, dark_mode=args.dark)
                pdf.create_cover()
                for title, paras in loaded_chapters:
                    pdf.add_chapter(title, paras)
                pdf.output(str(pdf_file))
                print(f"  {GREEN}✓ PDF file saved to: {pdf_file}{RESET}")
            except Exception as e:
                print(f"  {RED}✗ PDF generation failed: {e}{RESET}")
                sys.exit(1)

        print(f"\n{GREEN}🎉 Packaging complete!{RESET}\n")
    finally:
        # Clean up downloaded cover image
        if downloaded_cover and cover_image and cover_image.exists():
            cover_image.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
