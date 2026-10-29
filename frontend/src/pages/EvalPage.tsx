import { useState } from "react";
import { Button, Card, Descriptions, List, Spin, message } from "antd";
import { PlayCircleOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { EvalRun, listDatasets, runEval } from "../api/eval";

export default function EvalPage() {
  const { data: datasets, isLoading } = useQuery({ queryKey: ["datasets"], queryFn: listDatasets });
  const [currentRun, setCurrentRun] = useState<EvalRun | null>(null);
  const [running, setRunning] = useState(false);

  const handleRun = async (datasetId: string) => {
    setRunning(true);
    try {
      const run = await runEval(datasetId);
      setCurrentRun(run);
      message.success("评测完成");
    } catch {
      message.error("评测失败");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <h2>评测中心</h2>
      <List
        loading={isLoading}
        dataSource={datasets ?? []}
        renderItem={(ds) => (
          <List.Item
            actions={[
              <Button
                key="run"
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={running}
                onClick={() => void handleRun(ds.id)}
              >
                跑分
              </Button>,
            ]}
          >
            <List.Item.Meta title={ds.name} description={`${ds.count} 题`} />
          </List.Item>
        )}
      />
      {currentRun && (
        <Card title="最近跑分结果" style={{ marginTop: 24 }}>
          <Spin spinning={running}>
            <Descriptions column={2} bordered size="small">
              {Object.entries(currentRun.metrics).map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  {String(value)}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Spin>
        </Card>
      )}
    </div>
  );
}
