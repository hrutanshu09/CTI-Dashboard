import axios from 'axios';

// The base URL for your backend server
axios.defaults.withCredentials = true;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';
const LOG_API_BASE_URL = process.env.REACT_APP_LOG_API_BASE_URL || 'http://127.0.0.1:8001';
const THREAT_REPORT_API_BASE_URL =
  process.env.REACT_APP_THREAT_REPORT_API_BASE_URL || LOG_API_BASE_URL;
const DASHBOARD_API_BASE_URL =
  process.env.REACT_APP_DASHBOARD_API_BASE_URL || LOG_API_BASE_URL;

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
    if (error.response?.data?.detail) {
      return `AI service error: ${error.response.data.detail}`;
    }
    return "Sorry, I couldn't connect to the AI service. Please ensure the backend server is running.";
  }
};


// --- Keep the existing mock functions for other features ---

export const getDashboardStats = async () => {
  try {
    const response = await axios.get(`${DASHBOARD_API_BASE_URL}/dashboard/stats`);
    return response.data;
  } catch (error) {
    console.error('Error fetching dashboard stats:', error);
    return { totalCVEs: 0, iocDetections: 0, criticalAlerts: 0 };
  }
};

export const getSeverityData = async () => {
  try {
    const response = await axios.get(`${DASHBOARD_API_BASE_URL}/dashboard/severity`, {
      params: { range: '30d' },
    });
    return Array.isArray(response.data) ? response.data : [];
  } catch (error) {
    console.error('Error fetching severity breakdown:', error);
    return [];
  }
};

