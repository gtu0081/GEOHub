import { useEffect, useMemo, useState } from "react";
import { useFetcher } from "@remix-run/react";
import { JOB_ACTIVE, type Job } from "./jobs";

/**
 * Shared polling/submit state for one skill's job list (content, measure,
 * knowledge, compare). Mirrors the dashboard's diagnosis polling pattern.
 */
export function useSkillJobs(initialJobs: Job[], apiPrefix: string) {
  const fetcher = useFetcher<{ job?: Job; error?: string }>();
  const [jobs, setJobs] = useState<Job[]>(initialJobs);

  useEffect(() => {
    const payload = fetcher.data;
    if (payload?.job) {
      setJobs((prev) =>
        prev.some((job) => job.job_id === payload.job!.job_id) ? prev : [payload.job!, ...prev],
      );
    }
  }, [fetcher.data]);

  const hasActive = useMemo(
    () => jobs.some((job) => JOB_ACTIVE.has(job.status)),
    [jobs],
  );

  useEffect(() => {
    if (!hasActive) return;
    let consecutiveFailures = 0;
    const timer = setInterval(async () => {
      const active = jobs.filter((job) => JOB_ACTIVE.has(job.status));
      const updates = await Promise.all(
        active.map((job) =>
          fetch(`/api/${apiPrefix}/${job.job_id}`)
            .then((response) => (response.ok ? response.json() : null))
            .catch(() => null),
        ),
      );
      // Stop polling after repeated failures (job redacted/retired or auth lost).
      if (updates.every((update) => update === null)) {
        consecutiveFailures += 1;
        if (consecutiveFailures >= 3) {
          setJobs((prev) =>
            prev.map((job) =>
              JOB_ACTIVE.has(job.status)
                ? { ...job, status: "failed", error: "Polling stopped: job is no longer reachable" }
                : job,
            ),
          );
        }
        return;
      }
      consecutiveFailures = 0;
      setJobs((prev) =>
        prev.map((job) => {
          const update = updates.find(
            (candidate): candidate is Job => candidate?.job_id === job.job_id,
          );
          return update ?? job;
        }),
      );
    }, 2500);
    return () => clearInterval(timer);
  }, [hasActive, jobs, apiPrefix]);

  const latest = jobs.find((job) => job.status === "succeeded");
  const failedJob = jobs.find((job) => job.status === "failed");
  const actionError = fetcher.data?.error ?? failedJob?.error ?? null;

  return {
    jobs,
    hasActive,
    latest,
    actionError,
    submitting: fetcher.state !== "idle",
    submit: (formData: FormData) => fetcher.submit(formData, { method: "POST" }),
  };
}
