import React from 'react';

const MarkdownRenderer = ({ text }) => {
  // Regex to find text wrapped in double asterisks (e.g., **bold text**)
  const parts = text.split(/(\*\*.*?\*\*)/g);

  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          // Render the text inside the asterisks as bold
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        // Render normal text
        return part;
      })}
    </>
  );
};

export default MarkdownRenderer;