export const analyzeLogFile = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const ipRegex = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;
    const ipRegexPlain = /\b(?:\d{1,3}\.){3}\d{1,3}\b/;
    const cveRegex = /\bCVE-\d{4}-\d{4,7}\b/i;
    const hashRegex = /\b[a-f0-9]{32,64}\b/i;
    const urlRegex = /\bhttps?:\/\/[^\s/$.?#].[^\s]*\b/i;
    const domainRegex = /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b/i;
    const mitreRegex = /\bT\d{4}(?:\.\d{3})?\b/i;
    const nonIocFileExtRegex = /\.(csv|txt|log|json|xml|pdf|docx?|xlsx?|pptx?)$/i;

    const unique = (arr) => [...new Set(arr.filter(Boolean))];
    const normalizeIndicator = (value) => String(value || '').trim();

    const extractIocCandidatesFromText = (text) => {
      const value = String(text || '');
      const candidates = [];

      candidates.push(...(value.match(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g) || []));
      candidates.push(...(value.match(/\bCVE-\d{4}-\d{4,7}\b/gi) || []));
      candidates.push(...(value.match(/\b[a-f0-9]{32,64}\b/gi) || []));
      candidates.push(...(value.match(/\bhttps?:\/\/[^\s/$.?#].[^\s]*\b/gi) || []));
      candidates.push(...(value.match(/\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b/gi) || []));
      candidates.push(...(value.match(/\bT\d{4}(?:\.\d{3})?\b/gi) || []));

      return unique(candidates.map(normalizeIndicator));
    };

    const isLikelyIoc = (match) => {
      const explicit = String(match?.type || '').toLowerCase();
      const indicator = normalizeIndicator(match?.label || match?.source || '');
      if (!indicator) return false;

      if (explicit.includes('ip') || explicit.includes('domain') || explicit.includes('url') || explicit.includes('hash') || explicit.includes('cve')) {
        return true;
      }

      if (nonIocFileExtRegex.test(indicator)) {
        return false;
      }

      if (indicator.includes(' ') && !urlRegex.test(indicator)) {
        return false;
      }

      return (
        ipRegexPlain.test(indicator) ||
        cveRegex.test(indicator) ||
        hashRegex.test(indicator) ||
        urlRegex.test(indicator) ||
        domainRegex.test(indicator) ||
        mitreRegex.test(indicator)
      );
    };

    const extractIps = (match) => {
      const metadata = match?.metadata || {};
      const metadataIps = [metadata.src_ip, metadata.source_ip, metadata.dest_ip, metadata.dst_ip];
      const textIps = String(match?.text || '').match(ipRegex) || [];
      return unique([...metadataIps, ...textIps]);
    };

    const inferIocType = (indicator, explicit = '') => {
      const explicitType = String(explicit || '').toLowerCase();
      if (explicitType.includes('ip')) return 'IP';
      if (explicitType.includes('url')) return 'URL';
      if (explicitType.includes('hash')) return 'Hash';
      if (explicitType.includes('domain')) return 'Domain';
      if (explicitType.includes('cve')) return 'CVE';

      const label = String(indicator || '');
      if (/\b(?:\d{1,3}\.){3}\d{1,3}\b/.test(label)) return 'IP';
      if (/\bCVE-\d{4}-\d{4,7}\b/i.test(label)) return 'CVE';
      if (/\bT\d{4}(?:\.\d{3})?\b/i.test(label)) return 'MITRE Technique';
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

    const summarizeEvidence = (examples = []) => {
      const evidence = examples
        .map((ex) => String(ex?.evidence || '').trim())
        .find((text) => text.length > 0);

      if (!evidence) return 'Limited contextual evidence is currently available.';
      const sentence = evidence.split(/[.!?]/).map((s) => s.trim()).find(Boolean) || evidence;
      return sentence.slice(0, 180);
    };

    const extractStructuredAttackDetails = (examples = []) => {
      const evidenceText = examples.map((ex) => String(ex?.evidence || '')).join(' ');
      if (!evidenceText.trim()) return null;

      const titleMatch = evidenceText.match(/Title:\s*([^|.\n]+)/i);
      const categoryMatch = evidenceText.match(/Category:\s*([^|.\n]+)/i);
      const attackTypeMatch = evidenceText.match(/Attack Type:\s*([^|.\n]+)/i);

      const title = String(titleMatch?.[1] || '').trim();
      const category = String(categoryMatch?.[1] || '').trim();
      const attackType = String(attackTypeMatch?.[1] || '').trim();

      if (!title && !category && !attackType) return null;
      return { title, category, attackType };
    };

    const buildAffectedAssets = (item) => {
      const assets = [];
      if (Array.isArray(item.relatedIps)) assets.push(...item.relatedIps);

      const hostRegex = /\b(?:host|hostname|server|endpoint)\s*[:=]\s*([a-zA-Z0-9._-]+)/gi;
      const userRegex = /\b(?:user|username|account)\s*[:=]\s*([a-zA-Z0-9._-]+)/gi;
      const text = (item.examples || []).map((e) => String(e?.evidence || '')).join(' ');

      let match;
      while ((match = hostRegex.exec(text)) !== null) assets.push(`host:${match[1]}`);
      while ((match = userRegex.exec(text)) !== null) assets.push(`user:${match[1]}`);

      const uniqueAssets = unique(assets.filter(Boolean));
      return uniqueAssets.length > 0
        ? uniqueAssets
        : ['No specific host/user/IP asset extracted from current evidence'];
    };

    const buildActionPlan = (iocType, topSeverity) => {
      const severityLead =
        topSeverity === 'Critical' || topSeverity === 'High'
          ? 'Execute containment immediately and escalate to incident response lead.'
          : 'Open an investigation ticket and monitor for recurrence.';

      if (iocType === 'IP') {
        return [
          severityLead,
          'Block or rate-limit the IP at firewall/WAF and monitor denied-traffic trends.',
          'Correlate the IP against authentication, proxy, and endpoint telemetry.',
          'Review impacted systems and close exposed entry points.',
        ];
      }
      if (iocType === 'Domain/Indicator' || iocType === 'Domain' || iocType === 'URL') {
        return [
          severityLead,
          'Block the domain/URL in DNS and web proxy controls.',
          'Hunt for historical connections to this indicator across user endpoints.',
          'Review phishing/web gateway controls and tighten policies.',
        ];
      }
      if (iocType === 'Hash') {
        return [
          severityLead,
          'Search EDR/AV telemetry for this hash and isolate matching endpoints.',
          'Quarantine suspicious binaries and collect forensic artifacts.',
          'Patch and harden affected systems before restoring normal operations.',
        ];
      }
      if (iocType === 'CVE') {
        return [
          severityLead,
          'Identify assets affected by this CVE and validate exposure.',
          'Apply vendor patch/mitigation and verify remediation success.',
          'Add temporary detections for exploit behavior until patch rollout completes.',
        ];
      }
      if (iocType === 'MITRE Technique') {
        return [
          severityLead,
          'Run hunt queries aligned to this MITRE technique across SIEM and EDR.',
          'Validate whether behavior appears on critical assets or privileged accounts.',
          'Tune detections and response playbooks for this technique pattern.',
        ];
      }

      return [
        severityLead,
        'Validate this indicator across SIEM, endpoint, and network telemetry.',
        'Contain suspicious activity and scope potential lateral movement.',
        'Document findings and update SOC triage guidance.',
      ];
    };

    const buildNarrative = (item) => {
      const sourceCount = Array.isArray(item.sources) ? item.sources.length : 0;
      const evidenceSummary = summarizeEvidence(item.examples);
      const iocType = item.iocType;
      const topSeverity = item.topSeverity;
      const structured = extractStructuredAttackDetails(item.examples);

      const whatHappened = structured
        ? [
            structured.title ? `- ${structured.title}` : null,
            structured.category ? `- Category: ${structured.category}` : null,
            structured.attackType ? `- Attack Type: ${structured.attackType}` : null,
          ]
            .filter(Boolean)
            .join('\n')
        : `IOC "${item.indicator}" (${iocType}) triggered ${item.occurrences} time(s) at ${topSeverity} severity. Evidence: ${evidenceSummary}.`;

      let whyItMatters =
        topSeverity === 'Critical' || topSeverity === 'High'
          ? 'This pattern suggests potentially active malicious behavior that can impact service availability, data confidentiality, or account integrity.'
          : 'This pattern may represent early-stage malicious behavior and should be investigated before it escalates.';

      if (iocType === 'CVE') {
        whyItMatters = 'This indicates a known vulnerability path that could be exploited if exposed assets remain unpatched.';
      } else if (iocType === 'Hash') {
        whyItMatters = 'This may represent a malicious artifact that can execute across endpoints and enable persistence.';
      } else if (iocType === 'MITRE Technique') {
        whyItMatters = 'This behavior maps to an adversary technique, which helps prioritize targeted detection and containment actions.';
      } else if (iocType === 'IP' || iocType === 'Domain/Indicator' || iocType === 'Domain' || iocType === 'URL') {
        whyItMatters = 'This external indicator can be used for command-and-control, phishing, or intrusion attempts if not blocked quickly.';
      }

      if (sourceCount > 1) {
        whyItMatters += ' Correlation across multiple sources increases confidence.';
      }

      return {
        whatHappened,
        whyItMatters,
        affectedAssets: buildAffectedAssets(item),
        actionPlan: buildActionPlan(iocType, topSeverity),
      };
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
          const indicatorFromLabel = normalizeIndicator(match?.label || match?.source || '');
          const extractedFromText = extractIocCandidatesFromText(match?.text || '');
          const mergedIndicators = unique([
            ...(isLikelyIoc(match) ? [indicatorFromLabel] : []),
            ...extractedFromText,
          ]);

          mergedIndicators.forEach((indicator) => {
            const iocType = inferIocType(indicator, match?.type);
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

        const normalizedIocType = String(item.iocType || 'Indicator');
        const narrative = buildNarrative({
          ...item,
          iocType: normalizedIocType,
          topSeverity,
        });

        return {
          ...item,
          iocType: normalizedIocType,
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
          whatHappened: narrative.whatHappened,
          whyItMatters: narrative.whyItMatters,
          affectedAssets: narrative.affectedAssets,
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
          actionPlan: narrative.actionPlan,
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
export const getRecentAlerts = async (limit = 10) => {
  try {
    const response = await axios.get(`${DASHBOARD_API_BASE_URL}/dashboard/recent-alerts`, {
      params: { limit },
    });
    return Array.isArray(response.data) ? response.data : [];
  } catch (error) {
    console.error('Error fetching recent alerts:', error);
    return [];
  }
};

export const clearDashboardMetrics = async (source = 'all') => {
  try {
    const response = await axios.delete(`${DASHBOARD_API_BASE_URL}/dashboard/clear`, {
      params: { source },
    });
    return response.data;
  } catch (error) {
    console.error('Error clearing dashboard metrics:', error);
    throw new Error('Failed to clear dashboard metrics.');
  }
};

