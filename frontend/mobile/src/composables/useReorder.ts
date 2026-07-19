/**
 * useReorder -- 通用拖拽排序 Composable
 *
 * 提供:
 *   - 从 localStorage 加载/保存排序
 *   - 拖拽事件处理器 (dragstart, dragover, dragenter, dragleave, drop, dragend)
 *   - 自动追加未保存的新条目
 *
 * @typeParam T 元素类型, 需要包含 `id: string` 字段
 *
 * @example
 * ```typescript
 * const { items, dragIndex, dragOverIdx, onDragStart, onDragEnd } =
 *   useReorder<MyItem>(() => [...defaults], { key: 'my_order' })
 * ```
 */

import { shallowRef, type Ref } from 'vue'

// ==================== 类型定义 ====================

export interface UseReorderOptions {
  /** localStorage 存储键名 */
  key: string
}

export interface UseReorderReturn<T> {
  /** 排序后的列表 */
  items: Ref<T[]>
  /** 拖拽源索引 */
  dragIndex: Ref<number>
  /** 拖拽目标索引 */
  dragOverIdx: Ref<number>
  /** 开始拖拽 */
  onDragStart: (idx: number, e: DragEvent) => void
  /** 拖拽经过 */
  onDragOver: (idx: number, e: DragEvent) => void
  /** 拖拽进入 */
  onDragEnter: (idx: number) => void
  /** 拖拽离开 */
  onDragLeave: (idx: number) => void
  /** 放置 (自动保存排序) */
  onDrop: (idx: number, e: DragEvent) => void
  /** 拖拽结束 */
  onDragEnd: () => void
  /** 手动保存当前排序到 localStorage */
  saveOrder: () => void
}

// ==================== Composable ====================

/**
 * 通用拖拽排序 Composable
 *
 * @param itemsFactory 创建默认列表的工厂函数
 * @param options 配置选项
 */
export function useReorder<T extends { id: string }>(
  itemsFactory: () => T[],
  options: UseReorderOptions,
): UseReorderReturn<T> {
  const items = shallowRef<T[]>(itemsFactory())
  const dragIndex = shallowRef(-1)
  const dragOverIdx = shallowRef(-1)

  /** 从 localStorage 加载已保存的排序 */
  function loadOrder(): void {
    try {
      const saved = localStorage.getItem(options.key)
      if (saved) {
        const order: string[] = JSON.parse(saved)
        const map = new Map(items.value.map(b => [b.id, b]))
        const ordered: T[] = []
        for (const id of order) {
          const item = map.get(id)
          if (item) ordered.push(item)
        }
        // 追加未保存的新条目
        for (const item of items.value) {
          if (!ordered.find(b => b.id === item.id)) {
            ordered.push(item)
          }
        }
        items.value = ordered
      }
    } catch {
      // 忽略损坏数据
    }
  }

  /** 保存当前排序到 localStorage */
  function saveOrder(): void {
    try {
      localStorage.setItem(
        options.key,
        JSON.stringify(items.value.map(b => b.id)),
      )
    } catch {
      // 忽略存储错误
    }
  }

  // ==================== 拖拽事件处理器 ====================

  function onDragStart(idx: number, e: DragEvent): void {
    dragIndex.value = idx
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/plain', String(idx))
    }
  }

  function onDragOver(idx: number, e: DragEvent): void {
    if (dragIndex.value === idx || dragIndex.value < 0) return
    e.dataTransfer!.dropEffect = 'move'
    dragOverIdx.value = idx
  }

  function onDragEnter(idx: number): void {
    if (dragIndex.value === idx || dragIndex.value < 0) return
    dragOverIdx.value = idx
  }

  function onDragLeave(idx: number): void {
    if (dragOverIdx.value === idx) {
      dragOverIdx.value = -1
    }
  }

  function onDrop(idx: number, _e: DragEvent): void {
    if (dragIndex.value < 0 || dragIndex.value === idx) {
      dragOverIdx.value = -1
      dragIndex.value = -1
      return
    }
    const arr = [...items.value]
    const [moved] = arr.splice(dragIndex.value, 1)
    arr.splice(idx, 0, moved)
    items.value = arr
    saveOrder()
    dragOverIdx.value = -1
    dragIndex.value = -1
  }

  function onDragEnd(): void {
    dragOverIdx.value = -1
    dragIndex.value = -1
  }

  // 初始化: 加载已保存的排序
  loadOrder()

  return {
    items,
    dragIndex,
    dragOverIdx,
    onDragStart,
    onDragOver,
    onDragEnter,
    onDragLeave,
    onDrop,
    onDragEnd,
    saveOrder,
  }
}
