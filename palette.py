"""元件库：白板上可以右键取用的函数。

全部来自本工程「已导出」的函数，rt 是 BoardRt 里对应的别名；
端口类型不在这里写死——引擎启动后逐个 :t，用 GHC 自己算的类型。
最后一类「适配」是连线胶水，界面上单独标色，不冒充实翻译函数。
"""

CATEGORIES = [
    ("input", "输入", "#c0fe04"),
    ("parse", "解析", "#a9d6ff"),
    ("elab", "精化", "#d6b4ff"),
    ("kernel", "内核", "#ffd300"),
    ("eval", "求值", "#7ee0c0"),
    ("print", "打印", "#9aa397"),
    ("math", "数学", "#ff8d75"),
    ("syntax", "语法", "#8fb8ff"),
    ("driver", "驱动", "#b0e070"),
    ("json", "JSON", "#c9c9c9"),
    ("adapt", "适配", "#ff9f43"),
]

# kind: fn（对 BoardRt 里的别名求类型）| value（前端输入的字面量）
COMPS = [
    # ---------------------------------------------------------------- 输入 --
    dict(id="v_text", kind="value", cat="input", label="文本", vtype="String", editor="text",
         desc="一段字符串。给解析器、命题、战术都用它。", sample='def two : N := Succ (Succ Zero)'),
    dict(id="v_int", kind="value", cat="input", label="整数", vtype="Int", editor="int", sample="0"),
    dict(id="d_preludeGlobal", rt="d_preludeGlobal", cat="input", label="预置全局", desc="Driver.preludeGlobal"),
    dict(id="d_preludeInitial", rt="d_preludeInitial", cat="input", label="预置初始", desc="已装好前置库的 Ob，开题用它"),
    dict(id="k_emptyGlobal", rt="k_emptyGlobal", cat="input", label="空全局", desc="Kernel.emptyGlobal"),
    dict(id="v_emptyEnv", rt="v_emptyEnv", cat="input", label="空环境", desc="Eval.emptyEnv"),
    dict(id="l_preludeSource", rt="l_preludeSource", cat="input", label="前置库源码", desc="Prelude.preludeSource，44 条声明"),

    # ---------------------------------------------------------------- 解析 --
    dict(id="p_parseProgram", rt="p_parseProgram", cat="parse", label="解析源码",
         desc="Parser.parseProgram：.opl 文本 → [PreDecl]，错误在 Either 左边"),
    dict(id="declNames", rt="declNames", cat="adapt", label="声明名表",
         desc="直接给你源码里定义的每一行名字"),

    # ---------------------------------------------------------------- 精化 --
    dict(id="e_runPreDecls", rt="e_runPreDecls", cat="elab", label="检查声明",
         desc="Elaborate.runPreDecls：全局 + 声明表 → (新全局, 输出, 错误)"),
    dict(id="e_runPreDeclsWith", rt="e_runPreDeclsWith", cat="elab", label="检查声明·带提示",
         desc="runPreDeclsWith：多一个提示表参数，auto 会先试这些引理"),
    dict(id="e_runPreDeclsFull", rt="e_runPreDeclsFull", cat="elab", label="检查声明·完整",
         desc="runPreDeclsFull：返回 Ob，可继续开题"),
    dict(id="e_resolveClosed", rt="e_resolveClosed", cat="elab", label="消解项",
         desc="resolveClosed：表面项 → 内核项，顺手查名字"),
    dict(id="e_startProof", rt="e_startProof", cat="elab", label="开题",
         desc="startProof：Ob + 命题 → (证明状态, 新 Ob)"),
    dict(id="e_stepProof", rt="e_stepProof", cat="elab", label="推进一步",
         desc="stepProof：Ob + 状态 + 一条战术 → 新状态"),
    dict(id="e_proofFrontier", rt="e_proofFrontier", cat="elab", label="当前目标",
         desc="proofFrontier：还没关掉的子目标"),
    dict(id="e_proofGoal", rt="e_proofGoal", cat="elab", label="目标项",
         desc="proofGoal：当前待证的类型（内核项）"),

    # ---------------------------------------------------------------- 内核 --
    dict(id="k_findDef", rt="k_findDef", cat="kernel", label="查定义类型",
         desc="findDef：全局 + 名字 → 类型"),
    dict(id="k_findDefEnv", rt="k_findDefEnv", cat="kernel", label="查定义体",
         desc="findDefEnv：全局 + 名字 → 定义体"),
    dict(id="k_checkIn", rt="k_checkIn", cat="kernel", label="检查项对类型",
         desc="checkIn：全局 + 语境 + 项 + 类型，内核唯一裁判"),
    dict(id="k_inferIn", rt="k_inferIn", cat="kernel", label="推断类型",
         desc="inferIn：全局 + 语境 + 项 → 类型"),
    dict(id="k_ensureTypeIn", rt="k_ensureTypeIn", cat="kernel", label="确认是类型",
         desc="ensureTypeIn：判断一项是否落在某个宇宙里"),
    dict(id="k_runNormalize", rt="k_runNormalize", cat="kernel", label="规范化",
         desc="runNormalize：全局 + 语境 + 项 → 范式"),
    dict(id="k_isPropableT", rt="k_isPropableT", cat="kernel", label="可作命题?",
         desc="isPropableT：是不是一个能拿来证的命题"),
    dict(id="k_assumptions", rt="k_assumptions", cat="kernel", label="语境假设",
         desc="assumptions：语境 → 带编号的假设表"),
    dict(id="k_primTypeScheme", rt="k_primTypeScheme", cat="kernel", label="原语类型",
         desc="primTypeScheme：层级 + 原语名 → 类型"),
    dict(id="k_primNames", rt="k_primNames", cat="kernel", label="原语名表",
         desc="Kernel.primNames"),

    # ---------------------------------------------------------------- 求值 --
    dict(id="v_eval", rt="v_eval", cat="eval", label="求值",
         desc="eval：环境 + 项 → 值"),
    dict(id="v_evalAt", rt="v_evalAt", cat="eval", label="求值·带层",
         desc="evalAt：多一个层级参数"),
    dict(id="v_quote", rt="v_quote", cat="eval", label="回引",
         desc="quote：值 + 层 → 项，求值之后想再打印时用"),
    dict(id="v_vfst", rt="v_vfst", cat="eval", label="取第一项",
         desc="vfst：依赖对的左投影"),
    dict(id="v_vsnd", rt="v_vsnd", cat="eval", label="取第二项",
         desc="vsnd：依赖对的右投影"),

    # ---------------------------------------------------------------- 打印 --
    dict(id="r_pretty", rt="r_pretty", cat="print", label="打印项",
         desc="pretty：内核项 → 带名字的可读文本"),
    dict(id="r_prettyNamed", rt="r_prettyNamed", cat="print", label="打印项·带名",
         desc="prettyNamed：先给一串显示名"),

    # ---------------------------------------------------------------- 数学 --
    dict(id="m_findCounterexample", rt="m_findCounterexample", cat="math", label="找反例",
         desc="findCounterexample：全局 + 深度 + 命题，有限搜一遍"),
    dict(id="m_searchEnv", rt="m_searchEnv", cat="math", label="检索引理",
         desc="searchEnv：在假设表里按词找，返回命中"),

    # ---------------------------------------------------------------- 语法 --
    dict(id="s_shift", rt="s_shift", cat="syntax", label="移位",
         desc="shift：de Bruijn 索引整体平移"),
    dict(id="s_substTop", rt="s_substTop", cat="syntax", label="顶层代换",
         desc="substTop：把一个项代进最内层绑定"),
    dict(id="s_termEq", rt="s_termEq", cat="syntax", label="项相等?",
         desc="termEq：结构比较，不做归约"),
    dict(id="s_binderName", rt="s_binderName", cat="syntax", label="绑定显示名",
         desc="binderName：给绑定位置挑一个不撞车的名字"),

    # ---------------------------------------------------------------- 驱动 --
    dict(id="d_preludeMessages", rt="d_preludeMessages", cat="driver", label="前置库消息",
         desc="preludeMessages：装载前置库时记下的话"),

    # ---------------------------------------------------------------- JSON --
    dict(id="j_parseJson", rt="j_parseJson", cat="json", label="读 JSON",
         desc="parseJson：文本 → JVal"),
    dict(id="j_encodeJson", rt="j_encodeJson", cat="json", label="写 JSON",
         desc="encodeJson：JVal → 文本"),
    dict(id="j_jstr", rt="j_jstr", cat="json", label="JSON 字符串",
         desc="jstr：String → JVal"),

    # ---------------------------------------------------------------- 适配 --
    dict(id="t2_1", rt="t2_1", cat="adapt", label="二元组·1", desc="取第一项"),
    dict(id="t2_2", rt="t2_2", cat="adapt", label="二元组·2", desc="取第二项"),
    dict(id="t3_1", rt="t3_1", cat="adapt", label="三元组·1", desc="取第一项"),
    dict(id="t3_2", rt="t3_2", cat="adapt", label="三元组·2", desc="取第二项"),
    dict(id="t3_3", rt="t3_3", cat="adapt", label="三元组·3", desc="取第三项"),
    dict(id="t4_1", rt="t4_1", cat="adapt", label="四元组·1", desc="取第一项"),
    dict(id="t4_2", rt="t4_2", cat="adapt", label="四元组·2", desc="取第二项"),
    dict(id="t4_3", rt="t4_3", cat="adapt", label="四元组·3", desc="取第三项"),
    dict(id="t4_4", rt="t4_4", cat="adapt", label="四元组·4", desc="取第四项"),
    dict(id="fromOk", rt="fromOk", cat="adapt", label="取成功值",
         desc="Either String a → a；失败时把错误抛成异常，节点会标红"),
    dict(id="errText", rt="errText", cat="adapt", label="取错误文本",
         desc="Either String a → String；成功时是空串"),
    dict(id="fromMaybe", rt="fromMaybe", cat="adapt", label="取 Maybe 值",
         desc="Maybe a → a"),
    dict(id="maybeText", rt="maybeText", cat="adapt", label="Maybe 文本",
         desc="Maybe a → String，Nothing 显示成 Nothing"),
    dict(id="showIt", rt="showIt", cat="adapt", label="显示",
         desc="Show a => a → String"),
    dict(id="lenOf", rt="lenOf", cat="adapt", label="长度",
         desc="[a] → Int"),
    dict(id="stepState", rt="stepState", cat="adapt", label="步进后的状态",
         desc="StepResult → ProofState；StepDone 时说明已证完"),
    dict(id="stepTerm", rt="stepTerm", cat="adapt", label="证明项",
         desc="StepResult → Term；证完才有"),
    dict(id="goalOf", rt="goalOf", cat="adapt", label="命题",
         desc="从「def 名字 : 类型 := 体」里取出类型，得到 PTerm"),
    dict(id="tacticsOf", rt="tacticsOf", cat="adapt", label="战术表",
         desc="从「def 名字 : 类型 := 战术…」里取出 [Tact]"),
    dict(id="tactOf", rt="tactOf", cat="adapt", label="单条战术",
         desc="只取第一条战术，喂给 stepProof"),
    dict(id="goalLines", rt="goalLines", cat="adapt", label="目标行",
         desc="[GoalView] → [String]，把假设与目标排成可读的几行"),
]


