import { useCallback, useState } from "react";

import { planRoutes } from "../api/client";
import type { RoutePlanRequest, RoutePlanResponse } from "../types";

export type RequestStatus = "idle" | "loading" | "success" | "error";

interface UseRoutePlanResult {
  status: RequestStatus;
  error: string | null;
  run: (input: RoutePlanRequest) => Promise<RoutePlanResponse | null>;
  reset: () => void;
}

export function useRoutePlan(): UseRoutePlanResult {
  const [status, setStatus] = useState<RequestStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (input: RoutePlanRequest) => {
    setStatus("loading");
    setError(null);
    try {
      const result = await planRoutes(input);
      setStatus("success");
      return result;
    } catch (caught) {
      setStatus("error");
      if (caught instanceof Error) {
        setError(caught.message);
      } else {
        setError("An unexpected error occurred.");
      }
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  return { status, error, run, reset };
}
