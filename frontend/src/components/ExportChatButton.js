import React from 'react';
import jsPDF from 'jspdf';
import './ExportChatButton.css';

const ExportChatButton = ({ messages, selectedDocument, disabled = false }) => {
  const exportToPDF = async () => {
    if (!messages || messages.length === 0) {
      alert('No chat messages to export!');
      return;
    }

    try {
      // Create PDF document
      const pdf = new jsPDF();
      let yPosition = 20;
      const pageHeight = pdf.internal.pageSize.height;
      const margin = 15;
      const lineHeight = 6;
      const pageWidth = pdf.internal.pageSize.getWidth();

      // Logo
      const logo = "data:image/png;base64,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"
      pdf.addImage(logo, 'PNG', pageWidth - 40, 10, 25, 25); // (x, y, width, height)

      // Add header
      pdf.setFontSize(16);
      pdf.setTextColor(40, 40, 40);
      pdf.text('Chat Export', margin, yPosition);
      yPosition += 10;

      pdf.setFontSize(10);
      pdf.setTextColor(100, 100, 100);
      pdf.text(`Document: ${selectedDocument || 'Untitled'}`, margin, yPosition);
      yPosition += 5;
      pdf.text(`Exported: ${new Date().toLocaleString()}`, margin, yPosition);
      yPosition += 15;

      // Add messages
      pdf.setFontSize(11);
      
      messages.forEach((message, index) => {
        // Check if we need a new page
        if (yPosition > pageHeight - 30) {
          pdf.addPage();
          yPosition = 20;
        }

        // Set color based on message type
        if (message.type === 'user') {
          pdf.setTextColor(0, 100, 0); // Green for user
          pdf.setFont(undefined, 'bold');
          pdf.text('You:', margin, yPosition);
        } else if (message.type === 'assistant') {
          pdf.setTextColor(0, 0, 150); // Blue for assistant
          pdf.setFont(undefined, 'bold');
          pdf.text('Assistant:', margin, yPosition);
        } else {
          pdf.setTextColor(150, 0, 0); // Red for errors
          pdf.setFont(undefined, 'bold');
          pdf.text('System:', margin, yPosition);
        }

        yPosition += lineHeight;

        // Reset font for message content
        pdf.setFont(undefined, 'normal');
        pdf.setTextColor(0, 0, 0);

        // Split long messages into multiple lines
        const lines = pdf.splitTextToSize(message.content, 170);
        
        lines.forEach(line => {
          if (yPosition > pageHeight - 20) {
            pdf.addPage();
            yPosition = 20;
          }
          if (line.toLowerCase().includes("action performed:")) {
            line = "An action was performed.";
          }
          pdf.text(line, margin, yPosition);
          yPosition += lineHeight;
        });

        // Add spacing between messages
        yPosition += 5;

        // Add sources if available
        if (message.retrieved && message.retrieved.length > 0) {
          if (yPosition > pageHeight - 30) {
            pdf.addPage();
            yPosition = 20;
          }
          
          pdf.setFontSize(9);
          pdf.setTextColor(100, 100, 100);
          yPosition += lineHeight;
          
          pdf.setFontSize(11);
          yPosition += 5;
        }
      });

      pdf.setFontSize(10);
      pdf.text("Created by InsightSphere Agent", margin, pageHeight - 10);  
      // Save the PDF
      const fileName = `chat-export-${selectedDocument || 'document'}-${Date.now()}.pdf`;
      pdf.save(fileName);

    } catch (error) {
      console.error('Error exporting PDF:', error);
      alert('Failed to export chat. Please try again.');
    }
  };

  
  return (
    <div className="export-chat-container">
      <button 
        className="export-btn"
        onClick={exportToPDF}
        disabled={disabled || !messages || messages.length === 0}
        title="Export chat as PDF"
      >
        Export PDF
      </button>
      
      {/* <button 
        className="export-btn txt"
        onClick={exportToTXT}
        disabled={disabled || !messages || messages.length === 0}
        title="Export chat as Text"
      >
        📝 Export TXT
      </button> */}
    </div>
  );
};

export default ExportChatButton;