// This is a mock API service. Replace with actual Axios calls to your FastAPI backend.

export const getDashboardStats = async () => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({
        totalCVEs: 142,
        iocDetections: 78,
        criticalAlerts: 9,
      });
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

export const getCVEData = async (cveId) => {
  // In a real app, you would use axios:
  // const response = await axios.get(`/api/cve/${cveId}`);
  // return response.data;

  return new Promise(resolve => {
    setTimeout(() => {
      if (!cveId) {
        resolve(null);
        return;
      }
      resolve({
        cve_id: cveId,
        description: "A critical remote code execution vulnerability exists in the Web Server component. An unauthenticated, remote attacker could exploit this vulnerability to execute arbitrary code with system-level privileges.",
        cvss_score: 9.8,
        ai_summary: "This is a critical RCE flaw in the Web Server. Attackers can exploit it remotely without authentication to take full control of the system. The primary impact is total loss of confidentiality, integrity, and availability. **Immediate patching is required.** Apply the vendor's security update or restrict network access to the affected service."
      });
    }, 1200);
  });
};

export const analyzeLogFile = async (file) => {
    console.log("Uploading file:", file.name);
    return new Promise(resolve => {
        setTimeout(() => {
            resolve([
                { timestamp: '2025-10-04 17:25:10', sourceIp: '198.51.100.54', ioc: 'bad.evilcorp.com', type: 'URL', severity: 'High' },
                { timestamp: '2025-10-04 17:28:02', sourceIp: '203.0.113.12', ioc: 'eicar.com.txt', type: 'Hash', severity: 'Critical' },
                { timestamp: '2025-10-04 17:31:45', sourceIp: '192.0.2.88', ioc: '192.0.2.88', type: 'IP', severity: 'Medium' },
            ]);
        }, 1500);
    });
};