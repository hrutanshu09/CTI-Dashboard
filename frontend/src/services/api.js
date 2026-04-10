import axios from 'axios';

// The base URL for your backend server
const API_BASE_URL = 'http://127.0.0.1:8000';
const LOG_API_BASE_URL = process.env.REACT_APP_LOG_API_BASE_URL || 'http://127.0.0.1:8001';
const THREAT_REPORT_API_BASE_URL =
  process.env.REACT_APP_THREAT_REPORT_API_BASE_URL || LOG_API_BASE_URL;

// --- Functions that call the new backend ---

export const getCVEData = async (cveId) => {
  if (!cveId) {
    return null;
  }
  try {
    const response = await axios.get(`${API_BASE_URL}/api/cve-summary/${cveId}`);
    return response.data;
  } catch (error) {
    console.error("Error fetching CVE summary:", error);
    if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error('Failed to fetch CVE data from the backend.');
  }
};

export const getAIResponse = async (prompt) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/ai-assistant`, {
      prompt: prompt,
    });
    return response.data.response;
  } catch (error) {
    console.error("Error fetching AI response:", error);
    return "Sorry, I couldn't connect to the AI service. Please ensure the backend server is running.";
  }
};


// --- Keep the existing mock functions for other features ---

export const getDashboardStats = async () => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({ totalCVEs: 142, iocDetections: 78, criticalAlerts: 9 });
    }, 500);
  });
};

export const getSeverityData = async () => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve([
        { name: 'Critical', value: 15, fill: '#FF3131' },
        { name: 'High', value: 45, fill: '#FFA500' },
        { name: 'Medium', value: 70, fill: '#FFD700' },
        { name: 'Low', value: 20, fill: '#00BFFF' },
      ]);
    }, 500);
  });
};

export const analyzeLogFile = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const ipRegex = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;

    const toTitleCase = (value) =>
      value
        ? value
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, (c) => c.toUpperCase())
        : 'Unknown';

    const unique = (arr) => [...new Set(arr.filter(Boolean))];

    const extractIps = (match) => {
      const metadata = match?.metadata || {};
      const metadataIps = [metadata.src_ip, metadata.source_ip, metadata.dest_ip, metadata.dst_ip];
      const textIps = String(match?.text || '').match(ipRegex) || [];
      return unique([...metadataIps, ...textIps]);
    };

    const inferIocType = (match) => {
      const explicit = String(match?.type || '').toLowerCase();
      if (explicit) return toTitleCase(explicit);

      const label = String(match?.label || '');
      if (/\b(?:\d{1,3}\.){3}\d{1,3}\b/.test(label)) return 'IP';
      if (label.includes('://')) return 'URL';
      if (/^[a-f0-9]{32,64}$/i.test(label)) return 'Hash';
      if (label.includes('.')) return 'Domain/Indicator';
      return 'Indicator';
    };

    const inferSeverity = (match) => {
      const label = String(match?.label || '').toLowerCase();
      if (label.includes('critical')) return 'Critical';
      if (label.includes('high')) return 'High';
      if (label.includes('medium')) return 'Medium';
      if (label.includes('low')) return 'Low';
      return 'Medium';
    };

    const mapToThreatRows = (payload) => {
      const chunkResults = payload?.analysis || [];
      const rows = [];
      const details = [];

      chunkResults.forEach((chunkResult) => {
        const chunkId = chunkResult?.chunk_id ?? '-';
        const matches = chunkResult?.analysis?.matches || [];

        matches.forEach((match) => {
          const ips = extractIps(match);
          const iocType = inferIocType(match);
          const indicator = match?.label || match?.source || 'N/A';

          rows.push({
            timestamp: `Chunk ${chunkId}`,
            sourceIp: ips[0] || 'N/A',
            ioc: indicator,
            type: iocType,
            severity: inferSeverity(match),
          });

          details.push({
            chunkId,
            indicator,
            iocType,
            severity: inferSeverity(match),
            source: match?.source || 'unknown',
            score: typeof match?.score === 'number' ? Number(match.score.toFixed(4)) : null,
            ips,
            exampleText: String(match?.text || '').slice(0, 260),
          });
        });
      });

      const groupedDetails = Object.values(
        details.reduce((acc, entry) => {
          const key = `${entry.indicator}::${entry.iocType}`;
          if (!acc[key]) {
            acc[key] = {
              indicator: entry.indicator,
              iocType: entry.iocType,
              occurrences: 0,
              severities: [],
              relatedIps: [],
              sources: [],
              examples: [],
              scoreValues: [],
            };
          }

          const item = acc[key];
          item.occurrences += 1;
          item.severities.push(entry.severity);
          item.relatedIps = unique([...item.relatedIps, ...entry.ips]);
          item.sources = unique([...item.sources, entry.source]);
          if (typeof entry.score === 'number') item.scoreValues.push(entry.score);

          if (item.examples.length < 3) {
            item.examples.push({
              chunkId: entry.chunkId,
              ip: entry.ips[0] || 'N/A',
              evidence: entry.exampleText || 'No evidence text available',
              score: entry.score,
            });
          }

          return acc;
        }, {})
      ).map((item) => {
        const topSeverity =
          item.severities.includes('Critical') ? 'Critical' :
          item.severities.includes('High') ? 'High' :
          item.severities.includes('Medium') ? 'Medium' :
          'Low';

        return {
          ...item,
          topSeverity,
          avgScore:
            item.scoreValues.length > 0
              ? Number(
                  (
                    item.scoreValues.reduce((sum, value) => sum + value, 0) /
                    item.scoreValues.length
                  ).toFixed(4)
                )
              : null,
          stakeholderSummary:
            `Indicator "${item.indicator}" was detected ${item.occurrences} time(s) from ${item.sources.join(', ')} with ${topSeverity} risk.`,
          executiveView:
            topSeverity === 'Critical' || topSeverity === 'High'
              ? 'This finding can impact business operations if not contained quickly.'
              : 'This finding is currently moderate but should be monitored and addressed.',
          socView:
            item.relatedIps.length > 0
              ? `Monitor and alert on these IPs: ${item.relatedIps.join(', ')}. Correlate with authentication, network, and endpoint telemetry.`
              : 'Correlate this indicator with authentication, network, and endpoint telemetry to identify related entities.',
          itOpsView:
            'Validate affected systems, isolate suspicious hosts when necessary, enforce hardening controls, and patch vulnerable assets.',
          actionPlan: [
            'Validate whether this IOC is present in current logs, SIEM, and endpoint telemetry.',
            'Contain suspicious activity (block IOC, isolate host, or disable compromised credentials).',
            'Hunt for lateral movement and persistence using related indicators and timestamps.',
            'Document findings and escalation status for SOC lead and management review.',
          ],
        };
      });

      return { rows, groupedDetails };
    };

    try {
      const response = await axios.post(
        `${LOG_API_BASE_URL}/logs/analyze`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000,
        }
      );

      return mapToThreatRows(response.data);
    } catch (error) {
      console.error("Error analyzing log file:", error);
      if (error.response && error.response.data && error.response.data.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to analyze the log file.');
    }
};

export const queryLogInsights = async (query) => {
  try {
    const response = await axios.post(`${LOG_API_BASE_URL}/logs/query`, { query });
    return response.data;
  } catch (error) {
    console.error("Error querying log insights:", error);
    if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error('Failed to query log insights.');
  }
};


export const analyzeThreatReportFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await axios.post(
      `${THREAT_REPORT_API_BASE_URL}/threat-reports/analyze`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000,
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error analyzing threat report:', error);
    if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error('Failed to analyze the threat report.');
  }
};

export const queryThreatReportInsights = async ({ query, reportId, mode = 'hybrid' }) => {
  const payload = { query, mode };
  if (mode !== 'global_only' && reportId) {
    payload.report_id = reportId;
  }

  try {
    const response = await axios.post(
      `${THREAT_REPORT_API_BASE_URL}/threat-reports/query`,
      payload,
      { timeout: 120000 }
    );
    return response.data;
  } catch (error) {
    console.error('Error querying threat report insights:', error);
    if (error.response && error.response.data && error.response.data.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error('Failed to query threat report insights.');
  }
};
export const getRecentAlerts = async () => {
    return new Promise(resolve => {
        setTimeout(() => {
            resolve([
                { timestamp: '2025-10-12 14:15:02', sourceIp: '203.0.113.12', ioc: 'eicar.com.txt', type: 'Hash', severity: 'Critical' },
                { timestamp: '2025-10-12 11:45:10', sourceIp: '198.51.100.54', ioc: 'bad.evilcorp.com', type: 'URL', severity: 'High' },
                { timestamp: '2025-10-12 09:21:33', sourceIp: '198.51.100.91', ioc: 'suspicious-login.sh', type: 'Filename', severity: 'High' },
                { timestamp: '2025-10-11 22:10:05', sourceIp: '192.0.2.88', ioc: '192.0.2.88', type: 'IP', severity: 'Medium' },
            ]);
        }, 800);
    });
};