def by_id():
    return {c["id"]: c for c in COMPS}


def categories():
    return [{"id": i, "label": l, "color": c} for i, l, c in CATEGORIES]


STARTER = {
    "name": "开题 → intro n",
    "nodes": [
        {"id": "g1", "comp": "v_text", "x": 40, "y": 40,
         "value": "def goal : forall (n : N), Eq N (add n 0) n := id"},
        {"id": "g2", "comp": "goalOf", "x": 300, "y": 60},
        {"id": "g3", "comp": "fromOk", "x": 560, "y": 70},
        {"id": "g4", "comp": "d_preludeInitial", "x": 300, "y": 330},
        {"id": "g5", "comp": "e_startProof", "x": 820, "y": 140},
        {"id": "g6", "comp": "fromOk", "x": 1080, "y": 150},
        {"id": "g7", "comp": "t2_1", "x": 1330, "y": 80},
        {"id": "g8", "comp": "t2_2", "x": 1330, "y": 300},
        {"id": "g9", "comp": "v_text", "x": 40, "y": 470,
         "value": "def t : N := begin\n  intro n\nend"},
        {"id": "g10", "comp": "tactOf", "x": 300, "y": 470},
        {"id": "g11", "comp": "fromOk", "x": 560, "y": 470},
        {"id": "g12", "comp": "e_stepProof", "x": 1580, "y": 190},
        {"id": "g13", "comp": "fromOk", "x": 1830, "y": 190},
        {"id": "g13b", "comp": "t2_2", "x": 2080, "y": 190},
        {"id": "g14", "comp": "stepState", "x": 2330, "y": 190},
        {"id": "g15", "comp": "e_proofFrontier", "x": 2580, "y": 190},
        {"id": "g16", "comp": "goalLines", "x": 2810, "y": 190},
    ],
    "edges": [
        {"from": "g1", "to": "g2", "toPort": 0},
        {"from": "g2", "to": "g3", "toPort": 0},
        {"from": "g4", "to": "g5", "toPort": 0},
        {"from": "g3", "to": "g5", "toPort": 1},
        {"from": "g5", "to": "g6", "toPort": 0},
        {"from": "g6", "to": "g7", "toPort": 0},
        {"from": "g6", "to": "g8", "toPort": 0},
        {"from": "g9", "to": "g10", "toPort": 0},
        {"from": "g10", "to": "g11", "toPort": 0},
        {"from": "g8", "to": "g12", "toPort": 0},
        {"from": "g7", "to": "g12", "toPort": 1},
        {"from": "g11", "to": "g12", "toPort": 2},
        {"from": "g12", "to": "g13", "toPort": 0},
        {"from": "g13", "to": "g13b", "toPort": 0},
        {"from": "g13b", "to": "g14", "toPort": 0},
        {"from": "g14", "to": "g15", "toPort": 0},
        {"from": "g15", "to": "g16", "toPort": 0},
    ],
}

