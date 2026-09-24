# FrontierPlan

**Plan まではAstraが決め、実行はMainが回す。**

Codex向けの明示起動専用Pluginです。[axiom_for_herdr](https://github.com/phni3j9a/axiom_for_herdr)
の進め方（Mainが統合・レビュー判定・完了判断を持ち、Lunaが実装し、独立したSolがレビューする）を
土台に、実装前の調査・設計・Plan作成だけをAstraに一任します。herdr版ではMainにDevinなどの
既存エージェントも使えます。子エージェントはCodexで起動します。

## 流れ

| フェーズ | 判断する人 | Mainの役割 |
|---|---|---|
| 調査〜Plan確定 | **Astra**。Lunaへの調査依頼とユーザーへの質問もAstraが決める | 判断せずに中継する（Astraの文面はそのまま表示、ユーザーの返事はそのままAstraへ） |
| 実装〜レビュー | **Main**（axiom_for_herdrと同じ） | 分割・割当・統合・指摘の採否。担当Workerはレビューサイクルの最後まで残す |
| 詰まったとき | MainがAstraに相談し、採否はMainが決める | 相談の材料を用意する |
| 最終確認 | **Astraが1回だけ**AC表・指摘・Planとのずれを返す | 指摘をReviewerの指摘と同じく判定し、完了報告を書く |

ユーザーに返すのは、Astraの質問やPlanの提示、完了報告、範囲やコストが変わる分岐
（推奨案つきの選択肢）の3つだけです。レビューの回数や経過時間では返しません。

Astraは、解釈によってコストが大きく変わる場合、Issueにない受入条件を足す場合、
新しい設計や重い検証が必要な場合に、Planの段階でユーザーに尋ねます。Planは
IssueのACを基準にし、より単純な代替案と2段の検証（反復中は絞った確認、最後に1回だけフル実行）
を書き、内部実装の細部は書きません。詳しくは [Astraの規約](plugins/frontierplan/core/astra.md)。

v0.1ではAstraが最終受入の門番で、ユーザーへ戻る経路もありませんでした。実案件で
作業が収束しなかったため、v0.2でこの形に作り直しました（[Issue #11](https://github.com/phni3j9a/frontierplan/issues/11)）。
v0.1で作ったrunはv0.2のhelperでは続けられません。v0.1のまま終えてください。

## 2つの入口

| SKILL | 実行方式 |
|---|---|
| `astraplan-herdr` | herdr上の見える別ペイン |
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
| Main | 起動済みセッションを継承 | 起動元を継承 | Plan前は中継、実行中は分割・割当・統合・レビュー判定・完了報告 |
| Researcher | `gpt-6-luna` | `max` + fast | Astraの依頼による読み取り専用の調査 |
| Worker | `gpt-6-luna` | `max` + fast | 実装・テスト・修正・監視 |
| Design | `gpt-6-sol` | `max` | 任意の実装フェーズUI担当 |
| Reviewer | `gpt-6-sol` | `xhigh` | 独立レビュー。同じセッションで回数上限なく再レビュー |

`profiles/director/astra.toml` と `profiles/*.toml` で役割別に管理します。profilesは
FrontierPlan内部の設定で、Codexのカスタムエージェント登録ではありません。Mainのprofileは
`inherit_session = true` のみで、モデル・effort・tierを指定しません。
subagent版では子が孫を起動できない（`agents.max_depth` 既定1）ため、Astraの調査依頼は
両backendともMainの中継で起動します。

## インストール

必要条件: **Python 3.11+**、対応するCodexとモデルへのアクセス（Gitは最終確認の材料にHEADを記録するためだけに使います）。
herdr版は同一ホストのherdrが必要です。subagent版はCodex上でモデル/effort指定、同一セッション
継続、待機、終了のnativeツールが必要です。こちらの会話のコネクタが子へ自動移植される
わけではありません。Astraが必要な調査ツールを使えるかも確認してください。

herdr版のMainは、検証済みの現在ペインからエージェント種別・セッションIDを取得し、
terminal IDと組み合わせて識別します。取得できないホストでは、独立に確認した実際の識別情報を
`FRONTIERPLAN_MAIN_AGENT` と `FRONTIERPLAN_MAIN_SESSION_ID` で明示指定します。
明示指定は初期化だけでなく、その後の両helperへの呼び出しにも必要です。
詳しくは [herdr手順](plugins/frontierplan/backends/herdr.md) を参照してください。
非CodexホストではSKILLと参照先の規約を明示的に読み込み、同じherdrホスト上のhelperを
実行できる必要があります。Devinでは `devin plugins install` がAgent Plugins manifestを
持つGitHubリポジトリ・git URL・ローカルフォルダを受け付け、両SKILLを
`/frontierplan:astraplan-herdr` / `/frontierplan:astraplan-subagent` として公開します。
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

配布物は `python3 tools/package_release.py` で生成します。単体Plugin ZIPは中に
`plugin.json`、互換用`.codex-plugin/plugin.json`、2 SKILL、共通Core/profiles/scriptsを含みます。
ZIPを展開しても、別のaxiomリポジトリを参照しません。

## 実行の境界

- Plan確定前は、AstraとAstraが依頼したResearcher以外は起動しません。Mainは調査も要約もしません。
- 実装許可はAstraが記録します（許可にあたるユーザー発言の番号）。記録がなければ `start` できません。
- Plan作成中にユーザーが書き込んだら、その発言をAstraへ渡すまで古い判断は採用されません。
- 最終確認はPlanごとに1回です。修正はAstraに戻さず、担当Workerと同じReviewerで確認します。
- Worker/Design/Reviewerはレビューサイクルが終わったら閉じます。Astraは`finish`まで残します。
  未解決のブロッカーを持つ参加者は、全体の終了まで閉じません。
- Mainの実行継続中は最大5分を目安に未回収結果をまとめて照合します。herdrの`check`は通知履歴に
  依存せず状態を確認し、`wait`は既定・最大300秒です。native版の`status`には`uncollected`一覧があります。
  バックグラウンドwaitだけ残してMainのターンを終えても自動再開は保証されません。

herdr版の配置はMainが左40%、Astraが右60%。ResearcherやWorkerが入ると右側をAstra上40%・
実行領域下60%へ分け、以降は実行領域内で左右に分割します。手動リサイズを維持し、役割の領域や
端末の識別が崩れた場合は操作を停止します。

herdr操作とnative tool呼び出しは別のbackendです。native版のPython helperは
モデルを起動するランタイムではなく、Mainが実際のnativeツールを呼び出すための
packet/receipt管理です。

## 検証と制限

```
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 tools/package_release.py
```

GitHub Actionsにも同じ検証を登録しています。詳細は [検証手順](docs/validation.md)。
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
