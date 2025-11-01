import React, { useState } from 'react';
import './App.css';

function App() {
  const [userId, setUserId] = useState('alice@example.com');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  
  const [query, setQuery] = useState('');
  const [querying, setQuerying] = useState(false);
  const [answer, setAnswer] = useState(null);
  
  // const [apiUrl, setApiUrl] = useState('http://localhost:8000');
  const [apiUrl, setApiUrl] = useState('https://insightsphere-production.up.railway.app');
  console.log('API URL:', apiUrl);

  const [showSettings, setShowSettings] = useState(false);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setUploadStatus(null);
    } else {
      setUploadStatus({ type: 'error', message: 'Please select a valid PDF file' });
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setUploadStatus({ type: 'error', message: 'Please select a file first' });
      return;
    }
    if (!userId) {
      setUploadStatus({ type: 'error', message: 'Please enter a user ID' });
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
    if (!query.trim()) return;
    if (!userId) {
      setAnswer({ type: 'error', message: 'Please enter a user ID' });
      return;
    }

    setQuerying(true);
    setAnswer(null);

    try {
      console.log('`${apiUrl}/api/query`:', `${apiUrl}/api/query`);
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

  const quickUserSwitch = (email) => {
    setUserId(email);
    setAnswer(null);
    setUploadStatus(null);
  };

  const handleQueryKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  return (
    <div className="app-container">
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
              placeholder="http://localhost:8000"
            />
          </div>
        </div>
      )}

      <div className="main-content">
        {/* User Selection Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-section">
            <h3 className="sidebar-title">Current User</h3>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="user-input-sidebar"
              placeholder="user@example.com"
            />
          </div>

          <div className="sidebar-section">
            <h3 className="sidebar-title">Quick Switch</h3>
            <div className="user-list">
              {[
                { email: 'alice@example.com', name: 'Alice Chen', avatar: 'AC', color: '#6366f1' },
                { email: 'bob@example.com', name: 'Bob Smith', avatar: 'BS', color: '#8b5cf6' },
                { email: 'charlie@example.com', name: 'Charlie Wu', avatar: 'CW', color: '#ec4899' }
              ].map((user) => (
                <button
                  key={user.email}
                  onClick={() => quickUserSwitch(user.email)}
                  className={`user-card ${userId === user.email ? 'active' : ''}`}
                >
                  <div className="user-avatar" style={{ backgroundColor: user.color }}>
                    {user.avatar}
                  </div>
                  <div className="user-info">
                    <div className="user-name">{user.name}</div>
                    <div className="user-email">{user.email}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
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
              />
              <label htmlFor="file-upload" className="file-dropzone">
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
                    <div className="upload-text">Drop PDF here or click to browse</div>
                    <div className="upload-hint">Maximum file size: 10MB</div>
                  </>
                )}
              </label>

              <button
                onClick={handleUpload}
                disabled={uploading || !file || !userId}
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
                  placeholder="What would you like to know?"
                  className="query-input"
                  rows="4"
                />
              </div>

              <button
                onClick={handleQuery}
                disabled={querying || !query.trim() || !userId}
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