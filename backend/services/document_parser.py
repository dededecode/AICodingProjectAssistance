"""需求文档解析：支持 Word(.docx) / Excel(.xlsx) / Markdown(.md/.markdown)。"""
import os
import re
from pathlib import Path

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _plain_table_text(tbl_el):
    """纯文本表格提取：按行取单元格文本，合并单元格去重，支持嵌套表格。"""
    from docx.oxml.ns import qn

    lines = []
    for row in tbl_el.findall(qn("w:tr")):
        seen = set()
        cells = []
        for cell in row.findall(qn("w:tc")):
            if cell in seen:
                continue
            seen.add(cell)
            texts = []
            for p in cell.findall(qn("w:p")):
                t = "".join((x.text or "") for x in p.iter(qn("w:t")))
                if t.strip():
                    texts.append(t.strip())
            # 单元格内的嵌套表格
            for nested in cell.findall(qn("w:tbl")):
                nt = _plain_table_text(nested)
                if nt:
                    texts.append(f"[嵌套表格]\n{nt}")
            cell_text = " ".join(texts).strip()
            cells.append(cell_text)
        line = " | ".join(c for c in cells if c)
        if line:
            lines.append(line)
    return "\n".join(lines)


def parse_docx(path: str) -> str:
    """解析 Word(.docx) 为纯文本：按文档顺序遍历段落与表格（含嵌套表格）。"""
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(path)
    body = doc.element.body
    parts = []
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            t = "".join((x.text or "") for x in child.iter(qn("w:t")))
            if t.strip():
                parts.append(t.strip())
        elif child.tag == qn("w:tbl"):
            t = _plain_table_text(child)
            if t:
                parts.append(t)
    return "\n".join(parts)


def _extract_drawing_image(el, rels, image_dir, rel_prefix, image_info, counter):
    """从 drawing/pict 元素中抽取图片，存储并返回引用标记。"""
    blip = el.find(f".//{{{_A_NS}}}blip")
    if blip is None:
        return None
    embed = blip.get(f"{{{_R_NS}}}embed")
    if not embed or embed not in rels:
        return None
    part = rels[embed]
    blob = part.blob

    # 名称：优先取文档图片的 alt 文本(descr) / 名称(name)
    cNvPr = el.find(f".//{{{_A_NS}}}cNvPr")
    name = ""
    if cNvPr is not None:
        name = (cNvPr.get("descr") or cNvPr.get("name") or "").strip()
    counter[0] += 1
    safe = re.sub(r'[\\/:*?"<>|\r\n]', "_", name or "image")
    ext = ".png"
    lower = safe.lower()
    if lower.endswith((".jpg", ".jpeg", ".gif", ".bmp", ".png")):
        ext = os.path.splitext(safe)[1]
        safe = os.path.splitext(safe)[0]
    filename = f"{counter[0]:03d}_{safe}{ext}"
    filepath = os.path.join(image_dir, filename)
    with open(filepath, "wb") as f:
        f.write(blob)
    # 相对 MEDIA_ROOT 的路径（用于前端拼接 /media/ 访问）
    rel_path = f"{rel_prefix}/{filename}" if rel_prefix else filename
    marker = f"【图片:{safe}】({rel_path})"
    image_info.append({"marker": marker, "path": filepath, "name": safe, "file": filename, "url": rel_path})
    return marker


def _para_to_text(p_el, rels, image_dir, rel_prefix, image_info, counter):
    buf = []
    for el in p_el:
        if el.tag.endswith("}r"):
            for sub in el:
                if sub.tag.endswith("}t"):
                    buf.append(sub.text or "")
                elif sub.tag.endswith("}drawing") or sub.tag.endswith("}pict"):
                    m = _extract_drawing_image(sub, rels, image_dir, rel_prefix, image_info, counter)
                    if m:
                        buf.append(m)
        elif el.tag.endswith("}drawing") or el.tag.endswith("}pict"):
            m = _extract_drawing_image(el, rels, image_dir, rel_prefix, image_info, counter)
            if m:
                buf.append(m)
        elif el.tag.endswith("}t"):
            buf.append(el.text or "")
    return "".join(buf).strip()


def _table_to_text(tbl_el, rels, image_dir, rel_prefix, image_info, counter):
    lines = []
    for row in tbl_el.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
        cell_texts = []
        for cell in row.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
            t = _cell_text(cell, rels, image_dir, rel_prefix, image_info, counter)
            cell_texts.append(t)
        lines.append(" | ".join([c for c in cell_texts if c]))
    return "\n".join([l for l in lines if l])


def _cell_text(tc_el, rels, image_dir, rel_prefix, image_info, counter):
    texts = []
    for p in tc_el.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        t = _para_to_text(p, rels, image_dir, rel_prefix, image_info, counter)
        if t:
            texts.append(t)
    return " ".join(texts)


def parse_docx_rich(path: str, image_dir: str, rel_prefix: str = ""):
    """解析图文 Word：抽取图片存储到 image_dir，并在文本中标记图片引用。

    返回 (文本, 图片信息列表 [ {marker, path, name, file, url} ])。
    """
    from docx import Document
    from docx.oxml.ns import qn

    os.makedirs(image_dir, exist_ok=True)
    doc = Document(path)
    rels = doc.part.related_parts
    body = doc.element.body
    parts = []
    image_info = []
    counter = [0]
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            t = _para_to_text(child, rels, image_dir, rel_prefix, image_info, counter)
            if t:
                parts.append(t)
        elif child.tag == qn("w:tbl"):
            t = _table_to_text(child, rels, image_dir, rel_prefix, image_info, counter)
            if t:
                parts.append(t)
    return "\n".join(parts), image_info


def parse_xlsx(path: str) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    lines = []
    for ws in wb.worksheets:
        lines.append(f"## 工作表：{ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def parse_markdown(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def parse_file(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return parse_docx(file_path)
    if ext in (".xlsx", ".xlsm"):
        return parse_xlsx(file_path)
    if ext in (".md", ".markdown", ".txt"):
        return parse_markdown(file_path)
    raise ValueError(f"不支持的文件类型：{ext}（支持 .docx / .xlsx / .md / .txt）")


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 80) -> list:
    """将长文本切成带重叠的块，便于向量化检索。"""
    if not text:
        return []
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - overlap
    return chunks


def save_upload(file, dest_dir: str, filename: str) -> str:
    """保存上传文件到磁盘，返回绝对路径。"""
    os.makedirs(dest_dir, exist_ok=True)
    file_path = os.path.join(dest_dir, filename)
    with open(file_path, "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
    return file_path
