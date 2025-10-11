import React from 'react';
import { FileUp } from 'lucide-react';

const ReportUpload = () => {
    return (
        <div className="bg-panel p-6 rounded-lg border border-border">
            <h2 className="text-lg font-semibold text-white mb-4">Upload Threat Report</h2>
            <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-neon-blue transition-colors">
                <FileUp className="mx-auto h-12 w-12 text-gray-500" />
                <p className="mt-4 text-sm text-gray-400">
                  <span className="font-semibold text-neon-blue">Upload a report</span> for vector analysis.
                </p>
                <p className="text-xs text-gray-500 mt-1">Supports PDF, TXT, MD files</p>
            </div>
        </div>
    );
};

export default ReportUpload;