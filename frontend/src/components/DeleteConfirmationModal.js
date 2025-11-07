// components/DeleteConfirmationModal.js
import React from 'react';

const DeleteConfirmationModal = ({ show, filename, onConfirm, onCancel }) => {
  if (!show) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content delete-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">
            🗑️ Delete Document
          </h2>
        </div>
        
        <div className="modal-body">
          <p>Are you sure you want to delete this document?</p>
          <p>
            <strong className="filename-to-delete">{filename}</strong>
          </p>
          <p className="warning-text">
            ⚠️ This action cannot be undone. All associated data will be permanently removed.
          </p>
        </div>
        
        <div className="modal-footer">
          <button className="secondary-button" onClick={onCancel}>
            Cancel
          </button>
          <button className="primary-button danger-button" onClick={onConfirm}>
            Delete Document
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteConfirmationModal;