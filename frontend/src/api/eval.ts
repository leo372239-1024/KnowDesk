import { client } from "./client";

export interface EvalDataset {
  id: string;
  name: string;
  count: number;
}

export interface EvalRun {
  id: string;
  dataset_id: string;
  metrics: Record<string, unknown>;
  report: string;
  created_at: string;
}

export async function listDatasets(): Promise<EvalDataset[]> {
  const { data } = await client.get("/eval/datasets");
  return data;
}

export async function runEval(datasetId: string): Promise<EvalRun> {
  const { data } = await client.post(`/eval/run/${datasetId}`);
  return data;
}
