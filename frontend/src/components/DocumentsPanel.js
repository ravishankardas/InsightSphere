// src/components/DocumentsPanel.js
import React from 'react';
import DocumentItem from './DocumentItem';
import EmptyState from './EmptyState'; // Assuming you create a small utility for this

export default function DocumentsPanel({ 
  documents, 
  loadingDocuments, 
  selectedDocument, 
  deletingDoc, 
  handleDocumentClick, 
  handleDeleteClick 
}) {
  return (
    <div className="documents-panel">
      <div className="documents-header">
        <h2 className="documents-title">My Documents</h2>
        <p className="documents-subtitle">Upload and manage your files</p>
      </div>

      <div className="documents-list">
        {loadingDocuments ? (
          <EmptyState icon="📚" text="Loading documents..." />
        ) : documents.length === 0 ? (
          <EmptyState icon="📚" text="No documents yet" />
        ) : (
          documents.map((doc, index) => {
            const docName = typeof doc === "string" ? doc : (doc.source || doc.name || doc.file || "");
            
            return (
              <DocumentItem
                key={index}
                doc={doc}
                isSelected={selectedDocument === docName}
                isDeleting={deletingDoc}
                handleDocumentClick={handleDocumentClick}
                handleDeleteClick={handleDeleteClick}
              />
            );
          })
        )}
      </div>
    </div>
  );
}