// src/components/DeleteConfirmationModal.js
import React from 'react';

export default function DeleteConfirmationModal({ show, filename, onConfirm, onCancel }) {
    if (!show) {
        return null;
    }

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal-content delete-modal" onClick={(e) => e.stopPropagation()}>
                <button className="modal-close" onClick={onCancel}>
                    ×
                </button>
                
                <div className="modal-header">
                    <h2 className="modal-title">⚠️ Confirm Deletion</h2>
                </div>

                <div className="modal-body">
                    <p>
                        Are you absolutely sure you want to permanently delete the document:
                        <br/>
                        {/* <strong className="filename-to-delete">"{filename}"</strong> */}
                    </p>
                    {/* <p className="warning-text">
                        This action **cannot be undone** and will remove all associated data and indexing from your knowledge base.
                    </p> */}
                </div>

                <div className="modal-footer">
                    <button className="secondary-button" onClick={onCancel}>
                        Cancel
                    </button>
                    <button 
                        className="primary-button danger-button" 
                        onClick={onConfirm}
                    >
                        Yes
                    </button>
                </div>
            </div>
        </div>
    );
}