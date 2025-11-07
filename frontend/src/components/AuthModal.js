// src/components/AuthModal.js
import React from 'react';
import { SignUp, SignIn } from "@clerk/clerk-react";

export default function AuthModal({ showAuthModal, authMode, setShowAuthModal, setAuthMode }) {
  if (!showAuthModal) return null;

  const handleSwitchAuth = () => {
    setAuthMode(prev => prev === "signup" ? "signin" : "signup");
  };

  return (
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
          <p>
            {authMode === "signup" ? "Already have an account? " : "Don't have an account? "}
            <button className="auth-switch-link" onClick={handleSwitchAuth}>
              {authMode === "signup" ? "Sign In" : "Sign Up"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}