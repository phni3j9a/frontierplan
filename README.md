# FrontierPlan

**Astra researches, designs, plans and accepts. Main coordinates execution.**

Codex向けの明示起動専用Pluginです。herdr版ではMainにDevinなどの既存エージェントも
使用でき、子エージェントは引き続きCodexで起動します。実装に入るまでは、要求理解・コードや外部情報の
調査・必要な隔離検証・ユーザーへの回答・設計・Plan作成を同じAstraが単独で担当します。
Mainはその間、会話と環境情報の受け渡し・セッション管理だけを行います。
実装開始後はMainがタスク分割・担当割当・統合・通常のレビュー判定を進め、最後に
Astraが成果物を確認して最終受理とユーザーへの報告を行います。

## 2つの入口、1つの共通ルール

| SKILL | 実行方式 |
|---|---|
| `astraplan-herdr` | herdr上の見える別ペイン |
| `astraplan-subagent` | Codexのnative subagentツール |

```
$frontierplan:astraplan-herdr
この機能を調査・設計して実装まで進めてください。
```

```
$frontierplan:astraplan-subagent
この機能の設計を相談したいです。まだ実装しないでください。
```

各SKILLは `allow_implicit_invocation: false`。呼び出した作業とその続きだけに適用し、
通常の小さなタスクでは自動起動しません。明示起動後はAstraを省略しません。
Axiomとは別Pluginで、既存リポジトリ・設定を変更せず併存できます。同じ作業で混用しません。

## 役割とモデル

| 役割 | モデル | effort | 責務 |
|---|---|---|---|
| Director | `gpt-6-astra` | `xhigh` | 調査・対話・設計・Plan・方針変更・最終受理・最終報告 |
| Main | 起動済みセッションを継承 | 起動元を継承 | 受け渡し・分割・割当・統合・通常のレビュー判定 |
| Worker | `gpt-6-luna` | `max` | 実装・テスト・修正・監視。fastは別設定 |
| Design | `gpt-6-sol` | `max` | 任意の実装フェーズUI担当。重要な事前設計はAstra |
| Reviewer | `gpt-6-sol` | `xhigh` | 独立レビュー。同じセッションで再レビュー |

`profiles/director/astra.toml` と `main.toml / worker.toml / design.toml / reviewer.toml`
で役割別に管理します。両SKILLは同じprofiles/coreを共有します。
profilesはFrontierPlan内部の設定で、Codexのカスタムエージェント登録ではありません。
GPT-6 Sol / Lunaへの更新は両backendで新しく作る子タスクに適用されます。
既存タスクの継続では、作成時に保存したprofileと同じセッションを使います。
モデルIDと対応effortは [GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol) /
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) の公式資料で確認しています。
Mainのprofileは `inherit_session = true` のみで、モデル・effort・tierを指定しません。
Mainのモデルは実行中に変更しません。将来のFableはDirector profile/接続処理を追加する
拡張点だけを確保し、未対応SKILLや架空の接続方法は登録していません。

## インストール

必要条件: **Python 3.11+**、Git（実装成果物の検証）、対応するCodexとモデルへのアクセス。
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

- 実装前にWorker/Design/Reviewerは起動しません。調査はAstra自身が行います。
- Planと実装許可は別です。相談のみならDirectorの返答で完結します。
- Mainは合意済み基準に沿うレビュー判定だけを行い、要求変更や重大なリスクはAstraへ戻します。
- 実装差分・検証結果・却下/保留を含むレビュー証拠をAstraへ返します。古い候補の受理を流用しません。
- Worker/Designは、限定した実装・修正・検証の割当てごとに原則フレッシュで起動します。直前の小修正だけ再利用する場合は理由を記録します。同じIssueのworktreeは継続利用できます。
- Mainが完了報告を回収し、統合・書込み/所有プロセスの終了・そのセッションの役割終了を確認して記録したら、レビュー前でもWorker/Designを解放します。報告は残し、修正は新Workerへ現在のPlan・finding・完了条件・検証・前報告を引き継ぎます。
- 独立Reviewerは同じセッションで再レビューし、Astraの最終受理まで維持します。herdr版では受理後に安全を確認して`finish`前に解放し、native版では最終整理で閉じます。保持が必要な場合は具体的な理由を記録します。
- レビューは通常、初回と修正確認を目安にします。同じ指摘が2回の修正確認後も残る、または受入条件が増え続ける場合は、次の修正を自動で回さずDirectorが設計・範囲・十分な検証を整理します。回数による自動合格にはしません。
- Mainの実行継続中は最大5分を目安に未回収結果をまとめて照合し、対応するnative通知では早めに処理します。herdrの`check`は通知履歴に依存せず状態を確認し、`wait`は既定・最大300秒で未回収報告または現在の状態を返します。native版の`status`には`uncollected`一覧があります。
- 待機の外側もホストが対応する方法・上限で同じ実行handleを待ち続けます。バックグラウンドwaitだけ残してMainのターンを終えても自動再開は保証されません。実ホストで未検証の通知・復帰を「監視継続中」と断定しません。
- Astraは途中の返答や待機では閉じず、全体の`finish`まで維持します。Mainは閉じません。

herdr版の配置はMainが左40%、Astraが右60%。実装開始時に右側をAstra上40%・
実行領域下60%へ分け、以降のWorker/Design/Reviewerは実行領域内で左右に分割します。
手動リサイズを維持し、役割の領域や端末の識別が崩れた場合は操作を停止します。
実行中の解放には `release-check` / `release`、全体終了後の後片付けには `close` を使います。
詳しくは[herdr手順](plugins/frontierplan/backends/herdr.md#release-completed-execution-participants)。

herdr操作とnative tool呼び出しは別のbackendです。native版のPython helperは
モデルを起動するランタイムではなく、Mainが実際のnativeツールを呼び出すための
packet/receipt管理です。動かないPython-to-spawn_agentブリッジは用意していません。

## 検証と制限

```
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 tools/package_release.py
```

GitHub Actionsにも同じ検証を登録しています。詳細は [検証手順](docs/validation.md)。
自動テストはローカルの状態遷移・Git差分・模擬herdrを検証するもので、実モデルの
ルーティング・課金・実機UI・権限・nativeツール互換性の実証ではありません。
`tests/test_main_identity.py` は模擬Devin Main、識別失敗時の停止、Codex互換性、
CLIの別プロセス実行と共通ledgerの一連の操作を検証します。Devin＋herdrの実機検証とは区別します。

子の方針はworkspace-write + never。herdrは起動時に要求しますが、実効値は環境で
確認が必要です。native子は親の権限を継承し得るため、指示文だけで権限を制限したとは
扱いません。必要条件を満たせない場合は停止・報告し、勝手に権限拡大/モデル変更しません。

helperは協調的な手順/鮮度チェックで、認証・sandbox・ユーザー同意の自動判定ではありません。
候補のfingerprintはHEAD/index/追跡対象/非ignoredの未追跡ファイルを含み、ignored成果物や
外部状態は別途証拠が必要です。v1ではsubmoduleの候補検証を明示的に拒否します。
runは一時ディレクトリに保存します。永続成果物は必要に応じて通常のプロジェクトへ残してください。

[設計](docs/architecture.md) / [共通ルール](plugins/frontierplan/core/workflow.md) /
[herdr手順](plugins/frontierplan/backends/herdr.md) /
[subagent手順](plugins/frontierplan/backends/subagent.md) /
[ライセンス・参考元](plugins/frontierplan/THIRD_PARTY_NOTICES.md)
