import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  const tokenInStorage = localStorage.getItem('netrax_token');
  const userInStorage = localStorage.getItem('netrax_user');
  const isAuth = isAuthenticated || (!!tokenInStorage && !!userInStorage);

  if (!isAuth) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
