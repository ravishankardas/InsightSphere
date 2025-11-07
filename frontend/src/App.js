// src/App.js
import React, { useState, useEffect, useCallback } from "react";
import { SignedIn, SignedOut, useUser } from "@clerk/clerk-react";
import "./App.css";

// Components
import TopNav from "./components/TopNav";
import SettingsPanel from "./components/SettingsPanel";
import DocumentsPanel from "./components/DocumentsPanel";
import ChatPanel from "./components/ChatPanel";
import AuthModal from "./components/AuthModal";
import DeleteConfirmationModal from './components/DeleteConfirmationModal';

export default function App() {
  const API_KEY = process.env.REACT_APP_API_KEY;
  const NUM_QUERIES_ALLOWED = process.env.REACT_APP_NUM_QUERIES_ALLOWED || 2;

  const { user, isSignedIn } = useUser();
  const userId = user?.primaryEmailAddress?.emailAddress || user?.id || null;

  // --- State Variables ---
  // API Config
  const [apiUrl, setApiUrl] = useState(
    process.env.NODE_ENV === 'development'
      ? process.env.REACT_APP_BACKEND_URL_DEV
      : process.env.REACT_APP_BACKEND_URL_PROD
  );
  
  // UI & Auth State
  const [showSettings, setShowSettings] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("signup");

  // Document State
  const [documents, setDocuments] = useState([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [deletingDoc, setDeletingDoc] = useState(null);
  const [loadingChatHistory, setLoadingChatHistory] = useState(false);
  
  // Upload State
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [file, setFile] = useState(null);

  // Chat/Query State
  const [query, setQuery] = useState("");
  const [querying, setQuerying] = useState(false);
  const [documentChats, setDocumentChats] = useState({});
  const [loadingChats, setLoadingChats] = useState(false);
  const [messages, setMessages] = useState([]);
  const [rateLimited, setRateLimited] = useState(false);
  const [retryAfter, setRetryAfter] = useState(0);
  
  // Delete Modal State
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [docToDelete, setDocToDelete] = useState(null);

  // --- Helper & Utility Functions ---
  const testBackendConnection = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/health`);
      if (res.ok) {
        console.log("Backend is reachable");
        return true;
      }
    } catch (err) {
      console.error("Backend connection failed:", err);
    }
    return false;
  }, [apiUrl]);

  // ---- Cache Management Functions ----
  const getCachedChats = useCallback(() => {
    if (!userId) return {};
    try {
      return JSON.parse(localStorage.getItem(`chatHistory_${userId}`) || '{}');
    } catch (error) {
      console.error("Error reading cache:", error);
      return {};
    }
  }, [userId]);

  const updateCache = useCallback((documentName, messages) => {
    if (!userId || !documentName) return;
    
    const cachedChats = getCachedChats();
    const updatedCache = {
      ...cachedChats,
      [documentName]: messages
    };
    
    localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(updatedCache));
    setDocumentChats(updatedCache);
  }, [userId, getCachedChats]);

  const clearCache = useCallback(() => {
    if (userId) {
      localStorage.removeItem(`chatHistory_${userId}`);
    }
    setDocumentChats({});
    setMessages([]);
  }, [userId]);

  // ---- Document Functions ----
  const loadDocuments = useCallback(async () => {
    if (!userId) return;

    setLoadingDocuments(true);
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents`, { method: "GET", headers });

      if (res.ok) {
        const data = await res.json();
        setDocuments(data || []);

        if (!selectedDocument && data && data.length > 0) {
          const first = data[0];
          const firstName = typeof first === "string" ? first : (first.source || first.name || first.file || "");
          if (firstName) setSelectedDocument(firstName);
        }
      } else {
        setUploadStatus({ type: "error", message: `Failed to load documents: ${res.status}` });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Failed to load documents: ${err.message}` });
    } finally {
      setLoadingDocuments(false);
    }
  }, [userId, API_KEY, apiUrl, selectedDocument]);

  // ---- Load All Chat History on Login ----
  useEffect(() => {
    const loadAllChatHistory = async () => {
      if (isSignedIn && userId && documents.length > 0) {
        try {
          setLoadingChatHistory(true);
          console.log("📚 Loading all chat history to cache...");
          
          const allChats = {};
          let loadedCount = 0;
          
          // Load chat history for ALL documents
          for (const doc of documents) {
            const docName = typeof doc === "string" ? doc : (doc.source || doc.name || doc.file || "");
            if (docName) {
              try {
                const messages = await loadChatFromBackend(docName);
                allChats[docName] = messages;
                loadedCount++;
                console.log(`✅ Cached ${messages.length} messages for ${docName}`);
              } catch (error) {
                console.error(`❌ Failed to load chat for ${docName}:`, error);
                allChats[docName] = [];
              }
            }
          }
          
          // Store in localStorage for fast access
          localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(allChats));
          setDocumentChats(allChats);
          
          console.log(`🎉 Loaded ${loadedCount} document chats to cache`);
        } catch (error) {
          console.error("Error loading all chat history:", error);
        } finally {
          setLoadingChatHistory(false);
        }
      }
    };

    if (documents.length > 0) {
      loadAllChatHistory();
    }
  }, [isSignedIn, userId, documents]);

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;

    setDeletingDoc(docToDelete);
    setShowDeleteModal(false);
    
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(docToDelete)}`, { method: "DELETE", headers });

      if (res.ok) {
        setDocuments(documents.filter(doc => doc !== docToDelete));
        if (selectedDocument === docToDelete) setSelectedDocument(null);
        
        // Remove from cache
        const cachedChats = getCachedChats();
        delete cachedChats[docToDelete];
        localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(cachedChats));
        setDocumentChats(cachedChats);
        
        setUploadStatus({ type: "success", message: `Document "${docToDelete}" deleted successfully.` });
      } else {
        const data = await res.json();
        setUploadStatus({ type: "error", message: data.detail || "Failed to delete document." });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Network error: ${err.message}` });
    } finally {
      setDeletingDoc(null);
      setDocToDelete(null);
    }
  };

  const handleDocumentClick = async (filename) => {
    if (selectedDocument === filename) return;
    
    console.log(`🔄 Switching from ${selectedDocument} to ${filename}`);
    
    // Save current document before switching
    if (selectedDocument && messages.length > 0) {
      await saveChatToBackend(selectedDocument, messages);
    }
    
    setLoadingChatHistory(true);
    
    // Try to load from cache FIRST (instant)
    const cachedChats = getCachedChats();
    
    if (cachedChats[filename]) {
      setMessages(cachedChats[filename]);
      setLoadingChatHistory(false);
      console.log(`⚡ Loaded ${cachedChats[filename].length} messages from cache`);
    } else {
      // Fallback to API (should rarely happen after initial cache)
      try {
        const loadedMessages = await loadChatFromBackend(filename);
        setMessages(loadedMessages);
        
        // Update cache for next time
        updateCache(filename, loadedMessages);
        console.log(`✅ Loaded ${loadedMessages.length} messages from backend and cached`);
      } catch (error) {
        console.error("Error loading chat:", error);
        setMessages([]);
      } finally {
        setLoadingChatHistory(false);
      }
    }
    
    setSelectedDocument(filename);
  };

  // ---- Upload & Query Handlers ---
  const handleUpload = async (selectedFile) => {
    if (!API_KEY || !isSignedIn || !selectedFile) {
      if (!isSignedIn) { setAuthMode("signup"); setShowAuthModal(true); }
      return;
    }

    setUploading(true);
    setUploadStatus({ type: "info", message: "Uploading and processing document..." });
    
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const headers = { "X-API-Key": API_KEY };
      if (userId) headers["X-User-Id"] = userId;
      
      const res = await fetch(`${apiUrl}/api/upload/pdf/auto?preset=balanced`, { method: "POST", headers, body: formData });
      const data = await res.json();
      
      if (res.ok) {
        const chunks = data.text_chunks || data.indexed_chunks || 0;
        const tables = data.tables || 0;
        const images = data.images || 0;
        let message = `✅ Document uploaded successfully! Processed ${chunks} text chunks`;
        if (tables > 0 || images > 0) {
          const parts = [];
          if (tables > 0) parts.push(`${tables} tables`);
          if (images > 0) parts.push(`${images} images`);
          message += ` and extracted ${parts.join(', ')}`;
        }
        setUploadStatus({ type: "success", message: message });

        setTimeout(() => { loadDocuments(); }, 2000);
        const returnedName = data?.file?.source || data?.source || selectedFile?.name;
        if (returnedName) setSelectedDocument(returnedName);
        
        // Clear file input
        const fileInput = document.getElementById('file-upload');
        if (fileInput) fileInput.value = '';

      } else {
        const errorMsg = data.detail || "Upload failed";
        setUploadStatus({ type: "error", message: `Upload failed: ${errorMsg}` });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Network error: ${err.message}.` });
    } finally {
      setUploading(false);
      setFile(null);
    }
  };

  const handleFileChange = async (e) => {
    if (!isSignedIn) { setAuthMode("signup"); setShowAuthModal(true); return; }
    
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    
    if (selectedFile.type !== "application/pdf") {
      setUploadStatus({ type: "error", message: "Please select a PDF file." });
      return;
    }

    setFile(selectedFile);
    setUploadStatus(null);
    await handleUpload(selectedFile);
  };

  const handleQuery = async () => {
    if (rateLimited) {
      const errorMessage = {
        type: "error",
        content: `Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`,
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    if (!API_KEY) {
      const errorMessage = {
        type: "error", 
        content: "Configuration Error: Missing API Key.", 
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      setQuerying(false);
      return;
    }

    if (!isSignedIn) {
      setAuthMode("signup");
      setShowAuthModal(true);
      return;
    }

    if (!query.trim()) {
      const errorMessage = {
        type: "error",
        content: "Please enter a question.",
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    if (!selectedDocument) {
      const errorMessage = {
        type: "error",
        content: "Please upload and select a document first.",
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    // Add user message to chat
    const userMessage = {
      type: "user",
      content: query.trim(),
      isUser: true,
      timestamp: new Date().toISOString()
    };
    
    // Update messages and cache immediately
    setMessages(prev => {
      const newMessages = [...prev, userMessage];
      updateCache(selectedDocument, newMessages);
      return newMessages;
    });
    
    setQuerying(true);
    setQuery("");

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      };

      if (userId) {
        headers["X-User-Id"] = userId;
      }

      const bodyPayload = {
        query: getConversationContext(userMessage.content),
        top_k: 6,
        source: selectedDocument,
        use_query_rewriting: false,
      };

      const res = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
      });

      if (res.status === 429) {
        const retryAfterHeader = res.headers.get('Retry-After');
        const waitTime = retryAfterHeader ? parseInt(retryAfterHeader) : 60;
        
        setRateLimited(true);
        setRetryAfter(waitTime);
        
        const interval = setInterval(() => {
          setRetryAfter(prev => {
            if (prev <= 1) {
              clearInterval(interval);
              setRateLimited(false);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

        throw new Error(`Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`);
      }

      const data = await res.json();

      if (res.ok) {
        if (data.answer && !data.answer.includes("OpenAI is not configured") && !data.answer.includes("no context found")) {
          const assistantMessage = {
            type: "assistant",
            content: data.answer,
            isUser: false,
            retrieved: data.sources || data.retrieved || [],
            timestamp: new Date().toISOString()
          };
          
          // Update messages with assistant response and cache
          setMessages(prev => {
            const newMessages = [...prev, assistantMessage];
            updateCache(selectedDocument, newMessages);
            return newMessages;
          });

          // Save to backend
          setTimeout(() => {
            saveChatToBackend(selectedDocument, [...messages, userMessage, assistantMessage]);
          }, 100);

        } else {
          let errorMessage = "The document was uploaded but no meaningful content was extracted. ";
          errorMessage += "This could be because:\n• The PDF is scanned or image-based\n• The backend AI service is not properly configured";
          
          const errorResponse = {
            type: "error",
            content: errorMessage,
            isUser: false,
            timestamp: new Date().toISOString()
          };
          
          setMessages(prev => {
            const newMessages = [...prev, errorResponse];
            updateCache(selectedDocument, newMessages);
            return newMessages;
          });

          setTimeout(() => {
            saveChatToBackend(selectedDocument, [...messages, userMessage, errorResponse]);
          }, 100);
        }
      } else {
        const errorDetail = data.detail || "Query failed";
        let userFriendlyMessage = "Query failed. Please try again.";
        
        if (errorDetail.includes("OpenAI")) {
          userFriendlyMessage = "Backend configuration error: AI service is not properly configured on the server.";
        } else if (errorDetail.includes("no context")) {
          userFriendlyMessage = "No searchable content found in the document. The PDF might be scanned or contain only images.";
        } else if (errorDetail.includes("Authentication required")) {
          userFriendlyMessage = "Authentication error: Please sign out and sign in again.";
        }
        
        const errorMessage = {
          type: "error",
          content: userFriendlyMessage,
          isUser: false,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => {
          const newMessages = [...prev, errorMessage];
          updateCache(selectedDocument, newMessages);
          return newMessages;
        });

        setTimeout(() => {
          saveChatToBackend(selectedDocument, [...messages, userMessage, errorMessage]);
        }, 100);
      }
    } catch (err) {
      const errorMessage = {
        type: "error",
        content: err.message.includes('Rate limited') ? err.message : `Network error: ${err.message}.`,
        isUser: false,
        timestamp: new Date().toISOString()
      };
      
      setMessages(prev => {
        const newMessages = [...prev, errorMessage];
        updateCache(selectedDocument, newMessages);
        return newMessages;
      });

      setTimeout(() => {
        saveChatToBackend(selectedDocument, [...messages, userMessage, errorMessage]);
      }, 100);
    } finally {
      setQuerying(false);
    }
  };
  
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  // API functions for chat persistence
  const saveChatToBackend = async (documentName, messages) => {
    if (!isSignedIn || !userId || !documentName) {
      console.log("Skipping save - not signed in or no document selected");
      return;
    }
    
    try {
      const headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      console.log(`💾 Saving ${messages.length} messages for: ${documentName}`);
      
      const response = await fetch(`${apiUrl}/api/query/chats/save`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          document_name: documentName,
          messages: messages
        }),
      });

      const data = await response.json();
      if (data.success) {
        console.log("✅ Chat saved successfully");
      } else {
        console.error("❌ Failed to save chat:", data.message);
      }
    } catch (error) {
      console.error("❌ Error saving chat to backend:", error);
    }
  };


  // Conversation memory helper
  const getConversationContext = (currentQuery) => {
    if (!selectedDocument || !userId) return currentQuery;
    
    // Check if this query needs conversation context
    const needsMemory = 
      currentQuery.toLowerCase().includes('what was') ||
      currentQuery.toLowerCase().includes('previous') ||
      currentQuery.toLowerCase().includes('again') ||
      currentQuery.toLowerCase().includes('earlier') ||
      currentQuery.toLowerCase().includes('before');
    
    if (!needsMemory) return currentQuery;
    
    // Get recent messages from localStorage cache
    const cachedChats = JSON.parse(localStorage.getItem(`chatHistory_${userId}`) || '{}');
    const currentChat = cachedChats[selectedDocument] || [];
    
    if (currentChat.length < 2) return currentQuery;
    
    // Get last 2 Q&A pairs for context
    const recentPairs = [];
    for (let i = Math.max(0, currentChat.length - 4); i < currentChat.length; i += 2) {
      if (currentChat[i] && currentChat[i + 1]) {
        recentPairs.push({
          question: currentChat[i].content,
          answer: currentChat[i + 1].content
        });
      }
    }
    
    if (recentPairs.length === 0) return currentQuery;
    
    // Build enhanced query with context
    let context = "Previous conversation:\n";
    recentPairs.forEach((pair, index) => {
      context += `Q: ${pair.question}\nA: ${pair.answer}\n\n`;
    });
    
    return `${context}Current question: ${currentQuery}`;
  };

  const loadChatFromBackend = async (documentName) => {
    if (!isSignedIn || !userId || !documentName) {
      console.log("Skipping load - not signed in or no document name");
      return [];
    }
    
    try {
      const headers = {
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      console.log(`📂 Loading chat for: ${documentName}`);
      
      const response = await fetch(`${apiUrl}/api/query/chats/load/${encodeURIComponent(documentName)}`, {
        method: "GET",
        headers,
      });

      const data = await response.json();
      if (data.success) {
        console.log(`✅ Loaded ${data.messages.length} messages for ${documentName}`);
        return data.messages;
      } else {
        console.error("❌ Failed to load chat:", data.message);
        return [];
      }
    } catch (error) {
      console.error("❌ Error loading chat from backend:", error);
      return [];
    }
  };

  // Auto-save when messages change (with debounce)
  useEffect(() => {
    if (selectedDocument && messages.length > 0) {
      // Update cache immediately
      updateCache(selectedDocument, messages);
      
      // Debounced save to backend
      const saveTimeout = setTimeout(() => {
        saveChatToBackend(selectedDocument, messages);
      }, 5000);
      
      return () => clearTimeout(saveTimeout);
    }
  }, [messages, selectedDocument, updateCache]);

  // Clear cache on logout
  useEffect(() => {
    if (!isSignedIn) {
      clearCache();
    }
  }, [isSignedIn, clearCache]);

  // Load initial chat from cache when document is selected
  useEffect(() => {
    if (selectedDocument && userId) {
      const cachedChats = getCachedChats();
      if (cachedChats[selectedDocument]) {
        setMessages(cachedChats[selectedDocument]);
        console.log(`⚡ Loaded ${cachedChats[selectedDocument].length} messages from cache for ${selectedDocument}`);
      } else {
        // If not in cache, load from backend
        const loadFromBackend = async () => {
          setLoadingChatHistory(true);
          try {
            const loadedMessages = await loadChatFromBackend(selectedDocument);
            setMessages(loadedMessages);
            updateCache(selectedDocument, loadedMessages);
          } catch (error) {
            console.error("Error loading chat:", error);
            setMessages([]);
          } finally {
            setLoadingChatHistory(false);
          }
        };
        loadFromBackend();
      }
    }
  }, [selectedDocument, userId, getCachedChats, updateCache]);

  useEffect(() => {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }, [messages, querying]);

  useEffect(() => {
    if (uploadStatus?.type === 'success') {
      const timer = setTimeout(() => setUploadStatus(null), 4000);
      return () => clearTimeout(timer);
    }
    if (uploadStatus?.type === 'success' && !uploading && selectedDocument) {
      setTimeout(() => {
        const chatMessages = document.querySelector('.chat-messages');
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
      }, 100);
    }
  }, [uploadStatus, uploading, selectedDocument]);

  useEffect(() => {
    if (isSignedIn && userId) {
      loadDocuments();
    } else {
      setDocuments([]);
      setSelectedDocument(null);
    }
  }, [isSignedIn, userId, loadDocuments]);

  useEffect(() => {
    testBackendConnection();
  }, [apiUrl, testBackendConnection]);

  const openSignUp = () => { setAuthMode("signup"); setShowAuthModal(true); };
  const openSignIn = () => { setAuthMode("signin"); setShowAuthModal(true); };
  const handleDeleteClick = (filename) => { setDocToDelete(filename); setShowDeleteModal(true); };
  const handleDeleteCancel = () => { setShowDeleteModal(false); setDocToDelete(null); };

  return (
    <div className="app-container">
      <DeleteConfirmationModal
        show={showDeleteModal}
        filename={docToDelete}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      <AuthModal 
        showAuthModal={showAuthModal}
        authMode={authMode}
        setShowAuthModal={setShowAuthModal}
        setAuthMode={setAuthMode}
      />

      <TopNav
        showSettings={showSettings}
        setShowSettings={setShowSettings}
        openSignIn={openSignIn}
        openSignUp={openSignUp}
      />

      {showSettings && (
        <SettingsPanel 
          apiUrl={apiUrl} 
          setApiUrl={setApiUrl} 
          testBackendConnection={testBackendConnection} 
        />
      )}

      <div className="main-content two-column">
        <DocumentsPanel
          documents={documents}
          loadingDocuments={loadingDocuments}
          selectedDocument={selectedDocument}
          deletingDoc={deletingDoc}
          handleDocumentClick={handleDocumentClick}
          handleDeleteClick={handleDeleteClick}
        />

        <ChatPanel
          selectedDocument={selectedDocument}
          messages={messages}
          query={query}
          setQuery={setQuery}
          handleQuery={handleQuery}
          handleKeyPress={handleKeyPress}
          handleFileChange={handleFileChange}
          querying={querying}
          uploading={uploading}
          uploadStatus={uploadStatus}
          rateLimited={rateLimited}
          numQueriesAllowed={NUM_QUERIES_ALLOWED}
          loadingChats={loadingChats}
          loadingChatHistory={loadingChatHistory}
        />
      </div>
    </div>
  );
}