PRELUDE = {
    "name": "前置库自检",
    "nodes": [
        {"id": "b1", "comp": "l_preludeSource", "x": 40, "y": 60},
        {"id": "b2", "comp": "p_parseProgram", "x": 300, "y": 70},
        {"id": "b3", "comp": "fromOk", "x": 540, "y": 80},
        {"id": "b4", "comp": "k_emptyGlobal", "x": 300, "y": 250},
        {"id": "b5", "comp": "e_runPreDecls", "x": 780, "y": 150},
        {"id": "b6", "comp": "t3_3", "x": 1020, "y": 80},
        {"id": "b7", "comp": "lenOf", "x": 1220, "y": 80},
        {"id": "b8", "comp": "t3_1", "x": 1020, "y": 240},
        {"id": "b9", "comp": "v_text", "x": 1020, "y": 380, "value": "add"},
        {"id": "b10", "comp": "k_findDef", "x": 1260, "y": 300},
        {"id": "b11", "comp": "fromMaybe", "x": 1480, "y": 300},
        {"id": "b12", "comp": "r_pretty", "x": 1680, "y": 300},
    ],
    "edges": [
        {"from": "b1", "to": "b2", "toPort": 0},
        {"from": "b2", "to": "b3", "toPort": 0},
        {"from": "b4", "to": "b5", "toPort": 0},
        {"from": "b3", "to": "b5", "toPort": 1},
        {"from": "b5", "to": "b6", "toPort": 0},
        {"from": "b6", "to": "b7", "toPort": 0},
        {"from": "b5", "to": "b8", "toPort": 0},
        {"from": "b8", "to": "b10", "toPort": 0},
        {"from": "b9", "to": "b10", "toPort": 1},
        {"from": "b10", "to": "b11", "toPort": 0},
        {"from": "b11", "to": "b12", "toPort": 0},
    ],
}

SAMPLES = [
    {"id": "proof", "label": "证明：开题 → intro n", "graph": STARTER},
    {"id": "prelude", "label": "编译：前置库自检", "graph": PRELUDE},
]
