import { useEffect, useState } from "react";
import { Drawer, Empty, Spin, Table, Tag } from "antd";
import { getTrace } from "../api/chat";
import { TraceSpan } from "../types/chat";

interface TracePanelProps {
  traceId: string | null;
  open: boolean;
  onClose: () => void;
}

export function TracePanel({ traceId, open, onClose }: TracePanelProps) {
  const [spans, setSpans] = useState<TraceSpan[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !traceId) return;
    setLoading(true);
    getTrace(traceId)
      .then((detail) => setSpans(detail.spans ?? []))
      .catch(() => setSpans([]))
      .finally(() => setLoading(false));
  }, [open, traceId]);

  const columns = [
    { title: "节点", dataIndex: "name", key: "name" },
    {
      title: "耗时(ms)",
      dataIndex: "elapsed_ms",
      key: "elapsed_ms",
      render: (v: number) => (v != null ? <Tag color="blue">{v}</Tag> : "-"),
    },
  ];

  return (
    <Drawer title="调用链路 Trace" open={open} onClose={onClose} width={560}>
      {loading ? (
        <Spin />
      ) : spans.length === 0 ? (
        <Empty description="暂无 trace 数据" />
      ) : (
        <Table
          rowKey={(row, i) => `${row.name}-${i}`}
          columns={columns}
          dataSource={spans}
          size="small"
          pagination={false}
        />
      )}
    </Drawer>
  );
}
