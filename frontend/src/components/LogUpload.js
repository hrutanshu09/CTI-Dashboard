import React, { useState } from 'react';
import { UploadCloud } from 'lucide-react';
import ThreatTable from './ThreatTable';
import Loader from './Loader';
import { analyzeLogFile } from '../services/api';

const LogUpload = () => {
  const [isUploading, setIsUploading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (file) {
      setIsUploading(true);
      setResults([]);
      setError('');
      try {
        const data = await analyzeLogFile(file);
        setResults(data);
      } catch (err) {
        setError('Failed to analyze the log file.');
      } finally {
        setIsUploading(false);
      }
    }
  };

  return (
    <div className="bg-panel p-6 rounded-lg border border-border h-full flex flex-col">
      <h2 className="text-lg font-semibold text-white mb-4">Log Analyzer</h2>
      <div className="relative border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-neon-blue transition-colors">
        <UploadCloud className="mx-auto h-12 w-12 text-gray-500" />
        <p className="mt-4 text-sm text-gray-400">
          <span className="font-semibold text-neon-blue">Click to upload</span> or drag and drop.
        </p>
        <p className="text-xs text-gray-500 mt-1">Supports .log, .csv, .json files</p>
        <input
          type="file"
          className="absolute top-0 left-0 w-full h-full opacity-0 cursor-pointer"
          onChange={handleFileUpload}
          disabled={isUploading}
        />
      </div>
      
      <div className="mt-4 flex-grow overflow-y-auto min-h-[150px]">
        {isUploading && <Loader text="Analyzing logs..."/>}
        {error && <p className="text-neon-red text-center">{error}</p>}
        {results.length > 0 && <ThreatTable threats={results} />}
      </div>
    </div>
  );
};

export default LogUpload;