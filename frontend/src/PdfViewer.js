// PdfViewer.jsx
import React from "react";
import "./App.css";

export default function PdfViewer({ fileUrl }) {
  return (
    <div className="pdf-viewer-wrapper">
      {!fileUrl ? (
        <div className="pdf-empty">
          <div className="pdf-empty-emoji">📄</div>
          <div className="pdf-empty-text">No document loaded. Upload a PDF to view it here.</div>
        </div>
      ) : (
        <div className="pdf-doc-scroll">
          <iframe
            src={fileUrl}
            title="PDF Viewer"
            width="100%"
            height="100%"
            style={{
              border: "none",
              minHeight: "800px"
            }}
          />
        </div>
      )}
    </div>
  );
}