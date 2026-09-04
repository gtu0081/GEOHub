import { Badge } from "@shopify/polaris";
import { statusTone, type Job } from "../lib/jobs";

export function JobStatusBadge({ job }: { job: Job }) {
  const scoreSuffix = job.overall_score != null ? ` · ${job.overall_score}` : "";
  return (
    <Badge tone={statusTone(job.status)}>{`${job.status}${scoreSuffix}`}</Badge>
  );
}
