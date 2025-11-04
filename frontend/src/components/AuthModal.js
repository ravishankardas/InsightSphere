// src/components/AuthModal.js
import React from 'react';
import { SignUp, SignIn } from "@clerk/clerk-react";

export default function AuthModal({ showAuthModal, setShowAuthModal, authMode, setAuthMode }) {
    if (!showAuthModal) return null;

    return (
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
    );
}