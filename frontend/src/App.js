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

const TOOLS = [
  { id: "upload", title: "Upload", desc: "Add PDFs to build your knowledge base", icon: "📄" },
  { id: "search", title: "Search", desc: "Ask natural-language questions", icon: "🔎" },
  { id: "summaries", title: "Summaries", desc: "Auto-generate concise notes", icon: "📝" },
  { id: "topics", title: "Topic Map", desc: "Visualize topic clusters", icon: "🕸️" },
];

export default function App() {
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
    setFile(selectedFile);
    setUploadStatus(null);
    const url = URL.createObjectURL(selectedFile);
    setFileUrl(url);
    setViewerPage(1);
    setHighlight(null);
    // auto-switch to upload tool so user sees preview
    setActiveTool("upload");
  };

  const handleUpload = async () => {
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
      const headers = {};
      if (userId) headers["X-User-Id"] = userId;
      const res = await fetch(`${apiUrl}/api/upload/pdf`, {
        method: "POST",
        headers,
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setUploadStatus({
          type: "success",
          message: `Indexed ${data.indexed_chunks ?? data.n_chunks ?? 0} chunks.`,
        });
        // Keep local preview active (fileUrl)
        setActiveTool("upload");
      } else {
        setUploadStatus({ type: "error", message: data.detail || data.message || "Upload failed." });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Network error: ${err.message}` });
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
  };

  const handleQuery = async () => {
    if (!isSignedIn) {
      setAuthMode("signup");
      setShowAuthModal(true);
      return;
    }
    if (!query.trim()) return;

    setQuerying(true);
    setAnswer(null);
    setHighlight(null);

    try {
      const headers = { "Content-Type": "application/json" };
      if (userId) headers["X-User-Id"] = userId;
      const res = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query: query, top_k: 4 }),
      });
      const data = await res.json();
      if (res.ok) {
        // Normalize sources/retrieved fields
        const retrieved = data.retrieved ?? data.sources ?? data.results ?? [];
        setAnswer({ type: "success", answer: data.answer ?? "", retrieved });

        // If first retrieved has page, jump and highlight
        const first = retrieved?.[0];
        if (first) {
          // backend metadata naming can vary; try common keys
          const page =
            first.metadata?.page ??
            first.metadata?.page_number ??
            first.page ??
            first.page_number ??
            first.pageIndex ??
            null;
          const snippet = first.snippet ?? first.content ?? first.text ?? first.display_content ?? "";
          if (page) {
            setViewerPage(Number(page));
            setHighlight({ page: Number(page), snippet });
            // switch to left viewer visible (upload tool shows it already), ensure active tool visible
            setActiveTool("upload");
          } else {
            // fallback: show snippet overlay without page move
            setHighlight({ page: 1, snippet });
          }
        }
      } else {
        setAnswer({ type: "error", message: data.detail || data.message || "Query failed." });
      }
    } catch (err) {
      setAnswer({ type: "error", message: `Network error: ${err.message}` });
    } finally {
      setQuerying(false);
    }
  };

  // click source -> jump & highlight
  const handleSourceClick = (src) => {
    const page =
      src.metadata?.page ??
      src.metadata?.page_number ??
      src.page ??
      src.page_number ??
      src.pageIndex ??
      null;
    const snippet = src.snippet ?? src.content ?? src.text ?? src.display_content ?? "";
    if (page) {
      setViewerPage(Number(page));
      setHighlight({ page: Number(page), snippet });
      setActiveTool("upload");
    } else {
      setHighlight({ page: 1, snippet });
    }
  };

  // ---- Render ----
  return (
    <div className="app-container">
      {/* Auth modal */}
      {showAuthModal && (
        <div className="modal-overlay" onClick={() => setShowAuthModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowAuthModal(false)}>
              ×
            </button>
            <div className="modal-header">
              <div className="brand-icon-large">IS</div>
              {authMode === "signup" ? (
                <>
                  <h2 className="modal-title">Create Your Account</h2>
                  <p className="modal-subtitle">Join InsightSphere to start building your knowledge base</p>
                </>
              ) : (
                <>
                  <h2 className="modal-title">Welcome Back</h2>
                  <p className="modal-subtitle">Sign in to access your documents</p>
                </>
              )}
            </div>

            {authMode === "signup" ? (
              <SignUp routing="virtual" appearance={{ elements: { rootBox: "mx-auto", card: "shadow-none" } }} afterSignUpUrl="/" />
            ) : (
              <SignIn routing="virtual" appearance={{ elements: { rootBox: "mx-auto", card: "shadow-none" } }} afterSignInUrl="/" />
            )}

            <div className="auth-switch">
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
            <button className="settings-button" onClick={() => setShowSettings(!showSettings)} aria-label="Toggle settings" title="Settings">
              ⚙️
            </button>

            <SignedOut>
              <button className="ghost-button" onClick={openSignIn}>
                Sign In
              </button>
              <button className="primary-button small" onClick={openSignUp}>
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

      {/* Two-column main */}
      <div className="main-content two-column">
        {/* LEFT: PDF viewer (flexible) */}
        <div className="left-panel">
          <PdfViewer fileUrl={fileUrl} goToPage={viewerPage} highlightSnippet={highlight} />
        </div>

        {/* RIGHT: Controls */}
        <div className="right-panel">
          {/* Tools sidebar header (small) */}
          <div className="content-card" style={{ padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 800, color: "var(--primary)" }}>InsightSphere</div>
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
                <button onClick={handleUpload} disabled={uploading || !file} className="primary-button">
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
                <button onClick={handleQuery} disabled={querying || !query.trim() || !isSignedIn} className="primary-button">
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
