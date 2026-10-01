# FrontierPlan

**PlanまではAstraが決め、実行はMainが回す。**

v0.5.2は、役割分担と進め方を教える明示起動専用Pluginです。
独自ランタイム・台帳・JSON判断・受領証はありません。
Herdrでは公式CLIと同梱SKILL、native版ではホストの実ツールを直接使います。

[axiom_for_herdr](https://github.com/phni3j9a/axiom_for_herdr)の進め方を土台に、
実装前の調査・設計・PlanをAstraが担当します。実装開始後はMainが割当・統合・
レビュー判定を担当します。Reviewerは担当タスクの実装を検証し、最後にAstraが
成果物全体の目的達成を一度確認して、Mainが完了を判断します。
具体的な実装方法や報告形式は担当エージェントに任せます。

## 3つの入口

| SKILL | 実行方式 |
|---|---|
| `astraplan-herdr` | Herdr上の見える別ペイン。子はCodex |
| `astraplan-herdr-swe2` | 同じ配置で、ResearcherとWorkerだけDevin SWE-2 |
| `astraplan-subagent` | Codexのnative subagentツール |

```text
$frontierplan:astraplan-herdr
この機能を調査・設計して実装まで進めてください。
```

3入口とも明示起動です。通常の依頼で自動起動せず、呼び出した作業とその続きに適用します。
Mainは起動済みのホスト・モデル・設定を継承します。Herdr版ではClaude CodeやDevinも
Mainにできます。native版にはCodexの対応ツールが必要です。

## 進め方とモデル

Astraの調査依頼・質問・Planとユーザーの返事はMainがそのまま中継します。
実装の依頼があれば、その許可範囲でPlanから実行へ進み、形式上の再承認は求めません。
相談だけの依頼なら相談で終えます。

実行時の確認は、次の分担で進めます。

| 担当 | 確認・判断すること |
|---|---|
| Reviewer | Mainが割り当てたWorker／Designのタスクが正しく完了したか。実装・検証結果・関連する退行を独立して確認 |
| Astra（Director） | 統合した成果物がユーザーの目的とPlanを満たすか。タスク分割による抜けや全体の方向のずれをPlanごとに一度確認 |
| Main | タスクの割当・統合・結合確認の手配、両者の指摘の採否、完了判断 |

Reviewerの基準はMainが渡した目的・範囲・完了条件です。Workerの完了報告だけで
判断せず、意味のあるタスクのまとまりで実装を確認します。タスク間の結合確認も
MainがWorkerに割り当て、その結果をReviewerが検証します。

初回は対象範囲を一通り確認して指摘をまとめ、再確認は採用した修正とその影響を中心に
進めます。判断済みの論点は新しい根拠がなければ蒸し返さず、要件と必要な検証が
満たされたらMainがレビューを終了します。新しく判明した実害のある不具合は引き続き扱います。

修正は同じWorker／Design、再レビューは同じReviewerへ戻し、回数制限で打ち切りません。
Astraは全体の整合を確認し、タスクの実装レビューを繰り返しません。最終確認の指摘を
採用した修正も担当者とReviewerで確認し、Astraへ再確認を求める受入ループは作りません。

モデル・effort・tierは[共通の役割表](plugins/frontierplan/core/roles.md)に集約しています。
SWE-2版はResearcher／Workerの起動だけを差し替えます。
[共通の進め方](plugins/frontierplan/core/workflow.md)が3入口の共通仕様です。

## ペイン配置はそのまま

```text
+--------------------+------------------------------+
|                    | Astra                        |
|                    | 右側の上40%                  |
| Main               +--------------+---------------+
| 左40%              | Researcher / Worker /        |
|                    | Design / Reviewer            |
|                    | 右側の下60%                  |
+--------------------+------------------------------+
                     <---------- 右60% -------------->
```

Mainを右へ `--ratio 0.4` で分け、必要になったらAstraの下へ `--ratio 0.4` で実行領域を作ります。
追加担当は実行領域で最も幅の広いペインを右へ `--ratio 0.5` で分割します。
`--no-focus` を使い、ユーザーの手動リサイズや他のペインを保ちます。
配置の検査で作業を止める仕組みはありません。
具体的なCLI例は[Herdr手順](plugins/frontierplan/backends/herdr.md)にあります。

## 導入

実行時のPythonは不要です。Herdr版には、Herdr内で動くMain、子のCodex CLIと
指定モデルへのアクセスが必要です。SWE-2版はDevin CLIと利用枠も必要です。
native版にはモデル／effort指定、同じ相手への追加指示、待機ができるホストが必要です。

CodexのMarketplace登録:

```bash
codex plugin marketplace add phni3j9a/frontierplan
codex plugin add frontierplan@frontierplan-local
```

CLIの対応状況は `codex plugin --help` で確認し、Plugin一覧からの導入も利用できます。
ローカルcheckoutを使う場合は、Marketplace登録先をリポジトリの絶対パスにします。

Claude Code（Herdr版のMain）:

```text
/plugin marketplace add phni3j9a/frontierplan
/plugin install frontierplan@frontierplan
```

新しいセッションで `/frontierplan:astraplan-herdr` または `-swe2` を明示指定します。
DevinでもPluginを導入した上で同じスラッシュ入口を利用します。
`allow_implicit_invocation: false`、`disable-model-invocation: true`、
`triggers: [user]` で各ホストの明示起動を維持しています。

各入口は、ホストが読み込んだPlugin内の相対参照から共通文書を読みます。
Herdrの操作方法は `herdr --skill` で導入済みバイナリと一致する説明を読み、
FrontierPlan側には操作マニュアルを重複収録しません。設定の自動変更はありません。

## 権限と継続の扱い

Codex子の起動例は `workspace-write` と `never` を要求します。
実効権限はホスト・バージョンに依存し、native子は親から継承する場合があります。
モデルや権限を指示文だけで保証したとは扱いません。

SWE-2版は従来どおりDevinの `dangerous` を使います。OS sandboxなしで全ツールを
自動承認するため、Codexの起動要求より広い権限です。Researcherへの「読むだけ」という
指示も強制ではありません。[SWE-2の差分](plugins/frontierplan/backends/swe2.md)を参照してください。

待機後はMainが応答を読んで次の操作を判断します。Herdrの `idle`／`done` は
仕事の成功や報告の回収を保証しません。長い作業ではPlan・参加者ID・未完了事項・
次の操作を短い引継ぎメモに残します。バックグラウンド待機だけでは、停止したMainの
自動再開は保証されません。専用の台帳や常駐監視は持ちません。

## v0.3／v0.4からの移行

既存の進行中runは、そのrunを始めたPluginで終えてから更新してください。
v0.5.0は旧台帳を読み込まず、新しい作業から文書中心の手順を使います。
`scripts/`、`profiles/`、`FRONTIERPLAN_MAIN_*` による独自操作は廃止しました。
更新時はPluginをホストの通常手順で置き換え、新しいセッションで入口を読み直します。
導入済みコピーをこのリポジトリの変更だけで自動更新することはありません。

0.4.0は過去の別設計で使われたため再利用せず、文書中心の構成を0.5.0で導入しました。
0.5.1ではReviewerのタスク確認とAstraの全体確認の責任範囲を明確にしています。
0.5.2では、軽量構成のまま初回レビュー・再確認・完了判断の方針を補っています。
Worker–Reviewer間の直接進行を追加する改訂ではありません。

## 開発・配布・検証

開発用ツールにはPython 3.11+とGitが必要です。

```bash
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 tools/package_release.py
```

ZIP生成はGit管理対象の現在の内容だけを使います。新規ファイルを収録するときは先に
stageしてください。Git管理外のローカル設定やキャッシュは入りません。
Plugin／source ZIPを `dist/` に生成し、どちらも展開して検証します。
単体Pluginは3入口・共通文書・backend案内・manifest・MIT noticesで構成されます。

自動テストは配布形式・明示起動・参照先・ZIP収録を検証します。
実モデルの性能や実機での一連の協調動作を保証するものではありません。
v0.5.1の実装・レビューはユーザー指定によりMain単独で実施しました。
v0.5.2の収束方針は文書の整合性と配布チェックを検証対象とし、実モデルでの
往復数・所要時間・見落としの比較は未実施です。
[検証範囲と実機確認手順](docs/validation.md)で証拠の範囲を区別しています。

[設計](docs/architecture.md) /
[ライセンス・参考元](plugins/frontierplan/THIRD_PARTY_NOTICES.md)
