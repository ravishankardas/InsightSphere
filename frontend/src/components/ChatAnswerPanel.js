// src/components/ChatAnswerPanel.js

import React from 'react';

export default function ChatAnswerPanel({
    // Upload Props
    isSignedIn,
    file: activeFile, // Renamed to avoid conflict with `file` input object
    uploading,
    uploadStatus,
    handleFileChange,
    handleUpload,
    
    // Query Props
    query,
    setQuery,
    querying,
    answer,
    handleQuery,
    handleSourceClick,
}) {
    return (
        <section className="right-panel chat-answer-panel">

            {/* 1. UPLOAD SECTION (Moved to top of right column) */}
            <div className="upload-section content-card">
                <div className="card-header">
                    <h2 className="section-title">⬆️ Upload New PDF</h2>
                </div>
                
                <input
                    type="file"
                    id="file-upload"
                    accept=".pdf"
                    onChange={handleFileChange}
                    style={{ display: "none" }}
                    disabled={!isSignedIn}
                />
                <div className="upload-controls">
                    <label 
                        htmlFor="file-upload" 
                        className={`upload-label-button ${!isSignedIn ? 'disabled' : ''}`}
                    >
                        <span role="img" aria-label="select">📁</span> {activeFile?.name ? `File Selected: ${activeFile.name}` : 'Select PDF'}
                    </label>
                    
                    {activeFile && (
                        <button 
                            onClick={handleUpload} 
                            disabled={uploading} 
                            className="primary-button small"
                        >
                            {uploading ? "Processing..." : `Upload to Index`}
                        </button>
                    )}
                </div>
                
                {uploadStatus && (
                    <div className={`alert alert-${uploadStatus.type}`} style={{ marginTop: '10px' }}>
                        <div className="alert-icon">{uploadStatus.type === "success" ? "✓" : "⚠"}</div>
                        <div className="alert-text">{uploadStatus.message}</div>
                    </div>
                )}
            </div>

            {/* 2. QUERY & ANSWER SECTION (Below upload) */}
            <div className="content-card">
                <div className="card-header">
                    <h2 className="section-title">🔎 Ask Questions</h2>
                </div>

                <div className="query-area">
                    <p className="card-subtitle">
                        {activeFile ? `Querying active document: ${activeFile.name}` : 'Querying all available documents.'}
                    </p>
                    <textarea
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="query-input"
                        rows="4"
                        placeholder={isSignedIn ? "Ask your question..." : "Sign in to search"}
                        disabled={!isSignedIn}
                    />
                    <div className="action-row">
                        <button onClick={handleQuery} disabled={querying || !query.trim() || !isSignedIn} className="primary-button">
                            {querying ? "Searching..." : "Ask"}
                        </button>
                    </div>
                </div>
            </div>

            {/* Answer / Sources (The output below the input) */}
            {answer && (
                <section className="content-card answer-section">
                    <div className="card-header">
                        <h3 className="card-title">Response</h3>
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
        </section>
    );
}