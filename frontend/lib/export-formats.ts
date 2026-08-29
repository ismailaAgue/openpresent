// Shared export-format metadata (ADR-049) — extracted from studio/
// page.tsx's FORMAT_CONFIG so the project editor page can offer the
// same format choices without a third copy of this table. One source
// of truth for "what formats exist, what do we call them, what's
// their file extension" across every page that needs to know.

export type ExportFormat = "pptx" | "document_docx" | "document_pdf";

export interface ExportFormatMeta {
  format: ExportFormat;
  label: string;       // "presentation", "document", ...
  shortLabel: string;  // "Slides", "Document", ... — for compact UI like a <select>
  extension: string;   // "pptx", "docx", "pdf"
  isSvg: boolean;
}

export const EXPORT_FORMATS: ExportFormatMeta[] = [
  { format: "pptx", label: "presentation", shortLabel: "Slides (.pptx)", extension: "pptx", isSvg: false },
  { format: "document_docx", label: "document", shortLabel: "Document (.docx)", extension: "docx", isSvg: false },
  { format: "document_pdf", label: "PDF", shortLabel: "Document (.pdf)", extension: "pdf", isSvg: false },
];

export function exportFormatMeta(format: string): ExportFormatMeta {
  return EXPORT_FORMATS.find((f) => f.format === format) ?? EXPORT_FORMATS[0];
}
