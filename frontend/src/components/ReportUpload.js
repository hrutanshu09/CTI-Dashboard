import React, { useState } from 'react';
import { FileUp } from 'lucide-react';
import Loader from './Loader';
import {
  analyzeThreatReportFile,
  queryThreatReportInsights,
} from '../services/api';
import { useModuleState } from '../context/ModuleStateContext';

const ReportUpload = () => {
  const { moduleState, setModuleState, resetModuleState } = useModuleState('reporting');
  const {
    error,
    queryError,
    reportId,
    analysisPayload,
    mode,
    query,
    queryResponse,
    querySources
  } = moduleState;
  const [isUploading, setIsUploading] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);

  const resetQueryState = () => {
    setModuleState({
      query: '',
      queryResponse: '',
      querySources: [],
      queryError: ''
    });
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setModuleState({
      error: '',
      queryError: '',
      analysisPayload: null,
      reportId: ''
    });
    resetQueryState();

    try {
      const data = await analyzeThreatReportFile(file);
      setModuleState({
        analysisPayload: data,
        reportId: data?.report_id || ''
      });
    } catch (err) {
      setModuleState({ error: err.message || 'Failed to analyze report.' });
    } finally {
      setIsUploading(false);
    }
  };

  const handleFurtherQuery = async (event) => {
    event.preventDefault();

    if (!query.trim() || isQuerying) return;
    if ((mode === 'hybrid' || mode === 'report_only') && !reportId) {
      setModuleState({ queryError: 'Upload and analyze a report first to use report-based modes.' });
      return;
    }

    setIsQuerying(true);
    setModuleState({
      queryError: '',
      queryResponse: '',
      querySources: []
    });

    try {
      const data = await queryThreatReportInsights({
        query: query.trim(),
        reportId,
        mode,
      });

      const responseText =
        data?.response?.response ||
        data?.response ||
        (typeof data === 'string' ? data : JSON.stringify(data, null, 2));

      setModuleState({
        queryResponse: String(responseText),
        querySources: Array.isArray(data?.response?.sources) ? data.response.sources : []
      });
    } catch (err) {
      setModuleState({ queryError: err.message || 'Failed to run query.' });
    } finally {
      setIsQuerying(false);
    }
  };

  const iocs = analysisPayload?.iocs || {};
  const analysis = analysisPayload?.analysis || {};

  const summaryLines = Array.isArray(analysis.summary_lines) ? analysis.summary_lines : [];
  const threatTypes = Array.isArray(analysis.threat_types) ? analysis.threat_types : [];
  const detections = Array.isArray(analysis.detections) ? analysis.detections : [];
  const topIocs = Array.isArray(analysis.top_iocs) ? analysis.top_iocs : [];
  const topCves = Array.isArray(analysis.top_cves) ? analysis.top_cves : [];
  const actionsImmediate = Array.isArray(analysis.actions_immediate) ? analysis.actions_immediate : [];
  const actions24h = Array.isArray(analysis.actions_24h) ? analysis.actions_24h : [];
  const actions7d = Array.isArray(analysis.actions_7d) ? analysis.actions_7d : [];

  return (
    <div className="bg-panel p-6 rounded-lg border border-border h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Upload Threat Report</h2>
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
        <FileUp className="mx-auto h-12 w-12 text-gray-500" />
        <p className="mt-4 text-sm text-gray-400">
          <span className="font-semibold text-neon-blue">Upload a report</span> for threat-report RAG analysis.
        </p>
        <p className="text-xs text-gray-500 mt-1">Supports .pdf, .txt, .log files</p>

        <input
          type="file"
          accept=".pdf,.txt,.log"
          className="absolute top-0 left-0 w-full h-full opacity-0 cursor-pointer"
          onChange={handleFileUpload}
          disabled={isUploading}
        />
      </div>

      <div className="mt-4 flex-grow overflow-y-auto min-h-[180px]">
        {isUploading && <Loader text="Analyzing threat report..." />}
        {error && <p className="text-neon-red text-sm">{error}</p>}

        {analysisPayload && (
          <div className="space-y-4">
            <div className="border border-border rounded-lg p-4 bg-background/40">
              <h3 className="text-white font-semibold">Executive Summary (4-6 Lines)</h3>
              {summaryLines.length > 0 ? (
                <ul className="list-disc list-inside mt-2 text-sm text-gray-200 space-y-1">
                  {summaryLines.map((line, idx) => (
                    <li key={`summary-${idx}`}>{line}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-200 mt-2 whitespace-pre-wrap">{analysis.summary || 'No summary available.'}</p>
              )}
            </div>

            <div className="border border-border rounded-lg p-4 bg-background/40">
              <h3 className="text-white font-semibold">Threat Types + Evidence</h3>
              {threatTypes.length > 0 ? (
                <div className="mt-2 space-y-2">
                  {threatTypes.map((t, idx) => (
                    <div key={`threat-type-${idx}`} className="border border-border rounded p-2 bg-panel/40">
                      <p className="text-sm text-white font-medium">{t.type || 'Unknown'}</p>
                      <p className="text-xs text-gray-300 mt-1 whitespace-pre-wrap">{t.evidence || 'No evidence provided.'}</p>
                      <p className="text-xs text-gray-400 mt-1">Scope: {t.source_scope || 'unknown'}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-200 mt-2 whitespace-pre-wrap">{analysis.threat_type || 'No threat type available.'}</p>
              )}
            </div>

            <div className="border border-border rounded-lg p-4 bg-background/40">
              <h3 className="text-white font-semibold">Top IOCs & CVEs</h3>
              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-gray-400 mb-1">Top IOCs</p>
                  {topIocs.length > 0 ? (
                    <ul className="list-disc list-inside text-gray-200 space-y-1">
                      {topIocs.map((ioc, idx) => (
                        <li key={`top-ioc-${idx}`}>
                          {ioc.indicator} ({ioc.type})
                          {ioc.source_scope ? ` [${ioc.source_scope}]` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-gray-200">No top IOC ranking generated.</p>
                  )}
                </div>
                <div>
                  <p className="text-gray-400 mb-1">Top CVEs</p>
                  {topCves.length > 0 ? (
                    <ul className="list-disc list-inside text-gray-200 space-y-1">
                      {topCves.map((cve, idx) => (
                        <li key={`top-cve-${idx}`}>
                          {cve.cve}
                          {cve.source_scope ? ` [${cve.source_scope}]` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-gray-200">No CVEs found.</p>
                  )}
                </div>
              </div>

              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-gray-400">All IPs</p>
                  <p className="text-gray-200 break-all">{(iocs.ips || []).length ? iocs.ips.join(', ') : 'None'}</p>
                </div>
                <div>
                  <p className="text-gray-400">All Domains</p>
                  <p className="text-gray-200 break-all">{(iocs.domains || []).length ? iocs.domains.join(', ') : 'None'}</p>
                </div>
                <div>
                  <p className="text-gray-400">All Hashes</p>
                  <p className="text-gray-200 break-all">{(iocs.hashes || []).length ? iocs.hashes.join(', ') : 'None'}</p>
                </div>
                <div>
                  <p className="text-gray-400">All CVEs</p>
                  <p className="text-gray-200 break-all">{(iocs.cves || []).length ? iocs.cves.join(', ') : 'None'}</p>
                </div>
              </div>
            </div>

            <div className="border border-border rounded-lg p-4 bg-background/40">
              <h3 className="text-white font-semibold">Detection Signals</h3>
              {detections.length > 0 ? (
                <ul className="list-disc list-inside mt-2 text-sm text-gray-200 space-y-1">
                  {detections.map((d, idx) => (
                    <li key={`det-${idx}`}>
                      {d.signal} {d.source_scope ? `[${d.source_scope}]` : ''}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-200 mt-2">No detection signals generated.</p>
              )}
            </div>

            <div className="border border-border rounded-lg p-4 bg-background/40">
              <h3 className="text-white font-semibold">Prioritized Action Plan</h3>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-sm text-left text-gray-300 border border-border rounded">
                  <thead className="bg-panel/60 text-gray-200">
                    <tr>
                      <th className="px-3 py-2 border-b border-border">Window</th>
                      <th className="px-3 py-2 border-b border-border">Action</th>
                      <th className="px-3 py-2 border-b border-border">Scope</th>
                    </tr>
                  </thead>
                  <tbody>
                    {actionsImmediate.map((a, idx) => (
                      <tr key={`act-imm-${idx}`}>
                        <td className="px-3 py-2 border-b border-border">Immediate</td>
                        <td className="px-3 py-2 border-b border-border">{a.action}</td>
                        <td className="px-3 py-2 border-b border-border">{a.source_scope || 'unknown'}</td>
                      </tr>
                    ))}
                    {actions24h.map((a, idx) => (
                      <tr key={`act-24-${idx}`}>
                        <td className="px-3 py-2 border-b border-border">24h</td>
                        <td className="px-3 py-2 border-b border-border">{a.action}</td>
                        <td className="px-3 py-2 border-b border-border">{a.source_scope || 'unknown'}</td>
                      </tr>
                    ))}
                    {actions7d.map((a, idx) => (
                      <tr key={`act-7d-${idx}`}>
                        <td className="px-3 py-2 border-b border-border">7d</td>
                        <td className="px-3 py-2 border-b border-border">{a.action}</td>
                        <td className="px-3 py-2 border-b border-border">{a.source_scope || 'unknown'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="border border-border rounded-lg p-4 bg-background/40">
              <h3 className="text-white font-semibold mb-3">Further Query</h3>
              <form onSubmit={handleFurtherQuery} className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Mode</label>
                    <select
                      value={mode}
                      onChange={(e) => setModuleState({ mode: e.target.value })}
                      className="w-full bg-panel border border-border rounded-md px-3 py-2 text-sm text-white"
                      disabled={isQuerying}
                    >
                      <option value="hybrid">Hybrid (Report + Global)</option>
                      <option value="report_only">Report Only</option>
                      <option value="global_only">Global Only</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Report ID</label>
                    <input
                      type="text"
                      value={reportId}
                      onChange={(e) => setModuleState({ reportId: e.target.value })}
                      className="w-full bg-panel border border-border rounded-md px-3 py-2 text-xs text-gray-200"
                      placeholder="Set automatically after upload"
                      disabled={isQuerying}
                    />
                  </div>
                </div>

                <textarea
                  value={query}
                  onChange={(e) => setModuleState({ query: e.target.value })}
                  placeholder="Ask a report question (e.g., What CVEs are mentioned in this report?)"
                  className="w-full min-h-[90px] bg-panel border border-border rounded-md px-3 py-2 text-sm text-white"
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

              {querySources.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs text-gray-400">Evidence Sources (Query Stage)</p>
                  {querySources.map((source, idx) => {
                    const metadata = source?.metadata || {};
                    const scope = source?.retrieval_scope || (metadata.report_id ? 'report' : 'global');
                    return (
                      <div key={`source-${idx}`} className="bg-panel border border-border rounded-md p-2">
                        <p className="text-xs text-gray-300">
                          Scope: <span className="text-white">{scope}</span>
                          {' | '}Type: <span className="text-white">{source?.type || 'unknown'}</span>
                          {' | '}Source: <span className="text-white">{source?.source || 'unknown'}</span>
                        </p>
                        <p className="text-xs text-gray-400 mt-1 whitespace-pre-wrap">
                          {String(source?.text || '').slice(0, 260)}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportUpload;
