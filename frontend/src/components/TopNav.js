// src/components/TopNav.js
import React from 'react';
import { SignedIn, SignedOut, UserButton } from "@clerk/clerk-react";

export default function TopNav({ showSettings, setShowSettings, openSignIn, openSignUp }) {
  return (
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
            aria-label="Toggle settings" 
            title="Settings"
          >
            ⚙️
          </button>

          <SignedOut>
            <button className="primary-button small auth-button-fixed" onClick={openSignIn}>
              Sign In
            </button>
            <button className="primary-button small auth-button-fixed" onClick={openSignUp}>
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
  );
}