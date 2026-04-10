import React, { useState } from 'react';
import { UploadCloud } from 'lucide-react';
import ThreatTable from './ThreatTable';
import Loader from './Loader';
import { analyzeLogFile, queryLogInsights } from '../services/api';
import { useModuleState } from '../context/ModuleStateContext';

const LogUpload = () => {
  const { moduleState, setModuleState, resetModuleState } = useModuleState('logAnalyzer');
  const { results, iocDetails, query, queryResponse, queryError, error } = moduleState;
  const [isUploading, setIsUploading] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);

  const getSeverityClass = (severity) => {
    switch (String(severity).toLowerCase()) {
      case 'critical':
        return 'bg-red-900/40 text-neon-red';
      case 'high':
        return 'bg-orange-900/40 text-orange-400';
      case 'medium':
        return 'bg-yellow-900/40 text-yellow-300';
      default:
        return 'bg-blue-900/40 text-blue-300';
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (file) {
      setIsUploading(true);
      setModuleState({
        results: [],
        iocDetails: [],
        queryResponse: '',
        queryError: '',
        error: ''
      });
      try {
        const data = await analyzeLogFile(file);
        setModuleState({
          results: data.rows || [],
          iocDetails: data.groupedDetails || []
        });
      } catch (err) {
        setModuleState({ error: err.message || 'Failed to analyze the log file.' });
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleFurtherQuery = async (event) => {
    event.preventDefault();
    if (!query.trim() || isQuerying) return;

    setIsQuerying(true);
    setModuleState({ queryResponse: '', queryError: '' });

    try {
      const data = await queryLogInsights(query.trim());
      const responseText =
        data?.response?.response ||
        data?.response ||
        (typeof data === 'string' ? data : JSON.stringify(data, null, 2));
      setModuleState({ queryResponse: String(responseText) });
    } catch (err) {
      setModuleState({ queryError: err.message || 'Failed to run further query.' });
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="bg-panel p-6 rounded-lg border border-border h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Log Analyzer</h2>
        <button
          type="button"
          onClick={resetModuleState}
          className="text-xs px-3 py-1 rounded-md border border-border text-gray-300 hover:text-white hover:border-neon-blue transition-colors"
          disabled={isUploading || isQuerying}
        >
          Clear
        </button>
      </div>
      <div className="relative border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-neon-blue transition-colors">
        <UploadCloud className="mx-auto h-12 w-12 text-gray-500" />
        <p className="mt-4 text-sm text-gray-400">
          <span className="font-semibold text-neon-blue">Click to upload</span> or drag and drop.
        </p>
        <p className="text-xs text-gray-500 mt-1">Supports .log, .txt, .rtf, .csv files</p>
        <input
          type="file"
          accept=".log,.txt,.rtf,.csv"
          className="absolute top-0 left-0 w-full h-full opacity-0 cursor-pointer"
          onChange={handleFileUpload}
          disabled={isUploading}
        />
      </div>
      
      <div className="mt-4 flex-grow overflow-y-auto min-h-[150px]">
        {isUploading && <Loader text="Analyzing logs..."/>}
        {error && <p className="text-neon-red text-center">{error}</p>}
        {results.length > 0 && <ThreatTable threats={results} />}

        {iocDetails.length > 0 && (
          <div className="mt-6 border border-border rounded-lg p-4 bg-background/40">
            <h3 className="text-white font-semibold mb-3">IOC(Indicators of Compromise) Brief</h3>
            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
              {iocDetails.map((item, index) => (
                <div key={`${item.indicator}-${index}`} className="border border-border rounded-md p-3 bg-panel/50">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-gray-300">
                        IOC: <span className="text-white font-medium break-all">{item.indicator}</span>
                      </p>
                    </div>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityClass(item.topSeverity)}`}>
                      {item.topSeverity}
                    </span>
                  </div>

                  <div className="mt-3 bg-background/60 border border-border rounded p-2">
                    <p className="text-xs text-gray-400">What Happened</p>
                    <p className="text-sm text-gray-200 mt-1">{item.whatHappened || item.stakeholderSummary}</p>
                  </div>

                  <div className="mt-3 bg-background/60 border border-border rounded p-2">
                    <p className="text-xs text-gray-400">Why It Matters</p>
                    <p className="text-sm text-gray-200 mt-1">{item.whyItMatters || item.executiveView}</p>
                  </div>

                  <div className="mt-3">
                    <p className="text-xs text-gray-400">Affected Assets</p>
                    <p className="text-sm text-gray-200 break-all mt-1">
                      {Array.isArray(item.affectedAssets)
                        ? item.affectedAssets.join(', ')
                        : (item.relatedIps.length > 0 ? item.relatedIps.join(', ') : 'No asset extracted from available evidence')}
                    </p>
                  </div>

                  <div className="mt-3">
                    <p className="text-xs text-gray-400">Recommended Action Plan</p>
                    <ol className="mt-1 text-sm text-gray-200 list-decimal list-inside space-y-1">
                      {item.actionPlan.map((step, stepIndex) => (
                        <li key={`${item.indicator}-action-${stepIndex}`}>{step}</li>
                      ))}
                    </ol>
                  </div>

                  <div className="mt-3">
                    <p className="text-xs text-gray-400 mb-1">Examples (IOC + IP + Evidence)</p>
                    <div className="space-y-2">
                      {item.examples.map((example, exIndex) => (
                        <div key={`${item.indicator}-ex-${exIndex}`} className="bg-background/70 border border-border rounded p-2">
                          <p className="text-xs text-gray-300">
                            Chunk {example.chunkId} | IP: <span className="text-white font-mono">{example.ip}</span>
                            {typeof example.score === 'number' ? ` | Score: ${example.score}` : ''}
                          </p>
                          <p className="text-xs text-gray-400 mt-1 whitespace-pre-wrap">{example.evidence}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {(results.length > 0 || iocDetails.length > 0) && (
          <div className="mt-6 border border-border rounded-lg p-4 bg-background/40">
            <h3 className="text-white font-semibold mb-3">Further Query</h3>
            <form onSubmit={handleFurtherQuery} className="space-y-3">
              <textarea
                value={query}
                onChange={(e) => setModuleState({ query: e.target.value })}
                placeholder="Ask a deeper question (e.g., Which IOC looks most risky and why?)"
                className="w-full min-h-[90px] bg-panel border border-border rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-neon-blue"
                disabled={isQuerying}
              />
              <button
                type="submit"
                className="bg-neon-blue text-black font-semibold px-4 py-2 rounded-md hover:bg-opacity-80 transition-opacity disabled:opacity-50"
                disabled={isQuerying || !query.trim()}
              >
                {isQuerying ? 'Querying...' : 'Run Query'}
              </button>
            </form>

            {queryError && <p className="mt-3 text-sm text-neon-red">{queryError}</p>}
            {queryResponse && (
              <div className="mt-4 p-3 bg-panel border border-border rounded-md">
                <p className="text-xs text-gray-400 mb-1">Query Result</p>
                <pre className="text-sm text-gray-200 whitespace-pre-wrap font-sans">{queryResponse}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default LogUpload;
