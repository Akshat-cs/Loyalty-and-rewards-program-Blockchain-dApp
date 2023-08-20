import React, { createContext, useContext, useState } from 'react';

const PointsContext = createContext();

export const usePoints = () => {
  return useContext(PointsContext);
};

export const PointsProvider = ({ children }) => {
  const [points, setPoints] = useState(0);

  const updatePoints = (newPoints) => {
    setPoints(newPoints);
  };

  return (
    <PointsContext.Provider value={{ points, updatePoints }}>
      {children}
    </PointsContext.Provider>
  );
};
