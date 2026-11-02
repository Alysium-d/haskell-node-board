# 函数白板 · Haskell 节点连线

**先看 [`教程.md`](教程.md)**——从双击到给自己加一个新元件，15 分钟走一遍。

双击 `函数白板.cmd`，浏览器以独立窗口打开一张画布。**右键取函数，拖端口连线，值立刻出来。**

双击后黑窗口里会先打印一张体检表，再开窗口：

```
函数白板 · 体检
  Python   3.8.10  (C://Users//你//AppData//Local//Programs//Python//Python38//python.exe)
  GHC      9.10.3  (C://ghcup//bin//ghc.exe)
  工程     E://olib//verify//hask  [ok]
  运行时   ...\rt\BoardRt.hs  [ok]
  端口     8771  空闲
  结论     可以启动
```

### 双击没反应 / 报 `'python' is not recognized`

启动脚本不依赖 PATH：它按 `py -3` → `where python` → `%LOCALAPPDATA%\Programs\Python\Python3*`
→ `%USERPROFILE%\.workbuddy\binaries\python\versions\*` → `C://Python3*` 的顺序找一个能用的 Python 3，
GHC 同理（`where ghc` → `C://ghcup//bin` → `%USERPROFILE%\ghcup\bin`）。都找不到时它会停下来说清楚缺什么，
不会一闪而过。

仍然是 `'python' is not recognized`，说明你跑的是旧版脚本——重新生成一次，或直接手动：
`"C://Users//你//AppData//Local//Programs//Python//Python38//python.exe" server.py --app`。

想只体检不开窗：`start.cmd --doctor`。

不是「读代码的桌面」，是 Grasshopper 那种**函数白板**：左边进、右边出，中间是端口上的类型；
接错了线当场拒绝，接对了就在节点里看到结果。所有元件都是这个工程里**真实导出的函数**。

## 三种用法

**取元件。** 在空白处右键，弹出元件库：按「解析 / 精化 / 内核 / 求值 / 打印 / 数学 / 语法 / 驱动 / JSON / 适配」分类，
带搜索。也可以按空格或点顶栏「元件库」。点一项就落在右键的位置。

**连线。** 从右边的圆点拖到另一个节点的左边圆点。拖动时，能接的端口亮绿、接不上的标红；
接错会告诉你「`[String]` 不是 `String`」。一个输入只接一条线，重新拖会替换；从输入端起拖可以把线摘下来重接。
绕成环会被拒。

**看类型。** 每个端口上写的就是它的类型，长类型悬停看全文。节点标题悬停显示来源（`Opl.Kernel.findDef`）。
没有 `Show` 实例的值（`Global`、`ProofState`）显示成 `⟨ProofState⟩`，仍可继续往下接。

## 为什么是「即时」

服务端起一个**常驻 GHCi**：启动时 `:load` 一次，全部模块留在内存里（约 1.4 秒）。
之后画布上任何改动，只对变了的节点重发一条 `let` 绑定——不重新编译模块、不链接、不重启进程。

状态栏右边会写清楚这次发生了什么：

```
算完 · 43ms            本次重算 9 个 · 沿用 8 个
```

改一个战术名，17 个节点里只有下游 9 个重算；不动就 0 个，0ms。
图的结构相同、字面量相同，连 `let` 都不发（按签名哈希命中缓存）。

## 两个示例

顶栏「示例」里有两张图，都是真的：

**证明：开题 → intro n**（17 节点）
`命题文本 → goalOf → PTerm`、`预置初始 → Ob` → `startProof` → 拆包拿到 `ProofState`；
另一路 `战术文本 → tactOf → Tact` → `stepProof` → `stepState` → `proofFrontier → goalLines`。
最右边的节点写着 `n : N ⊢ Eq N (add n 0) n`——把战术文本改成 `intro m`，它会变成 `m : N ⊢ …`；
改成别的命题，`intro` 会当场报「目标不是函数类型」。

**编译：前置库自检**（12 节点）
`前置库源码 → parseProgram → runPreDecls → 拆包`：错误表是 `[]`，消息表 32 条，
再 `findDef "add"` + `pretty` 拿到 `forall (_ : Nat), forall (_ : Nat), Nat`。

## 元件从哪来

`palette.py` 里是一张手工表：每一项指向 `rt/BoardRt.hs` 里的一个别名，例如

```haskell
k_findDef = Ke.findDef          -- Opl.Kernel.findDef
e_startProof = El.startProof    -- Opl.Elaborate.startProof
```

**端口类型不写死**：引擎启动后对每个别名发一次 `:t`，用 GHC 自己算出来的类型当端口。
所以 `palette.py` 里没有一行类型声明，界面也不会和源码漂移。`palette.py` 里写着 `rt=` 的项，
启动时若 `:t` 失败就会被报出来——元件表是自检的。

「适配」那一类是连线胶水（拆元组、取 `Either` 的右边、`Show` 成文本、从声明里抠出 `PTerm`），
界面里单独一个颜色，不冒充实翻译函数。

## 键盘

| 键 | 作用 |
|---|---|
| 右键 | 元件库 / 节点菜单 |
| 空格 | 元件库 |
| 拖动空白 | 平移；滚轮 | 缩放（端口不跟着缩，始终可点） |
| `F` | 缩放到全部 |
| `Delete` | 删除选中的节点或连线 |
| `Ctrl/⌘ + Z` | 撤销（`Shift` 重做） |
| `Esc` | 关掉浮层 |

## 换个工程

```
python server.py --root D:\path\to\project
```

要求：`ghc` 在 PATH 里，工程能被 `ghc -isrc` 直接编译（只依赖 boot 包，或已有包环境）。
换工程后要改 `rt/BoardRt.hs` 的 import 和别名，再改 `palette.py` 的 `rt=`——这是「打包好的函数」的边界：
白板只认你显式接进来的函数。

## 文件

```
hask_nodes/
  server.py           HTTP + 元件表 + 图求值 + 图存取
  engine.py           常驻 GHCi：:t 取类型、按签名哈希增量重绑
  palette.py          元件表与两个示例图
  rt/BoardRt.hs       工程函数的别名 + 连线胶水（:load 的就是它）
  static/             无依赖前端：index.html / board.css / app.js
  data/graph.json     自动保存的画布
  tools/cdp.py        最小 CDP 客户端
  tools/nodetest.py   交互自检：真鼠标事件跑一遍取元件、连线、改字、撤销
```

## 边界

- **类型必须对得上**才让接：只做结构比较（同构造子、列表元素、元组逐位、类型变量通配）。
  不做类型推断，不会替你补 `fromIntegral`。
- 一个输入一条线，没有「多路合并」；要合并就显式加一个节点。
- 节点图是纯表达式，没有状态机语义：`stepProof` 这种「有状态」的函数靠把新 `Ob` 传下去模拟，
  不会自动回滚。
- 常驻 GHCi 意味着**内存里有一份解释执行的工程**；改了 `.hs` 要点顶栏引擎状态重启引擎。
- 服务只绑 `127.0.0.1`，没有鉴权。
