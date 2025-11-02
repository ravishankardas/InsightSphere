import React, { useState } from 'react';
import { SignUp, SignIn, SignedIn, SignedOut, UserButton, useUser } from '@clerk/clerk-react';
import './App.css';

function App() {
  const { user, isSignedIn } = useUser();
  const userId = user?.primaryEmailAddress?.emailAddress;

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  
  const [query, setQuery] = useState('');
  const [querying, setQuerying] = useState(false);
  const [answer, setAnswer] = useState(null);
  
  const [apiUrl, setApiUrl] = useState(process.env.BACKEND_URL || 'https://insightsphere-production.up.railway.app');
  const [showSettings, setShowSettings] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState('signup'); // 'signup' or 'signin'

  const handleFileChange = (e) => {
    if (!isSignedIn) {
      setAuthMode('signup');
      setShowAuthModal(true);
      return;
    }
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setUploadStatus(null);
    } else {
      setUploadStatus({ type: 'error', message: 'Please select a valid PDF file' });
    }
  };

  const handleUpload = async () => {
    if (!isSignedIn) {
      setAuthMode('signup');
      setShowAuthModal(true);
      return;
    }
    if (!file) {
      setUploadStatus({ type: 'error', message: 'Please select a file first' });
      return;
    }

    setUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${apiUrl}/api/upload/pdf`, {
        method: 'POST',
        headers: {
          'X-User-Id': userId,
        },
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setUploadStatus({
          type: 'success',
          message: `Document indexed successfully. ${data.indexed_chunks} chunks processed.`,
        });
        setFile(null);
        const fileInput = document.getElementById('file-upload');
        if (fileInput) fileInput.value = '';
      } else {
        setUploadStatus({
          type: 'error',
          message: data.detail || 'Upload failed',
        });
      }
    } catch (error) {
      setUploadStatus({
        type: 'error',
        message: `Connection error: ${error.message}`,
      });
    } finally {
      setUploading(false);
    }
  };

  const handleQuery = async () => {
    if (!isSignedIn) {
      setAuthMode('signup');
      setShowAuthModal(true);
      return;
    }
    if (!query.trim()) return;

    setQuerying(true);
    setAnswer(null);

    try {
      const response = await fetch(`${apiUrl}/api/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userId,
        },
        body: JSON.stringify({
          query: query,
          top_k: 4,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setAnswer({
          type: 'success',
          answer: data.answer,
          sources: data.sources,
          retrieved: data.retrieved,
        });
      } else {
        setAnswer({
          type: 'error',
          message: data.detail || 'Query failed',
        });
      }
    } catch (error) {
      setAnswer({
        type: 'error',
        message: `Connection error: ${error.message}`,
      });
    } finally {
      setQuerying(false);
    }
  };

  const handleQueryKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  const openSignUp = () => {
    setAuthMode('signup');
    setShowAuthModal(true);
  };

  const openSignIn = () => {
    setAuthMode('signin');
    setShowAuthModal(true);
  };

  return (
    <div className="app-container">
      {/* Auth Modal - Separate Sign Up and Sign In */}
      {showAuthModal && (
        <div className="modal-overlay" onClick={() => setShowAuthModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowAuthModal(false)}>×</button>
            <div className="modal-header">
              <div className="brand-icon-large">IS</div>
              {authMode === 'signup' ? (
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

            {authMode === 'signup' ? (
              <SignUp 
                routing="virtual"
                appearance={{
                  elements: {
                    rootBox: "mx-auto",
                    card: "shadow-none"
                  }
                }}
                afterSignUpUrl="/"
              />
            ) : (
              <SignIn 
                routing="virtual"
                appearance={{
                  elements: {
                    rootBox: "mx-auto",
                    card: "shadow-none"
                  }
                }}
                afterSignInUrl="/"
              />
            )}

            <div className="auth-switch">
              {authMode === 'signup' ? (
                <p>
                  Already have an account?{' '}
                  <button className="auth-switch-link" onClick={() => setAuthMode('signin')}>
                    Sign In
                  </button>
                </p>
              ) : (
                <p>
                  Don't have an account?{' '}
                  <button className="auth-switch-link" onClick={() => setAuthMode('signup')}>
                    Sign Up
                  </button>
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Top Navigation */}
      <nav className="top-nav">
        <div className="nav-content">
          <div className="nav-brand">
            <div className="brand-icon">IS</div>
            <span className="brand-name">InsightSphere</span>
          </div>
          <div className="nav-actions">
            <button 
              className="settings-button"
              onClick={() => setShowSettings(!showSettings)}
            >
              ⚙️
            </button>
            <SignedOut>
              <button 
                className="secondary-button"
                onClick={openSignIn}
              >
                Sign In
              </button>
              <button 
                className="login-button"
                onClick={openSignUp}
              >
                Sign Up
              </button>
            </SignedOut>
            <SignedIn>
              <UserButton afterSignOutUrl="/" />
            </SignedIn>
          </div>
        </div>
      </nav>

      {/* Settings Panel */}
      {showSettings && (
        <div className="settings-panel">
          <div className="settings-content">
            <label className="settings-label">Backend API URL</label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="settings-input"
              placeholder="https://insightsphere-production.up.railway.app"
            />
          </div>
        </div>
      )}

      <div className="main-content">
        {/* User Info Sidebar */}
        <aside className="sidebar">
          <SignedOut>
            <div className="sidebar-section">
              <div className="login-prompt-card">
                <div className="login-prompt-icon">🚀</div>
                <h3 className="login-prompt-title">Get Started</h3>
                <p className="login-prompt-text">
                  Create a free account to upload documents and access your personal AI-powered knowledge base.
                </p>
                <button 
                  className="primary-button"
                  onClick={openSignUp}
                >
                  Create Account
                </button>
                <div className="sidebar-signin-link">
                  Already have an account?{' '}
                  <button className="link-button" onClick={openSignIn}>
                    Sign In
                  </button>
                </div>
              </div>
            </div>
          </SignedOut>

          <SignedIn>
            <div className="sidebar-section">
              <h3 className="sidebar-title">Current User</h3>
              <div className="user-profile-card">
                <img 
                  src={user?.imageUrl} 
                  alt={user?.firstName || 'User'}
                  className="user-profile-image"
                />
                <div className="user-profile-info">
                  <div className="user-profile-name">
                    {user?.firstName} {user?.lastName}
                  </div>
                  <div className="user-profile-email">{userId}</div>
                </div>
              </div>
            </div>
          </SignedIn>
        </aside>

        {/* Main Content Area */}
        <main className="content-area">
          {/* Upload Section */}
          <section className="content-card">
            <div className="card-header">
              <h2 className="card-title">Document Upload</h2>
              <p className="card-subtitle">Upload PDF documents to build your knowledge base</p>
            </div>
            
            <div className="upload-area">
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="file-input-hidden"
                id="file-upload"
                disabled={!isSignedIn}
              />
              <label 
                htmlFor="file-upload" 
                className={`file-dropzone ${!isSignedIn ? 'disabled' : ''}`}
                onClick={(e) => {
                  if (!isSignedIn) {
                    e.preventDefault();
                    openSignUp();
                  }
                }}
              >
                {file ? (
                  <>
                    <div className="file-icon-success">📄</div>
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">{(file.size / 1024).toFixed(2)} KB</div>
                  </>
                ) : (
                  <>
                    <div className="upload-icon">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                      </svg>
                    </div>
                    <div className="upload-text">
                      {isSignedIn ? 'Drop PDF here or click to browse' : 'Create an account to upload documents'}
                    </div>
                    {isSignedIn && <div className="upload-hint">Maximum file size: 10MB</div>}
                  </>
                )}
              </label>

              <button
                onClick={handleUpload}
                disabled={uploading || !file}
                className="primary-button"
              >
                {uploading ? 'Processing...' : 'Upload Document'}
              </button>

              {uploadStatus && (
                <div className={`alert alert-${uploadStatus.type}`}>
                  <div className="alert-icon">
                    {uploadStatus.type === 'success' ? '✓' : '⚠'}
                  </div>
                  <div className="alert-text">{uploadStatus.message}</div>
                </div>
              )}
            </div>
          </section>

          {/* Query Section */}
          <section className="content-card">
            <div className="card-header">
              <h2 className="card-title">Ask Questions</h2>
              <p className="card-subtitle">Query your documents using natural language</p>
            </div>

            <div className="query-area">
              <div className="query-input-wrapper">
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyPress={handleQueryKeyPress}
                  placeholder={isSignedIn ? "What would you like to know?" : "Create an account to search your documents"}
                  className="query-input"
                  rows="4"
                  disabled={!isSignedIn}
                />
              </div>

              <button
                onClick={handleQuery}
                disabled={querying || !query.trim() || !isSignedIn}
                className="primary-button"
              >
                {querying ? 'Searching...' : 'Search Documents'}
              </button>
            </div>
          </section>

          {/* Answer Section */}
          {answer && (
            <section className="content-card answer-section">
              <div className="card-header">
                <h2 className="card-title">Response</h2>
              </div>
              
              {answer.type === 'error' ? (
                <div className="alert alert-error">
                  <div className="alert-icon">⚠</div>
                  <div className="alert-text">{answer.message}</div>
                </div>
              ) : (
                <div className="answer-content">
                  <div className="answer-box">
                    <p className="answer-text">{answer.answer}</p>
                  </div>

                  {answer.retrieved && answer.retrieved.length > 0 && (
                    <div className="sources-section">
                      <h3 className="sources-title">Source Documents ({answer.retrieved.length})</h3>
                      <div className="sources-grid">
                        {answer.retrieved.map((source, idx) => (
                          <div key={idx} className="source-item">
                            <div className="source-header">
                              <span className="source-number">{idx + 1}</span>
                              {source.distance && (
                                <span className="source-score">
                                  {((1 - source.distance) * 100).toFixed(1)}% match
                                </span>
                              )}
                            </div>
                            {source.meta && (
                              <div className="source-meta">
                                <div className="source-filename">{source.meta.source}</div>
                                {source.meta.chunk_index !== undefined && (
                                  <div className="source-chunk">Chunk {source.meta.chunk_index}</div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;