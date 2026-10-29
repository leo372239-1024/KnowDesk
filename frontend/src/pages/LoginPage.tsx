import { Button, Card, Form, Input, message } from "antd";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";

interface LoginForm {
  username: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();

  const onFinish = async (values: LoginForm) => {
    try {
      await login(values.username, values.password);
      message.success("登录成功");
      navigate("/chat");
    } catch {
      message.error("用户名或密码错误");
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", background: "#f5f5f5" }}>
      <Card title="KnowDesk 登录" style={{ width: 360 }}>
        <Form<LoginForm> onFinish={onFinish} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input placeholder="admin" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password placeholder="admin123" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
