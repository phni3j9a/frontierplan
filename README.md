# FrontierPlan

**AstraがPlanを決め、Worker–Reviewerがタスクを仕上げ、Mainが統合・完了する。**

Codex向けの明示起動専用Pluginです（Claude Code・Devinにも導入できます）。[axiom_for_herdr](https://github.com/phni3j9a/axiom_for_herdr)
を土台に、実装前の調査・設計・Plan作成をAstraに一任します。実装タスクはWorkerとReviewerが
直接やり取りして完了させ、Mainは通常レビューの中継・採否判断から外れます。herdr版ではMainにDevinなどの
既存エージェントやClaude Codeも使えます。子エージェントはCodexで起動します。

## 流れ

| フェーズ | 判断する人 | Mainの役割 |
|---|---|---|
| 調査〜Plan確定 | **Astra**。Lunaへの調査依頼とユーザーへの質問もAstraが決める | 判断せずに中継する（Astraの文面はそのまま表示、ユーザーの返事はそのままAstraへ） |
| 実装〜レビュー | **Worker–Reviewerペア**。担当タスクの具体的な不適合だけを確認 | 短いタスクを割当て、PASS済み成果物を回収・統合する |
| 詰まったとき | **Main**。Plan判断だけAstraに相談する | 要求の曖昧さ・環境・同じ原因で進展しない状態を解消する |
| 最終確認 | **Astraが1回だけ**AC表・具体的な問題・Planとのずれを返す（否認権なし） | 完了・修正・再計画を決める。具体的な修正は新しいペアへ渡す |

ユーザーに返すのは、Astraの質問やPlanの提示、完了報告、範囲やコストが変わる分岐
（推奨案つきの選択肢）の3つだけです。レビューの回数や経過時間では返しません。

Astraは、解釈によってコストが大きく変わる場合、Issueにない受入条件を足す場合、
新しい設計や重い検証が必要な場合に、Planの段階でユーザーに尋ねます。Planは
IssueのACを基準にし、より単純な代替案と2段の検証（反復中は絞った確認、最後に1回だけフル実行）
を書き、内部実装の細部は書きません。詳しくは [Astraの規約](plugins/frontierplan/core/astra.md)。

v0.1ではAstraが最終受入の門番で、ユーザーへ戻る経路もありませんでした。実案件で
作業が収束しなかったため、v0.2でこの形に作り直しました（[Issue #11](https://github.com/phni3j9a/frontierplan/issues/11)）。
v0.1で作ったrunはv0.2のhelperでは続けられません。v0.1のまま終えてください。

v0.4では[Issue #17](https://github.com/phni3j9a/frontierplan/issues/17)のペア方式へ移行します。
短いTask Contractに対する検証・最小修正を基本とし、将来拡張や好みをレビューの追加要件にしません。
直接通信だけで収束改善が実証されたとは扱いません。旧版で実行中の未ペアrunは旧版で終え、
途中から暗黙に移行させないでください。

## 3つの入口

| SKILL | 実行方式 |
|---|---|
| `astraplan-herdr` | herdr上の見える別ペイン |
| `astraplan-herdr-swe2` | herdr版と同じ。ResearcherとWorkerだけDevin CLIの`swe-2-max`で起動 |
| `astraplan-subagent` | Codexのnative subagentツール |

```
$frontierplan:astraplan-herdr
この機能を調査・設計して実装まで進めてください。
```

各SKILLは `allow_implicit_invocation: false`。呼び出した作業とその続きだけに適用し、
通常の小さなタスクでは自動起動しません。Axiomとは別Pluginで、同じ作業で混用しません。

## 役割とモデル

| 役割 | モデル | effort | 責務 |
|---|---|---|---|
| Director (Astra) | `gpt-6-astra` | `xhigh` | 調査・設計・ユーザーへの質問・Plan・実装許可の記録、実行中の相談、1回の最終確認 |
| Main | 起動済みセッションを継承 | 起動元を継承 | Plan前は中継、実行中はペア割当・成果物統合・行き詰まりの解消・完了報告 |
| Researcher | `gpt-6-luna` | `max` + fast | Astraの依頼による読み取り専用の調査 |
| Worker | `gpt-6-luna` | `max` + fast | 実装・テスト・修正・監視 |
| Design | `gpt-6-sol` | `max` | 任意の実装フェーズUI担当 |
| Reviewer | `gpt-6-sol` | `xhigh` | 担当Task Contractを検証。具体的な指摘をWorkerへ直接返し、現候補にPASSを出す |

`astraplan-herdr-swe2` では、Luna枠のResearcherとWorkerを Devin CLI の `swe-2-max`
（effortはモデル名に含まれ、fast枠はありません）に置き換えます。Astra・Design・Reviewerは
上の表のままです。詳しくは[SWE-2版](#swe-2版astraplan-herdr-swe2)を参照してください。

`profiles/director/astra.toml` と `profiles/*.toml` で役割別に管理します（swe2版の2役割は
`profiles/swe2/*.toml`）。profilesは
FrontierPlan内部の設定で、Codexのカスタムエージェント登録ではありません。Mainのprofileは
`inherit_session = true` のみで、モデル・effort・tierを指定しません。
subagent版では子が孫を起動できない（`agents.max_depth` 既定1）ため、Astraの調査依頼は
両backendともMainの中継で起動します。

## インストール

必要条件: **Python 3.11+**、対応するCodexとモデルへのアクセスおよび**Git worktree**（未コミット変更も含む候補の識別に必要）。
herdr版は同一ホストのherdrが必要です。subagent版はCodex上でモデル/effort指定、同一セッション
継続、待機、終了に加え、**子同士が同じセッションを再開できるnativeツール**が必要です。
通知や親からの継続しかできないホストはペア方式に未対応です。Main中継で取り繕いません。こちらの会話のコネクタが子へ自動移植される
わけではありません。Astraが必要な調査ツールを使えるかも確認してください。

herdr版のMainは、検証済みの現在ペインからエージェント種別・セッションIDを取得し、
terminal IDと組み合わせて識別します。取得できないホストでは、独立に確認した実際の識別情報を
`FRONTIERPLAN_MAIN_AGENT` と `FRONTIERPLAN_MAIN_SESSION_ID` で明示指定します。
明示指定は初期化だけでなく、その後の両helperへの呼び出しにも必要です。
詳しくは [herdr手順](plugins/frontierplan/backends/herdr.md) を参照してください。
非CodexホストではSKILLと参照先の規約を明示的に読み込み、同じherdrホスト上のhelperを
実行できる必要があります。Devinでは `devin plugins install` がAgent Plugins manifestを
持つGitHubリポジトリ・git URL・ローカルフォルダを受け付け、両SKILLを
`/frontierplan:astraplan-herdr` / `/frontierplan:astraplan-herdr-swe2` /
`/frontierplan:astraplan-subagent` として公開します。
SKILL frontmatterの `triggers: [user]` はDevin側でも明示起動を維持する宣言で、
Codexの `allow_implicit_invocation: false` と同じ方針です。subagent backendは
Codex nativeツールが必要なためDevinでは動作せず、DevinをMainにする場合はherdr版を
使います。対象ホストでの実機互換性は別途検証してください。

SKILLはPlugin rootを自身の2階層上として解決します。Devinのスラッシュ起動のように
ホストがSKILL.mdのパスを渡さない場合、Mainはホストが導入・読み込んだPluginのコピーだけを
使い、ソースのclone・worktree・展開済みZIPなど検索で見つかった別のコピーでは代用しません。
一意に特定できなければ停止してユーザーに確認し、最初のhelper実行前に解決したrootを示します。
cloneを開発用に使う場合は、そのフォルダをホストへPluginとして導入してください。

Marketplace登録:
```
codex plugin marketplace add phni3j9a/frontierplan
```
その後、Plugin一覧から **FrontierPlan** を選んでインストールし、新しいセッションで
SKILLを明示指定します。CLIの `plugin add` が利用可能な環境では:
```
codex plugin add frontierplan@frontierplan-local
```
pluginsがfeature flagの環境では `codex --enable plugins ...` を使います。サブコマンドは
導入済みCLIの `codex plugin --help` を確認してください。ユーザー設定の自動変更はしません。
ソースをcloneして `codex plugin marketplace add /absolute/path/to/frontierplan` でも登録できます。

Claude Code（herdr版のMainとして使う場合）:
```
/plugin marketplace add phni3j9a/frontierplan
/plugin install frontierplan@frontierplan
```
CLIでは `claude plugin marketplace add phni3j9a/frontierplan` と
`claude plugin install frontierplan@frontierplan` です。導入後の新しいセッションで
`/frontierplan:astraplan-herdr`（または `-swe2`）を明示指定します。各SKILLは `disable-model-invocation: true`
を持つため、Claude Codeが通常の依頼で自動起動することはありません。Claude Codeは
herdr上で `agent: "claude"` とセッションIDを報告するため、Mainの識別は現在ペインから
自動で行われます（`FRONTIERPLAN_MAIN_*` の明示指定は不要です）。`astraplan-subagent` は
Codex nativeツールが必要なためClaude Codeでは使えず、起動しても停止・報告します。
Claude Code用のmanifestは `.claude-plugin/marketplace.json`（リポジトリ直下）と
`plugins/frontierplan/.claude-plugin/plugin.json` で、`claude plugin validate --strict` で確認できます。

配布物は `python3 tools/package_release.py` で生成します。単体Plugin ZIPは中に
`plugin.json`、互換用`.codex-plugin/plugin.json`と`.claude-plugin/plugin.json`、3 SKILL、共通Core/profiles/scriptsを含みます。
ZIPを展開しても、別のaxiomリポジトリを参照しません。

## SWE-2版（astraplan-herdr-swe2）

```
$frontierplan:astraplan-herdr-swe2
この機能を調査・設計して実装まで進めてください。
```

Mainは `herdr.py init --variant swe2` でrunを作り、以降は通常のherdr版と同じ手順です。
variantはrunに記録され、途中で変更やフォールバックはしません（subagent backendでは使えません）。

- 必要条件: herdr版の条件に加えて Devin CLI（SWE-2を使えるアカウント）。
- 起動: `devin --permission-mode dangerous --model swe-2-max --export <task>/devin-session.json`。
  Devinはユーザー自身の設定をそのまま読み込みます（herdrのDevin連携フックも含む）。
  FrontierPlanは設定ファイルやルールを追加しません。
- 実効モデル: `collect` がDevin自身のsession exportから記録された `observed_models` を
  `session_evidence` として返します。起動引数や子の自己申告では確認扱いにしません。

**権限はCodex版より広くなります（意図した選択です）。** Devinのbypassモード（`dangerous`）は
OS sandboxなしで全ツールを自動承認します。ユーザーが書ける場所ならどこでもファイルを編集・
シェル実行でき、Web取得・ネットワーク・Devinに設定したMCPツールも確認なしで使えます。
Researcherが読むだけであること、公開やcommitをしないことは役割の指示で、強制ではありません。
この信頼を置ける環境でだけ使ってください。

Devinの `--sandbox` モードを使わない理由: sandboxではファイル編集ツールが許可ルールを置いても
確認待ちになり、herdrのペインが止まります。編集ツールを拒否してシェルだけで編集させる方法も
試しましたが、止まる経路が残り、大きな編集の品質も落ちやすいため採用しませんでした
（[検証手順](docs/validation.md)）。

その他の違い:
- effortはモデル名に含まれ（`swe-2-max`）、fast枠はありません。
- workspaceのDevinプロジェクト設定（`.devin/config*.json` やルール・フック）は通常どおり子にも効きます。
- SWE-2の利用はDevinのプランと利用枠に従います。

実herdrでの確認結果は[検証手順](docs/validation.md)を参照してください。

## 実行の境界

- Plan確定前は、AstraとAstraが依頼したResearcher以外は起動しません。Mainは調査も要約もしません。
- 実装許可はAstraが記録します（許可にあたるユーザー発言の番号）。記録がなければ `start` できません。
- Plan作成中にユーザーが書き込んだら、その発言をAstraへ渡すまで古い判断は採用されません。
- 最終確認はPlanごとに1回です。後続の具体的な修正は新しいペアで確認し、Astraには戻しません。
- 同じWorker/DesignとReviewerをタスク完了まで維持します。最新候補のPASSとMainの回収後に
  **両ペインを閉じます**。Astraは`finish`まで残します。未解決ブロッカーは、解消または証跡を
  引き継いだ担当変更まで残します。終了のために未解決をPASS扱いにはしません。
- PASSは契約・候補の実ファイル・Reviewer・最新報告に結び付けます。Mainの回収前に内容が
  変われば古いPASSは使えません。回収後の変更は別タスクでレビューし、古い成果物を再監査し続けません。
- Mainの実行継続中は最大5分を目安に未回収結果をまとめて照合します。herdrの`check`は通知履歴に
  依存せず状態を確認し、`wait`は既定・最大300秒です。native版の`status`には`uncollected`一覧があります。
  バックグラウンドwaitだけ残してMainのターンを終えても自動再開は保証されません。

swe2版のDevinの子は上の[SWE-2版](#swe-2版astraplan-herdr-swe2)の権限で動きます。

herdr版の配置はMainが左40%、Astraが右60%。ResearcherやWorkerが入ると右側をAstra上40%・
実行領域下60%へ分け、以降は実行領域内で左右に分割します。手動リサイズを維持し、役割の領域や
端末の識別が崩れた場合は操作を停止します。

herdr操作とnative tool呼び出しは別のbackendです。native版のPython helperは
モデルを起動するランタイムではなく、packet/receipt管理です。Mainは実際のnative起動・終了
ツールを使い、通常レビューの継続ツールは登録済みの子自身が呼び出します。

## ペアの操作

Plan開始後、Mainは短い契約を渡してペアを作成します。
```
python3 "$hd" pair-spawn --run "$run" --file "$contract" [--cwd "$worktree"]
```
子は生成されたpacketの`pairs.py begin/submit`を使い、候補・指摘・修正・PASSを直接交換します。
MainはPASSまたは行き詰まりだけを受け取り、PASSなら次を実行します。
```
python3 "$pp" collect --task "$worker"
python3 "$hd" pair-close --task "$worker"
```
`hd`と`pp`は導入済みPluginの`scripts/herdr.py`、`scripts/pairs.py`の絶対パスです。
並列作業は専用worktreeまたは重ならない`--scope`で分離します。候補のmanifestはファイルの
ハッシュでありソースの複製ではないため、レビューしたworktree・diff・証跡は統合まで保持します。
詳しくは[ペア手順](plugins/frontierplan/core/pairs.md)を参照してください。

## 検証と制限

```
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 tools/package_release.py
```

GitHub Actionsにも同じ検証を登録しています。詳細は [検証手順](docs/validation.md)。
**Issue #17の実Herdrペア往復はローカルCodexでの検証待ちです。nativeの実往復も未検証です。**
[ローカル検証の引継ぎ手順](docs/issue-17-validation.md)に、同一Worker修正→同一Reviewer PASS→
Main回収→両ペイン終了の確認項目と、残すべき証跡を記載しています。
自動テストはローカルの状態遷移と模擬herdrを検証するもので、実モデルのルーティング・課金・
Planの適切さ・実機UI・権限・nativeツール互換性の実証ではありません。実herdr（0.9.1）での
ペイン配置は合成エージェントのsmokeで確認済みです（[証跡](docs/evidence/issue-11-herdr-layout.json)）。

子の方針はworkspace-write + never。herdrは起動時に要求しますが、実効値は環境で
確認が必要です。native子は親の権限を継承し得るため、指示文だけで権限を制限したとは
扱いません。必要条件を満たせない場合は停止・報告し、勝手に権限拡大/モデル変更しません。

helperは協調的な手順チェックで、認証・sandbox・ユーザー同意の自動判定ではありません。
runは一時ディレクトリに保存します。永続成果物は必要に応じて通常のプロジェクトへ残してください。

[設計](docs/architecture.md) / [共通ルール](plugins/frontierplan/core/workflow.md) /
[Astra](plugins/frontierplan/core/astra.md) / [レビュー](plugins/frontierplan/core/review.md) /
[herdr手順](plugins/frontierplan/backends/herdr.md) /
[subagent手順](plugins/frontierplan/backends/subagent.md) /
[ライセンス・参考元](plugins/frontierplan/THIRD_PARTY_NOTICES.md)
