import React from 'react';
import CVESummary from '../components/CVESummary';

const ThreatIntelPage = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-white mb-6">Threat Intelligence</h1>
      <CVESummary />
    </div>
  );
};

export default ThreatIntelPage;