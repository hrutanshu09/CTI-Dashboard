import React, { useState, useEffect } from 'react';
import { getCVEData } from '../services/api';
import Loader from './Loader';
import { Search } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer'; // Import the new component
import { useModuleState } from '../context/ModuleStateContext';

const useTypingEffect = (text = '', speed = 20) => {
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        if (!text) return;
        setDisplayedText('');
        let i = 0;
        const intervalId = setInterval(() => {
            if (i < text.length) {
                setDisplayedText(prev => prev + text.charAt(i));
                i++;
            } else {
                clearInterval(intervalId);
            }
        }, speed);

        return () => clearInterval(intervalId);
    }, [text, speed]);

    return displayedText;
};

const CVESummary = () => {
    const { moduleState, setModuleState } = useModuleState('threatIntel');
    const { cveId, cveData, error } = moduleState;
    const [isLoading, setIsLoading] = useState(false);
    const summaryText = useTypingEffect(cveData?.ai_summary);
    const isTyping = cveData?.ai_summary && summaryText.length < cveData.ai_summary.length;

    const handleSearch = async (e) => {
        e.preventDefault();
        if (!cveId) return;
        setIsLoading(true);
        setModuleState({ cveData: null, error: '' });
        try {
            const data = await getCVEData(cveId);
            if (data) {
                setModuleState({ cveData: data });
            } else {
                setModuleState({ error: `CVE ID "${cveId}" not found.` });
            }
        } catch (err) {
            setModuleState({ error: err.message || 'An unexpected error occurred.' });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        
        <div className="bg-panel p-6 rounded-lg border border-border h-full flex flex-col">
            <h2 className="text-lg font-semibold text-white mb-4">CVE Lookup & AI Summary</h2>
            <form onSubmit={handleSearch} className="flex gap-2 mb-4">
                <input
                    type="text"
                    value={cveId}
                    onChange={(e) => setModuleState({ cveId: e.target.value })}
                    placeholder="Enter CVE ID (e.g., CVE-2024-12345)"
                    className="w-full bg-background border border-border rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-neon-blue text-sm"
                />
                <button type="submit" className="bg-neon-blue text-black font-bold px-4 py-2 rounded-md flex items-center gap-2 hover:bg-opacity-80 transition-opacity disabled:opacity-50" disabled={isLoading}>
                    <Search size={16} />
                </button>
            </form>
            
            <div className="flex-grow min-h-[200px]">
              {isLoading && <Loader text="Fetching CVE data..."/>}

              {!isLoading && !cveData && !error && (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <p>Enter a CVE ID to get details from the National Vulnerability Database.</p>
                </div>
              )}

              {error && (
                <div className="flex items-center justify-center h-full text-neon-red">
                  <p>{error}</p>
                </div>
              )}

              {cveData && (
                  <div className="space-y-4 animate-fade-in">
                      <div>
                          <h3 className="text-xl font-bold text-neon-red">{cveData.cve_id} - CVSS: {cveData.cvss_score}</h3>
                          <p className="text-sm text-gray-400 mt-2">{cveData.description}</p>
                      </div>
                      <div>
                          <h4 className="font-semibold text-white mb-2">AI-Powered Threat Summary</h4>
                          <div className="text-sm text-gray-300 bg-background/50 p-4 rounded-md border border-border min-h-[120px]">
                            <MarkdownRenderer text={summaryText} />
                            {isTyping && <span className="inline-block w-2 h-4 bg-neon-blue animate-pulse ml-1 opacity-80"></span>}

                            </div>
                      </div>
                  </div>
              )}
            </div>
        </div>

        
    );
};

export default CVESummary;
