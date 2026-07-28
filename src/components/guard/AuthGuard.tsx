import { ReactNode, useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import Loading from "@/components/ui/Loading";
import useAuthStore from "@/store/auth";

interface AuthGuardProps {
  children: ReactNode;
}

export default function AuthGuard({
  children,
}: AuthGuardProps) {
  const location = useLocation();

  const {
    authenticated,
    loading,
    initialize,
  } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (!authenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location,
        }}
      />
    );
  }

  return <>{children}</>;
}