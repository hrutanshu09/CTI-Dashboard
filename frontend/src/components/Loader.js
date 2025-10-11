import React from 'react';
import { LoaderCircle } from 'lucide-react';

const Loader = ({ size = 32, text = 'Loading...' }) => {
  return (
    <div className="flex flex-col justify-center items-center h-full w-full gap-4 text-sm">
      <LoaderCircle className="animate-spin text-neon-blue" size={size} />
      <span className="text-gray-400">{text}</span>
    </div>
  );
};

export default Loader;