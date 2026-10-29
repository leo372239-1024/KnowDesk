# Component Guidelines

> KnowDesk 前端组件如何编写：结构、props、样式、可访问性。

## 组件结构

函数组件，命名导出，类型显式。结构顺序固定：hook 调用 → 派生数据 → 事件处理器 → JSX：

```tsx
export function Citation({ docId, chunkId, onOpen }: CitationProps) {
  const { data: chunk } = useChunk(docId, chunkId);

  const handleOpen = () => onOpen(docId, chunkId);

  return (
    <a onClick={handleOpen} className="citation">
      [doc#{chunkId}]
    </a>
  );
}
```

- 组件内 hook 调用数量稳定、顺序稳定（不写在条件里）。
- 数据获取一律下沉到 `useXxx` hook，组件只消费状态。

## Props 约定

- Props 用 `interface XxxProps` 显式定义，紧贴组件上方。
- 事件回调以 `on` 前缀（`onOpen`、`onDelete`），可选回调默认无操作。
- 需要透传 AntD 组件原生属性时用 `extends Omit<ButtonProps, ...>` 而非 `any`。
- 避免「props 钻透」（层层透传无消费的 prop）；超出 2 层考虑组合或 context。

## 样式与主题

- 统一用 AntD `ConfigProvider` 主题 token（主色、圆角、字号），组件内**不硬编码颜色值**。
- 需要自定义样式用 CSS Modules 或 AntD `token` 变量；禁止内联 `style={{color: '#xxx'}}`。
- 间距/尺寸用 AntD 的 `Space`、`Row/Col` 栅格，不手写 margin 像素魔法数。

## 可访问性（a11y）

- 交互元素用原生语义（`button`/`a`/`input`），不 `div onClick` 冒充按钮。
- 图标按钮必须有 `aria-label`。
- 引用跳转、拒答提示等关键状态对读屏可见（ARIA live region 用于流式答案状态）。

## 反模式

- ❌ 巨型组件（>300 行）不拆分。
- ❌ default export、`any` props、`React.FC` 显式标注（用 `function` + 显式 props）。
- ❌ 组件内定义子组件（每次渲染重建，丢失状态）。
- ❌ 硬编码颜色/魔法数字。
