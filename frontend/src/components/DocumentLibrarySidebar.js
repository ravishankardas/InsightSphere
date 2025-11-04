// src/components/DocumentLibrarySidebar.js

import React from 'react';

export default function DocumentLibrarySidebar({
    isSignedIn,
    file,
    documentList,
    loadingDocuments,
    // Removed: handleDeleteDocument (replaced by modal logic)
    handleDocumentClick,
    handleDeleteClick, // <-- Used to open the Delete Confirmation Modal
    fetchDocumentList
}) {
    return (
        <section className="left-panel document-library-sidebar">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0 0 10px 0' }}>
                <h2 className="section-title" style={{ margin: 0 }}>📚 Document Library</h2>
                <button 
                    onClick={fetchDocumentList} 
                    disabled={loadingDocuments}
                    className="secondary-button small"
                    title="Refresh Document List"
                >
                    {loadingDocuments ? 'Wait...' : 'Refresh'}
                </button>
            </div>
            
            {loadingDocuments && <div className="loading-indicator">Loading documents...</div>}
            
            <ul className="document-list-column">
                {!loadingDocuments && documentList.length > 0 ? (
                    documentList.map((filename, index) => (
                        <li key={index} className={`document-item ${file?.name === filename ? 'active' : ''}`}>
                            <span 
                                className="filename-text" 
                                onClick={() => handleDocumentClick(filename)}
                                title={`Click to search within ${filename}`}
                            >
                                📄 {filename}
                            </span>
                            <button 
                                className="delete-button" 
                                // This now correctly calls the function that opens the modal in App.js
                                onClick={() => handleDeleteClick(filename)} 
                                title="Permanently delete this document and all its data"
                            >
                                🗑️
                            </button>
                        </li>
                    ))
                ) : (
                    <li className="empty-state">
                        {!loadingDocuments && isSignedIn ? "No documents. Upload one on the right to start." : "Sign in to see your documents."}
                    </li>
                )}
            </ul>
        </section>
    );
}   