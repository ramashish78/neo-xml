import io
import zipfile
from html import escape

from app.core.access import Access
from app.core.errors import AppError
from app.core.permissions import DM_APPROVED, DM_PUBLISH, DM_PUBLISHED
from app.repositories.base import DataModules, PublicationModules, TransformationJobs
from app.services.audit_service import AuditService
from app.services.content_helpers import check_code, next_code, require_active_workspace
from app.services.file_service import FileService


class PublishingService:
    def __init__(self, db):
        self.db = db
        self.publications = PublicationModules(db)
        self.jobs = TransformationJobs(db)
        self.modules = DataModules(db)
        self.files = FileService(db)
        self.access = Access(db)
        self.audit = AuditService(db)

    def create_publication(self, user: dict, body, ip: str) -> dict:
        require_active_workspace(self.db, user, self.access, body.workspace_id)
        self._modules_in_workspace(body.workspace_id, body.data_module_ids)
        code = check_code(body.pm_code, "publication code") if body.pm_code else next_code(
            self.publications, body.workspace_id, "pm_code", "PM"
        )
        doc = self.publications.insert(
            {
                "workspace_id": body.workspace_id,
                "pm_code": code,
                "title": body.title,
                "data_module_ids": body.data_module_ids,
                "status": "draft",
                "revision": 1,
                "created_by": str(user["_id"]),
            },
            "Duplicate publication code",
        )
        self.audit.record(str(user["_id"]), "publication.create", "publication_module", str(doc["_id"]), ip)
        return doc

    def list_publications(self, user: dict, workspace_id: str | None, limit: int, skip: int):
        query = {}
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
            query["workspace_id"] = workspace_id
        elif not self.access.is_super(user):
            query["workspace_id"] = {"$in": [str(item) for item in user.get("workspace_ids") or []]}
        return self.publications.list(query, limit, skip, [("updated_at", -1)])

    def get_publication(self, user: dict, publication_id: str) -> dict:
        doc = self.publications.get(publication_id)
        if not doc:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, doc["workspace_id"])
        return doc

    def patch_publication(self, user: dict, publication_id: str, body, ip: str) -> dict:
        doc = self.get_publication(user, publication_id)
        if doc["status"] == "published":
            raise AppError(409, "Published publication modules are immutable")
        fields = {}
        if body.title is not None:
            fields["title"] = body.title
        if body.data_module_ids is not None:
            self._modules_in_workspace(doc["workspace_id"], body.data_module_ids)
            fields["data_module_ids"] = body.data_module_ids
        updated = self.publications.update(publication_id, fields) if fields else doc
        self.audit.record(str(user["_id"]), "publication.update", "publication_module", publication_id, ip)
        return updated

    def run(self, user: dict, body, ip: str) -> dict:
        publication = self.get_publication(user, body.publication_id)
        modules = self._modules_in_workspace(publication["workspace_id"], publication["data_module_ids"])
        for module in modules:
            if module["status"] not in {DM_APPROVED, DM_PUBLISHED}:
                raise AppError(409, "Publishing requires approved content")
        job = self.jobs.insert(
            {
                "publication_id": str(publication["_id"]),
                "workspace_id": publication["workspace_id"],
                "scenario": body.scenario,
                "status": "running",
                "output_path": None,
                "output_file_id": None,
                "logs": [f"Started {body.scenario} transformation"],
                "created_by": str(user["_id"]),
            }
        )
        touched = []
        try:
            for module in modules:
                if module["status"] == DM_APPROVED:
                    self.modules.update(str(module["_id"]), {"status": DM_PUBLISH})
                    touched.append(str(module["_id"]))
            payload, ext, mime, name = self._render(publication, modules, body.scenario)
            stored = self.files.save_generated(
                "output",
                payload,
                ext,
                name,
                publication["workspace_id"],
                str(user["_id"]),
                mime,
            )
            for module_id in touched:
                self.modules.update(module_id, {"status": DM_PUBLISHED})
            self.publications.update(str(publication["_id"]), {"status": "published"})
            logs = [f"Started {body.scenario} transformation", f"Wrote {stored['relative_path']}"]
            updated = self.jobs.update(
                str(job["_id"]),
                {
                    "status": "completed",
                    "output_path": stored["relative_path"],
                    "output_file_id": str(stored["_id"]),
                    "logs": logs,
                },
            )
        except Exception as exc:
            for module_id in touched:
                self.modules.update(module_id, {"status": DM_APPROVED})
            self.jobs.update(
                str(job["_id"]),
                {"status": "failed", "logs": [f"Started {body.scenario} transformation", "Transformation failed"]},
            )
            if isinstance(exc, AppError):
                raise
            raise AppError(500, "Internal server error") from exc
        self.audit.record(str(user["_id"]), "publish.run", "publication_module", str(publication["_id"]), ip)
        return updated

    def get_job(self, user: dict, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if not job:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, job["workspace_id"])
        return job

    def _modules_in_workspace(self, workspace_id: str, ids: list[str]) -> list:
        found = []
        for module_id in ids:
            module = self.modules.get(module_id)
            if not module or module.get("workspace_id") != workspace_id:
                raise AppError(404, "Resource not found")
            found.append(module)
        return found

    def _render(self, publication: dict, modules: list, scenario: str):
        title = publication["title"]
        blocks = []
        for module in modules:
            xml = ""
            file_doc = self.files.repo.get(module["file_id"])
            if file_doc:
                xml = self.files.read_doc(file_doc).decode("utf-8", errors="replace")
            blocks.append((module["dmc"], module["title"], xml))
        if scenario == "web":
            html = self._html(title, blocks)
            return html.encode(), "html", "text/html", f"{publication['pm_code']}.html"
        if scenario == "pdf":
            lines = [title] + [f"{dmc} {name}" for dmc, name, _xml in blocks]
            return _simple_pdf(lines), "pdf", "application/pdf", f"{publication['pm_code']}.pdf"
        html = self._html(title, blocks)
        manifest = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            f"<ietp pm=\"{escape(publication['pm_code'])}\"><title>{escape(title)}</title></ietp>"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("index.html", html)
            archive.writestr("manifest.xml", manifest)
        return buffer.getvalue(), "zip", "application/zip", f"{publication['pm_code']}.zip"

    def _html(self, title: str, blocks: list[tuple[str, str, str]]) -> str:
        parts = [f"<html><head><title>{escape(title)}</title></head><body>", f"<h1>{escape(title)}</h1>"]
        for dmc, name, xml in blocks:
            parts.append(f"<h2>{escape(dmc)} {escape(name)}</h2>")
            parts.append(f"<pre>{escape(xml)}</pre>")
        parts.append("</body></html>")
        return "".join(parts)


def _simple_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 12 Tf"]
    y = 750
    for line in lines[:40]:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        safe = safe.encode("latin-1", errors="replace").decode("latin-1")[:90]
        commands.append(f"1 0 0 1 50 {y} Tm ({safe}) Tj")
        y -= 16
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        ),
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)
