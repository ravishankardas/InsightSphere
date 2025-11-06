// App.js
import React, { useState, useEffect } from "react";
import {
  SignUp,
  SignIn,
  SignedIn,
  SignedOut,
  UserButton,
  useUser,
} from "@clerk/clerk-react";
import "./App.css";
import PdfViewer from './PdfViewer';
import DeleteConfirmationModal from './components/DeleteConfirmationModal';

const TOOLS = [
  { id: "upload", title: "Upload", desc: "Add PDFs to build your knowledge base", icon: "📄" },
  { id: "search", title: "Search", desc: "Ask natural-language questions", icon: "🔎" },
  { id: "summaries", title: "Summaries", desc: "Auto-generate concise notes", icon: "📝" },
  { id: "topics", title: "Topic Map", desc: "Visualize topic clusters", icon: "🕸️" },
];

export default function App() {
  const API_KEY = process.env.REACT_APP_API_KEY;

  const { user, isSignedIn } = useUser(); // clerk hook
  const userId = user?.primaryEmailAddress?.emailAddress || user?.id || null;

  // Upload / preview
  const [file, setFile] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  // Query / answers
  const [query, setQuery] = useState("");
  const [querying, setQuerying] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);

  // Documents state
  const [documents, setDocuments] = useState([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState(null);
  
  // Delete modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [docToDelete, setDocToDelete] = useState(null);

  // UI state
  const [apiUrl, setApiUrl] = useState(
    process.env.NODE_ENV === 'development'
      ? process.env.REACT_APP_BACKEND_URL_DEV
      : process.env.REACT_APP_BACKEND_URL_PROD || 'https://insightsphere-production.up.railway.app'
  );

  const [showSettings, setShowSettings] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("signup"); // 'signup' or 'signin'
  const [activeTool, setActiveTool] = useState("welcome");

  // PDF viewer controls
  const [viewerPage, setViewerPage] = useState(null);
  const [highlight, setHighlight] = useState(null);

  // ensure modal opens if user tries something while signed out
  useEffect(() => {
    if (isSignedIn) {
      setShowAuthModal(false);
    }
  }, [isSignedIn]);

  // Load documents when user signs in
  useEffect(() => {
    if (isSignedIn && userId) {
      loadDocuments();
    } else {
      setDocuments([]);
    }
  }, [isSignedIn, userId]);

  // ---- Document Functions ----
  const loadDocuments = async () => {
    if (!userId) return;

    setLoadingDocuments(true);
    try {
      const headers = {
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      const res = await fetch(`${apiUrl}/api/documents`, {
        method: "GET",
        headers,
      });

      if (res.ok) {
        const data = await res.json();
        // Ensure documents is an array of filename strings or objects you expect
        setDocuments(data || []);

        // If there is no currently selectedDocument, pick the first one by default
        // Support both arrays of strings and arrays of objects with .source/.name
        if (!selectedDocument && data && data.length > 0) {
          const first = data[0];
          const firstName = typeof first === "string" ? first : (first.source || first.name || first.file || "");
          if (firstName) setSelectedDocument(firstName);
        }
      } else {
        console.error("Failed to load documents");
      }
    } catch (err) {
      console.error("Failed to load documents:", err);
    } finally {
      setLoadingDocuments(false);
    }
  };


  const handleDeleteClick = (filename) => {
    setDocToDelete(filename);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;

    setDeletingDoc(docToDelete);
    setShowDeleteModal(false);
    
    try {
      const headers = {
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      const res = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(docToDelete)}`, {
        method: "DELETE",
        headers,
      });

      if (res.ok) {
        // Remove from local state
        setDocuments(documents.filter(doc => doc !== docToDelete));
        
        // If the deleted document is currently being viewed, clear it
        if (file && file.name === docToDelete) {
          handleClearPreview();
        }
        
        // Show success message
        setUploadStatus({
          type: "success",
          message: `Document "${docToDelete}" deleted successfully.`
        });
        
        // Clear message after 3 seconds
        setTimeout(() => setUploadStatus(null), 3000);
      } else {
        const data = await res.json();
        setUploadStatus({
          type: "error",
          message: data.detail || "Failed to delete document."
        });
      }
    } catch (err) {
      setUploadStatus({
        type: "error",
        message: `Network error: ${err.message}`
      });
    } finally {
      setDeletingDoc(null);
      setDocToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setDocToDelete(null);
  };

  const handleDocumentClick = (filename) => {
    // You could implement logic here to load and display the document
    // For now, we'll just show a message
    setSelectedDocument(filename);
    console.log("Document clicked:", filename);
    // If you have a way to retrieve the document URL, you could set it here:
    // setFileUrl(documentUrl);
  };

  const handleClearSelection = () => {
    setSelectedDocument(null);
  };

  const handleSourceClick = (src) => {
    const page = src.metadata?.page ?? src.page ?? 1;
    setViewerPage(page);
    setHighlight({
      page,
      text: src.snippet || src.content?.slice(0, 100),
    });
  };

  // ---- Handlers ----
  const openSignUp = () => {
    setAuthMode("signup");
    setShowAuthModal(true);
  };
  const openSignIn = () => {
    setAuthMode("signin");
    setShowAuthModal(true);
  };

 const handleFileChange = (e) => {
    if (!isSignedIn) {
      setAuthMode("signup");
      setShowAuthModal(true);
      return;
    }
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    if (selectedFile.type !== "application/pdf") {
      setUploadStatus({ type: "error", message: "Please select a PDF file." });
      return;
    }

    // Clear old URL before setting new one
    if (fileUrl) {
      URL.revokeObjectURL(fileUrl);
    }

    setFile(selectedFile);
    setUploadStatus(null);
    const url = URL.createObjectURL(selectedFile);
    setFileUrl(url);
    setViewerPage(1);
    setHighlight(null);
    setActiveTool("upload");

    // <-- NEW: Make the newly-selected file the active/selected document
    // Use the filename as the identifier that will be sent to the backend
    setSelectedDocument(selectedFile.name);
  };


  const handleUpload = async () => {
    // 1. NEW SECURITY CHECK: Ensure API Key is available
    if (!API_KEY) {
        setUploadStatus({ type: "error", message: "Configuration Error: Missing API Key." });
        // Setting uploading to false is crucial here to unblock the UI
        setUploading(false); 
        return;
    }

    if (!isSignedIn) {
        setAuthMode("signup");
        setShowAuthModal(true);
        return;
    }
    if (!file) {
        setUploadStatus({ type: "error", message: "Please select a file first." });
        return;
    }

    setUploading(true);
    setUploadStatus(null);
    const formData = new FormData();
    formData.append("file", file);

    try {
        // 2. CORRECTLY ADDING CUSTOM HEADERS FOR FILE UPLOAD
        const headers = { 
            "X-API-Key": API_KEY,
        };
        
        // This is safe because 'FormData' handles the Content-Type automatically.
        if (userId){
            headers["X-User-Id"] = userId;
        }
        
        // Use the smart auto-detection endpoint with balanced preset
        const res = await fetch(`${apiUrl}/api/upload/pdf/auto?preset=balanced`, {
            method: "POST",
            headers,
            body: formData,
        });
        
        const data = await res.json();
        
        if (res.ok) {
        // Build success message with details
        const chunks = data.text_chunks || data.indexed_chunks || 0;
        const tables = data.tables || 0;
        const images = data.images || 0;
        const mode = data.mode_used || 'unknown';
        const complexity = data.complexity_score;

        let message = `Indexed ${chunks} chunks`;

        if (tables > 0 || images > 0) {
            const parts = [];
            if (tables > 0) parts.push(`${tables} tables`);
            if (images > 0) parts.push(`${images} images`);
            message += ` (${parts.join(', ')})`;
        }

        if (complexity !== undefined) {
            message += ` • Mode: ${mode} (complexity: ${complexity}/100)`;
        }

        setUploadStatus({
            type: "success",
            message: message,
        });

        // Reload documents list
        loadDocuments();

        // <-- NEW: If backend returned canonical filename (data.file.source or data.file.name),
        // use that as the selected document. Otherwise fallback to the local file.name.
        const returnedName = data?.file?.source || data?.file?.name || file?.name;
        if (returnedName) {
            setSelectedDocument(returnedName);
        }

        // Keep local preview active (fileUrl)
        setActiveTool("upload");
    } else {
        setUploadStatus({ 
            type: "error", 
            message: data.detail || data.message || "Upload failed." 
        });
    }

    } catch (err) {
        setUploadStatus({ 
            type: "error", 
            message: `Network error: ${err.message}` 
        });
    } finally {
        setUploading(false);
    }
};

  const handleClearPreview = () => {
    if (fileUrl) {
      URL.revokeObjectURL(fileUrl);
    }
    setFile(null);
    setFileUrl(null);
    setViewerPage(null);
    setHighlight(null);
    setUploadStatus(null);
    setAnswer(null);
    setQuery("");
  };

  const handleQuery = async () => {
    // Security / prechecks
    if (!API_KEY) {
      console.error("API Key is missing. Cannot make secure request.");
      setAnswer({ type: "error", message: "Configuration Error: Missing API Key." });
      setQuerying(false);
      return;
    }

    if (!isSignedIn) {
      setAuthMode("signup");
      setShowAuthModal(true);
      return;
    }
    if (!query.trim()) {
      setAnswer({ type: "error", message: "Please enter a question." });
      return;
    }

    // You must have selected a document to query its vectors
    if (!selectedDocument) {
      setAnswer({ type: "error", message: "Select a document from 'My Documents' to query." });
      return;
    }

    setQuerying(true);
    setAnswer(null);
    setHighlight(null);

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      };

      if (userId) {
        headers["X-User-Id"] = userId;
      }

      // Normalize the filename to match how you store 'source' in the vector DB.
      const normalizedSource = String(selectedDocument).trim().toLowerCase();

      const bodyPayload = {
        query: query.trim(),
        top_k: 4,
        source: normalizedSource,
        use_query_rewriting: true
      };

      const res = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
      });

      const data = await res.json();

      if (res.ok) {
        setAnswer({
          type: "success",
          answer: data.answer || "No answer provided.",
          retrieved: data.retrieved || [],
        });
      } else {
        setAnswer({
          type: "error",
          message: data.detail || data.message || "Query failed.",
        });
      }
    } catch (err) {
      setAnswer({
        type: "error",
        message: `Network error: ${err.message}`,
      });
    } finally {
      setQuerying(false);
      setQuery("");
    }
  };


  return (
    <div className="app-container">
      {/* Delete Confirmation Modal */}
      <DeleteConfirmationModal
        show={showDeleteModal}
        filename={docToDelete}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="modal-overlay" onClick={() => setShowAuthModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowAuthModal(false)}>
              ×
            </button>
            <div className="auth-container">
              {authMode === "signup" ? (
                <SignUp routing="virtual" signInUrl="#" />
              ) : (
                <SignIn routing="virtual" signUpUrl="#" />
              )}
              {authMode === "signup" ? (
                <p>
                  Already have an account?{" "}
                  <button className="auth-switch-link" onClick={() => setAuthMode("signin")}>
                    Sign In
                  </button>
                </p>
              ) : (
                <p>
                  Don't have an account?{" "}
                  <button className="auth-switch-link" onClick={() => setAuthMode("signup")}>
                    Sign Up
                  </button>
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Top nav */}
      <nav className="top-nav">
        <div className="nav-content">
          <div className="nav-brand">
            <div className="brand-icon">IS</div>
            <span className="brand-name">InsightSphere</span>
          </div>

          <div className="nav-actions">
            <button className="settings-button" aria-label="Toggle settings" title="Settings"> ⚙️
            </button>

            <SignedOut>
              <button className="primary-button small auth-button-fixed" onClick={openSignIn}>
                Sign In
              </button>
              <button className="primary-button small auth-button-fixed" onClick={openSignUp}>
                Sign Up
              </button>
            </SignedOut>

            <SignedIn>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <UserButton afterSignOutUrl="/" />
              </div>
            </SignedIn>
          </div>
        </div>
      </nav>

      {/* Settings panel */}
      {showSettings && (
        <div className="settings-panel">
          <div className="settings-content">
            <label className="settings-label">Backend API URL</label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="settings-input"
              placeholder="https://api.example.com"
            />
            <p className="card-subtitle" style={{ marginTop: 8 }}>
              Overrides REACT_APP_BACKEND_URL for local testing.
            </p>
          </div>
        </div>
      )}

      {/* Three-column main layout */}
      <div className="main-content three-column">
        {/* LEFT: Documents panel */}
        <div className="documents-panel">
          <div className="content-card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h2 className="card-title">My Documents</h2>
                  <p className="card-subtitle">Uploaded PDFs ({documents.length})</p>
                </div>
                {selectedDocument && (
                  <button 
                    className="clear-selection-button" 
                    onClick={handleClearSelection}
                    title="Clear selection"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
                        
            {!isSignedIn ? (
              <div className="empty-state">
                <div className="empty-icon">🔒</div>
                <p className="empty-text">Sign in to view your documents</p>
              </div>
            ) : loadingDocuments ? (
              <div className="empty-state">
                <div className="empty-icon">⏳</div>
                <p className="empty-text">Loading documents...</p>
              </div>
            ) : documents.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📄</div>
                <p className="empty-text">No documents yet. Upload a PDF to get started!</p>
              </div>
            ) : (
              <div className="documents-list">
                {documents.map((doc, idx) => (
                  <div 
                    key={idx} 
                    className={`document-item ${selectedDocument === doc ? 'selected' : ''}`}
                  >
                    <div 
                      className="document-content"
                      onClick={() => handleDocumentClick(doc)}
                    >
                      <div className="document-icon">📄</div>
                      <div className="document-info">
                        <div className="document-name" title={doc}>{doc}</div>
                      </div>
                    </div>
                    <button
                      className="delete-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteClick(doc);
                      }}
                      disabled={deletingDoc === doc}
                      title="Delete document"
                    >
                      {deletingDoc === doc ? "⏳" : "D"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* CENTER: PDF viewer */}
        <div className="center-panel">
          <PdfViewer fileUrl={fileUrl} />
        </div>

        {/* RIGHT: Controls */}
        <div className="controls-panel">
          {/* Tools sidebar header (small) */}
          <div className="content-card" style={{ padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, color: "var(--primary)" }}>InsightSphere</div>
                <div className="small muted">Tools & actions</div>
              </div>
              <div>
                <SignedIn>
                  <div className="small muted">Signed in as {user?.firstName ?? user?.email ?? "you"}</div>
                </SignedIn>
                <SignedOut>
                  <div className="small muted">Sign in to save your library</div>
                </SignedOut>
              </div>
            </div>
          </div>

          {/* Upload card */}
          <section className="content-card">
            <div className="card-header">
              <h2 className="card-title">Upload Document</h2>
              <p className="card-subtitle">Upload PDFs to your private collection</p>
            </div>

            <div className="upload-area">
              <input type="file" accept=".pdf" onChange={handleFileChange} id="file-upload" className="file-input-hidden" />
              <label
                htmlFor="file-upload"
                className={`file-dropzone ${!isSignedIn ? "disabled" : ""}`}
                onClick={(e) => {
                  if (!isSignedIn) {
                    e.preventDefault();
                    openSignUp();
                  }
                }}
              >
                {file ? (
                  <div className="file-preview">
                    <div className="file-icon">📄</div>
                    <div className="file-meta">
                      <div className="file-name">{file.name}</div>
                      <div className="file-size">{(file.size / 1024).toFixed(2)} KB</div>
                    </div>
                  </div>
                ) : (
                  <div className="upload-prompt">
                    <div className="upload-icon">⬆️</div>
                    <div className="upload-text">{isSignedIn ? "Drop PDF here or click to browse" : "Create an account to upload documents"}</div>
                  </div>
                )}
              </label>

              <div className="action-row">
                <button onClick={handleUpload} disabled={uploading || !file} className="secondary-button">
                  {uploading ? "Processing..." : "Upload"}
                </button>
                <button onClick={handleClearPreview} disabled={!fileUrl} className="secondary-button">
                  Clear Preview
                </button>
              </div>

              {uploadStatus && (
                <div className={`alert alert-${uploadStatus.type}`}>
                  <div className="alert-icon">{uploadStatus.type === "success" ? "✓" : "⚠"}</div>
                  <div className="alert-text">{uploadStatus.message}</div>
                </div>
              )}
            </div>
          </section>

          {/* Query card */}
          <section className="content-card">
            <div className="card-header">
              <h2 className="card-title">Search Documents</h2>
              <p className="card-subtitle">Ask questions and get answers with cited snippets</p>
            </div>

            <div className="query-area">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="query-input"
                rows="4"
                placeholder={isSignedIn ? "Ask something like: What are the main contributions?" : "Sign in to search"}
                disabled={!isSignedIn}
              />
              <div className="action-row">
                <button onClick={handleQuery} disabled={querying || !query.trim() || !isSignedIn} className="secondary-button">
                  {querying ? "Searching..." : "Ask"}
                </button>
                <button
                  onClick={() => {
                    setQuery("");
                    setAnswer(null);
                    setHighlight(null);
                  }}
                  className="secondary-button"
                >
                  Clear
                </button>
              </div>
            </div>
          </section>

          {/* Answer / Sources */}
          {answer && (
            <section className="content-card answer-section">
              <div className="card-header">
                <h2 className="card-title">Response</h2>
              </div>

              {answer.type === "error" ? (
                <div className="alert alert-error">
                  <div className="alert-icon">⚠</div>
                  <div className="alert-text">{answer.message}</div>
                </div>
              ) : (
                <>
                  <div className="answer-box">
                    <p className="answer-text">{answer.answer}</p>
                  </div>

                  {answer.retrieved && answer.retrieved.length > 0 && (
                    <div className="sources-section">
                      <h3 className="sources-title">Sources</h3>
                      <div className="sources-grid">
                        {answer.retrieved.map((src, idx) => (
                          <div key={idx} className="source-item" onClick={() => handleSourceClick(src)}>
                            <div className="source-header">
                              <span className="source-number">{idx + 1}</span>
                              <span className="source-score">{src.distance ? `${((1 - src.distance) * 100).toFixed(1)}%` : ""}</span>
                            </div>
                            <div className="source-filename">{src.metadata?.source || src.metadata?.file || "Document"}</div>
                            <div className="source-chunk small">{src.snippet ?? (src.content && src.content.slice(0, 160) + "...")}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}