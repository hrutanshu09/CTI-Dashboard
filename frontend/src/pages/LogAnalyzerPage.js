import React from 'react';
import LogUpload from '../components/LogUpload';

const LogAnalyzerPage = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-white mb-6">Log Analyzer</h1>
      <LogUpload />
    </div>
  );
};

export default LogAnalyzerPage;