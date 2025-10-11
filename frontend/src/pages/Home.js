import React from 'react';

const Home = () => {
  return (
    <div className="flex-1 flex items-center justify-center text-center">
      <div>
        <h1 className="text-4xl font-bold text-white">Welcome to Project Nova</h1>
        <p className="mt-4 text-lg text-gray-400">
          Your centralized Cyber Threat Intelligence dashboard.
        </p>
        <p className="mt-2 text-gray-500">
          Select a section from the sidebar to begin.
        </p>
      </div>
    </div>
  );
};

export default Home;