-- 白板运行时。
--
-- 每条绑定都只是「工程已导出函数」的一个别名（q_/k_/e_/p_/... 前缀区分模块），
-- 外加最后一节连线用的适配函数。白板的端口类型不靠猜：引擎启动时对每个名字
-- 发一次 :t，把 GHC 自己算出来的类型当作端口类型。
module BoardRt where

import qualified Opl.Parser as Ps
import qualified Opl.Elaborate as El
import qualified Opl.Kernel as Ke
import qualified Opl.Pretty as Pr
import qualified Opl.Eval as Ev
import qualified Opl.MathTools as Mt
import qualified Opl.Syntax as Sy
import qualified Opl.Driver as Dr
import qualified Opl.Prelude as Pl
import qualified Opl.Json as Js
import Opl.Parser (PTerm, Tact, PreDecl (..), PreBody (..))
import Opl.Elaborate (GoalView (..), ProofState, StepResult (..))
import Opl.Syntax (Term, Name)

-- ---------------------------------------------------------------- 解析 --
p_parseProgram = Ps.parseProgram

-- ---------------------------------------------------------------- 精化 --
e_runPreDecls = El.runPreDecls
e_runPreDeclsWith = El.runPreDeclsWith
e_runPreDeclsFull = El.runPreDeclsFull
e_resolveClosed = El.resolveClosed
e_startProof = El.startProof
e_stepProof = El.stepProof
e_finishProof = El.finishProof
e_proofFrontier = El.proofFrontier
e_proofGoal = El.proofGoal

-- ---------------------------------------------------------------- 内核 --
k_emptyGlobal = Ke.emptyGlobal
k_findDef = Ke.findDef
k_findDefEnv = Ke.findDefEnv
k_checkDef = Ke.checkDef
k_inferIn = Ke.inferIn
k_checkIn = Ke.checkIn
k_ensureTypeIn = Ke.ensureTypeIn
k_runNormalize = Ke.runNormalize
k_isPropableT = Ke.isPropableT
k_assumptions = Ke.assumptions
k_primTypeScheme = Ke.primTypeScheme
k_primNames = Ke.primNames

-- ---------------------------------------------------------------- 求值 --
v_emptyEnv = Ev.emptyEnv
v_eval = Ev.eval
v_evalAt = Ev.evalAt
v_quote = Ev.quote
v_vfst = Ev.vfst
v_vsnd = Ev.vsnd
v_primNames = Ev.primNames

-- ---------------------------------------------------------------- 打印 --
r_pretty = Pr.pretty
r_prettyNamed = Pr.prettyNamed

-- ---------------------------------------------------------------- 数学 --
m_findCounterexample = Mt.findCounterexample
m_searchEnv = Mt.searchEnv

-- ---------------------------------------------------------------- 语法 --
s_shift = Sy.shift
s_substTop = Sy.substTop
s_termEq = Sy.termEq
s_binderName = Sy.binderName

-- ---------------------------------------------------------------- 驱动 --
d_preludeGlobal = Dr.preludeGlobal
d_preludeInitial = Dr.preludeInitial
d_preludeMessages = Dr.preludeMessages

-- ---------------------------------------------------------------- 前置 --
l_preludeSource = Pl.preludeSource

-- ---------------------------------------------------------------- JSON --
j_parseJson = Js.parseJson
j_encodeJson = Js.encodeJson
j_jstr = Js.jstr

-- ================================================================ 适配 ==
-- 下面这些不是工程里的函数，是连线用的胶水；界面里单独一类，标为「适配」。

t2_1 (a, _) = a
t2_2 (_, b) = b
t3_1 (a, _, _) = a
t3_2 (_, b, _) = b
t3_3 (_, _, c) = c
t4_1 (a, _, _, _) = a
t4_2 (_, b, _, _) = b
t4_3 (_, _, c, _) = c
t4_4 (_, _, _, d) = d

fromOk :: Either String a -> a
fromOk (Right a) = a
fromOk (Left e) = error ("上游失败：" ++ e)

errText :: Either String a -> String
errText (Left e) = e
errText (Right _) = ""

fromMaybe :: Maybe a -> a
fromMaybe (Just a) = a
fromMaybe Nothing = error "Nothing"

maybeText :: Show a => Maybe a -> String
maybeText (Just a) = show a
maybeText Nothing = "Nothing"

showIt :: Show a => a -> String
showIt = show

lenOf :: [a] -> Int
lenOf = length

-- 工程没有导出「字符串 → PTerm」，但 PreDecl 的构造子可见：
-- 从一条声明里把类型/策略取出来，交给 startProof / stepProof。
goalOf :: String -> Either String PTerm
goalOf src = case Ps.parseProgram src of
  Left e -> Left ("解析失败：" ++ e)
  Right ds ->
    case [t | PDef _ (Just t) _ <- ds] ++ [t | PAxiom _ t <- ds] ++ [t | PProp _ t _ <- ds] of
      (t : _) -> Right t
      [] -> Left "没找到带类型标注的声明（写法：def 名字 : 类型 := 体）"

tacticsOf :: String -> Either String [Tact]
tacticsOf src = case Ps.parseProgram src of
  Left e -> Left ("解析失败：" ++ e)
  Right ds ->
    case [ts | PDef _ _ (TacticBody ts) <- ds] ++ [ts | PProp _ _ (TacticBody ts) <- ds] of
      (ts : _) -> Right ts
      [] -> Left "没找到策略脚本（写法：def 名字 : 类型 := 战术…）"

tactOf :: String -> Either String Tact
tactOf src = case tacticsOf src of
  Left e -> Left e
  Right (t : _) -> Right t
  Right [] -> Left "策略脚本是空的"

stepState :: StepResult -> ProofState
stepState (StepOpen ps) = ps
stepState (StepDone _) = error "这条战术已经关掉全部目标；用 stepTerm 取证明项"

stepTerm :: StepResult -> Term
stepTerm (StepDone t) = t
stepTerm (StepOpen _) = error "还没证完，当前不是证明项"

goalLines :: [GoalView] -> [String]
goalLines = map (\g -> unwords (map (\(n, t) -> n ++ " : " ++ t) (gvHyps g)) ++ " ⊢ " ++ gvTarget g)

declNames :: String -> Either String [String]
declNames src = map nameOf . filter ((/= "") . nameOf) <$> Ps.parseProgram src
  where
    nameOf (PDef n _ _) = n
    nameOf (PAxiom n _) = n
    nameOf (PProp n _ _) = n
    nameOf _ = ""
