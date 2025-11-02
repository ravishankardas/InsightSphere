// PdfViewer.jsx
import React, { useRef, useState, useEffect } from "react";
import { Document, Page } from "react-pdf";
import "./App.css";

import { pdfjs } from "react-pdf";
// Use the worker entry which works in many setups

// Use the static worker we copied into public/
pdfjs.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL || ""}/pdf.worker.min.mjs`;




export default function PdfViewer({ fileUrl, goToPage, highlightSnippet }) {
  // fileUrl: blob/object url or remote url to PDF
  // goToPage: integer page to jump to (1-index)
  // highlightSnippet: { page, snippet, sourceIndex } OR null

  const [numPages, setNumPages] = useState(null);
  const [pageHeight, setPageHeight] = useState({});
  const containerRef = useRef();
  const pageRefs = useRef({}); // refs per page element

  useEffect(() => {
    if (goToPage && pageRefs.current[goToPage]) {
      // scroll page into view smoothly
      pageRefs.current[goToPage].scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [goToPage, fileUrl]);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    // small reset of page refs
    pageRefs.current = {};
  }

  // small helper to render highlight overlay next to page
  const renderHighlightOverlay = () => {
    if (!highlightSnippet || !highlightSnippet.page) return null;
    const page = highlightSnippet.page;
    const el = pageRefs.current[page];
    if (!el) {
      // page not rendered yet
      return null;
    }

    // We'll place the overlay at the top of the page (approximate highlight)
    return (
      <div
        className="pdf-highlight-overlay"
        style={{
          top: el.getBoundingClientRect().top - containerRef.current.getBoundingClientRect().top + 12,
        }}
      >
        <div className="pdf-highlight-badge">Related</div>
        <div className="pdf-highlight-snippet">{highlightSnippet.snippet}</div>
      </div>
    );
  };

  return (
    <div className="pdf-viewer-wrapper" ref={containerRef}>
      {!fileUrl ? (
        <div className="pdf-empty">
          <div className="pdf-empty-emoji">📄</div>
          <div className="pdf-empty-text">No document loaded. Upload a PDF or select a document.</div>
        </div>
      ) : (
        <div className="pdf-doc-scroll">
          <Document file={fileUrl} onLoadSuccess={onDocumentLoadSuccess} renderMode="canvas">
            {Array.from(new Array(numPages), (el, index) => (
              <div
                key={`page_${index + 1}`}
                ref={(r) => (pageRefs.current[index + 1] = r)}
                className="pdf-page-wrapper"
              >
                <Page pageNumber={index + 1} width={700} />
                {/* placeholder for precise bbox-based highlights in future */}
              </div>
            ))}
          </Document>
          {/* overlay (positioned absolute relative to wrapper) */}
          {renderHighlightOverlay()}
        </div>
      )}
    </div>
  );
}
