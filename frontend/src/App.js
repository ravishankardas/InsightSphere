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
  // ---- Load Documents AND Chat History on Login ----
// ---- Load Documents AND Chat History on Login ----
useEffect(() => {
  const loadDocumentsAndChats = async () => {
    if (isSignedIn && userId) {
      try {
        setLoadingDocuments(true);
        setLoadingChatHistory(true);
        
        console.log("📚 Loading documents and chat history...");
        
        // 1. Load documents first
        const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
        const res = await fetch(`${apiUrl}/api/documents`, { method: "GET", headers });

        if (res.ok) {
          const documentsData = await res.json();
          const normalizedDocuments = documentsData || [];
          setDocuments(normalizedDocuments);
          console.log(`✅ Loaded ${normalizedDocuments.length} documents`);

          // 2. Load chat history for ALL documents
          if (normalizedDocuments.length > 0) {
            const allChats = {};
            let loadedCount = 0;
            
            for (const doc of normalizedDocuments) {
              const docName = typeof doc === "string" ? doc : (doc.source || doc.name || doc.file || "");
              if (docName) {
                try {
                  // Use normalized document name for loading
                  const normalizedDocName = docName.toLowerCase();
                  const messages = await loadChatFromBackend(normalizedDocName);
                  allChats[normalizedDocName] = messages;
                  loadedCount++;
                  console.log(`✅ Cached ${messages.length} messages for ${normalizedDocName}`);
                } catch (error) {
                  console.error(`❌ Failed to load chat for ${docName}:`, error);
                  allChats[docName.toLowerCase()] = [];
                }
              }
            }
            
            // Store in localStorage for fast access
            localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(allChats));
            setDocumentChats(allChats);
            
            // 3. Auto-select first document and load its messages
            const firstDoc = normalizedDocuments[0];
            const firstName = typeof firstDoc === "string" ? firstDoc : (firstDoc.source || firstDoc.name || firstDoc.file || "");
            if (firstName) {
              const normalizedFirstName = firstName.toLowerCase();
              setSelectedDocument(normalizedFirstName);
              setMessages(allChats[normalizedFirstName] || []);
            }
            
            console.log(`🎉 Loaded ${loadedCount} document chats to cache`);
          } else {
            console.log("No documents found for user");
          }
        } else {
          console.error("Failed to load documents:", res.status);
          setUploadStatus({ type: "error", message: `Failed to load documents: ${res.status}` });
        }
      } catch (error) {
        console.error("Error loading documents and chats:", error);
        setUploadStatus({ type: "error", message: `Error loading data: ${error.message}` });
      } finally {
        setLoadingDocuments(false);
        setLoadingChatHistory(false);
      }
    }
  };

  if (isSignedIn && userId) {
    loadDocumentsAndChats();
  } else {
    // Clear everything on logout
    setDocuments([]);
    setSelectedDocument(null);
    setMessages([]);
    setDocumentChats({});
  }
}, [isSignedIn, userId, API_KEY, apiUrl]);

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;

    setDeletingDoc(docToDelete);
    setShowDeleteModal(false);
    
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(docToDelete)}`, { method: "DELETE", headers });

      if (res.ok) {
        // 1. Remove document from documents list
        setDocuments(documents.filter(doc => doc !== docToDelete));
        
        // 2. Clear chat history from localStorage cache
        const cachedChats = JSON.parse(localStorage.getItem(`chatHistory_${userId}`) || '{}');
        delete cachedChats[docToDelete];
        localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(cachedChats));
        setDocumentChats(cachedChats);
        
        // 3. Clear current messages if viewing the deleted document
        if (selectedDocument === docToDelete) {
          setSelectedDocument(null);
          setMessages([]);
        }
        
        // 4. Also delete from backend database (optional but recommended)
        await deleteChatHistoryFromBackend(docToDelete);
        
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

  const deleteChatHistoryFromBackend = async (documentName) => {
  if (!isSignedIn || !userId || !documentName) {
    console.log("Skipping chat history deletion - not signed in");
    return;
  }
  
  try {
    const headers = {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      "X-User-Id": userId,
    };

    console.log(`🗑️ Deleting chat AND document for: ${documentName}`);
    
    // This will delete both chat history AND document content
    const response = await fetch(`${apiUrl}/api/query/chats/delete/${encodeURIComponent(documentName)}`, {
      method: "DELETE",
      headers,
    });

    const data = await response.json();
    if (data.success) {
      console.log("✅ Chat history AND document content deleted from backend");
      if (data.chroma_deleted !== undefined) {
        console.log(`📊 ChromaDB deletion: ${data.chroma_deleted ? 'Success' : 'Not found'}`);
      }
    } else {
      console.error("❌ Failed to delete chat history and document:", data.message);
    }
  } catch (error) {
    console.error("❌ Error deleting chat history and document:", error);
  }
};

  const handleDocumentClick = async (filename) => {
  const normalizedFilename = filename.toLowerCase();
  
  if (selectedDocument === normalizedFilename) return;
  
  console.log(`🔄 Switching from ${selectedDocument} to ${normalizedFilename}`);
  
  // Save current document before switching
  if (selectedDocument && messages.length > 0) {
    await saveChatToBackend(selectedDocument, messages);
  }
  
  setLoadingChatHistory(true);
  
  // Try to load from cache FIRST (instant)
  const cachedChats = getCachedChats();
  
  if (cachedChats[normalizedFilename]) {
    setMessages(cachedChats[normalizedFilename]);
    setLoadingChatHistory(false);
    console.log(`⚡ Loaded ${cachedChats[normalizedFilename].length} messages from cache`);
  } else {
    // Fallback to API (should rarely happen after initial cache)
    try {
      const loadedMessages = await loadChatFromBackend(normalizedFilename);
      setMessages(loadedMessages);
      
      // Update cache for next time
      updateCache(normalizedFilename, loadedMessages);
      console.log(`✅ Loaded ${loadedMessages.length} messages from backend and cached`);
    } catch (error) {
      console.error("Error loading chat:", error);
      setMessages([]);
    } finally {
      setLoadingChatHistory(false);
    }
  }
  
  setSelectedDocument(normalizedFilename);
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

      // Save current chat before switching to new document
      if (selectedDocument && messages.length > 0) {
        await saveChatToBackend(selectedDocument, messages);
      }

      const returnedName = data?.file?.source || data?.source || selectedFile?.name;
      if (returnedName) {
        const normalizedName = returnedName.toLowerCase();
        
        // Check if this document already has chat history
        setLoadingChatHistory(true);
        try {
          const existingChat = await loadChatFromBackend(normalizedName);
          
          if (existingChat && existingChat.length > 0) {
            // Document has existing chat history - load it
            setMessages(existingChat);
            updateCache(normalizedName, existingChat);
            console.log(`📖 Loaded existing chat history (${existingChat.length} messages) for ${normalizedName}`);
          } else {
            // New document - clear chat area
            setMessages([]);
            console.log(`🆕 New document - chat area cleared for ${normalizedName}`);
            
            // Create empty chat record for new document
            await saveChatToBackend(normalizedName, []);
          }
        } catch (error) {
          console.error("Error checking chat history:", error);
          // If there's an error, assume it's a new document
          setMessages([]);
          await saveChatToBackend(normalizedName, []);
        } finally {
          setLoadingChatHistory(false);
        }
        
        setSelectedDocument(normalizedName);
      }
      
      // Refresh documents list
      setTimeout(() => { loadDocuments(); }, 2000);
      
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
        source: selectedDocument.toLowerCase(),
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
  
  // Don't save if we're just creating an empty record (let backend handle this)
  if (messages.length === 0) {
    console.log("Skipping save - no messages to save");
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

  // useEffect(() => {
  //   if (isSignedIn && userId) {
  //     loadDocuments();
  //   } else {
  //     setDocuments([]);
  //     setSelectedDocument(null);
  //   }
  // }, [isSignedIn, userId, loadDocuments]);

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